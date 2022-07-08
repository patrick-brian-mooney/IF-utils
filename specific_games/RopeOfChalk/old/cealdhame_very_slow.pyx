#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#cython: language_level=3
"""A quick hack to explore a tangential issue in Ryan Veeder's A Rope of Chalk
(an IFComp 2020 game). The question is not essential to the game but caught my
attention anyway: Is it possible to move through the realm of Cealdhame, a
sub-game in Act IV of the drama, by traversing each pathway exactly once?

The program has the additional constraint that a "successful" path, in
addition to the "traverse each edge exactly once" criterion, must terminate on
an "outside square", one from which one can exit the map directly without
stepping back into another location in the same map.

The layout of the map is a hexagonal (no N/S connections) layout that looks
like this:

01  02  03  04  05
  06  07  08  09
10  11  12  13  14
  15  16  17  18
19  20  21  22  23

... where each numbered space is connected to other spaces E/W of it, plus
those spaces NE, NW, SE, SW.

Again, the game makes no effort to get the player to notice this question, but
I'm curious anyway.

This quick Python 3.X hack is copyright 2020 by Patrick Mooney. It is part of
Patrick Mooney's IF Utils, all of which are released under the GPL, either
version 3 or, at your option, any later version. See the file LICENSE.md for
details.
"""

#FIXME: Important! This is known to grow slow quite quickly. I'll take a look at it as soon as I can, but that's not this week.


import bz2
import collections
import datetime
import pickle

from pathlib import Path

import sys
import time
import typing


pathways = {
    1:  (2, 6),
    2:  (1, 6, 7, 3),
    3:  (2, 7, 8, 4),
    4:  (3, 8, 9, 5),
    5:  (4, 9),
    6:  (1, 2, 7, 11, 10),
    7:  (2, 3, 8, 12, 11, 6),
    8:  (7, 3, 4, 9, 13, 12),
    9:  (8, 4, 5, 14, 13),
    10: (6, 11, 15),
    11: (10, 6, 7, 12, 15, 16),
    12: (11, 7, 8, 13, 17, 16),
    13: (12, 8, 9, 14, 18, 17),
    14: (13, 9, 18),
    15: (10, 11, 16, 20, 19),
    16: (15, 11, 12, 17, 21, 20),
    17: (16, 12, 13, 18, 22, 21),
    18: (13, 14, 23, 22, 17),
    19: (15, 20),
    20: (19, 15, 16, 21),
    21: (20, 16, 17, 22),
    22: (21, 17, 18, 23),
    23: (18, 22),
}

cdef set all_paths = set()                                                      # Will be expanded later, in initialization routines.

cdef set border_locations = {1, 2, 3, 4, 5, 9, 14, 18, 23, 22, 21, 20, 19, 15, 10, 6}
cdef int checkpoint_interval = 8            # How often do we checkpoint save data? E.g., 8 means "if the length of the path is a multiple of 8, or is less than 8"

cdef list solutions_found = list()
cdef list paths_exhausted = list(),
cdef int failures = 0
cdef float run_time = 0.0,                                                      # in seconds.
last_save = datetime.datetime(1980, 1, 1, 0, 0, 0)                              # Force a discretionary save to happen soon.


run_start = datetime.datetime.now()

script_location = Path("/home/patrick/Documents/programming/python_projects/IF utils/specific_games/RopeOfChalk")
progress_data_path = script_location / 'cealdhame_progress.pkl'
cdef int save_interval = 15 * 60                                                # Minimum number of seconds between "discretionary" saves.


# Utility functions.
cdef float total_time():
    """Get the total time since the run started.
    """
    return (datetime.datetime.now() - run_start).total_seconds()


def prune_exhausted_paths(list_of_paths: typing.List[typing.Tuple[int, int]]) -> typing.List[typing.Tuple[int, int]]:
    """Prune redundant paths from LIST_OF_PATHS. A path is REDUNDANT if it
    represents a path-beginning that will never be reached because a shorter path-
    beginning that is also on the list will nip that longer path before it's
    reached. For instance, if [a, b, c, d] is on the list, then it makes the paths
    [a, b, c, d, g], [a, b, c, d, v], and any other paths beginning
    [a, b, c, d, ...] redundant.
    """
    cdef:
        list ret = list()
        tuple p
        int prune_len
        bint prune

    for p in list_of_paths:
        prune = False
        for prune_len in range(1, len(p) - checkpoint_interval):
            if p[:-prune_len] in list_of_paths:
                prune = True
                break
        if not prune:
            ret.append(p)

    if len(ret) < len(list_of_paths):
        print(f" ... pruned {len(list_of_paths) - len(ret)} redundant entries!")

    return ret


cdef void save_progress(bint discretionary=False) except *:
    """Save the progress data so that we can restore it on subsequent runs. If
    DISCRETIONARY is True, the routine skips the save if we've performed a save
    recently, i.e. within the last SAVE_INTERVAL seconds.
    """
    global solutions_found, paths_exhausted, failures, last_save
    start_time = time.monotonic()

    if discretionary:
        if (datetime.datetime.now() - last_save).total_seconds() < save_interval:
            return

    paths_exhausted = prune_exhausted_paths(paths_exhausted)
    progress_data = {
        'solutions_found': solutions_found,
        'paths_exhausted': paths_exhausted,
        'failures': failures,
        'run_time': total_time(),
        }
    with bz2.open(progress_data_path, mode='wb') as progress_data_file:
        pickle.dump(progress_data, progress_data_file, protocol=-1)

    print(f"Saved progress in {time.monotonic() - start_time} seconds!")
    last_save = datetime.datetime.now()


cdef void restore_progress() except *:
    """Restore progress data from the progress file, if there is one.
    """
    global solutions_found, paths_exhausted, failures, run_start, last_save

    if not progress_data_path.exists():  # Nothing to restore!
        return
    if not progress_data_path.is_file():
        print(f"WARNING: filesystem object at {progress_data_path} is not a regular file! Weirdness with progress data may result.")

    with open(progress_data_path, mode='rb') as progress_data_file:
        progress_data = pickle.load(progress_data_file)
    
    solutions_found, paths_exhausted, failures = progress_data['solutions_found'], progress_data['paths_exhausted'], progress_data['failures']

    last_save = datetime.datetime(1980, 1, 1, 0, 0, 0)                  # Force the next discretionary save to occur.
    run_start = datetime.datetime.now() - datetime.timedelta(seconds=progress_data['run_time'])
    print("Successfully restored previously made progress!")


def _flatten_list(l: typing.abc.Iterable) -> typing.Generator[int, None, None]:
    """Takes an iterable, L, which may contain other iterables, and returns a generator
    that produces the individual elements that comprise the original iterable L.
    No matter how many levels deep the iterability of L goes, the resulting
    generator will return the elements of those iterables, rather than the
    iterables themselves. So _flatten_list([1, 2, [3, 4, [5, 6, 7], [8, 9]]]) yields
    1, 2, 3, 4, 5, 6, 7, 8, 9, one item at a time.

    The explanation above is an oversimplification: this code means "list and tuple"
    by "iterable" in the explanation above, not other types of iterables. Notably,
    it does not return the individual characters comprising a string, but simply the
    whole string at once, as if strings were not iterable at all.
    """
    for elem in l:
        if isinstance(elem, collections.abc.Iterable) and not isinstance(elem, (str, bytes)):
            yield from elem
        else:
            yield elem


# Startup checks and pre-computation.
cdef void validate_data() except *:
    """Perform basic sanity checks to detect data entry errors in the data above.
    """
    for start in pathways:
        assert start in set(_flatten_list(pathways.values()))       # Ensure at least one pathway leads to this data.
        for end in pathways[start]:
            try:
                assert start in pathways[end]                       # Ensure path is reciprocal
            except AssertionError:
                print(f"Path {start} to {end} is one-way!")


cdef void compute_paths() except *:
    """Set up the global variable ALL_PATHS.
    """
    global all_paths
    for start in pathways:
        for end in pathways[start]:
            all_paths.add(tuple(sorted([start, end])))


cdef void set_up() except *:
    """Perform setup tests.
    """
    validate_data()
    compute_paths()
    restore_progress()


cdef void bump_failures() except *:
    """Increase the failure count. Print a notice if the number is right to do so.
    """
    global failures, solutions_found

    failures += 1
    if (failures % 100000) == 0:
        print(f"{failures / 1000000.0} million failures so far (and {len(solutions_found)} successes!) in {total_time() / 3600} hours")


cdef void handle_discretionary_checkpoint(tuple steps_taken):
    global paths_exhausted
    if ((len(steps_taken) % checkpoint_interval) == 0) or (len(steps_taken) < checkpoint_interval):
        paths_exhausted.append(steps_taken)
        save_progress(True)
        sys.exit()      # FIXME! This is only here for debugging purposes, to force the code to quit when we're profiling!


# Actual solution to the problem.
cdef void solve_from(int current_location,
                     tuple steps_taken) except *:
    """Given CURRENT_LOCATION, our current location, and STEPS_TAKEN, a list of
    previous moves, iterate over all possible remaining moves, i.e. those that begin
    in our current location and have not yet been taken, iterate over all possible
    moves. Calls itself repeatedly to explore every possible path, terminating a
    path's investigation when it dead-ends, and printing solutions to STDOUT.
    """
    cdef:
        int previous_checkpoint_length
        tuple remaining_paths, possible_moves
        tuple m

    global paths_exhausted, solutions_found

    previous_checkpoint_length = checkpoint_interval * (len(steps_taken) // checkpoint_interval)
    if steps_taken[:previous_checkpoint_length] in paths_exhausted:    # This path has already been explored. Don't go down it again.
        return

    remaining_paths = tuple(p for p in all_paths if p not in steps_taken)
    if (not remaining_paths):                                           # If we've hit every pathway ...
        if (current_location in border_locations):                      # Are we in a border location?
            solutions_found.append(steps_taken)
            print(f"Solution # {solutions_found: 5}: {steps_taken}")
            save_progress()
        else:
            bump_failures()
            handle_discretionary_checkpoint(steps_taken)                                                 
        return

    possible_moves = tuple(p for p in remaining_paths if current_location in p)
    if (not possible_moves):                                            # Of the untrod paths, are any adjacent to us?
        bump_failures()
        handle_discretionary_checkpoint(steps_taken)
        return
    for m in sorted(possible_moves):                                    # If so, tread them, sequentially and recursively.
        new_location = [move for move in m if move != current_location][0]
        solve_from(new_location, steps_taken + (m,))


cdef void wrap_up():
    print(f"Run finished!\n{len(solutions_found)} solutions found!\n{failures} dead-end paths!")


def solve() -> None:
    set_up()
    solve_from(12, tuple())
    wrap_up()
