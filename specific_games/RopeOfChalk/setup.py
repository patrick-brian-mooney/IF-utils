#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick distutils script to build the cealdhame.pyx Cython code into a Python
extension module.
"""

from setuptools import setup
from Cython.Build import cythonize

setup(ext_modules=cythonize("cealdhame.pyx"))
