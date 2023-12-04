#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actually run the explore_possibilities code, setting up and seeking successful
paths through All Things Devours. See the explore_possibilities documentation
for more details. This file is just a wrapper that sets up and runs the code in
that module.

This script is part of Patrick Mooney's collection of interactive-fiction
related utilities, and is copyright 2023 by Patrick Mooney. It is released
under the GPL, either version 3 or (at your option) any later version. See the
file LICENSE for a copy of this license.
"""


import os

from pathlib import Path

import pprint
import sys


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
print(f"Running under: {sys.version}\nsys.path is:")
pprint.pprint(f"{sys.path}\n\n\n\n")


import pyximport        # http://cython.org
pyximport.install(build_dir=Path("/home/patrick/Documents/programming/python_projects/IF utils/specific_games/ATD/build"))


import explore_possibilities as ep


if __name__ == "__main__":
    print(f"Starting up! Running under Python {sys.version_info}")
    ep.main()
