#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actually run the explore_possibilities code, setting up and seeking successful
paths through All Things Devours.See the explore_possibilities documentation
for more details.  This file is just a wrapper that runs the
Cythonized code in that module.
"""


import sys

import pyximport; pyximport.install()

import explore_possibilities as ep


if __name__ == "__main__":
    print(f"Starting up! Running under Python {sys.version_info}")
    ep.main()
