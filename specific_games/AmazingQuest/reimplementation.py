"""A re-implementation of Nick Montfort's Amazing Quest, an IFComp entry, in Python.

Thanks to Ant for the annotated code at https://ahopeful.wordpress.com/2020/10/04/ifcomp-2020-amazing-quest-nick-montfort-c64-basic/.

Needs to be run from a terminal.
"""

import shutil, random, time


actions = ['Sneak up and raid', 'Speak plainly', 'Sacrifice to the gods', 'Seek out help', 'Send gifts',]
motions = ['alight on', 'are blown to', 'behold', 'detect', 'find', 'land on',]
articles = ['a', 'a',]
adjectives = [ 'brutal', 'dark', 'dim', 'diverse', 'dry', 'dusty', 'fine', 'fortified', 'hexagonal', 'huge', 'luminous', 'pious', 'proud', 'retrograde', 'spare', 'tiny', 'uniform', 'wet',]
places = ['area', 'capital', 'moon', 'land', 'palace', 'settlement', 'port', 'city', 'outpost', 'planet', 'stronghold',]


# Utility functions.
def get_terminal_width():
    """Get the current terminal width."""
    ret, _ = shutil.get_terminal_size()
    if ret <= 0:
        return 40
    return ret


# Line 0 in original! (The BASIC mostly sets up global data that's been done more cleanly above.)
travails_remaining = 11

# POKE53280,d       # set background frame color to dark gray.
# POKE53281,d       # also set background color to same dark gray, so that there is no visible frame.

print('\n\n' + (" " * round((get_terminal_width() - 13) / 2)) + "AMAZING QUEST\n\n")
print("The gods grant victory.")


# Line 1 in original! (The BASIC mostly sets up global data that's been done more cleanly without READ/DATA statements.
print("Now to home!")


while travails_remaining > 0:
    # Line 2 in original! Re-implement the GOTO logic from BASIC as a WHILE loop in Python, moving the condition above from line 6.
    print('\nYou %s %s %s %s.' % (random.choice(motions), random.choice(articles), random.choice(adjectives), random.choice(places)))
    print(random.choice(actions), end='')

    # Line 3 in original!
    _ = input("-Y/n? ")
    time.sleep(2 * random.random())             # This is similar in effect but implemented substantially differently from the original.

    # Line 4 in original!
    r = random.random()
    if r < 0.2:
        print("Attacked, a ship lost!")         # here is the line that was buggy in the original version
    # Line 5 in original!
    elif r < 0.4:
        print("Well-you see an amazing %s." % random.choice(["sea", "sky", "sun"]))
    # Line 6 in original!
    else:
        travails_remaining -= 1
        print("Yes! You win %s." % random.choice(["jewels", "cattle", "bread"]))

# Lines 7-9 in original are only data statements!
# Line 10 in original! (reached only after D has been sufficiently decremented and the WHILE loop has ended.)
print("\nAt last, the battered shuttle brings you\nalone home to family, hearth, rest.")

# Line 11 in original is a data statement, followed by this comment!
# REMix! (c) 2020 nick montfort, nickm.com

