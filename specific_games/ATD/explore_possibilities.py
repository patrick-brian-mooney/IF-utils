#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A quick hack to explore the possibility space in All Things Devours, a piece
of interactive fiction published by Toby Ord (under the name "half sick of
shadows") in 2004. ATD is a tight little puzzle game involving time-travel;
part of its appeal is how tightly interlocked the elements of the various
puzzles are with each other and how solutions to one puzzle put constraints on
other puzzles. At the same time, having played through to a solution, it's easy
to wonder how many other ways the puzzles could be solved. This script is an
attempt to explore that question.

It "plays" ATD repeatedly, making all possible sequences of moves, looking for
those that result in successful outcomes and reporting them. It's also
interested in overcoming a technical limitation of the original, the maximum-
simultaneous-time-travel hard limit of 2; this script plays a hacked version of
ATD that has room for up to 16 different simultaneous interactions. (SURELY
there couldn't be room for THAT MANY simultaneous copies moving around the map
at the same time.)

This script is copyright 2019 by Patrick Mooney. It is released under the GPL,
either version 3 or (at your option) any later version. See the file LICENSE
for a copy of this license.
"""


import argparse
import collections
import datetime
import json
import os

from pathlib import Path

import pprint
import queue
import shlex, signal, subprocess, sys
import threading, time
import uuid


verbosity = 0       # How chatty are we being about our progress?
# Definitions of debugging levels:
# 0         Only print "regular things": solutions found, periodic processing updates, fatal errors
# 1         Also display warnings.
# 2         Also display chattery messages about large-scale progress.
# 3         Also display each node explored: location, action taken
# 4         Also chatter extensively about individual steps taken while exploring each node

# Program-running parameters. Probably not useful when not on my system. Override with -i  and -s, respectively.
interpreter_location = Path('/home/patrick/bin/dfrotz/dfrotz').resolve()
interpreter_flags = ["-m"]
story_file_location = Path('/home/patrick/games/IF/by author/Ord, Toby/as half sick of shadows/[2004] All Things Devours/devours.z5').resolve()

base_directory = Path(os.path.dirname(__file__)).resolve()
working_directory = base_directory / 'working'
save_file_directory = working_directory / 'saves'
successful_paths_directory = working_directory / 'successful_paths'
commands_file = base_directory / 'commands.txt'


# Global variable to hold a connection to the external process. It'll be rebound soon enough.
terp_proc = None                    # Just declaring it here so it's obviously in the global namespace.

# Global statistics
dead_ends = 0
successes = 0
script_run_start = datetime.datetime.now()


# Some data used when parsing the game's output.
failure_messages = [l.strip().lower() for l in ['*** You have failed ***',]]
success_messages = [l.strip().lower() for l in ['*** Success. Final, lasting success. ***',]]

mistake_messages = [l.strip().lower() for l in [
    "you do not have the key", "You can't, since", "There is no obvious way to", "The only exits are",
    "That's not a verb I recognise", "You see nothing ", "The slot emits a small beep and your card is rejected",
    "You don't need to worry about", "is locked in place.", "I only understood you as far as",
    "That's not something you can", "You can't see any such thing",  "The prototype's control panel only accepts",
    "Your timer only accepts", "Real adventurers do not use such language", "You can’t since", 'is already here.',
    "But you aren't", "The only exit is", "It is not clear",
]]

disambiguation_messages = [l.strip().lower() for l in [
    "Which do you mean",
]]


rooms = {'balcony': dict(),
         'conference room': dict(),
         'second floor corridor': dict(),
         'upstairs landing': dict(),
         'first floor equipment room': dict(),
         'first floor corridor': dict(),
         'foyer': dict(),
         'inside the prototype': dict(),
         'the deutsch laboratory': dict(),
         'basement equipment room': dict(),
         'basement corridor': dict(),
         'basement landing': dict(),
         }


with open(commands_file) as com_file:           # There are enough to make it worthwhile to store externally.
    all_commands = [l.strip().lower() for l in com_file if l.strip().lower()]


# Now. Utility routines first.
def debug_print(what, min_level=1) -> None:
    """Print WHAT, if the global VERBOSITY is at least MIN_LEVEL."""
    if verbosity >= min_level:
        print(what)


# ANd a utility class used to wrap an output stream for the TerpConnection, below.
class NonBlockingStreamReader(object):
    """Wrapper for subprocess.Popen's stdout and stderr streams, so that we can read
    from them without having to worry about blocking.

    Based extensively on Eyal Arubas's solution to the problem at
    http://eyalarubas.com/python-subproc-nonblock.html.
    """
    def __init__(self, stream) -> None:
        """stream: the stream to read from.
                Usually a process' stdout or stderr.
        """
        self._s = stream
        self._q = queue.Queue()
        self._quit = False              # Set to True to make the thread quit gracefully. Only do this when killing the process whose stream it's wrapping.

        def _populateQueue(stream, queue) -> None:
            """Collect lines from STREAM and put them in QUEUE."""
            while True:
                if self._quit:
                    self._q = None          # signal that we no longer have the queue open
                    return                  # returning from the function ends the thread.
                line = stream.readline()
                if line:
                    queue.put(line)
                else:
                    return                  # If the stream is closed, we're done. End the thread gracefully.

        self._t = threading.Thread(target=_populateQueue, args=(self._s, self._q))
        self._t.daemon = True
        self._t.start()             # start collecting lines from the stream

    def readline(self, timeout=None) -> bytes:
        """Returns the next line in the buffer, if there are any; otherwise, returns None.
        Waits up to TIMEOUT seconds for more data before returning None. If TIMEOUT is
        None, blocks until there IS more data in the buffer.
        """
        try:
            return self._q.get(block=timeout is not None, timeout=timeout)
        except queue.Empty:
            return None

    def readlines(self, *pargs, **kwargs) -> list:
        """Returns a list of all lines waiting in the buffer. If no lines are waiting in
        the buffer, returns an empty list. Takes *pargs and **kwargs to be compatible
        with .readlines() on a file object, but complains at debug level 1 if they are
        supplied.
        """
        if pargs:
            debug_print("WARNING! positional arguments %s supplied to NonBlockingStreamReader.readlines()! Ignoring..." % pargs, 1)
        if kwargs:
            debug_print("WARNING! keyword arguments %s supplied to NonBlockingStreamReader.readlines()! Ignoring..." % kwargs, 1)
        ret, next = list(), True
        while next:
            next = self.readline(0.1)
            if next:
                ret.append(next)
        return ret

    def read_text(self) -> str:
        """Returns all the text waiting in the buffer. Decodes it using the Python default
        encoding, which is basically always what we want in this scenario. Note that
        this is the only method on this object that performs decoding of text in the
        buffer: everything else deals with bytes-type streams.
        """
        ret = '\n'.join([l.decode() for l in self.readlines()]).strip().lstrip('>')
        return ret


class TerpConnection(object):
    """Maintains a connection to a running instance of a 'terp executing ATD. Also
    maintains a connection to the nonblocking reader that wraps its stdout stream.
    Also provides some convenience functions to control the 'terp in a higher-level
    way.
    """
    def __init__(self):
        """Opens a connection to a 'terp process that is playing ATD. Saves a reference to
        that process. Wraps its STDOUT stream in a nonblocking wrapper. Saves a
        reference to that wrapper. Provides functions for issuing a command to the
        'terp and reading the text that is returned.
        """
        parameters = [str(interpreter_location)] + interpreter_flags + [str(story_file_location)]
        self._proc = subprocess.Popen(parameters, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._nonblocking_reader = NonBlockingStreamReader(self._proc.stdout)
        opening_context = self.evaluate_context(self._get_output())
        opening_context['command'] = '[game start]'
        self._context_history = collections.ChainMap(opening_context)

    def __repr__(self):
        ret =  "< TerpConnection object\n"
        try:
            ret += "            room: " + self._context_history['room'] + '\n'
        except:
            ret += "            room: [unknown]\n"
        try:
            ret += "       inventory: " + str(self._context_history['inventory']) + '\n'
        except:
            ret += "       inventory: [unknown]\n"
        try:
            ret += "    last command: " + self._context_history['command'] + '\n'
        except:
            ret += "    last command: [unknown]\n"
        ret += ">"
        return ret

    def _clean_up(self):
        """Politely close down the connection to the 'terp. Store None in its wrapped
        objects to force a crash if we keep trying to work with it.
        """
        debug_print("Cleaning up the 'terp connection.")
        self._nonblocking_reader._quit = True
        time.sleep(0.5)
        self._proc.stdin.close()
        self._proc.terminate()
        self._proc, self._nonblocking_reader = None, None

    def _get_output(self) -> str:
        """Convenience function to return whatever output text is currently queued in the
        nonblocking wrapper around the 'terp's STDOUT stream.
        """
        debug_print("(read STDOUT from buffer)", 4)
        return self._nonblocking_reader.read_text()

    def _add_context_to_history(self, context: dict) -> None:
        """Adds the context to the front of the context-history chain, taking care only
        to add "sparsely": it drops information that duplicates the most current
        information in the context chain.
        """
        new = {k: v for k, v in context.items() if (k not in self._context_history or self._context_history[k] != v)}
        debug_print('(adding new frame %s to context history' % new, 4)
        self._context_history = self._context_history.new_child(new)

    def _get_last_output(self) -> str:
        """A utility function to repeat the last output that the 'terp produced. Does NOT
        look at or touch any data currently in the buffer waiting to be read.
        """
        debug_print('(last output re-read)', 4)
        return self._context_history['output']

    def _pass_command_in(self, command:str):
        """Passes a command in to the 'terp. This is a low-level atomic-type function that
        does nothing other than pass a command in to the 'terp. It doesn't read the
        output or do anything else about the command. It just passes a command into
        the 'terp.
        """
        debug_print("(passing command %s to 'terp" % command.upper(), 4)
        command = (command.strip() + '\n').encode()
        self._proc.stdin.write(command)
        self._proc.stdin.flush()

    def _process_command_and_return_output(self, command:str) -> str:
        """A convenience wrapper: passes a command into the terp, and returns whatever text
        the 'terp barfs back up. Does minimal processing on the command passed in -- it
        only encodes it from str to bytes using Python's default encoding -- and no
        processing on the output text, except for decoding it from bytes to str using
        Python's default encoding. In particular, it performs no EVALUATION of the
        text's output. leaving that to other code.
        """
        self._pass_command_in(command)
        return self._get_output()

    def _save_terp_state(self) -> Path:
        """Saves the interpreter state. It does this solely by causing the 'terp to
        generate a save file. It automagically figures out an appropriate file name
        in the SAVE_FILE_DIRECTORY, and returns a Path object describing the location
        of the save file. It does not make any effort to save anything that is not
        stored in the 'terp's save files.
        """
        found_name = False
        while not found_name:
            p = save_file_directory / str(uuid.uuid4())
            found_name = not p.exists()                         # Yes, vulnerable to race conditions, Vanishingly so, though.
        debug_print("(saving terp state to %s)" % p, 4)
        _ = self._process_command_and_return_output('save')
        _ = self._process_command_and_return_output(os.path.relpath(p, base_directory))
        return p

    def _restore_terp_to_save_file(self, save_file_path: Path) -> None:
        """Restores the 'terp state to the state represented by the save file at
        SAVE_FILE_PATH.
        """
        _ = self._process_command_and_return_output('restore')
        _ = self._process_command_and_return_output(str(save_file_path))
        pass

    def _restore_terp_state(self) -> None:
        """Restores the 'terp to the previous state."""
        debug_print("(restoring 'terp state to previous save file)", 4)
        assert 'checkpoint' in self._context_history.maps[1], "ERROR: trying to restore to a state for which there is no save file!"
        self._restore_terp_to_save_file(self._context_history.maps[1]['checkpoint'])
        # Calling code will also delete the _context_history frame; we don't do it here.

    def UNDO(self) -> bool:
        """Convenience function: undo the last turn in the 'terp. Returns True if the
        function executes an UNDO successfully, or False if it does not.
        """
        txt = self._process_command_and_return_output('undo')
        output = [l.strip() for l in txt.strip().split('\n')]
        output = [l for l in output if l]
        return ("undone" in output[-1].lower())

    def LOOK(self) -> None:
        """Convenience function: execute the LOOK command in the 'terp, print the results,
        and undo the command.
        """
        print(self._process_command_and_return_output('look'))
        self.UNDO()

    def _get_inventory(self) -> list:
        """Executes an INVENTORY command and undoes it, then interprets the results of
        the command.
        """
        debug_print("(getting PC inventory)", 4)
        inventory_text = self._process_command_and_return_output('inventory')
        self.UNDO()
        return list([l.strip() for l in inventory_text.split('\n') if (l.strip() and not l.strip().strip('>').lower().startswith("you're carrying:"))])

    def INVENTORY(self) -> None:
        """Convenience function: print the current inventory to the console, then undo the
        in-game action.
        """
        print(self._get_inventory())

    def evaluate_context(self, output: str) -> dict:
        """Looks at the output retrieved after running a command and infers as much as it
        can from the output text and returns a dictionary object that has fields with
        defined names that represents the data in a structured manner.

        Defined field names:
          'room'        If the function detects that the 'terp is signaling that the
                        player is in a new room, this is the name of that room.
          'inventory'   A list: the player's inventory.
          'time'        The ("objective," external) clock time at this point in the
                        story.
          'turns'       In narrative through-play sequence, which turn number is this?
          'checkpoint'  A full path to a save-state file that was saved as the context
                        was being evaluated, i.e. right after the command was executed.
          'command'     The command that was executed to bring the 'terp into the state
                        represented by this context grame.
          'output'      The game's output that we're processing: the response to the
                        "entered" command.
          'failed'      If the function detects that the mission failed, this is True.
          'success'     If we detect that our mission has succeeded (we have 'won'),
                        this is True.
          'mistake'     If we detect that the 'terp thinks the command is a mistake (e.g.,
                        if the command we're trying opens a door that isn't there), this
                        is set to True.
        """
        debug_print("(evaluating command results)", 4)
        output_lines = output.split('\n')
        ret = {'failed': False, 'success': False, 'mistake': False, 'output': output, 'time': None}
        try:
            ret['turns'] = 1 + len(self._context_history.maps)
        except AttributeError:      # The very first time we run, _context_history doesn't exist yet!
            ret['turns'] = 1
        # Next, check to see what time it is, if we can tell.
        for t in [l[l.rfind("4:"):].strip() for l in output_lines if '4:' in l]:
            ret['time'] = t
        # Next, check for complete failure. Then, check for game-winning success.
        aster_lines = [l.strip() for l in output_lines if l.strip().startswith('***')]
        for l in aster_lines:
            if l.strip().lower() in failure_messages:
                ret['failed'] = True
                return ret
            elif l.strip().lower() in success_messages:
                ret['success'] = True
                return ret
            elif l.strip() == "*******":
                pass        # This is just a textual separator that turns up occasionally. Ignore it.
            else:
                print('Game-ending asterisk line encountered that I cannot understand!')
                print("Line is:   " + l)
                time.sleep(1)
        # Next, check for mistakes.
        # First, check for disambiguation questions
        # Now, see if anything in the appropriate list BEGINS OR ENDS any output line.
        for l in [line.strip().lower() for line in output_lines]:
            for m in disambiguation_messages:
                if l.startswith(m) or l.endswith(m):
                    ret['mistake'] = True
                    return ret
            for m in mistake_messages:
                if l.startswith(m) or l.endswith(m):
                    ret['mistake'] = True
                    return ret
        # Next, check to see if we're in a new room. Room names appear on their own line. Luckily, it seems that ATD never winds up adding notes like "(inside the prototype)" to the end of location names.
        for l in [l.strip().lower() for l in output_lines]:
            if l in rooms:
                ret['room'] = l
        ret['checkpoint'] = self._save_terp_state()
        ret['inventory'] = self._get_inventory()
        return ret

    def unroll(self) -> None:
        """Undoes the last move on the stack. This involves both restoring the state of the
        interpreter and restoring the context history chain in the TerpConnection. Tries
        first to use the UNDO command within the 'terp, but restores from disk if this
        fails.
        """
        if not self.UNDO():
            self._restore_terp_state()
        try:
            self._context_history.maps[0]['checkpoint'].unlink()        # Erase the checkpoint file.
        except KeyError:        # There is no checkpoint for that interpreter frame?
            pass                 # No need to delete a save file, then.
        self._context_history = self._context_history.parents       # Drop one frame from the context chain.


def execute_command(command:str) -> dict:
    """Convenience function: execute the command COMMAND and return the new interpreter
    context as a dictionary with defined values. Note that this changes the 'terp's
    game state by executing COMMAND, of course: no save/restore bracketing is
    performed at this level.
    """
    text = terp_proc._process_command_and_return_output(command)
    return terp_proc.evaluate_context(text)


def record_solution() -> None:
    """Record the details of a solution in a JSON file. Name it automatically using the
    current date and time and the current run time of the script.
    """
    # The ChainMap stores the steps in most-to-least-recent order, but we want to serialize them in the opposite order.
    solution_steps = list(reversed(terp_proc._context_history.maps))
    found = False
    while not found:
        # FIXME: add current run time to filename.
        p = successful_paths_directory / datetime.datetime.now().isoformat() + '.json'
        found = not p.exists()
    p.write_text(json.dumps(solution_steps, default=str, indent=2, sort_keys=True))

def make_move() -> None:
    """Try a move. See if it wins. If it does, record the sequence of winning moves.

    If not, see if it loses. If not, see if it was useless. If either is true, just
    end this invocation and return to the calling function: there's no point in
    continuing if either is the case.

    If we didn't win, lose, or get told we made a mistake, the function calls itself
    again to make another move. Along the way, it does the record-keeping that needs
    to happen for us to be able to report the steps that lead to the success state.

    This function generates checkpoints for each move automatically, as a side effect
    that occurs while the game's output is being interpreted.
    """
    global successes, dead_ends

    for c in all_commands:
        try:                # execute_command() produces a checkpoint that will be used by unroll(), below.
            room_name = terp_proc._context_history['room'] if ('room' in terp_proc._context_history) else ['unknown']
            debug_print('move: (%s, %s)' % (room_name, c.upper()), 3)
            new_context = execute_command(c)
            terp_proc._add_context_to_history(new_context)
            terp_proc._context_history.maps[0]['command'] = c           # Add this now so it doesn't get optimized sparsely away.
            # Process the new context.
            if new_context['success']:
                print('Command %s won! Recording ...' % c)
                record_solution()
                successes += 1
            elif new_context['mistake']:
                debug_print('command %s was detected to be a mistake!' % c, 4)
                dead_ends += 1
            elif new_context['failed']:
                debug_print('command %s lost the game!' % c, 4)
                dead_ends += 1
            else:               # If we didn't win, lose, or get told we made a mistake, make another move.
                make_move()
        finally:
            if ((dead_ends + successes) % 1000 == 0) or ((verbosity >= 2) and ((dead_ends + successes) % 20 == 0)):
                print("Explored %d complete paths so far" % (dead_ends + successes))
            terp_proc.unroll()


def play_game() -> None:
    make_move()


def processUSR1(*args, **kwargs) -> None:
    """Handle the USR1 signal by increasing the debugging verbosity."""
    global verbosity
    verbosity += 1
    print("\nVerbosity increased to %d" % verbosity)


def processUSR2(*args, **kwargs) -> None:
    """Handle the USR2 signal by decreasing the debugging verbosity."""
    global verbosity
    verbosity -= 1
    print("\nVerbosity decreased to %d" % verbosity)


# No docstring here intentionally: let the __doc__ resolution when creating an ArgumentParser refer to the module-level docstring.
def set_up() -> None:
    global verbosity, interpreter_location, story_file_location
    global terp_proc
    debug_print("setting up program run!", 2)

    signal.signal(signal.SIGUSR1, processUSR1)
    signal.signal(signal.SIGUSR2, processUSR2)
    debug_print("  signal handlers installed!", 2)

    if len(sys.argv) >= 2:
        debug_print("  processing command-line arguments!", 2)
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--verbose', '-v', action='count', help="increase how chatty the script is about what it's doing")
        parser.add_argument('--quiet', '-q', action='count', help="decrease how chatty the script is about what it's doing")
        parser.add_argument('--interpreter', '--terp', '-i', '-t', help="specify the full path to the interpreter used to run All Things Devours")
        parser.add_argument('--story', '-s', help="specify the full pathname to the game file played by the interpreter")
        args = vars(parser.parse_args())

        verbosity += args['verbose'] or 0
        verbosity -= args['quiet'] or 0
        interpreter_location = args['interpreter'] or interpreter_location
        story_file_location = args['story'] or story_file_location

        debug_print('  command-line arguments are:' + pprint.pformat(args), 2)
        debug_print('  final verbosity is: %d' % verbosity, 2)
    else:
        debug_print("  no command-line arguments!", 2)

    # Set up the necessary directories. Not particularly robust against malicious interference and race conditions,
    # but this script is just for me, anyway. Assumes a cooperative, reasonably competent user.
    debug_print("  about to check directory structure ...", 2)
    if working_directory.exists():
        assert working_directory.is_dir(), "ERROR: %s exists, but is not a directory!" % working_directory
    else:
        working_directory.mkdir()
        debug_print("    successfully created working directory %s" % shlex.quote(working_directory))
    if save_file_directory.exists():
        assert save_file_directory.is_dir(), "ERROR: %s exists, but is not a directory!" % save_file_directory
    else:
        save_file_directory.mkdir()
        debug_print("    successfully created save file directory %s" % shlex.quote(save_file_directory))
    if successful_paths_directory.exists():
        assert successful_paths_directory.is_dir(), "ERROR: %s exists, but is not a directory!" % successful_paths_directory
    else:
        successful_paths_directory.mkdir()
        debug_print("    successfully created successful paths directory %s" % successful_paths_directory)
    debug_print("  directory structure validated!")

    terp_proc = TerpConnection()
    debug_print("\n\n  successfully initiated connection to new 'terp! It said:\n\n" + terp_proc._get_last_output() + "\n\n", 2)



if __name__ == "__main__":
    set_up()
    play_game()
