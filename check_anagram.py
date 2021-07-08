#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-
"""Anagram checker. Given two phrases, it checks whether they are anagrams of each
other. This comparison is always performed case-insensitively and looks only at
the alphanumeric components of the string.

Usage:

    anagram_checker.py "first phrase" "second phrase" [...]

Quotes are mandatory if the phrase being quoted contains spaces (or any other
character that your shell treats as having a special meaning). It is always
safe to wrap the phrases in quotes if you're unsure.

This script is copyright 2021 by Patrick Mooney. It is released to the public
under the terms of the GPL, either version 3 or (at your option) any later
version. See the file LICENSE.md for details.
"""


import collections
import pprint
import shlex
import sys
import typing


def get_lettercoount(what: str) -> str:
    return ''.join(sorted([c.casefold() for c in what if c.isalnum()]))


def check_anagrams(phrase_list: typing.Iterable):
    assert isinstance(phrase_list, typing.Iterable), "ERROR! check_anagrams() passed a non-iterable as phrase_list!"
    assert not isinstance(phrase_list, (str, bytes)), "ERROR! check_anagrams() passed a single string as phrase_list!"
    assert len(phrase_list) > 1, "ERROR! You must pass at least two phrases to check_anagram()!"

    reference = None
    for num, phrase in enumerate(phrase_list):
        if reference:
            if get_lettercoount(phrase) != reference:
                print("Phrase # %d, %s, is not an anagram of the first phrase!" %(1 + num, shlex.quote(phrase)))
                sys.exit(0)
        else:
            reference = get_lettercoount(phrase)
    print("\nAll supplied phrases are anagrams!")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        if sys.argv[1] in ['-h', '--help']:
            print(__doc__)
            sys.exit(0)
    if len(sys.argv) < 2:
        print("You must supply at least two phrases!")
        sys.exit(1)

    print("Checking the following phrases to see if they are anagrams of each other:")
    pprint.pprint(sys.argv[1:])
    check_anagrams(sys.argv[1:])
