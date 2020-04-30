#!/usr/bin/python3
# cython: language_level=3, boundscheck=False
# -*- coding: utf-8 -*-
"""Implementation of the guts of solve_Africa_map.py, a script to find
solutions to the "Africa" puzzle in beta version 1.62 of Greg Boettcher's
"Nothing But Mazes" (2019). Moved to a separate file so it can be Cythonized,
because running under pure Python, it has taken 200 days' worth of processor
time to explore not quite 88 billion pathways.

This script is copyright 2019-20 by Patrick Mooney. You may use it for any purpose
whatsoever provided that this copyright notice, unchanged, accompanies the
script.
"""


import datetime, json, os, shutil, sys, textwrap


# Set up basic parameters. If we have previous work checkpointed, these will all be overwritten.
start_time = datetime.datetime.now()

successful_paths, dead_end_paths = 0, 0

# Parameters for tracking previous work, in case we get interrupted
explored_paths = dict()
successful_paths_file = os.path.join(os.getcwd(), 'successful_paths_Africa.txt')

# Some basic info for tracking how long it's been since we've saved.
DEF save_interval = 4 * 60 * 60             # seconds
last_save_time = datetime.datetime.now()
force_save_after_next_node = False          # Sending signal USR2 to the script will set this to True, causing progress to be saved "relatively soon."

# Changing this next constant has subtle implications for data tracking. All in all, it's best to increase, not decrease, it, but not by too much.
DEF path_length_to_track = 12

# Other tracking parameters.
DEF minimum_trackable_length = 4
explored_paths_file = os.path.join(os.getcwd(), "explored_paths_Africa.json")

# Quick sanity check.
assert path_length_to_track >= minimum_trackable_length

# And data for the problem set.
borders = {
    'AO': ['CD', 'ZM', 'NA'],                                       # AO: Angola
    'BF': ['ML', 'NE', 'BJ', 'TG', 'GH', 'CI'],                     # BF: Burkina Faso
    'BI': ['RW', 'TZ', 'CD'],                                       # BI: Birundi
    'BJ': ['TG', 'BF', 'NE', 'NG'],                                 # BJ: Benin
    'BW': ['NA', 'ZM', 'ZW', 'ZA'],                                 # BW: Botswana
    'CG': ['GA', 'CM', 'CF', 'CD'],                                 # CG: Congo
    'CD': ['CG', 'CF', 'SS', 'UG', 'RW', 'BI', 'TZ', 'ZM', 'AO'],   # CD: Democratic Republic of the Congo
    'CF': ['TD', 'SD', 'SS', 'CD', 'CG', 'CM'],                     # CF: Central African Republic
    'CI': ['LR', 'GN', 'ML', 'BF', 'GH'],                           # CI: Côte d’Ivoire
    'CM': ['NG', 'TD', 'CF', 'CG', 'GA', 'GQ'],                     # CM: Cameroon
    'DJ': ['ER', 'ET', 'SO'],                                       # DJ: Djibouti
    'DZ': ['MA', 'EH', 'MR', 'ML', 'NE', 'LY', 'TN'],               # DZ: Algeria, of course
    'EG': ['LY', 'SD'],                                             # EG: Egypt
    'EH': ['MA', 'DZ', 'MR'],                                       # EH: Western Sahara
    'ER': ['SD', 'ET', 'DJ'],                                       # ER: Eritrea
    'ET': ['ER', 'DJ', 'SO', 'KE', 'SS', 'SD'],                     # ET: Ethiopia
    'GA': ['GQ', 'CM', 'CG'],                                       # GA: Gabon
    'GH': ['CI', 'BF', 'TG'],                                       # GH: Ghana
    'GM': ['SN'],                                                   # GM: Gambia
    'GN': ['GW', 'SN', 'ML', 'CI', 'LR', 'SL'],                     # GN: Guinea
    'GQ': ['CM', 'GA'],                                             # GQ: Equatorial Guinea
    'GW': ['SN', 'GN'],                                             # GW: Guinea-Bissau
    'KE': ['SO', 'ET', 'SS', 'UG', 'TZ'],                           # KE: Kenya
    'LR': ['SL', 'GN', 'CI'],                                       # LR: Liberia
    'LS': ['ZA'],                                                   # LS: Lesotho
    'LY': ['TN', 'DZ', 'NE', 'TD', 'SD', 'EG'],                     # LY: Libya
    'MA': ['EH', 'DZ'],                                             # MA: Morocco
    'ML': ['DZ', 'NE', 'BF', 'CI', 'GN', 'SN', 'MR'],               # ML: Mali
    'MR': ['EH', 'DZ', 'ML', 'SN'],                                 # MR: Mauritania
    'MW': ['TZ', 'MZ', 'ZM'],                                       # MW: Malawi
    'MZ': ['TZ', 'MW', 'ZM', 'ZW', 'ZA', 'SZ'],                     # MZ: Mozambique
    'NA': ['AO', 'ZM', 'BW', 'ZA'],                                 # NA: Namibia
    'NE': ['DZ', 'LY', 'TD', 'NG', 'BJ', 'BF', 'ML'],               # NE: Niger
    'NG': ['BJ', 'NE', 'TD', 'CM'],                                 # NG: Nigeria
    'RW': ['UG', 'TZ', 'BI', 'CD'],                                 # RW: Rwanda
    'SD': ['EG', 'LY', 'TD', 'CF', 'SS', 'ET', 'ER'],               # SD: Sudan
    'SL': ['GN', 'LR'],                                             # SL: Sierra Leone
    'SN': ['GM', 'MR', 'ML', 'GN', 'GW'],                           # SN: Senegal
    'SO': ['DJ', 'ET', 'KE'],                                       # SO: Somalia
    'SS': ['SD', 'ET', 'KE', 'UG', 'CD', 'CF'],                     # SS: South Sudan
    'SZ': ['MZ', 'ZA'],                                             # SZ: Swaziland
    'TD': ['CM', 'NG', 'NE', 'LY', 'SD', 'CF'],                     # TD: Chad, natch.
    'TN': ['DZ', 'LY'],                                             # TN: Tunisia
    'TZ': ['KE', 'UG', 'RW', 'BI', 'CD', 'ZM', 'MW', 'MZ'],         # TZ: Tanzania
    'TG': ['GH', 'BF', 'BJ'],                                       # TG: Togo
    'UG': ['SS', 'KE', 'TZ', 'RW', 'CD'],                           # UG: Uganda
    'ZA': ['NA', 'BW', 'ZW', 'MZ', 'SZ', 'LS'],                     # ZA: South Africa
    'ZM': ['CD', 'TZ', 'MW', 'MZ', 'ZW', 'BW', 'NA', 'AO'],         # ZM: Zambia
    'ZW': ['ZM', 'MZ', 'ZA', 'BW'],                                 # ZW: Zimbabwe
}


cpdef float time_so_far():
    """Convenience function that returns the number of seconds since the run started.
    If the run has been interrupted and restarted from checkpointing data, it
    returns the total time spent including checkpointed time on previous runs, since
    the load_previous_progress() function futzes the START_TIME global to make this
    possible.
    """
    return (datetime.datetime.now() - start_time).total_seconds()


cdef bint is_redundant_strand(which_path: str):
    """If the path in WHICH_PATH is redundant relative to the global progress store
    EXPLORED_PATHS, returns True; otherwise, returns False.

    "Redundant" means that the path in WHICH_PATH need not be stored, because the
    checkpointing data already includes a higher-order checkpoint that obviates the
    need to store this more-specific checkpoint. So if the higher-order path
    [c1, c2, c3, c4, c5] has been checkpointed, we need not checkpoint any of the
    more specific checkpoints [c1, c2, c3, c4, c5, c6, ...], because we've already
    determined that they've been explored fully by checkpointing the higher-order
    (i.e., shorter) path as completely explored. Despite this fact, the dictionary
    intentionally retains all strands of length 8 or less, even if they are
    redundant, so that it has a record of higher-order time-elapsed data.

    If WHICH_PATH is exactly equal to a key in the global EXPLORED_PATHS, this is
    not considered a match on its own: True is returned only if the path is also
    made redundant by a higher-order (i.e., shorter path length) key also existing.
    """
    global explored_paths

    if len([i for i in which_path.split("""', '""")]) <= 8:      # Retain all strands of length 8 or less.
        return False

    for key in explored_paths:
        if (which_path.startswith(key.rstrip(']'))) and (which_path != key):
            return True
    return False


cdef pretty_print(what: str):
    """Pretty-print a line of text that might need to be wrapped."""
    chosen_width = max(shutil.get_terminal_size()[0], 40)
    for line_num, line in enumerate(textwrap.wrap(what, width=chosen_width - 6, replace_whitespace=False, expand_tabs=False, drop_whitespace=False)):
        indent = "    " if (line_num > 0) else "  "         # Indent all lines after first.
        print(indent + line.strip())


cdef clean_progress_data():
    """Clean up the currently stored progress data by simplifying the data stored in
    the global variable EXPLORED_PATHS.

    This cleans out the EXPLORED_PATHS dictionary by taking advantage of the fact
    that, for each checkpointed path [p1, p2, p3, p4, p5, ...], the evaluation of
    global progress data first checks for [p1, p2, p3, p4, p5] as well as all other
    higher-order paths ([p1, p2, p3, p4] and [p1, p2, p3], etc.). That is to say
    that having [p1, p2, p3, p4] checkpointed makes it unnecessary to also have the
    sub-paths [p1, p2, p3, p4, p5, ...] checkpointed, because the higher-order path
    is also checkpointed. So once [p1, p2, p3, p4] (for instance) is checkpointed,
    any more specific sub-paths no longer need to be checkpointed.

    But these higher-order, more-specific sub-paths have ALREADY been checkpointed
    along the way, because we checkpoint all fully explored paths that are at most
    PATH_LENGTH_TO_TRACK, once they become fully checkpointed. this means that,
    when we complete exploring a tree of length less than PATH_LENGTH_TO_TRACK, we
    need to clean up the more specific tracking data that got us to this point.

    That's what this function does: it checks over each key in the global
    EXPLORED_PATHS dictionary to see if that checkpointing data is obsolete on the
    basis of more general checkpointing data that always exists. So a path
    [p1, p2, p3, p4, p5, ...] is pruned -- no longer stored -- if the higher-order
    path [p1, p2, p3, p4] is also checkpointed. That is, it cleans up the more
    specific checkpointing that's no longer necessary because it got us to the
    current more-advanced state.
    """
    global explored_paths

    pruned_dict = {k:v for k, v in explored_paths.items() if not is_redundant_strand(k)}
    if pruned_dict != explored_paths:
        pretty_print("[Pruned redundant data from the global progress store!]")
        explored_paths = pruned_dict


cdef save_progress(current_path: list):
    """Writes out the current progress data to EXPLORED_PATHS_FILE, first adding
    CURRENT_PATH as a path that has been completely explored, along with all of the
    relevant timing and counting data.
    """
    global successful_paths, dead_end_paths
    global explored_paths
    global last_save_time

    print('\n')
    pretty_print('(fully explored path ' + ' -> '.join(current_path) + ' -> ... ')
    explored_paths[str(current_path)] = {
        'success': successful_paths,
        'dead ends': dead_end_paths,
        'time': time_so_far()
        }

    clean_progress_data()
    with open(explored_paths_file, mode='w') as json_file:
        json.dump(explored_paths, json_file, indent=4)
    pretty_print('--updated progress data!)')
    print('\n')

    last_save_time = datetime.datetime.now()


cpdef find_path_from(starting_point: str, path_so_far: list=None):
    """Recursively checks all exits not yet visited to see whether they lead to a
    solution. If it finds one, it prints it. If there are no so-far-unvisited exits
    from STARTING_POINT, it just returns, allowing other branches to be explored.

    Because the script takes an incredibly long time to run (weeks!), it tracks how
    much partial progress it's made: it groups all possible paths into "strands"
    that start with paths of PATH_LENGTH_TO_TRACK (initially 6). That is, for each
    "strand" of paths starting with a known particular starting sequence of length 6
    (or whatever), the fact that that "strand" has been completely explored is
    tracked so that, if the program has to be restarted, that strand doesn't need to
    be explored again.

    "Explored strands" are tracked in a JSON file at the location of global constant
    EXPLORED_PATHS_FILE. On startup, the function load_previous_progress() reads
    this file and uses it to reconstruct the progress already made on the previous
    run(s). (Not all of it, but merely the bits that have been checkpointed by
    grouping "strands" according to the first PATH_LENGTH_TO_TRACK segments. Still,
    this is much better than having to re-start from scratch.)
    """
    global successful_paths, dead_end_paths
    global explored_paths
    global last_save_time
    global force_save_after_next_node

    if not path_so_far:
        path_so_far = [starting_point]

    # If we've tracked that we've explored this strand, or an ancestral strand including this one, in a previous run, just skip this branch.
    for i in range(minimum_trackable_length, len(path_so_far) + 1):
        if str(path_so_far[:i]) in explored_paths:
            return

    # Detect early: are we going to force a save at this level? Either because we caught USR2 or because it's been a long time?
    if ((datetime.datetime.now() - last_save_time).total_seconds() > save_interval) or force_save_after_next_node:
        force_save = True                               # Mark that we're going to save when we've finished exploring all paths that start from here.
        force_save_after_next_node = False
        last_save_time = datetime.datetime.now()        # Reset the counter; it'll be corrected when we actually save at the end of this invocation.
    else:                                                   # If we don't reset the counter, the path saved will be a super-specific dead end.
        force_save = False

    unvisited_states = [s for s in borders if s not in path_so_far]     # Make a list of all states in Africa that have not yet been visited in this path.
    if not unvisited_states:
        successful_paths += 1
        print("Solution #%d found! ... in %.3f hours." % (successful_paths, time_so_far()/3600))
        pretty_print(' -> '.join(path_so_far))
        print('\n')
        with open(successful_paths_file, mode="at") as success_file:
            success_file.write('path #%d (%.3f seconds): %s \n' % (successful_paths, time_so_far(), ' -> '.join(path_so_far)), '\n\n')
        return

    possible_steps = [s for s in borders[starting_point] if s not in path_so_far]
    if possible_steps:
        for s in possible_steps:
            find_path_from(s, path_so_far + [s])
    else:
        dead_end_paths += 1
        if dead_end_paths % 1000000 == 0:
            how_long = time_so_far()/3600
            print('  (%.3f billion dead-end paths so far, in %.2f hours [or %.3f days])' % (dead_end_paths / 1000000000,
                                                                                            how_long, how_long/24))

    if (len(path_so_far) <= path_length_to_track) and (str(path_so_far) not in explored_paths):                      #
        # Document we've finished this path, if it's at most the right length.
        save_progress(path_so_far)
    elif force_save:                                                    # Or if it's been long enough, or we caught the USR2 signal.
        save_progress(path_so_far)

def sanity_check() -> None:
    """Check that some basic parameters for the input data are not nonsensical before
    we begin running.
    """
    error = False
    for state, neighbors in borders.items():
        assert state not in neighbors, "ERROR: %s is marked as its own neighbor!" % state
        for n in neighbors:
            if n not in borders:
                print("ERROR! state %s has a neighbor, %s, that isn't defined as a state!" % (state, n))
                error = True
            elif state not in borders[n]:
                print("ERROR! %s has a neighbor, %s, but %s is not a neighbor to %s!" % (state, n, n, state))
                error = True
    if error:
        print("Unable to validate data!")
        sys.exit(1)
    else:
        print("No obvious data validation errors! Continuing...")



