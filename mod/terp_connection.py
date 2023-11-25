#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A class to maintain a connection to a console IF interpreter. Originally
developed for the ATD project, but comes in handy elsewhere.

Also contains utility code needed by the FrotzTerpConnection object.

This script is copyright 2019-23 by Patrick Mooney. It is released under the
GPL, either version 3 or (at your option) any later version. See the file
LICENSE for a copy of this license.
"""


import collections
import datetime
import json
import os
import pprint
import traceback

from pathlib import Path

import queue
import shlex
import subprocess
import sys
import threading
import time
import typing
import uuid


# Definitions of debugging verbosity levels:
# 0         Only print "regular things": solutions found, periodic processing updates, fatal errors
# 1         Also display warnings.
# 2         Also display chatty messages about large-scale progress.
# 3         Also display each node explored: (location, action taken) -> result
# 4         Also chatter extensively about individual steps taken while exploring each node
verbosity = 2  # How chatty are we being about our progress?
maximum_verbosity_level = 4


print_mutex = threading.Lock()
def safe_print(*args, **kwargs) -> None:
    """Print safely, i.e. in a way that ensures multiple threads aren't trying to print
    at the same time and stepping on each other's output.
    """
    with print_mutex:
        print(*args, **kwargs)


def safe_pprint(*args, **kwargs) -> None:
    """Same as safe_print, but safely pprints instead of printing."""
    with print_mutex:
        pprint.pprint(*args, **kwargs)


def debug_print(what: str, min_level: int=1) -> None:
    """Print WHAT, if the global VERBOSITY is at least MIN_LEVEL."""
    if verbosity >= min_level:
        safe_print(" " * min_level + what)       # Indent according to unimportance level.


if __name__ == "__main__":
    safe_print("No self-test code in this module, sorry! explore_ATD.py is a wrapper that runs this code.")
    sys.exit(1)


# Here's a utility class used to wrap an output stream for the FrotzTerpConnection, below.
class NonBlockingStreamReader(object):
    """Wrapper for subprocess.Popen's stdout and stderr streams, so that we can read
    from them without having to worry about blocking.

    Draws heavily from Eyal Arubas's solution to the problem at
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

    def readline(self, timeout=None) -> typing.Union[str, None]:
        """Returns the next line in the buffer, if there are any; otherwise, returns None.
        Waits up to TIMEOUT seconds for more data before returning None. If TIMEOUT is
        None, blocks until there IS more data in the buffer. Does not do any decoding.
        """
        try:
            return self._q.get(block=timeout is not None, timeout=timeout)
        except queue.Empty:
            return None

    def readlines(self, *pargs, **kwargs) -> typing.List[str]:
        """Returns a list of all lines waiting in the buffer. If no lines are waiting in
        the buffer, returns an empty list. Takes *pargs and **kwargs to be compatible
        with .readlines() on a file object, but complains at debug level 1 if they are
        supplied, in case I'm ever tempted to pass them in, or I ever thoughtlessly pass
        this object to anything that takes advantage of other features on more standard
        interfaces.
        """
        if pargs:
            debug_print(f"WARNING! positional arguments {pargs} supplied to NonBlockingStreamReader.readlines()! Ignoring...", 1)
        if kwargs:
            debug_print(f"WARNING! keyword arguments {kwargs} supplied to NonBlockingStreamReader.readlines()! Ignoring...", 1)
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


# And there is the object wrapping up a connection to an interpreter.
class FrotzTerpConnection(object):
    """Maintains a connection to a running instance of a 'terp executing a game. Also
    maintains a connection to the nonblocking reader that wraps its stdout stream.
    Provides functions for issuing a command to the 'terp and reading the text that
    is returned. Also provides some convenience functions to control the 'terp in a
    higher-level way.
    """
    # First, some constants used by the code to deal with dfrotz output
    mistake_messages = [""""oops" can only correct""", "after a few moments, you realise that", "already closed.",
                        "beg your pardon?", "but you aren't", "but you aren't in anything",
                        "darkness, noun.  an absence of light", "digging would achieve nothing here", "does not open.",
                        "error: unknown reason for", "for a while, but don't achieve much.", "i didn't understand that",
                        "i didn't understand the way", "i don't think much is to be achieved",
                        "i only understood you as far as", "impossible to place objects on top of it.",
                        "is already here.", "it is pitch dark, and you can't", "no pronouns are known to the game",
                        "nothing practical results", "real adventurers do not", "seem to be something you can lock.",
                        "seem to be something you can unlock.", "sorry, you can only have one",
                        "that would be less than courteous", "that's not a verb i recognise",
                        "that's not something you need to refer to", "the dreadful truth is, this is not a dream.",
                        "this dangerous act would achieve little", "to talk to someone, try",
                        "violence isn't the answer", "you aren't feeling especially", "you can only do that to",
                        "you can only get into something", "you can only use multiple objects",
                        "you can't put something inside", "you can't put something on", "you can't see any such thing",
                        "you can't use multiple objects", "you're carrying too many",
                        "you excepted something not included", "you jump on the spot, fruitlessly", "you see nothing",
                        "you seem to have said too little", "you seem to want to talk to someone, but",
                        ]

    disambiguation_messages = ["which do you mean", "please give one of the answers above"]

    failure_messages = [l.strip().casefold() for l in ['*** You have died ***,']]
    success_messages = [l.strip().casefold() for l in ['*** You have won ***',]]

    # Configuration options that can be overridden in subclasses
    interpreter_location = Path('/home/patrick/bin/dfrotz/dfrotz').resolve()
    interpreter_flags = ["-m", ]

    save_every_turn = True
    inventory_every_turn = True
    create_game_transcript = True

    # Configuration options that MUST be overridden in subclasses
    rooms = None
    story_file_location = None
    inventory_answer_tag = None # The beginning of a "you are carrying:" response, in casefold-case.

    # Configuration options related to filesystem paths. They MUST be overridden.
    base_directory = None
    working_directory = None
    save_file_directory = None
    logs_directory = None

    # Some parameters that can be overridden in subclasses to change behavior.
    transcript = True

    @staticmethod
    def _validate_directory(p: Path,
                            desc: str) -> None:
        """Checks to make sure that directory with path P and textual description
        DESC does in fact exist and is in fact a directory. Lets the program
        crash if that is not true, on the theory that that needs to be fixed before we
        can move forward.
        """
        if p.exists():
            assert p.is_dir(), "ERROR: %s exists, but is not a directory!" % p
        else:
            p.mkdir()
            safe_print("    successfully created %s directory %s" % (desc, shlex.quote(str(p))))

    def _empty_save_files(self) -> None:
        """Empty the save-file directory before beginning the run.
        """
        debug_print('(emptying saved-games directory ...)', 2)
        # Careful not to erase the single checkpoint file that's already been created by terp_connection.__init__()!
        files_to_erase = [f for f in self.save_file_directory.glob('*') if not f in self._all_checkpoints]
        for sav in files_to_erase:
            debug_print("(deleting %s ...)" % sav, 3)
            sav.unlink()

    def _set_up(self) -> None:
        """Set up the necessary directories. Not particularly robust against malicious
        interference and race conditions, but this script is just for me, anyway.
        Assumes a cooperative, reasonably competent user.
        """
        self._validate_directory(self.working_directory, "working")
        self._validate_directory(self.save_file_directory, "save file")
        self._validate_directory(self.logs_directory, 'logs')
        debug_print("  directory structure validated!")

        self._empty_save_files()

    def __init__(self):
        """Opens a connection to a 'terp process that plays ATD. Saves a reference to that
        process. Wraps its STDOUT stream in a nonblocking wrapper. Saves a reference to
        that wrapper. Initializes the command-history data structure. Does other setup.
        """
        assert self.rooms, f"ERROR! Class {self.__class__.__name__} does not specify a list of room names!"
        assert self.story_file_location, f"ERROR! Class {self.__class__.__name__} does not specify a story file location!"
        assert self.inventory_answer_tag, f"ERROR! Class {self.__class__.__name__} does not specify an inventory answer tag!"

        assert self.base_directory, f"ERROR! Class {self.__class__.__name__} does not specify a base directory!"
        assert self.working_directory, f"ERROR! Class {self.__class__.__name__} does not specify a working directory!"
        assert self.save_file_directory, f"ERROR! Class {self.__class__.__name__} does not specify a save file directory!"
        assert self.logs_directory, f"ERROR! Class {self.__class__.__name__} does not specify a logs directory!"

        assert self.base_directory.is_dir(), f"ERROR! {self.base_directory} does not exist or is not a directory!"
        assert self.working_directory.is_dir(), f"ERROR! {self.working_directory} does not exist or is not a directory!"
        assert self.save_file_directory.is_dir(), f"ERROR! {self.save_file_directory} does not exist or is not a directory!"
        assert self.logs_directory.is_dir(), f"ERROR! {self.logs_directory} does not exist or is not a directory!"

        parameters = [str(self.interpreter_location)] + self.interpreter_flags + [str(self.story_file_location)]
        self._proc = subprocess.Popen(parameters, shell=False, universal_newlines=True, bufsize=1,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self._reader = NonBlockingStreamReader(self._proc.stdout)
        opening_context = self.evaluate_context(self._get_output(), command='[game start]')
        self.context_history = collections.ChainMap(opening_context)
        self._set_up()
        if self.transcript:
            self.SCRIPT()

    def __str__(self) -> str:
        ret =  f"< {self.__class__.__name__} object; "
        try:
            ret += " room: " + self.current_room + ';'
        except Exception:
            ret += " room: [unknown]\n"
        try:
            ret += " inventory: " + str(self.peek_at_inventory) + ';'
        except Exception:
            ret += " inventory: [unknown];"
        try:
            ret += " last command: " + self.last_command
        except Exception:
            ret += " last command: [unknown]"
        ret += " >"
        return ret

    def document_problem(self,
                         problem_type: str,
                         data: dict,  # FIXME: containing what?
                         also_print: bool = True) -> None:
        """Document the fact that a problem situation arose.

        PROBLEM_TYPE is a string indicating what type of problem arose; it should be
        chosen from a small list of short standard strings. DATA is the data to be
        stored about the problem.

        A filename for the log file is automatically determined and the file is written
        to the logs/ directory.

        If ALSO_PRINT is True (the default), also dumps the complaint to the terminal.
        """
        found = False
        data['traceback'] = traceback.extract_stack()
        while not found:
            p = self.logs_directory / (problem_type + '_' + datetime.datetime.now().isoformat().replace(':', '_') + '.json')
            found = not p.exists()
        p.write_text(json.dumps(data, indent=2, default=str, sort_keys=True))
        if also_print:
            safe_print("PROBLEM TYPE: " + problem_type + '\n\nData:\n')
            safe_pprint(data)

    def _clean_up(self) -> None:
        debug_print("Cleaning up the 'terp connection.", 2)
        self.QUIT()

    def _definitely_quit(self) -> None:
        """Politely close down the connection to the 'terp. Store None in its wrapped
        objects to force a crash if we keep trying to work with it.
        """
        self._clean_up()
        self._proc.stdin.close()
        self._proc.terminate()
        self._reader._quit = True
        self._proc, self._reader = None, None

    def _get_output(self, retry: bool = True) -> str:
        """Convenience function to return whatever output text is currently queued in the
        nonblocking wrapper around the 'terp's STDOUT stream. If there is no text at
        all, then, if RETRY is True, sleep and retry several times until there is, or
        until we've been patient enough and give up. If there is no text at all and
        RETRY is False, just return an empty string.
        """
        debug_print("(read STDOUT from buffer)", 5)
        ret = self._reader.read_text()
        if (not ret) and retry:                 # Sometimes we need to wait on the buffer a few times.
            sleep_time = 0.1
            for i in range(20):                 # Should we just be upping the timeout on the read? -- probably not
                ret = self._reader.read_text()
                if ret:
                    break
                else:
                    time.sleep(sleep_time)
                    sleep_time *= 1.48          # Wait longer and longer for data from the 'terp.
            if not ret:
                self.document_problem("no data", data={'ERROR': "unable to get any data at all from the 'terp, even after being patient!"})
        return ret.lstrip().lstrip('>').lstrip()

    def _add_context_to_history(self, context: typing.Dict) -> None:       # FIXME: dict containing what?
        """Adds the context to the front of the context-history chain, taking care only
        to add "sparsely": it drops information that duplicates the most current
        information in the context chain.
        """
        new = {k: v for k, v in context.items() if ((k not in self.context_history) or (self.context_history[k] != v) or (k.strip().casefold() == "command"))}
        debug_print(f'(adding new frame {new} to context history', 4)
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

    def repeat_last_output(self) -> str:
        """A utility function to repeat the last output that the 'terp produced. Does NOT
        look at or touch any data currently in the buffer waiting to be read; it just
        consults the 'terp's context history to extract the last output that was
        recorded there.
        """
        debug_print('(re-reading last output)', 4)
        return self.context_history['output']

    @property
    def reconstruct_transcript(self) -> str:
        """Reconstruct a walkthrough to the current state from the context frames stored in
        the FrotzTerpConnection. Note that this may not be identical to the transcript
        actually kept by the program; that text is processed before the original text is
        thrown away. This is a reconstruction, though it should be a fairly close one.
        """
        return '\n\n'.join(reversed(['> ' + frame['command'] + '\n\n' + frame['output'] for frame in self.context_history.maps]))

    @property
    def list_walkthrough(self) -> typing.List[str]:
        """Convenience function: return a list of the commands that were executed to get
        the game into this state. Unlike text_walkthrough(), below, this doesn't return
        a single string that includes all commands, but rather a list in which each item
        is a single textual command.
        """
        return list(reversed([frame['command'] for frame in self.context_history.maps]))

    @property
    def text_walkthrough(self) -> str:
        """Convenience function: get a terse walkthrough consisting of the commands
        that produced the 'terp's current game state. Unlike list_walkthrough(), above,
        what is returned is a single string representing the entire walkthrough, in
        which steps are separated by periods, rather than a list of steps.

        This function is used to produce keys that index the current solution space for
        algorithmic-progress-checkpointing purposes, among other purposes.
        """
        return '. '.join(self.list_walkthrough).upper() + '.'

    @property
    def current_room(self) -> str:
        """Convenience function: get the name of the room currently occupied by the PC, if
        we can tell what room that is; otherwise, return a string indicating we don't
        know.
        """
        return self.context_history['room'] if ('room' in self.context_history) else '[unknown]'

    @property
    def last_command(self) -> str:
        """Convenience function: returns the last command passed into the 'terp, if there
        has been one; otherwise, returns None.
        """
        return self.context_history['command'] if ('command' in self.context_history) else None

    @property
    def peek_at_inventory(self) -> typing.List[str]:
        """Returns what the FrotzTerpConnection thinks is the current inventory. Note that this
        does not actually execute an INVENTORY command, which is in any case executed
        automatically at every turn; it just returns the result of the last INVENTORY
        command, which the 'terp stores.

        Use the all-caps INVENTORY convenience function to pass a new INVENTORY command
        to the 'terp and get the results of that.
        """
        return self.context_history['inventory'] if ('inventory' in self.context_history) else list()

    @property
    def _all_checkpoints(self) -> typing.List[Path]:
        """Convenience function to get a list of all checkpoints currently tracked by the FrotzTerpConnection."""
        return [frame['checkpoint'] for frame in self.context_history.maps if 'checkpoint' in frame]

    def has(self, what: str) -> bool:
        """Returns True if the PC currently has WHAT in her inventory, False otherwise.
        WHAT is a string that is compared case-insensitively to see if it's a partial
        match for anything in the PC's inventory. So, has('batt') returns True if the
        PC is carrying "a battery" or "two batteries" or "a base ball batt".

        Does not actually issue an in-game INVENTORY command; just peeks at what the
        result of the last one was. Since INVENTORY commands are issued every turn, then
        undone, this should be accurate.
        """
        what = what.casefold().strip()
        inventory = [i.casefold().strip() for i in self.peek_at_inventory]
        for item in inventory:
            if what in item:
                return True
        return False

    def _pass_command_in(self, command: str) -> None:
        """Passes a command in to the 'terp. This is a low-level atomic-type function that
        does nothing other than pass a command in to the 'terp. It doesn't read the
        output or do anything else about the command or its results. It just
        passes a command in to the 'terp.
        """
        assert isinstance(command, str)
        debug_print(f"(passing command {command.upper()} to 'terp)", 4)

        command = (command.strip() + '\n')
        self._proc.stdin.write(command)
        self._proc.stdin.flush()

    def process_command_and_return_output(self, command: str,
                                          be_patient: bool = True) -> str:
        """A convenience wrapper: passes a command into the 'terp, and returns whatever text
        the 'terp barfs back up. Does minimal processing on the command passed in -- it
        adds a newline (or rather, a newline is added by a function that is called by
        this function) -- and no processing on the output text. (All text is processed
        using the system default encoding because we're in text mode, or "universal
        newlines" mode, if you prefer. Heck, Python 3.6 does so prefer.) In particular,
        it performs no EVALUATION of the text's output, leaving that to other code.

        If BE_PATIENT is True, passes True to _get_output()'s RETRY parameter, so that
        it will be more patient while waiting for output. If not--and there are some
        annoying situations where the 'terp doesn't cough up any response--then just
        don't bother waiting if we can't get anything on the first attempt.
        """
        self._pass_command_in(command)
        return self._get_output(retry=be_patient)

    def _generate_save_name(self) -> Path:
        """Generate a filename for an auto-save file from the 'terp. Can be overridden
        by subclasses. By default, just use a UUID4. Subclasses may want to generate
        more human-meaningful names.
        """
        found_name = False
        while not found_name:
            p = self.save_file_directory / str(uuid.uuid4())
            found_name = not p.exists() # Vulnerable to race conditions, Vanishingly so, though. Still, be careful.
        return p

    def save_terp_state(self) -> Path:
        """Saves the interpreter state. It does this solely by causing the 'terp to
        generate a save file. It automagically figures out an appropriate file name
        in the SAVE_FILE_DIRECTORY, and returns a Path object describing the location
        of the save file. It does not make any effort to save anything that is not
        stored in the 'terp's save files. Things not saved include, but may not be
        limited to, SELF's context_history mappings.
        """
        p = self._generate_save_name()
        debug_print("(saving 'terp state to %s)" % p, 5)
        _ = self.process_command_and_return_output('save', be_patient=False)   # We can't expect to get a response here: the 'terp doesn't necessarily end its response with \n, because it's waiting for a response on the same line, so we won't get the prompt text until after we've passed the prompt answer in.
        # output = self.process_command_and_return_output(os.path.relpath(p, self.base_directory), be_patient=False)        #FIXME! remove this old line
        output = self.process_command_and_return_output(os.path.relpath(p, Path(os.getcwd())), be_patient=False)
        if ("save failed" in output.casefold()) or (not p.exists()):
            self.document_problem(problem_type='save_failed',
                                  data={'filename': str(p), 'output': [_, output], 'exists': p.exists()})
        return p

    def _restore_terp_to_save_file(self, save_file_path: Path) -> bool:
        """Restores the 'terp state to the state represented by the save file at
        SAVE_FILE_PATH. Returns True if the restoring action was successful, or False if
        it failed.
        """
        _ = self.process_command_and_return_output('restore', be_patient=False)
        output = self.process_command_and_return_output(os.path.relpath(save_file_path))
        return not ('failed' in output.casefold())

    def _undo_if_possible_or_restore(self, save_file_path: Path) -> bool:
        """Tries to issue an UNDO command. If that fails for some reason, issue a
        RESTORE command instead. Returns True if one of these succeeded, or False
        if neither was successful
        """
        if self.UNDO:
            return True
        else:
            return self._restore_terp_to_save_file(save_file_path)

    def _get_inventory(self) -> typing.List[str]:
        """Executes an INVENTORY command and undoes it, then interprets the results of
        the command.
        """
        debug_print("(getting PC inventory)", 4)
        inventory_text = self.process_command_and_return_output('inventory')
        if not self.UNDO():
            debug_print("Warning! Unable to undo INVENTORY command.", 2)
        ret = list([l.strip() for l in inventory_text.split('\n')])
        ret = [l for l in ret if l.strip().strip('.').strip()]
        ret = [l for l in ret if (l.strip() and not l.strip().strip('>').casefold().startswith(self.inventory_answer_tag))]
        ret = [l for l in ret if not l.strip().casefold().startswith(self.rooms)]
        if not ret:
            self.document_problem('cannot_get_inventory', data={'inventory_text': inventory_text, 'note': f"'{self.inventory_answer_tag}' not in output text!"})
        return ret

    def _get_score_text(self) -> str:
        """Executes a SCORE command and returns the text with which the interpreter
        responds. Does not issue an UNDO command because an extradiegetic command
        cannot be undone.
        """
        return self.process_command_and_return_output('score')

    def restore_terp_state(self) -> None:
        """Restores the 'terp to the previous state. Does not handle housekeeping for any
        other aspect of the FrotzTerpConnection; notably, does not drop the context_history
        frame from the context history stack.
        """
        debug_print("(restoring 'terp state to previous save file)", 5)
        assert 'checkpoint' in self.context_history.maps[1], "ERROR: trying to restore to a state for which there is no save file!"
        self._restore_terp_to_save_file(self.context_history.maps[1]['checkpoint'])

    def UNDO(self) -> typing.Union[bool, None]:
        """Convenience function: undo the last turn in the 'terp. Returns True if the
        function executes an UNDO successfully, or False if it does not.
        """
        txt = self.process_command_and_return_output('undo')
        if """you can't "undo" what hasn't been done""".casefold() in txt.casefold():
            return True         # "Nothing was done" is as good as successfully undoing. =)
        if not txt:
            self.document_problem(problem_type="cannot_undo", data={'output': None})
            return False
        if "undone.]" in txt.casefold():
            return True
        else:
            self.document_problem(problem_type="cannot_undo", data={"output": txt, 'note': '"undone.]" not in output!'})

    def LOOK(self) -> None:
        """Convenience function: execute the LOOK command in the 'terp, print the results,
        and undo the command.
        """
        safe_print(self.process_command_and_return_output('look'))
        if not self.UNDO():
            debug_print('WARNING: unable to undo LOOK command!', 2)

    def SCRIPT(self) -> None:
        """Determines an appropriate transcript name, and issues a SCRIPT command to the
        'terp to cause a transcript to be kept at that location.
        """
        found_name = False
        while not found_name:
            p = self.working_directory / ('transcript_' + datetime.datetime.now().isoformat().replace(':', '_'))
            found_name = not p.exists()  # Yes, vulnerable to race conditions, Vanishingly so, though.
        debug_print("(saving transcript to %s)" % p, 5)
        _ = self.process_command_and_return_output('script', be_patient=False)
        _ = self.process_command_and_return_output(os.path.relpath(p, self.base_directory))

    def INVENTORY(self) -> None:
        """Convenience wrapper: print the current inventory to the console, then undo the
        in-game action.
        """
        safe_print(self._get_inventory())

    def SCORE(self) -> None:
        """Convenience wrapper: print the result of the SCORE command to the terminal.
        Does not UNDO, because an extradiegetic action cannot be undone.
        """
        safe_print(self._get_score_text())

    def Y(self, be_patient=False) -> None:
        """Sends a Y ("yes") command to the 'terp."""
        _ = self.process_command_and_return_output('Y', be_patient=be_patient)

    def QUIT(self) -> None:
        """Sends a QUIT command to the 'terp, then keeps sending it Y commands until
        it gives up.
        """
        _ = self.process_command_and_return_output('QUIT', be_patient=False)
        try:
            start_time, iterations = datetime.datetime.now(), 0
            while (iterations <= 20) and ((datetime.datetime.now() - start_time).total_seconds() <= 30):
                _ = self.Y(be_patient=(iterations == 0))
                if iterations:
                    time.sleep(0.1)
                iterations += 1
        except BaseException:
            pass

    def evaluate_context(self, output: str,
                         command: str) -> typing.Dict[str, typing.Union[str, int, bool, Path, typing.List[str]]]:
        """Looks at the output retrieved after running a command and infers as much as it
        can from the output text, then returns a dictionary object that has fields with
        defined names that represents the data in a structured manner.

        Defined field names:
          'room'        If the function detects that the 'terp is signaling which room
                        the player is in, this is the name of that room.
          'inventory'   A list: the player's inventory.
          'turns'       In narrative through-play sequence, which turn number is this?
          'checkpoint'  A full path to a save-state file that was saved as the context
                        was being evaluated, i.e. right after the command was executed.
          'command'     The command that was executed to bring the 'terp into the state
                        represented by this context frame.
          'output'      The game's output that we're processing: the response to the
                        "entered" command.
          'failed'      If the function detects that the mission failed, this is True.
          'success'     If we detect that our mission has succeeded ('we have won'),
                        this is True, otherwise False.
          'mistake'     If we detect that the 'terp thinks the command is a mistake (e.g.,
                        if the command we're trying opens a door that isn't there), this
                        is set to True, otherwise False.
        """
        debug_print("(evaluating command results)", 4)
        output_lines = [l.strip() for l in output.split('\n')]
        output_lower = output.casefold().strip()
        ret = {'command': command,
               'failed': False,
               'success': False,
               'mistake': False,
               'output': output}

        try:
            ret['turns'] = 1 + len(self.context_history.maps)
        except AttributeError:      # The very first time we run, context_history doesn't exist yet!
            ret['turns'] = 1

        # Next, check for complete failure. Then, check for game-winning success.
        for m in self.failure_messages:
            if m in output_lower:
                ret['failed'] = True
                return ret
        for m in self.success_messages:
            if m in output_lower:
                ret['success'] = True
                return ret
        for l in [line for line in output_lines if line.startswith('**')]:
            if l == "*******":
                pass        # This is just a textual separator that turns up occasionally. Ignore it.
            else:
                self.document_problem('asterisk_line', data={'line': l, 'note': "Cannot interpret this game-ending asterisk line!"})

        # Next, check for disambiguation questions, then mistakes.
        # In each case, see if anything in the appropriate list BEGINS OR ENDS any output line.
        for l in [line.strip().casefold() for line in output_lines]:
            for m in self.disambiguation_messages:
                if l.startswith(m) or l.endswith(m):
                    self.document_problem(problem_type='disambiguation', data=ret)
                    ret['mistake'] = True
                    return ret
            for m in self.mistake_messages:
                if l.startswith(m) or l.endswith(m):
                    ret['mistake'] = True
                    return ret

        # Next, check to see if we're in a new room. Room names appear on their own line.
        for l in [l.strip().casefold() for l in output_lines if l.strip()]:
            if l.startswith(self.rooms):
                for r in self.rooms:
                    if l.startswith(r):
                        ret['room'] = l[:len(r)]
                        break
                break

        if not ret['success'] and not ret['failed'] and not ret['mistake']:        # Don't bother trying these if the game's over or we made no change.
            if self.save_every_turn:
                ret['checkpoint'] = self.save_terp_state()
            if self.inventory_every_turn:
                ret['inventory'] = self._get_inventory()

        return ret

    def execute_command(self, c: str) -> typing.Dict[str, typing.Union[str, int, bool, Path, typing.List[str]]]:
        """Convenience function: execute the command C and return the new interpreter
        context as a dictionary with defined values. Note that this changes the 'terp's
        game state by executing COMMAND, of course: no save/restore bracketing is
        performed at this level.
        """
        text = self.process_command_and_return_output(c)
        return self.evaluate_context(text, c)

    def make_single_move(self, c: str) -> typing.Dict[str, typing.Union[str, int, bool, Path, typing.List[str]]]:
        """Make a single move by executing the command C, and add the generated
        context frame to the play history.

        For convenience's sake, returns the new context frame after adding it to the
        play history.
        """
        new_context = self.execute_command(c)
        if ('checkpoint' not in new_context) or (not new_context['checkpoint'].exists()):
            if (not new_context['success']) and (not new_context['failed']) and (not new_context['mistake']):
                debug_print('WARNING: checkpoint not created for command ' + c.upper() + '!', 1)
        self._add_context_to_history(new_context)
        return new_context


# Some experimental adaptations to adapt the harness so it can also run a Glulx 'terp. Not yet functional.
class GlulxeTerpConnection(FrotzTerpConnection):
    interpreter_location = Path('/home/patrick/bin/glulxe/glulxe').resolve()
    interpreter_flags = [][:]


class HadeanLandsTerpConnection(GlulxeTerpConnection):
    rooms = ()
    story_file_location = Path("""/home/patrick/games/IF/by author/Plotkin, Andrew/[2014] Hadean Lands/HadeanLands.gblorb""")
    inventory_answer_tag = "You are carrying:".strip().casefold()
