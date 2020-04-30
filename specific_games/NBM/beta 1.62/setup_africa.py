#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Setup.py-type script to compile africa_guts.py into a Cython extension.

This script is copyright 2020 by Patrick Mooney. You may use it for any purpose
whatsoever provided that this copyright notice, unchanged, accompanies the
script.
"""


from setuptools import setup
from Cython.Build import cythonize

setup(
    name='solve_Africa_map program',
    ext_modules=cythonize("africa_guts.pyx"),
    zip_safe=False,
)
