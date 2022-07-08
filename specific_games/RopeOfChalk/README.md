# RopeOfChalk

A Cythonized script to explore the very tangential question "Can you pass through each roadway in the sub-map of Cealdhame exactly once?" in Ryan Veeder's [A Rope of Chalk](https://ifdb.tads.org/viewgame?id=l4ziasab1x8t799c), from IFComp 2020.

## `run_cealdhame.py`
A stub unit that runs the Cython code in `cealdhame.pyx`.

## `cealdhame.pyx`
The actual implementation in Cython of the algorithm searching the possiblity space.

## `optimization/`
Folder full of output from various versions of `cealdhame.py[x]`, as it is translated from pure-Python to Cython and then optimized, and (very brief) notes on the process.

## `old/`
Versions of `cealdhame.py[x]` that have been abandoned as unsupportably slow approaches.


<p>&nbsp;</p>
<footer>This file last updated 7 Jul 2022.</footer>
