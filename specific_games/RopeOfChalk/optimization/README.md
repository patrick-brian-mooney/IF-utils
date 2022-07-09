# `Optimization/`

Output of various versions of the script, including timing information, as the script is converted from pure-Python to Cython. These occur in both plain-text format and <a rel="muse" href="https://asciinema.org/">ASCIInema</a> JSON (as `.cast` files). ASCIInama `.cast` files are recorded with a terminal size of 150&nbsp;x&nbsp;30.

All timing runs were performed on the same computer using Python 3.9 under x64 Linux Mint 20.1.

The standard invocation of the script for timing purposes is something very close to `time python3.9 -u run_cealdhame.py 2>&1 | tee optimization/pure-python.txt`, with the filenames adjusted as necessary.

## `pure-python.txt`, `pure-python.cast`
The pure-Python version of `cealdhame.py`, as it occurs in [commit 0a329421d5675de3606f9079cf0e9e32102074d7](https://github.com/patrick-brian-mooney/IF-utils/commit/0a329421d5675de3606f9079cf0e9e32102074d7).

## `simply-compiled.txt`, `simply-compiled.cast`
The pure-Python version of `cealdhame.py`, renamed without other changes to `cealdhame.pyx` and compiled with Cython to see how that improves its performance. (Initial figures from the first hour of both runs suggest an improvement of approximately 34%.) Available in [commit a9d2a5f4e91fe850283bbe5db2518efdcf98c098](https://github.com/patrick-brian-mooney/IF-utils/commit/a9d2a5f4e91fe850283bbe5db2518efdcf98c098).

## `tuned-cython.txt`, `tuned_cython.cast`
The pure-Python version with most functions converted to Cython C-type function, plus static type annotations and common functions inlined. Speed over the first fifteen minutes suggests it's about 50% faster than the version being profiled in the `simply-compiled` logs. (Or about 650 times faster than the very slow version in `old/cealdhame_very_slow.pyx`.) This is the version in [commit 5cd99d6a7999b6329d5385a2ba3f56fa23e14b7a](https://github.com/patrick-brian-mooney/IF-utils/commit/5cd99d6a7999b6329d5385a2ba3f56fa23e14b7a).


<p>&nbsp;</p>
<footer>This file last updated 8 Jul 2022.</footer>

