#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decode hints for Wade Clark's Leadlight Gamma, and serve as a framework for
decoding hints for other games that have Scott Adams-style numeric hints,
where the hint is "encoded" by substituting a number for each word in the hint.
The hint itself is a comma-separated list of numbers, and the hint is protected
from accidental reading by the need to look up the word being expressed by each
number in a comma-separated list.

This script is part of Patrick Mooney's collection of interactive-fiction
related utilities, and is copyright 2023 by Patrick Mooney. It is released
under the GPL, either version 3 or (at your option) any later version. See the
file LICENSE for a copy of this license.
"""

import typing



hints_text = """1 PILLAR
2 THE
3 FOOT
4 KILL
5 BALLET
6 DRAFT
7 GLOVES
8 USE
9 ROOM
10 CUT
11 CLOSE
12 ARE
13 CONSIDER
14 HIDING
15 YOU
16 IT
17 DEAL
18 A
19 IPOD
20 HIDE
21 CAT
22 TITLE
23 WEAR
24 VINES
25 WARDROBE
26 OR
27 CHOSE
28 SLIPPERS
29 NEED
30 IN
31 SMASH
32 WELCOME
33 BEHIND
34 PLACE
35 HER
36 CHINA
37 YOUR
38 SONG
39 GYM
40 SHEARS
41 WINDOW
42 ROPE
43 LOOK
44 MONEY
45 YOU
46 BALCONY
47 RIBBON
48 104
49 TO
50 NARELLE
51 WITH
52 OTHER
53 PIN
54 SOMETHING
55 CAN
56 WEAPON
57 AND
58 FIREPLACE
59 TREE
60 AS
61 KEY
62 HAIRPIN
63 EXAMINE
64 IS
65 LISTEN
66 CREST
67 OF
68 PUSH
69 WIELD
70 SOME
71 105
72 UNLOCK
73 AGAIN
74 GIVE
75 MORE
76 TROPHY
77 SHE
78 BELL
79 INSIDE
80 KNEW
81 GLASSES
82 ON
83 FOR
84 TIE
85 MAT
86 CASE
87 EDGE
88 SAFE
89 MAGLITE
90 LAB
91 VISIT
92 FOUNDER
93 PASSWORD
94 OFF
95 3D
96 WITCH
97 FOUNTAIN
98 OPENS
99 ONE
100 VULNERABLE
101 LOCKET
102 GARDENER
103 HAS
104 LUCINDA
"""

def set_up(raw_hints=hints_text) -> typing.Dict[int, str]:
    """Parse the relevant hints text into a dictionary mapping integers onto words.
    Does some elementary error-checking along the way.
    """
    hints_lines = [l.strip() for l in raw_hints.split('\n') if l.strip()]
    hints_list = [tuple(elem.strip() for elem in i.split() if elem.strip()) for i in hints_lines]
    return {int(i[0]): i[1] for i in hints_list}


if __name__ == "__main__":
    key = set_up()
    print("Successfully decoded key; running ...")
    print("Press Ctrl-C to qui\n\n")
    while True:
        l = input("Enter comma-separated list of numbers to decode: ")
        if l:
            print(" ".join([key[int(num)] for num in [item.strip() for item in l.strip().split(',')]]))
