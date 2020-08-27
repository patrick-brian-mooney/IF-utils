#!/usr/bin/env python3.6
# -*- coding: utf-8 -*-
"""A quick hack to help solve the Africa-map puzzle in beta version 1.62 of Greg
Boettcher's Nothing But Mazes (2019). Because of the enormous number of
possible paths through the maze, this script takes a LONG TIME (weeks!) to scan
them all. For this reason, it periodically checkpoints its work in a JSON file
so it doesn't have to restart from scratch if it's interrupted.

This script is copyright 2019 by Patrick Mooney. You may use it for any purpose
whatsoever provided that this copyright notice, unchanged, accompanies the
script.
"""


import datetime, json, signal

import pyximport; pyximport.install()

import africa_guts as ag


def solve_maze() -> None:
    """Solve the maze, starting from Gambia."""
    print('Beginning program run!\n')
    ag.find_path_from('GM')


def load_previous_progress() -> None:
    """Loads previous progress data from the progress data file, inferring a few
    things, based on that data, along the way.
    """
    try:
        with open(ag.explored_paths_file, mode='r') as json_file:
            ag.explored_paths = json.load(json_file)
        ag.successful_paths = max([i['success'] for i in ag.explored_paths.values()])
        ag.dead_end_paths = max([i['dead ends'] for i in ag.explored_paths.values()])
        total_seconds_elapsed = max([i['time'] for i in ag.explored_paths.values()])
        ag.start_time = datetime.datetime.now() - datetime.timedelta(seconds=total_seconds_elapsed)
        print("\nSuccessfully loaded previous progress data!")
        print("  ... %d successful paths and %d dead end paths in %.3f hours so far.\n\n" % (ag.successful_paths, ag.dead_end_paths, (total_seconds_elapsed / 3600)))
    except Exception as err:            # Everything's already been initialized to being blank at the top of the script, anyway.
        print("Unable to load previous status data! Starting from scratch ...")


def processUSR1(*args, **kwargs) -> None:
    """Handle the USR1 signal by printing current status info."""
    print("\nCurrent status:")
    print("    successful paths:     ", ag.successful_paths)
    print("    dead end paths:       ", ag.dead_end_paths)
    print("    total time:            %.3f hours" % (ag.time_so_far() / 3600))
    print("                           %.3f days" % (ag.time_so_far() / (24 * 3600)))
    print("    time since last save:  %.3f minutes" % ((datetime.datetime.now() - ag.last_save_time).total_seconds() / 60))
    print("\n")


def processUSR2(*args, **kwargs) -> None:
    """Handle the USR2 signal by saving the current status.

    In point of fact, we don't save the current status here. We merely set a global
    flag that will cause the current status to be saved when the current node,
    wherever that happens to be when the signal is caught, is completely evaluated.
    This involves solve_maze() recursively calling itself more times, perhaps many
    more, though usually the current status winds up being saved relatively quickly,
    because the algorithm actually spends most of its time tracing through top-level
    branches with a lot of nearby leaf nodes. There is no guarantee of this,
    however. It depends on where the algorithm is when the signal is caught.

    Note that "saving progress" in this way is better than nothing, but doesn't
    guarantee that NO work will have to be re-performed on the next run.
    """
    ag.force_save_after_next_node = True
    print("Caught USR2 signal at %s, scheduling progress save ..." % datetime.datetime.now())
    processUSR1()           # Also display current status


def set_up() -> None:
    ag.sanity_check()
    load_previous_progress()
    signal.signal(signal.SIGUSR1, processUSR1)
    signal.signal(signal.SIGUSR2, processUSR2)


if __name__ == "__main__":
    set_up()
    solve_maze()
    print('\n\nDONE! There were %d solutions and %d dead ends found.' % (ag.successful_paths, ag.dead_end_paths))
    print('Exploring the map took %.3f hours.' % (ag.time_so_far()/3600))
