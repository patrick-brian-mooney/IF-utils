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
import os
import pprint
import queue
import shlex, signal, subprocess, sys
import threading, time


verbosity = 0       # How chatty are we being about our progress?
# Definitions of debugging levels:
# 0         Only print "regular things": solutions found, periodic processing updates, fatal errors
# 1         Also display warnings.
# 2         Also display chattery informative messages.
# 3         Also display each node explored: location, action taken

# Program-running parameters. Probably not useful when not on my system. Override with -i  and -s, respectively.
interpreter_location = '/home/patrick/bin/glulxe/glulxe'
story_file_location = '/home/patrick/games/IF/by author/Ord, Toby/as half sick of shadows/[2004] All Things Devours/hacking/devours.ulx'

working_directory = os.path.join(os.path.abspath(os.path.dirname(story_file_location)), 'working')
save_file_directory = os.path.join(working_directory, 'saves')
successful_paths_directory = os.path.join(working_directory, 'successful_paths')


# Global variables to hold the external process and related information.
terp_proc = None                    # Just declaring it here so it's obviously in the global namespace. It'll be rebound soon enough.


def debug_print(what, min_level=1) -> None:
    """Print WHAT, if the global VERBOSITY is at least MIN_LEVEL."""
    if verbosity >= min_level:
        print(what)


class UnexpectedEndOfStream(Exception):
    """Exception class for the NonBlockingStreamReader class, below. Designed by Eyal
    Arubas, very slightly modified.
    """
    pass


class NonBlockingStreamReader(object):
    """Wrapper for subprocess.Popen's stdout and stderr streams, so that we can read
    from them without having to worry about blocking.

    Based heavily on Eyal Arubas's solution to the problem at
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
                    raise UnexpectedEndOfStream

        self._t = threading.Thread(target=_populateQueue, args=(self._s, self._q))
        self._t.daemon = True
        self._t.start()             # start collecting lines from the stream

    def readline(self, timeout=None) -> bytes:
        """Returns the next line in the buffer, if there are any; otherwise, returns None."""
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
        buffer.
        """
        return '\n'.join([l.decode() for l in self.readlines()])


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
        self._proc = subprocess.Popen([interpreter_location, story_file_location], stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=False)
        self._nonblocking_reader = NonBlockingStreamReader(self._proc.stdout)
        debug_print("\n\n  successfully initiated connection to new 'terp! It said:\n\n" + self._get_output() + "\n\n", 2)

    def __repr__(self):
        return object.__repr__(self)        #FIXME!

    def _clean_up(self):
        """Politely close down the connection to the 'terp. Store None in its wrapped
        objects to force a crash if we keep trying to work with it.
        """
        self._nonblocking_reader._quit = True
        time.sleep(0.5)
        self._proc.stdin.close()
        self._proc.terminate()
        self._proc, self._nonblocking_reader = None, None

    def _get_output(self) -> str:
        """Convenience function to return whatever output text is currently queued in the
        nonblocking wrapper around the 'terp's STDOUT stream.
        """
        return self._nonblocking_reader.read_text()

    def _pass_command_in(self, command:str):
        """Passes a command in to the 'terp. This is a low-level atomic-type function that
        does nothing other than pass a command in to the 'terp. It doesn't read the
        output or do anything else about the command. It just passes a command into
        the 'terp.
        """
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

    def _process_command(self, command: str) -> dict:
        """Takes this 'terp, runs COMMAND through it, and looks at the output. Infers as
        much as it can from the output text and returns a dictionary object that has
        fields with defined names that represents the data in a structured manner.

        Defined field names:
          'failed'      If the function detects that the mission failed, this is True.
          'room'        If the function detects that the 'terp is signaling that the
                        player is in a new room, this is the name of that room.
          'inventory'   A list: the player's inventory.
          'checkpoint'  A full path to a save-state file.
        """
        command_lines = command.split('\n')



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
    debug_print("setting up program run!", 2)
    global verbosity, interpreter_location, story_file_location
    global terp_proc

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
    if os.path.exists(working_directory):
        assert os.path.isdir(working_directory), "ERROR: %s exists, but is not a directory!" % working_directory
    else:
        os.mkdir(working_directory)
        debug_print("    successfully created working directory %s" % shlex.quote(working_directory))
    if os.path.exists(save_file_directory):
        assert os.path.isdir(save_file_directory), "ERROR: %s exists, but is not a directory!" % save_file_directory
    else:
        os.mkdir(save_file_directory)
        debug_print("    successfully created save file directory %s" % shlex.quote(save_file_directory))
    if os.path.exists(successful_paths_directory):
        assert os.path.isdir(successful_paths_directory), "ERROR: %s exists, but is not a directory!" % successful_paths_directory
    else:
        os.mkdir(successful_paths_directory)
        debug_print("    successfully created successful paths directory %s" % shlex.quote(successful_paths_directory))
    debug_print("  directory structure validated!")

    terp_proc = TerpConnection()


def execute_command(command:str) -> TerpContext:
    """Convenience function: execute the command COMMAND and return the new interpreter
    context as a TerpContext object.
    """


def play_game() -> None:
    """Actually, for now, this is testing code."""
    print(terp_proc._process_command_and_return_output('down'))
    print(terp_proc._process_command_and_return_output('open door'))
    print(terp_proc._process_command_and_return_output('north'))

if __name__ == "__main__":
    set_up()
    play_game()
