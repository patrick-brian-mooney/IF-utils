"""A re-implementation of Nick Montfort's Amazing Quest, an IFComp entry, in Python.

Thanks to Ant for the annotated code at
https://ahopeful.wordpress.com/2020/10/04/ifcomp-2020-amazing-quest-nick-montfort-c64-basic/.

This is a more-of-less direct translation of the original, including the logic
that's motivated by the limitations of the BASIC language, into Python. A more
Pythonic implementation is available in reimplementation.py.

Needs to be run from a terminal.
"""

import math, shutil, random, time



data = [            # DATA statements are spread throughout the program, but collected here.
    5, 'neak up and raid', 'peak plainly', 'acrifice to the gods',                                                          # Line 3
    'eek out help',                                                                                                         # Line 4
    'end gifts', 6, 'alight on', 'are blown to', 'behold', 'detect', 'find', 'land on', 2, 'a', 'a', 18, 'brutal',          # Line 7
    'dark', 'dim', 'diverse', 'dry', 'dusty', 'fine', 'fortified', 'hexagonal', 'huge', 'luminous', 'pious', 'proud',       # Line 8
    'retrograde', 'spare', 'tiny', 'uniform', 'wet', 11, 'area', 'capital', 'moon', 'land', 'palace', 'settlement',         # Line 9
    'port', 'city', 'outpost', 'planet', 'stronghold',                                                                      # Line 11
]
_next_data_index = 0


# Utility functions: re-implementation of BASIC primitives.

def READ():
    """BASIC's READ statement is such a weird primitive."""
    global _next_data_index
    try:
        return data[_next_data_index]
    finally:
        _next_data_index += 1


def get_terminal_width():
    """Get the current terminal width."""
    ret, _ = shutil.get_terminal_size()
    if ret <= 0:
        return 40
    return ret


# Line 0 in original! Setting up global data.
d = 11

# POKE53280,d       # set background frame color to dark gray.
# POKE53281,d       # also set background color to same dark gray, so that there is no visible frame.

print('\n\n' + (" " * round((get_terminal_width() - 13) / 2)) + "AMAZING QUEST\n\n")
print("The gods grant victory.")


# Line 1 in original! Setting up global data.
a = dict()                          # In BASIC, DIM a$(99). Using int-indexed DICTs for BASIC arrays works fine here.
m = dict()                          # Montfort doesn't DIM this, meaning it's no more than 11 elements.

j=-1
for i in range(0, 5):
    m[i] = READ()                               # Or, in BASIC, READ m(i)
    for k in range (1, 1 + m[i]):
        a[j+k] = READ()
    j = j + k

print("Now to home!")


# Line 2 in original! Re-implement the GOTO logic from BASIC as a WHILE loop in Python, moving the condition here from line 6.

while d > 0:

    print('\nYou', end='')              # PRINT"{down}You";         PRINT statements ending with a semicolon don't have an implicit carriage return at the end.
    j = 5                               # adjustment from the BASIC value. different indexing?
    for i in range(1, 5):
        print(' ' + a[j + int(random.random() * m[i])], end='')
        j = j + m[i]
    print(".")
    print('S' + a[random.randint(0, 4)], end='')


    # Line 3 in original!

    z = input("-Y/n? ")
    time.sleep(2 * random.random())             # This is similar in effect but implemented substantially differently from the original.


    # Line 4 in original!

    r = random.random()
    if r < 0.2:
        print("Attacked" + ", a ship lost!")     # here is the line that was buggy in the original version


    # Line 5 in original!

    elif r < 0.4:
        print("Well-you see an amazing " + random.choice(["sea.", "sky.", "sun."]))


    # Line 6 in original!

    else:
        d -= 1
        print("Yes! You win " + random.choice(["jewels.", "cattle.", "bread."]))


# Lines 7-9 in original are only data statements!


# Line 10 in original! (reached only after D has been sufficiently decremented)

print("\nAt last, the battered shuttle brings you\nalone home to family, hearth, rest.")


# Line 11 in original is a data statement, followed by this comment!

# REMix! (c) 2020 nick montfort, nickm.com

