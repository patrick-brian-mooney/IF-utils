#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A quick hack to rename all files in the current directory so that the filename
extensions are all lowercase. agility expects this, and under Linux, filename
case does matter. When Agility was originally written, AGT games were typically
extracted from .zip archives on the command line under Linux, and lowercase
filename extensions were easy to ensure with the -L option to `unzip`; but this
is less easy to ensure in a graphically driven Linux, so this utility just
lowercases all filename extensions in the directory, first checking to make
sure that this won't clobber any existing files.

Usage:
    all_lowercase_names.py [dirname]

If DIRNAME is not specified, the current working directory is used.

Alternately, -h or --help may be specified to print this message.
"""


import os, shlex, sys
from pathlib import Path


def transform_case(p: Path) -> Path:
    """Returns a modified version of path P in which the filename's suffix is entirely
    in lowercase."""
    suffix = os.path.splitext(p)[1].lower()
    return p.with_suffix(suffix)


if len(sys.argv) > 1:
    if sys.argv[1].lower() in ['--help', '-h']:
        print(__doc__)
        sys.exit(0)
    elif len(sys.argv) > 2:
        print(__doc__)
        sys.exit(1)
    else:
        working_dir = Path(sys.argv[1])
else:
    working_dir = Path(os.getcwd())

for f in working_dir.glob("*"):
    lower_f = transform_case(f)
    if not lower_f.samefile(f):
        assert not lower_f.exists(), "ERROR! Lowercasing all names would overwrite file %s!" % shlex.quote(str(f))

print("About to process all files in directory %s ..." % shlex.quote(f))

for f in working_dir.glob("*"):
    lower_f = transform_case(f)
    if not f.samefile(lower_f):
        f.rename(lower_f)

print ("Done!\n")


