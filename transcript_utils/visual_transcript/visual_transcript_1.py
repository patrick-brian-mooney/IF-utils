#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Part of a series of scripts to help process visual screencasts of IF that cannot
produce a regular textual transcript, for whatever reason. (Often, this is
because the IF is quite old, from prior to the expectation that a transcript is
something a player should necessarily be able to create.) THIS script takes one
or more video files and converts them into still images. It should probably
generally be followed with visual_transcript_2.py, which starts the process of
removing duplicate frames.

This is a pretty quick hack, but works well enough for my purposes.

This program is part of a group of interactive fiction-related utilities by
Patrick Mooney. It is copyright 2018. It is released under the GNU GPL, either
version 3 or (at your option) any later version. See the file LICENSE.md for
details.
"""


import glob, os, time, shlex, subprocess


input_files = "/home/patrick/games/IF/to play/DEADHOTEL/transcripts/ReactOS.webm"       # A pattern to be matched by glob.glob.
output_dir = '/home/patrick/games/IF/to play/DEADHOTEL/transcripts/out'       # Where the output directories are created.


if __name__ == "__main__":
    for m in [os.path.abspath(mov) for mov in sorted(glob.glob(input_files))]:
        try:
            print("Processing " + m)
            olddir = os.getcwd()
            newdir = os.path.join(output_dir, os.path.basename(m).rstrip('.avi').rstrip('.webm').lstrip('hobbit_*'))
            os.mkdir(newdir)
            os.chdir(newdir)
            subprocess.call("ffmpeg -i " + shlex.quote(m) + " thumb%07d.png", shell=True)
        except BaseException as err:
            print("ERROR! The system said: %s" % err)
            time.sleep(1.5)
        finally:
           os.chdir(olddir)

