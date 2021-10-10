#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-
"""Calculates the additive numerical value of a word, where each letter is assigned a
numeric value (A=1, B=2, etc.), and summing the values.

Usage:

    numerical_name.py "word"

Quotes are mandatory if the phrase being quoted contains spaces (or any other
character that your shell treats as having a special meaning). It is always
safe to wrap the phrases in quotes if you're unsure.

Uses only the ASCII Roman-script letters, assumes the ordering of the English
alphabet, and converts all letters to uppercase. If "word" contains spaces or
other whitespace, splits the string on whitespace and returns a separate some
for each word in the split.

This script is copyright 2021 by Patrick Mooney. It is released to the public
under the terms of the GPL, either version 3 or (at your option) any later
version. See the file LICENSE.md for details.
"""


import string
import typing



def get_name_value(word: str) -> int:
    """Iterates over the string NAME, assigning a value to each letter in it, then
    summing the values, then returning that sum.
    """
    word = word.strip().upper()

    if len(word) == 0:      # handle degenerate case
        return 0

    if len(word) == 1:
        assert ord('A') <= ord(word) <= ord('Z'), "ERROR! this script cannot handle numbers or punctuation or anything other than whitespace and ASCII letters!"
        return 1 + (ord(word) - ord('A'))

    assert len(word.split()) == 1, "ERROR! strings with multiple whitespace-separated words cannot be passed to get_name_value()!"
    return sum(get_name_value(c) for c in word)


def print_word_values(what_words: typing.List[str]) -> None:
    """Do the actual work of printing out the calculated values for each string in
    WHAT_WORDS. Iterates over each string in that list. If a string in that list is
    made of more than one whitespace-separated word, print each word separately, just
    as if it was a separate entry in WHAT_WORDS.
    """
    for which_string in what_words:
        for word in which_string.strip().split():
            print(word, '\t->\t', get_name_value(word))


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"ERROR! {sys.argv[0]} must be called with a set of words to be evaluated (or -h/--help)!")
        sys.exit(1)
    if sys.argv[1].lower().strip() in ['-h', '--help']:
        print(__doc__)
        sys.exit()

    print_word_values(sys.argv[1:])
