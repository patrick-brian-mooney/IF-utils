#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#cython: language_level=3
"""A quick hack to explore a tangential issue in Ryan Veeder's A Rope of Chalk
(an IFComp 2020 game). The question is not essential to the game but caught my
attention anyway: Is it possible to move through the realm of Cealdhame, a
sub-game in Act IV of the drama, by traversing each pathway exactly once?

The program has the additional constraint that a computed path, in addition to
the "traverse each edge exactly once" criterion, a "successful" path must
terminate on an "outside square", one from which one can exit the map directly
without stepping back into another location in the same map.

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

This quick Python 3.X hack is copyright 2020-22 by Patrick Mooney. It is part
of Patrick Mooney's IF Utils, all of which are released under the GPL, either
version 3 or, at your option, any later version. See the file LICENSE.md for
details.
"""


import bz2
import collections

from pathlib import Path

import pickle
import string
import time


cdef set exhausted_paths = set()                                # of strings
cdef dict successful_paths = dict()                             # mapping movement-strings to list of movement-tuples
cdef int failures = 0

cdef float last_save = time.monotonic()
cdef float run_start = time.monotonic()

progress_data_path = Path(__file__).parent / 'cealdhame_progress.dat'
cdef int save_interval = 15 * 60                                # in seconds
cdef int checkpoint_interval = 8    # How often do we checkpoint save data? E.g., 8 means "if the length of the path is a multiple of 8, or is less than 8"


# Basic data: which spaces, by number, can you move to from each space?
cdef dict pathways = {
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

cdef set border_locations = {1, 2, 3, 4, 5, 9, 14, 18, 23, 22, 21, 20, 19, 15, 10, 6}


# Now, massage the data into an easier-to-deal-with form by creating a set of 2-tuples representing the various paths.
cdef set all_paths = set()


def expand_paths():
    cdef:
        int k, dest
        tuple v

    global all_paths

    for k, v in pathways.items():
        for dest in v:
            all_paths.add(tuple(sorted((k, dest))))


expand_paths()


# Now, some mappings between the paths and the labels that will be used to represent them.
# We match each path to an ASCII letter; there are more of those than there are possible pathways in this problem.
path_to_label = dict(zip(sorted(all_paths), sorted(string.ascii_letters)))
label_to_path = {v: k for k, v in path_to_label.items()}


# Some utility functions.
cdef inline float total_run_time() except *:
    """Get the total time since the run started.
    """
    return time.monotonic() - run_start


cdef inline float time_since_last_save():
    """Return the number of seconds since a save last happened."""
    return time.monotonic() - last_save


# utilities to save and restore progress-status data.
cdef void do_save() except *:
    """Save the data necessary to preserve the global state so that we can start from
    this place on the next run.
    """
    cdef dict data
    global last_save

    data = {
        'exhausted': exhausted_paths,
        'successful': successful_paths,
        'failures': failures,
        'runtime': total_run_time(),
    }

    with bz2.open(progress_data_path, mode='wb') as progress_file:
        pickle.dump(data, progress_file, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"  ... saved progress data to {progress_data_path.resolve()}, after accumulating {time_since_last_save() / 60.0} minutes' worth of new data!")
    last_save = time.monotonic()


def do_restore_data():
    """Restore the state data to the global variables tracking it.
    """
    cdef dict data
    global exhausted_paths, successful_paths, failures, run_start

    try:
        with bz2.open(progress_data_path, mode='rb') as progress_file:
            data = pickle.load(progress_file)
    except IOError as errrr:
        print(f"\nWARNING! Progress data not found, or unreadable! The system said: {errrr}")
        print("Restarting from scratch ...\n\n")
        return

    exhausted_paths = data['exhausted']
    successful_paths = data['successful']
    failures = data['failures']
    run_start = time.monotonic() - data['runtime']


cdef inline void prune_and_save(str steps_taken,
                                bint discretionary = True) except *:
    """Checks to see whether the global list of EXHAUSTED_PATHS needs to be pruned,
    based on the list of STEPS_TAKEN. If the length of STEPS_TAKEN is (a) less than
    the global constant CHECKPOINT_INTERVAL, or (b) a multiple of it, then the
    global list of exhausted paths needs to be pruned. Pruning takes time, but helps
    to keep the "is this path exhausted?" check run by is_exhausted() running
    quickly; these concerns are balanced against each other by adjusting the value
    of CHECKPOINT_INTERVAL.

    STEPS_TAKEN is the string showing steps taken so far.

    If DISCRETIONARY is False, the "check" step is skipped, and pruning and saving
    definitely happens; this is sometimes handy when saving.
    """
    cdef:
        set pruned
        str exh_p, known_key
    global exhausted_paths

    if discretionary:
        if not (len(steps_taken) <= checkpoint_interval):
            if not ((len(steps_taken) % checkpoint_interval) == 0):
                return
        if not time_since_last_save() >= save_interval:
            return

    pruned = set()
    for exh_p in sorted(sorted(exhausted_paths), key=len):
        for known_key in pruned:
            if exh_p.startswith(known_key):
                break
        else:
            pruned.add(exh_p)
    exhausted_paths = pruned
    do_save()


cdef inline bint is_exhausted(str path) except *:
    """Check if PATH is excluded from exploration on the basis of being already fully
    explored, or else a path that depends on having been already fully explored.

    This can probably be optimized further by taking CHECKPOINT_INTERVAL into
    account.
    """
    cdef int i

    if path in exhausted_paths:
        return True
    for i in range(len(path) - 1):
        if path[:-(i+1)] in exhausted_paths:
            return True
    return False


cdef inline bint is_victory(str path) except *:                  
    """Check to see if (a) we've hit every path, and (b) our last step finished on an
    outside square. Also perform the basic sanity check of making sure we didn't
    traverse any path twice. If all of this is true, returns True; otherwise False.
    """
    if len(path) != len(all_paths):
        return False
    if path_to_label[path[-1]][1] not in border_locations:
        return False
    if len(set(path)) != len(path):
        path_counts = collections.Counter(path)
        raise RuntimeError(f"Somehow, path(s) {(p for p in path_counts if path_counts[p] > 1)} was traversed multiple times!")
    return True


cdef void handle_victory(str path) except *:
    """Announce a victory, print it to the screen, and record it in the global
    SUCCESSFUL_PATHS variable. Then force a save.
    """
    global successful_paths

    readable_path = [label_to_path[p] for p in path]
    print(f"\n\nSolution found!\n\t{readable_path}\n\n")
    successful_paths[path] = readable_path
    do_save()


cdef inline void bump_failures() except *:                
    """Increase the failure count. Print a notice if the number is right to do so.
    """
    global failures

    failures += 1
    if (failures % 100000) == 0:
        print(f"{failures / 1000000.0} million failures so far (and {len(successful_paths)} successes!) in {total_run_time() / 60:.5f} minutes, or {total_run_time() / 3600:.5f} hours")


# The actual problem solution.
cdef void solve_from(int current_location,
                     str steps_taken) except *:
    """Given CURRENT_LOCATION, our current location, and STEPS_TAKEN, a list of
    previous moves, iterate over all possible remaining moves, i.e. those that begin
    in our current location and have not yet been taken, iterate over all possible
    moves. Calls itself repeatedly to explore every possible path, terminating a
    path's investigation when it dead-ends, and printing solutions to STDOUT.
    """
    cdef:
        list possible_moves, possible_paths, next_moves
        tuple path
        int m
        str label
    global exhausted_paths

    if is_victory(steps_taken):
        handle_victory(steps_taken)
        prune_and_save(steps_taken, discretionary=False)
        return

    if is_exhausted(steps_taken):           # Abort early if we know this pathway has been fully explored.
        return                              # (This is helpful when continuing from previously saved data.)

    possible_moves = sorted(pathways[current_location])
    possible_paths = [path_to_label[tuple(sorted((current_location, n)))] for n in possible_moves]
    possible_paths = [p for p in possible_paths if p not in steps_taken]
    next_moves = [[n for n in label_to_path[p] if n != current_location][0] for p in possible_paths]
    if not next_moves:
        bump_failures()

    for m in next_moves:
        path = tuple(sorted((current_location, m)))
        label = path_to_label[path]
        if label in steps_taken:                # Already been down that path? Move along.
            continue
        hypothetical_path = steps_taken + label
        if is_exhausted(hypothetical_path):
            continue

        solve_from(m, hypothetical_path)

    exhausted_paths.add(steps_taken)
    prune_and_save(steps_taken)

def solve() -> None:
    print("\n\n\nStarting up ...")
    do_restore_data()
    solve_from(current_location=12, steps_taken='')
