#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Implementation of the guts of solve_Africa_map.py, a script to find
solutions to the "Africa" puzzle in beta version 1.62 of Greg Boettcher's
"Nothing But Mazes" (2019). Moved to a separate file so it can be Cythonized,
because running under pure Python, it has taken 200 days' worth of processor
time to explore not quite 88 billion pathways.

This script is copyright 2019 by Patrick Mooney. You may use it for any purpose
whatsoever provided that this copyright notice, unchanged, accompanies the
script.
"""
