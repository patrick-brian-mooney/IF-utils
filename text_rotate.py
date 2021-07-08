#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-
"""ROT13 decoder. Also ROT[X] encoder, where X is a number from 0 to 26. Originally
written to brute-force the code in Jenni Polodna's room in Cragne Manor, though
it will hopefully be useful elsewhere. In any case, it doesn't crack the code
for the relevant book.

This script is copyright 2021 by Patrick Mooney. It is released to the public
under the terms of the GPL, either version 3 or (at your option) any later
version. See the file LICENSE.md for details.
"""


alphabet = "abcdefghijklmnopqrstuvwxyz"


def rot_decode(s: str, num_shift: int) -> str:
    """Return a string where S has had each character shifted forward by NUM_SHIFT
    positions, looping around at the end of the alphabet. If NUM_SHIFT is 13, it
    applies the classic ROT13 algorithm.
    """
    assert 0 <= num_shift <= 26, "ERROR! NUM_SHIFT must be between 0 and 26!"
    transposed = alphabet[num_shift:] + alphabet[:num_shift]
    trans_table = str.maketrans(alphabet, transposed)
    return s.translate(trans_table)


def rot_decode_exhaustively(s: str):
    """Apply all 26 possible text rotations to the string S.
    """
    print(f"Brute-forcing the coded string {s}...\n\n")
    for i in range(26):
        print(f"Trying value {i}:\n\n{rot_decode(s.lower(), i)}\n\n\n")


if __name__ == "__main__":
    import sys
    if 0 > len(sys.argv) > 2:
        print("Wrap the entire phrase you're trying to decode in quotation marks, please!")
        sys.exit(1)

    rot_decode_exhaustively(sys.argv[1])
