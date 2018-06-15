#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A program to extract Infocom z-code files from Apple II disk images. Inspired
by Steve Hugg's AP2IFC, but rewritten in a modern language that should make it
accessible to anyone, not just people running DOS. It also contains a few
additional enhancements.

Usage:
    
    ./ap2zc.py INPUT_FILE

The ap2zc program is part of a developing suite of interactive fiction-related
utilities. It is copyright 2018 by Patrick Mooney. It is released under the GNU
GPL, either version 3 or (at your option) any later version. See the file 
LICENSE.MD for details.

"""

import os, sys


versionLoc  = 0x3000
numWordsLoc = 0x301a

numSects  =  31 * 16
secTbl  = (0, 13, 11, 9, 7, 5, 3, 1, 14, 12, 10, 8, 6, 4, 2, 15)
wordsPerSect = (128, 128, 128, 64, 64) + (64, 64, 64)               # Note that the last three are purely conjectural


def print_usage(exit_code=0):
    print(__doc__)
    sys.exit(exit_code)


def do_extract(inputfile):
    print("opening %s ..." % inputfile, end=" ")
    with open(inputfile, 'rb') as source:
        source.seek(versionLoc)
        print("... success.")
        ver = ord(source.read(1))
        if ver not in range(1,9):
            print("Error: Z-code version in file is apparently %d; is disk image corrupt?")
            print("Quitting ...\n\n")
            sys.exit(2)
        else:
            print("Found version %d Z-code file" % ver)                   	# probably won't work with v6+ files, but none were ever released for Apple II, I think.
        outputfile = os.path.splitext(inputfile)[0] + ".z%d" % ver
        print("Opening output file %s ..." % outputfile, end=" ")
        with open(outputfile, 'wb') as dest:
            print("... success.")
            source.seek(numWordsLoc)
            numWords = int.from_bytes(source.read(2), byteorder="big")       # Decode the embedded C number.
            numChunks = numWords // wordsPerSect[ver]
            print("Copying ...", end=" ")
            for i in range(0, 1 + numChunks):
                track = i // 16
                sector = secTbl[i % 16]
                source.seek(versionLoc + (track * 16 + sector) * 256)
                dest.write(source.read(256))
            print("... finished.")


if __name__ == "__main__":
    if len(sys.argv) == 2:                                      # Reminder: the executable name is index zero
        if sys.argv[0].lower().strip() in ["--help", "-h"]:
            print_usage()
        else:
            do_extract(sys.argv[1])
    else:
        print_usage(1)
