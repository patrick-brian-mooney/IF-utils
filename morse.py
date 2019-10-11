#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A quick Morse code translator, originally for Heike Borchers's *Under the
Sea*, which was a game entered in IFComp 2019.

This script is copyright 2019 by Patrick Mooney. It is released to the public
under the terms of the GPL, either version 3 or (at your option) any later
version. See the file LICENSE.md for details.
"""
module_docstring = __doc__


import argparse

from pathlib import Path


# Unique signal objects for Morse code bits
DOT = object()
DASH = object()

# Morse Code dictionary provided by the game, translated into unique signal objects
morse = {(DOT, DASH): 'A',
         (DASH, DOT, DOT, DOT): 'B',
         (DASH, DOT, DASH, DOT): 'C',
         (DASH, DOT, DOT): 'D',
         (DOT,): 'E',
         (DOT, DOT, DASH, DOT): 'F',
         (DASH, DASH, DOT): 'G',
         (DOT, DOT, DOT, DOT): 'H',
         (DOT, DOT): 'I',
         (DOT, DASH, DASH, DASH): 'J',
         (DASH, DOT, DASH): 'K',
         (DOT, DASH, DOT, DOT): 'L',
         (DASH, DASH): 'M',
         (DASH, DOT): 'N',
         (DASH, DASH, DASH): 'O',
         (DOT, DASH, DASH, DOT): 'P',
         (DASH, DASH, DOT, DASH): 'Q',
         (DOT, DASH, DOT): 'R',
         (DOT, DOT, DOT): 'S',
         (DASH,): 'T',
         (DOT, DOT, DASH): 'U',
         (DOT, DOT, DOT, DASH): 'V',
         (DOT, DASH, DASH): 'W',
         (DASH, DOT, DOT, DASH): 'X',
         (DASH, DOT, DASH, DASH): 'Y',
         (DASH, DASH, DOT, DOT): 'Z',
         }


def is_upper(what:str) -> bool:
    """Convenience function: is WHAT uppercase, in Python's understanding?"""
    return what.isupper()


def decode(what:str, dash_selection_procedure:function=is_upper, error_tolerant:bool=False) -> str:
    """Decode WHAT, returning the decoded message. DASH_SELECTION_PROCEDURE should be a
    function that takes one parameter, an input character, and detects whether it
    constitutes a DOT or a DASH, returning the appropriate value. If ERROR_TOLERANT
    is True,  untranslatable DOT?DASH sequences are represented by a flag value
    rather than allowing the program to crash.
    """
    try:
        letters = [l.strip() for l in what.split() if l.strip()]
        ret = list()
        for l in letters:
            try:
                # Go through, bit by bit, assembling a key
                code = tuple([DASH if dash_selection_procedure(b) else DOT for b in l])
                ret.append(morse[code])
            except Exception as errr:
                if not error_tolerant:
                    raise errr
                ret.append('[???]')
        return ''.join(ret)
    except BaseException as errr:
        print("Unable to decode! The system said: %s" % errr)
        print("\nIs the dash selection procedure set correctly?\nDoes the text contain something other than English capital letters?")


def interpret_command_line() -> None:
    """Sets global variables based on command-line parameters. Also handles other
    aspects of command-line processing, such as responding to --help.
    """
    parser = argparse.ArgumentParser(description=module_docstring)
    parser.add_argument('to-decode')
    args = vars(parser.parse_args())
    decode(args['to-decode'])


if __name__ == "__main__":
    print(decode("""OOo  oOo  o  o  O  oo  Oo  OOo  ooo"""))
