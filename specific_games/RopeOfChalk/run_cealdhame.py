#!/usr/bin/env python3
"""A quick hack to explore a tangential issue in Ryan Veeder's A Rope of Chalk
(an IFComp 2020 game). See the documentation for cealdhame.pyx for more
information.

This file is just a harness which runs the code in cealdhame.pyx, which is
written in Cython for a huge speed boost. Requires Cython, of course.

This code is part of Patrick Mooney's IF Utils. Like the rest of that code, it
is released under the GNU GPL, either version 3 or (at your option) any other
version. See the file LICENSE.md for details.
"""

import pyximport; pyximport.install()

import cealdhame

if __name__ == "__main__":
    print("Beginning run!")
    cealdhame.set_up()
    cealdhame.solve_from(12)
    cealdhame.wrap_up()