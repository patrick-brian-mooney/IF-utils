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
module_docstring = __doc__


import argparse
import bz2
import collections
import datetime
import json
import os

from pathlib import Path

import pprint
import queue
import shlex, signal, string, subprocess, sys
import tarfile, threading, time, traceback
import uuid


# Definitions of debugging verbosity levels:
# 0         Only print "regular things": solutions found, periodic processing updates, fatal errors
# 1         Also display warnings.
# 2         Also display chatty messages about large-scale progress.
# 3         Also display each node explored: (location, action taken) -> result
# 4         Also chatter extensively about individual steps taken while exploring each node
verbosity = 2       # How chatty are we being about our progress?
transcript = True   # If True, issue a SCRIPT command at the beginning of the game to keep a transcript of the whole thing.

# Program-running parameters. Probably not useful when not on my system. Override with -i  and -s, respectively.
interpreter_location = Path('/home/patrick/bin/dfrotz/dfrotz').resolve()
interpreter_flags = ["-m"]
story_file_location = Path('/home/patrick/games/IF/by author/Ord, Toby/as half sick of shadows/[2004] All Things Devours/devours.z5').resolve()

base_directory = Path(os.path.dirname(__file__)).resolve()
working_directory = base_directory / 'working'
progress_checkpoint_file = working_directory / 'progress.json.bz2'

save_file_directory = working_directory / 'saves'
successful_paths_directory = working_directory / 'successful_paths'
logs_directory = working_directory / 'logs'

commands_file = base_directory / 'commands'
mistakes_file = base_directory / 'mistakes.json'
disambiguation_file = base_directory / 'disambiguation.json'
rooms_file = base_directory / 'rooms.json'

# Global statistics
dead_ends = 0
successes = 0
moves = 0
script_run_start = datetime.datetime.now()

progress_data = dict()


# Some data used when parsing the game's output.
failure_messages = [l.strip().lower() for l in ['*** You have failed ***',]]
success_messages = [l.strip().lower() for l in ['*** Success. Final, lasting success. ***',]]

# Some game data is stored in external files for various reasons.
mistake_messages = json.loads(mistakes_file.read_text())
disambiguation_messages = json.loads(disambiguation_file.read_text())
rooms = json.loads(rooms_file.read_text())

all_commands = dict()           # We'll fill this in in a bit.


# Now. Some utility routines first.
def debug_print(what, min_level=1) -> None:
    """Print WHAT, if the global VERBOSITY is at least MIN_LEVEL."""
    if verbosity >= min_level:
        print(" " * min_level + what)       # Indent according to unimportance level.


def get_total_time() -> float:
    """Returns the total number of seconds since the processing run started. Note that
    runs that start by restoring progress data from a previous run also fake the
    SCRIPT_RUN_START time so that this function returns the proper total wall time
    spent running the script to gather the current crop of data.
    """
    return (datetime.datetime.now() - script_run_start).total_seconds()


def is_redundant_strand(which_path: str) -> bool:
    """Checks to see whether WHICH_PATH is redundant relative to the global progress
    store. A path is considered to be redundant if it's not necessary to store it
    because a "further upstream" path has already been checkpointed as complete in a
    way that makes it uncessary to store data showing the WHICH_PATH is complete,
    because that upstream checkpoint-as-complete guarantees that WHICH_PATH will
    never be hit again in the first place. Returns True if WHICH_PATH is redundant
    in this sense.
    """
    for key in progress_data:
        if (which_path.startswith(key.rstrip('.'))) and (which_path != key):
            return True
    return False


def clean_progress_data() -> None:
    """Eliminate any checkpoints made redundant by the fact that a more-general
    progress checkpoint has been created.

    Note that we always keep all strands of length 4 or less.
    """
    global progress_data
    pruned_dict = {k: v for k, v in progress_data.items() if (k.count('.') <= 4) or (not is_redundant_strand(k))}
    if pruned_dict != progress_data:
        debug_print("(pruned redundant data from the data store)", 3)
        progress_data = pruned_dict


def document_problem(problem_type: str, data: dict) -> None:
    """Document the fact that a problem situation arose. During early exploratory runs,
    the intent is to gather as much data as possible about what future runs will be
    like rather than to actually solve the problem at hand (i.e., to fully explore the
    problem space). For this reason, detected problem conditions produce a report on
    the problem and keep running to keep gathering more information about the shape
    of the problem space.

    During later runs, the reports continue to be produced, because production of a
    report allows for judgments about whether the integrity of the run was
    compromised by the documented problems.

    PROBLEM_TYPE is a string indicating what type of problem arose; it should be
    chosen from a small list of short standard strings. DATA is the data to be
    stored about the problem.

    A filename for the log file is automatically determined and the file is written
    to the logs/ directory.
    """
    found = False
    data['traceback'] = traceback.extract_stack()
    while not found:
        p = base_directory / (problem_type + '_' + datetime.datetime.now().isoformat().replace(':', '_') + '.json')
        found = not p.exists()
    p.write_text(json.dumps(data, indent=2, default=str, sort_keys=True))


# These next are routines that determine whether a command is available as a guess at a particular point in time.
# Each function is passed one parameter, the current command being attempted (the function must look at the
# global 'terp state for anything else) and returns a boolean value: True if the command is available right now, or
# False otherwise. Many commands have no real need to be limited and so are mapped to always_true().

# Functions that have no need to look at the current command to know if their function is available can just consume
# it with *pargs syntax.
def always_true(*pargs) -> bool:
    """Utility function for commands that are always available. When we query whether
    they're available, just returns True.
    """
    return True


def only_one_timer_command(*pargs) -> bool:
    """Utility function for SET TIMER TO [number] commands. It returns True iff
    no SET TIMER TO [number] command has yet been entered; otherwise, it returns
    False.

    The rationale for this is that SET TIMER TO [number] is essentially a WAIT
    command every time in the game but once. (I suppose it is possible in theory
    that one could set the timer, drop it, run past it again and set it to a higher
    number, and this might even get around the 100-second time limit, but I can't
    manage to see how this could be helpful, given that the prototype is nowhere
    near the Conference Room-to-Outside path that the PC has to take under tight
    time constraints while the timer is ticking. This is maybe a bit iffy, but seems
    logically sound, all in all.) In any case, doing this makes the game's problem
    space much more navigable, so it's going to have to be necessary if a brute-
    force solution to the problem is going to be attempted in the first place.
    """
    return (not "set timer to" in terp_proc._walkthrough.lower())


def only_in_prototype(*pargs) -> bool:
    """This function is a filter for for actions that are only productive when the
    Protagonist is inside the time machine prototype. There are a huge number of
    such actions, most of which are SET PANEL TO [number]: these are only possible
    inside the Prototype because the panel is not portable.
    """
    return 'prototype' in terp_proc.context_history['room']


def not_twice_in_a_row(c: str) -> bool:
    """This function prevents the same command from being issued twice consecutively.
    This is useful for many commands, because it eliminates--well, REDUCES-- the
    "when a command succeeds once, it will generally succeed twice; but the second
    time is essentially a synonym for WAIT" problem.

    Note that "same command" in the paragraph above means "the EXACT SAME command',
    character for character, not "a similar command."
    """
    return (c.strip().strip(string.punctuation).strip().lower() == terp_proc.context_history['command'].strip().strip(string.punctuation).strip().lower())


def set_panel_once_before_pushing_button(c: str) -> bool:
    """This filter is for SET PANEL TO [number], a set of commands that have some
    comparatively complex requirements: 1. Only in the prototype. 2. Once a SET
    PANEL command has been executed, no others are allowed until after a successful
    PUSH SILVER BUTTON appears in the transcript (i.e., is not a mistake).

    Otherwise, allowing repeated SET PANEL TO commands is equivalent to WAIT.
    """
    if only_in_prototype(c):
        walkthrough = terp_proc._walkthrough.lower().strip()
        if 'set panel' not in walkthrough:
            return True
        elif 'push silver' in walkthrough:
            return (walkthrough.rindex('push silver') > walkthrough.rindex('set panel'))
    return False


def must_do_something_before_exiting_prototype(*pargs) -> bool:
    """Another rule to prevent an effective synonym for WAIT: a repeated GET IN/GET
    OUT OF PROTOTYPE cycle. This filter should be attached to EXITing verbs; it
    disallows them if the previous (effective) command is something that means GET
    IN PROTOTYPE, provided that the PC is in the Lab or the Prototype.
    """
    if 'prototype' not in terp_proc.context_history['room'].strip().lower():
        return True
    steps = list(reversed([h['command'] for h in terp_proc.context_history.maps if 'command' in h]))
    index = 0
    for i, s in enumerate(steps):               # Find the last occurrence
        if s.strip().lower() in ['enter prototype', 'go in']:
            index = i
    if index == len(steps) - 1:                 # If the last thing we did was get in, prohibit exiting.
        return False
    if index < 1:                               # If there's never been an entering command, allow the exiting command anyway, though it will almost certainly be interpreted as a mistake.
        return True
    steps = steps[1+index:]                     # Drop everything up to the last entering command.
    while steps:                                # Now drop WAITs until we hit something else.
        if steps[0].lower().strip() == 'wait':
            steps.pop(0)
        else:
            break                               # If there's anything left after the WAITs after the entering command,
    return bool([i for i in steps if i])        # ... return True to allow the exit command.

# Now that we've defined the filter functions, fill out the command-selection parameters.
with open(commands_file) as cmd_file:
    for l in cmd_file.readlines():
        l = l.strip().lower()
        if 'set timer' in l:
            all_commands[l] = only_one_timer_command
        elif 'set panel' in l:
            all_commands[l] = set_panel_once_before_pushing_button
        elif l in ['exit', 'go out']:
            all_commands[l] = must_do_something_before_exiting_prototype
        elif l.startswith('turn off') or l.startswith('turn on') or l.startswith('unlock') or l.startswith('close'):
            all_commands[l] = not_twice_in_a_row
        elif l.startswith('push') or l.startswith('turn on') or l.startswith('examine') or l.startswith('get') or l.startswith('open'):
            all_commands[l] = not_twice_in_a_row
        else:
            all_commands[l] = always_true


# And a utility class used to wrap an output stream for the TerpConnection, below.
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

    def readline(self, timeout=None) -> str:
        """Returns the next line in the buffer, if there are any; otherwise, returns None.
        Waits up to TIMEOUT seconds for more data before returning None. If TIMEOUT is
        None, blocks until there IS more data in the buffer. Does not do any decoding.
        """
        try:
            return self._q.get(block=timeout is not None, timeout=timeout)
        except queue.Empty:
            return None

    def readlines(self, *pargs, **kwargs) -> list:
        """Returns a list of all lines waiting in the buffer. If no lines are waiting in
        the buffer, returns an empty list. Takes *pargs and **kwargs to be compatible
        with .readlines() on a file object, but complains at debug level 1 if they are
        supplied, in case I'm ever tempted to pass them in, or I ever thoughtlessly pass
        this object to anything that takes advantage of other features on more standard
        interfaces.
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
        """Returns all the text waiting in the buffer.
        """
        ret = '\n'.join([l.rstrip() for l in self.readlines()]).strip().lstrip('>')
        return ret


class TerpConnection(object):
    """Maintains a connection to a running instance of a 'terp executing ATD. Also
    maintains a connection to the nonblocking reader that wraps its stdout stream.
    Provides functions for issuing a command to the 'terp and reading the text that
    is returned. Also provides some convenience functions to control the 'terp in a
    higher-level way.
    """
    def __init__(self):
        """Opens a connection to a 'terp process that is playing ATD. Saves a reference to
        that process. Wraps its STDOUT stream in a nonblocking wrapper. Saves a reference
        to that wrapper. Initialized the command-history data structure.
        """
        parameters = [str(interpreter_location)] + interpreter_flags + [str(story_file_location)]
        self._proc = subprocess.Popen(parameters, shell=False, universal_newlines=True, bufsize=1,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._reader = NonBlockingStreamReader(self._proc.stdout)
        opening_context = self.evaluate_context(self._get_output(), command='[game start]')
        self.context_history = collections.ChainMap(opening_context)
        if transcript:
            self.SCRIPT()

    def __str__(self):
        ret =  "< TerpConnection object; "
        try:
            ret += " room: " + self.context_history['room'] + ';'
        except Exception:
            ret += " room: [unknown]\n"
        try:
            ret += " inventory: " + str(self.context_history['inventory']) + ';'
        except Exception:
            ret += " inventory: [unknown];"
        try:
            ret += " last command: " + self.context_history['command']
        except Exception:
            ret += " last command: [unknown]"
        ret += " >"
        return ret

    def _clean_up(self):        # FIXME: this is currently unused!
        """Politely close down the connection to the 'terp. Store None in its wrapped
        objects to force a crash if we keep trying to work with it.
        """
        debug_print("Cleaning up the 'terp connection.")
        self._reader._quit = True
        self._proc.stdin.close()
        self._proc.terminate()
        self._proc, self._reader = None, None

    def _get_output(self, retry:bool=True) -> str:
        """Convenience function to return whatever output text is currently queued in the
        nonblocking wrapper around the 'terp's STDOUT stream. If there is no text at
        all, then, if RETRY is True, sleep and retry several times until there is, or
        until we've been patient enough and give up. If there is no text at all and
        RETRY is False, just return an empty string.
        """
        debug_print("(read STDOUT from buffer)", 4)
        ret = self._reader.read_text()
        if (not ret) and retry:              # Sometimes we need to wait on the buffer a few times.
            sleep_time = 0.1
            for i in range(20):  # FIXME: should we just be upping the timeout on the read? -- probably not
                ret = self._reader.read_text()
                if ret:
                    break
                else:
                    time.sleep(sleep_time)
                    sleep_time *= 1.33333        # Wait longer and longer for data from the 'terp.
                    if i > 5:
                        pass                    # Breakpoint!
            if not ret:
                debug_print("ERROR: unable to get any data from the 'terp!", 0)
        return ret

    def _add_context_to_history(self, context: dict) -> None:
        """Adds the context to the front of the context-history chain, taking care only
        to add "sparsely": it drops information that duplicates the most current
        information in the context chain.
        """
        new = {k: v for k, v in context.items() if (k not in self.context_history or self.context_history[k] != v)}
        debug_print('(adding new frame %s to context history' % new, 4)
        self.context_history = self.context_history.new_child(new)

    def _drop_history_frame(self):
        """Drop the most recent "command history" context frame from the command history.
        While doing so, delete the save-state checkpoint associated with the frame, if
        there is one.
        """
        try:
            self.context_history.maps[0]['checkpoint'].unlink()        # Erase the checkpoint file.
        except KeyError:            # There is no save-file made to checkpoint that interpreter frame?
            pass                    # No need to delete a save file, then.
        self.context_history = self.context_history.parents       # Drop one frame from the context chain.

    def get_last_output(self) -> str:
        """A utility function to repeat the last output that the 'terp produced. Does NOT
        look at or touch any data currently in the buffer waiting to be read.
        """
        debug_print('(re-reading last output)', 4)
        return self.context_history['output']

    @property
    def _walkthrough(self) -> str:
        """Convenience function: get a terse walkthrough consisting of the commands
        that produced the 'terp's current game state. This is used to index the
        current solution space for algorithmic-progress-checkpointing purposes.
        """
        ret = '. '.join((reversed([frame['command'] for frame in self.context_history.maps]))).upper()
        return ret + '.'

    @property
    def _all_checkpoints(self) -> list:
        """Convenience function to get a list of all checkpoints currently tracked by the TerpConnection."""
        return [frame['checkpoint'] for frame in self.context_history.maps if 'checkpoint' in frame]

    def create_progress_checkpoint(self) -> None:
        """Update the dictionary that keeps track of which possible branches of the problem
        space we've already tried. Write that updated dictionary to disk.
        """
        global progress_data
        progress_data[self._walkthrough] = {
            'dead ends': dead_ends,
            'successes': successes,
            'total moves': moves,
            'time': get_total_time(), }
        debug_print("(saving algorithmic progress data.)", 2)
        clean_progress_data()
        with bz2.open(progress_checkpoint_file, mode='wt') as pc_file:
            json.dump(progress_data, pc_file, default=str, indent=2, sort_keys=True)

    def _pass_command_in(self, command:str) -> None:
        """Passes a command in to the 'terp. This is a low-level atomic-type function that
        does nothing other than pass a command in to the 'terp. It doesn't read the
        output or do anything else about the command. It just passes a command into
        the 'terp.
        """
        debug_print("(passing command %s to 'terp" % command.upper(), 4)
        command = (command.strip() + '\n')
        self._proc.stdin.write(command)
        self._proc.stdin.flush()

    def process_command_and_return_output(self, command:str, be_patient:bool=True) -> str:
        """A convenience wrapper: passes a command into the terp, and returns whatever text
        the 'terp barfs back up. Does minimal processing on the command passed in -- it
        adds a newline -- and no processing on the output text. (All text is processed
        using the system default encoding because we're in text mode, or "universal
        newlines" mode, if you prefer.) In particular, it performs no EVALUATION of the
        text's output. leaving that to other code.

        If BE_PATIENT is True, pass True to _get_output()'s RETRY parameter, so that it
        will be more patient while waiting for output. If not--and there are some
        annoying situations where the 'terp doesn't cough up any response--then just
        don't bother waiting if we can't get anything on the first attempt.
        """
        self._pass_command_in(command)
        return self._get_output(retry=be_patient)

    def save_terp_state(self) -> Path:
        """Saves the interpreter state. It does this solely by causing the 'terp to
        generate a save file. It automagically figures out an appropriate file name
        in the SAVE_FILE_DIRECTORY, and returns a Path object describing the location
        of the save file. It does not make any effort to save anything that is not
        stored in the 'terp's save files. Things not saved include, but may not be
        limited to, SELF's context_history mappings.
        """
        found_name = False
        while not found_name:
            p = save_file_directory / str(uuid.uuid4())
            found_name = not p.exists()                         # Yes, vulnerable to race conditions, Vanishingly so, though.
        debug_print("(saving 'terp state to %s)" % p, 4)
        _ = self.process_command_and_return_output('save', be_patient=False)   # We can't expect to get a response here: the 'terp doesn't necessarily end it's response with \n, because it's waiting for a response on the same line, so we won't get the prompt text until after we've passed the prompt answer in.
        output = self.process_command_and_return_output(os.path.relpath(p, base_directory))
        if ("save failed" in output.lower()) or (not p.exists()):
            document_problem(problem_type='save_failed', data={'filename': str(p), 'output': [_, output], 'exists': p.exists()})
        return p

    def _restore_terp_to_save_file(self, save_file_path: Path) -> None:
        """Restores the 'terp state to the state represented by the save file at
        SAVE_FILE_PATH. Returns True if the restoring action was successful, or False if
        it failed.
        """
        _ = self.process_command_and_return_output('restore', be_patient=False)
        output = self.process_command_and_return_output(os.path.relpath(save_file_path))
        ret = not ('failed' in output.lower())
        if ret:
            return True
        else:
            return False

    def restore_terp_state(self) -> None:
        """Restores the 'terp to the previous state. Does not handle housekeeping for any
        other aspect of the TerpConnection; notably, does not drop the context_history
        frame from the context history stack.
        """
        debug_print("(restoring 'terp state to previous save file)", 4)
        assert 'checkpoint' in self.context_history.maps[1], "ERROR: trying to restore to a state for which there is no save file!"
        self._restore_terp_to_save_file(self.context_history.maps[1]['checkpoint'])

    def UNDO(self) -> bool:
        """Convenience function: undo the last turn in the 'terp. Returns True if the
        function executes an UNDO successfully, or False if it does not.
        """
        txt = self.process_command_and_return_output('undo')
        if """you can't "undo" what hasn't been done""".lower() in txt.lower():
            return True         # "Nothing was done" is as good as successfully undoing. =)
        if not txt:
            document_problem(problem_type="cannot_undo", data={'output': None})
            return False
        if "undone.]" in txt.lower():
            return True
        else:
            document_problem(problem_type="cannot_undo", data={"output": txt, 'note': '"undone.]" not in output!'})

    def LOOK(self) -> None:
        """Convenience function: execute the LOOK command in the 'terp, print the results,
        and undo the command.
        """
        print(self.process_command_and_return_output('look'))
        if not self.UNDO():
            debug_print('WARNING: unable to undo LOOK command!', 2)

    def SCRIPT(self) -> None:
        """Determines an appropriate transcript name, and issues a SCRIPT command to the
        'terp to cause a transcript to be kept at that location.
        """
        found_name = False
        while not found_name:
            p = working_directory / ('transcript_' + datetime.datetime.now().isoformat().replace(':', '_'))
            found_name = not p.exists()  # Yes, vulnerable to race conditions, Vanishingly so, though.
        debug_print("(saving terp state to %s)" % p, 4)
        _ = self.process_command_and_return_output('script', be_patient=False)
        _ = self.process_command_and_return_output(os.path.relpath(p, base_directory))

    def _get_inventory(self) -> list:
        """Executes an INVENTORY command and undoes it, then interprets the results of
        the command.
        """
        debug_print("(getting PC inventory)", 4)
        inventory_text = self.process_command_and_return_output('inventory')
        if not self.UNDO():
            debug_print("Warning! Unable to undo INVENTORY command.", 2)
        ret = list([l.strip() for l in inventory_text.split('\n') if (l.strip() and not l.strip().strip('>').lower().startswith("you're carrying:"))])
        try:
            ret = ret[1 + list([l.lower().strip() for l in ret]).index('you are carrying:'):]
        except (ValueError, IndexError) as errr:
            document_problem('cannot_get_inventory', data={'inventory_text': inventory_text, 'note': "'you are carrying:' not in output text!"})
        return ret

    def INVENTORY(self) -> None:
        """Convenience wrapper: print the current inventory to the console, then undo the
        in-game action.
        """
        print(self._get_inventory())

    def evaluate_context(self, output: str, command:str) -> dict:
        """Looks at the output retrieved after running a command and infers as much as it
        can from the output text, then returns a dictionary object that has fields with
        defined names that represents the data in a structured manner.

        Defined field names:
          'room'        If the function detects that the 'terp is signaling which room
                        the player is in, this is the name of that room.
          'inventory'   A list: the player's inventory.
          'time'        The ("objective," external) clock time at this point in the
                        story.
          'turns'       In narrative through-play sequence, which turn number is this?
          'checkpoint'  A full path to a save-state file that was saved as the context
                        was being evaluated, i.e. right after the command was executed.
          'command'     The command that was executed to bring the 'terp into the state
                        represented by this context frame.
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
        output_lines = [l.strip() for l in output.split('\n')]
        output_lower = output.lower().strip()
        ret = {'time': None, 'command': command,
               'failed': False, 'success': False, 'mistake': False,
               'output': output}
        try:
            ret['turns'] = 1 + len(self.context_history.maps)
        except AttributeError:      # The very first time we run, context_history doesn't exist yet!
            ret['turns'] = 1
        # Next, check to see what time it is, if we can tell.
        for t in [l[l.rfind("4:"):].strip() for l in output_lines if '4:' in l]:        # Time is always 4:xx:yy AM.
            ret['time'] = t
        # Next, check for complete failure. Then, check for game-winning success.
        for m in failure_messages:
            if m in output_lower:
                ret['failed'] = True
                return ret
        for m in success_messages:
            if m in output_lower:
                ret['success'] = True
                return ret
        for l in [line for line in output_lines if line.startswith('**')]:
            if l == "*******":
                pass        # This is just a textual separator that turns up occasionally. Ignore it.
            else:
                document_problem('asterisk_line', data={'line': l, 'note': "Cannot interpret this game-ending asterisk line!"})
        # Next, check for mistakes.
        # First, check for disambiguation questions
        # Now, see if anything in the appropriate list BEGINS OR ENDS any output line.
        for l in [line.strip().lower() for line in output_lines]:
            for m in disambiguation_messages:
                if l.startswith(m) or l.endswith(m):
                    document_problem(problem_type='disambiguation', data=ret)
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
        if not ret['success'] and not ret['failed'] and not ret['mistake']:        # Don't bother trying these if the game's over or we made no change.
            ret['checkpoint'] = self.save_terp_state()
            ret['inventory'] = self._get_inventory()
        return ret


terp_proc = TerpConnection()
print("\n\n  successfully initiated connection to new 'terp! It said:\n\n" + terp_proc.get_last_output() + "\n\n")


def execute_command(command:str) -> dict:
    """Convenience function: execute the command COMMAND and return the new interpreter
    context as a dictionary with defined values. Note that this changes the 'terp's
    game state by executing COMMAND, of course: no save/restore bracketing is
    performed at this level.
    """
    text = terp_proc.process_command_and_return_output(command)
    return terp_proc.evaluate_context(text, command)


def record_solution() -> None:
    """Record the details of a solution in a JSON file. Name it automatically using the
    current date and time and the current run time of the script.
    """
    # The ChainMap stores the steps in most-to-least-recent order, but we want to serialize them in the opposite order.
    solution_steps = list(reversed(terp_proc.context_history.maps))
    found = False
    while not found:
        # FIXME: add current run time to filename.
        p = successful_paths_directory / (datetime.datetime.now().isoformat().replace(':', '_') + '.json')
        found = not p.exists()
    p.write_text(json.dumps(solution_steps, default=str, indent=2, sort_keys=True))
    with tarfile.open(name=str(p).rstrip('json') + 'tar.bz2', mode='w:bz2') as save_file_archive:
        for c in [m['checkpoint'] for m in terp_proc.context_history.maps if 'checkpoint' in m]:
            if c.exists():
                save_file_archive.add(os.path.relpath(c))
            else:
                debug_print("Warning: unable to add non-existent file %s to archive!" % shlex.quote(str(c)), 2)


def make_moves(depth=0) -> None:
    """Try a move. See if it loses. If not, see if it was useless. If either is true,
    just undo it and move on to the next command: there's no point in continuing if
    either is the case. ("Useless" here means that the 'terp signaled back to us
    that it was a mistake in some sense.)

    Otherwise, check to see if we won. If we did, document the fact and move along.

    If we didn't win, lose, or get told we made a mistake, the function calls itself
    again to make another set of moves. Along the way, it does the record-keeping
    that needs to happen for us to be able to report the steps that led to the
    success state after the fact. One way that it does this is by managing "context
    frames," summaries of the game state that are kept in a chain. Most information
    in them is stored "sparsely," i.e. only if it changed since the previous frame
    (the exception being the 'command' field, which is always filled in.) These
    context frames are part of the global interpreter-program connection object and
    can be indexed like a dictionary to look at the current game state, or examined
    individually to see how the state has changed. Storing a "successful path"
    record involves storing each frame individually in a JSON file. Reconstructing
    the 'command' fields of each frame in the proper (i.e., reversed) order produces
    a walkthrough to the current path.

    This function also causes in-game "save" checkpoints to be created for each
    frame automatically, as a side effect that occurs when evaluate_context() is
    running to interpret the game's output.

    Leave DEPTH parameter set to zero when calling the function to start playing the
    game; the function uses this parameter internally to track how deep we are. This
    is occasionally useful for debugging purposes.
    """
    global successes, dead_ends, moves

    if is_redundant_strand(terp_proc._walkthrough):      # If we've tracked that we've been down this path, skip it.
        return

    these_commands = list(all_commands.keys())  # Putting them in random order doesn't make the process go faster ...
    #random.shuffle(these_commands)              # But it does make it less excruciating to watch.

    # Make sure we've got a save file to restore from after we try commands.
    if 'checkpoint' not in terp_proc.context_history.maps[0]:
        terp_proc.context_history['checkpoint'] = terp_proc.save_terp_state()
    # Keep a copy of our starting state. Dict() to collapse the ChaimMap to a flat state.
    # This data includes a reference to a save state that we'll restore to after every single move.
    starting_frame = dict(terp_proc.context_history)

    for c_num, c in enumerate(these_commands):
        if all_commands[c](c):  # check to see if we're allowed to try this command right now. If so ...
            try:                # execute_command() produces a checkpoint that will be used by _unroll(), below.
                room_name = terp_proc.context_history['room'] if ('room' in terp_proc.context_history) else ['unknown']
                new_context = execute_command(c)
                if ('checkpoint' not in new_context) or (not new_context['checkpoint'].exists()):
                    if (not new_context['success']) and (not new_context['failed']) and (not new_context['mistake']):
                        debug_print('WARNING: checkpoint not created for command ' + c.upper() + '!', 1)
                terp_proc._add_context_to_history(new_context)
                terp_proc.context_history.maps[0]['command'] = c           # Add again in case it got optimized sparsely away.
                move_result = "VICTORY!!" if new_context['success'] else ('mistake' if new_context['mistake'] else ('failure!' if new_context['failed'] else ''))
                debug_print(' ' * depth + ('move: (%s, %s) -> %s' % (room_name, c.upper(), move_result)), 3)
                # Process the new context.
                if new_context['success']:
                    print('Command %s won! Recording ...' % c)
                    record_solution()
                    successes += 1
                    time.sleep(5)               # Let THAT sit there on the debugging screen for a few seconds.
                elif new_context['mistake']:
                    debug_print('command %s was detected to be a mistake!' % c, 4)
                    dead_ends += 1
                elif new_context['failed']:
                    debug_print('command %s lost the game!' % c, 4)
                    dead_ends += 1
                else:               # If we didn't win, lose, or get told we made a mistake, make another move.
                    make_moves(depth=1+depth)
            except Exception as errrr:
                document_problem("general_exception", data={'error': errrr, 'command': c})
            finally:
                moves += 1
                total = dead_ends + successes
                if (total % 1000 == 0) or ((verbosity >= 2) and (total % 100 == 0)) or ((verbosity >= 4) and (total % 20 == 0)):
                    print("Explored %d complete paths so far, making %d total moves in %.2f minutes" % (total, moves, get_total_time()/60))
                terp_proc._restore_terp_to_save_file(starting_frame['checkpoint'])
                terp_proc._drop_history_frame()
    if len(terp_proc.context_history.maps) % 4 == 0:
        terp_proc.create_progress_checkpoint()


def play_game() -> None:
    """Devour all the paths in All Things Devours. Make one set of moves, and the
    make_moves() routine will keep making new ones.
    """
    make_moves()


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


def validate_directory(p: Path, description: str) -> None:
    """Checks to make sure that directory with path P and textual description
    DESCRIPTION does in fact exist and is in fact a directory. Lets the program
    crash if that is not true, on the theory that that needs to be fixed before we
    can move forward.
    """
    if p.exists():
        assert p.is_dir(), "ERROR: %s exists, but is not a directory!" % p
    else:
        p.mkdir()
        debug_print("    successfully created %s directory %s" % (description, shlex.quote(str(p))))


def empty_save_files() -> None:
    """Empty the save-file directory before beginning the run."""
    debug_print('(emptying saved-games directory ...)', 2)
    # Careful not to erase the single checkpoint file that's already been created by terp_connection.__init__()!
    files_to_erase = [f for f in save_file_directory.glob('*') if not f in terp_proc._all_checkpoints]
    for sav in files_to_erase:
        debug_print("(deleting %s ...)" % sav, 3)
        sav.unlink()


def interpret_command_line() -> None:
    """Sets global variables based on command-line parameters. Also handles other
    aspects of command-line processing, such as responding to --help.
    """
    global verbosity, transcript
    global interpreter_location, story_file_location
    debug_print("  processing command-line arguments!", 2)
    parser = argparse.ArgumentParser(description=module_docstring)
    parser.add_argument('--verbose', '-v', action='count',
                        help="increase how chatty the script is about what it's doing")
    parser.add_argument('--quiet', '-q', action='count', help="decrease how chatty the script is about what it's doing")
    parser.add_argument('--interpreter', '--terp', '-i', '-t', type=Path,
                        help="full path to the interpreter used to run All Things Devours")
    parser.add_argument('--story', '-s', type=Path,
                        help="full path to the game file played by the interpreter")
    parser.add_argument('--script', action='store_true')
    args = vars(parser.parse_args())

    if args['script']:
        terp_proc.SCRIPT()              # We didn't start when its __init__() was called. Start now.
    verbosity += args['verbose'] or 0
    verbosity -= args['quiet'] or 0
    interpreter_location = args['interpreter'] or interpreter_location
    story_file_location = args['story'] or story_file_location

    debug_print('  command-line arguments are:' + pprint.pformat(args), 2)


def load_progress_data() -> None:
    """Sets global variables based on saved progress data from a previous run of the
    script, if there is any saved progress data from a previous run of the script.
    """
    global dead_ends, successes, script_run_start, moves
    global progress_data
    try:
        with bz2.open(progress_checkpoint_file, mode='rt') as pc_file:
            progress_data = json.load(pc_file)
            script_run_start = datetime.datetime.now() - datetime.timedelta(seconds=max([t['time'] for t in progress_data.values()]))
            dead_ends = max([t['dead ends'] for t in progress_data.values()])
            successes = max([t['successes'] for t in progress_data.values()])
            moves = max([t['total moves'] for t in progress_data.values()])
        print("Successfully loaded previous progress data!")
    except Exception as errr:                   # Everything was initialized up top, anyway.
        print("Can't restore progress data: starting from scratch!")
        debug_print("Exception causing inability to read previous data: %s" % errr, 1)


def set_up() -> None:
    """Set up the many fiddly things that the experiment requires."""
    debug_print("setting up program run!", 2)

    signal.signal(signal.SIGUSR1, processUSR1)
    signal.signal(signal.SIGUSR2, processUSR2)
    debug_print("  signal handlers installed!", 2)

    empty_save_files()

    if len(sys.argv) >= 2:
        interpret_command_line()
    else:
        debug_print("  no command-line arguments!", 2)
    debug_print('  final verbosity is: %d' % verbosity, 2)

    # Set up the necessary directories. Not particularly robust against malicious interference and race conditions,
    # but this script is just for me, anyway. Assumes a cooperative, reasonably competent user.
    debug_print("  about to check directory structure ...", 2)
    validate_directory(working_directory, "working")
    validate_directory(save_file_directory, "save file")
    validate_directory(successful_paths_directory, "successful paths")
    validate_directory(logs_directory, 'logs')
    debug_print("  directory structure validated!")

    load_progress_data()


if __name__ == "__main__":
    set_up()
    play_game()
