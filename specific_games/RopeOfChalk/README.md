A Cythonized script to explore the very tangential question "Can you pass through each roadway in the sub-map of Cealdhame exactly once" in Ryan Veeder's [A Rope of Chalk](https://ifdb.tads.org/viewgame?id=l4ziasab1x8t799c), from IFComp 2020.

## `run_cealdhame.py`
A stub unit that runs the Cython code in `cealdhame.pyx`.

## `cealdhame.pyx`
The actual implementation in Cython of the algorithm searching the possiblity space.

**Note:** This is known to grow quite slow quite quickly. I'll take a look at what's making it slow, but it won't be this week.

<footer>This file last updated 7 Jul 2022.</footer>
