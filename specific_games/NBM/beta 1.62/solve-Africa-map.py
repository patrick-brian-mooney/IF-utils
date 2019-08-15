#!/usr/bin/env python3
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


import datetime, json, os, sys


# Set up basic parameters. If we have previous work checkpointed, these will all be overwritten.
start_time = datetime.datetime.now()
successful_paths, dead_end_paths = 0, 0

# Parameters for tracking previous work, in case we get interrupted
explored_paths = dict()
successful_paths_file = os.path.join(os.getcwd(), 'successful_paths_Africa.txt')

# Changing this next constant more or less (effectively) silently forces the run to re-start (well ... more or less), but doesn't reset any of its statistics.
path_length_to_track = 10
minimum_trackable_length = 4
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


def sanity_check() -> None:
    """Check that some basic parameters for the input data are not nonsensical before
    we begin running.
    """
    error = False
    for state, neighbors in borders.items():
        assert isinstance(neighbors, list), "ERROR: State %s has a NEIGHBORS that is not a list!" % state
        assert state not in neighbors, "ERROR: %s is marked as its own neighbor!" % state
        for n in neighbors:
            if n not in borders:
                print("ERROR! state %s has a neighbor, %s, that isn't defined as a state!" % (state, n))
                error = True
            elif state not in borders[n]:
                    print("ERROR! %s has a neighbor, %s, but %s is not a neighbor to %s!" % (state, n, state, n))
                    error = True
    if error:
        print("Unable to validate data!")
        sys.exit(1)
    else:
        print("No obvious data validation errors! Continuing...")


def time_so_far() -> float:
    """Convenience function that returns the number of seconds since the run started."""
    return (datetime.datetime.now() - start_time).total_seconds()


path_to_key = str           # Called so often that we just rebind to make them equivalent to save on the overhead from the calling-returning wrapper.
"""
def path_to_key(the_path:list) -> str:
    #Converts THE_PATH (a list of previously-visited country codes) into a canonical
    #representation used to index the global dictionary EXPLORED_PATHS.
    #
    return str(the_path)
"""

def find_path_from(starting_point:str, path_so_far:list=None) -> None:
    """Recursively checks all exits not yet visited to see whether they lead to a
    solution. If it finds one, it prints it. If there are no so-far-unvisited exits,
    it just returns, allowing other branches to be explored.

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
    grouping "strands" according to the first PATH_LENGTH_TO_TRACK segments.)
    """
    global successful_paths, dead_end_paths

    if not path_so_far:
        path_so_far = [starting_point]

    # If we've tracked that we've explored this strand, or ancestral strand including this on, in a previous run, just skip this branch.
    for i in range(minimum_trackable_length, len(path_so_far) + 1):    
        if path_to_key(path_so_far[:i]) in explored_paths:
            return

    unvisited_states = [s for s in borders if s not in path_so_far]
    if not unvisited_states:
        successful_paths += 1
        print("Solution #%d found! ... in %.3f seconds." % (successful_paths, time_so_far()))
        print('    ' + ' -> '.join(path_so_far) + '\n')
        with open(successful_paths_file, mode="at") as success_file:
            success_file.write('path #%d (%.3f seconds): %s \n' % (successful_paths, time_so_far(), ' -> '.join(path_so_far)))
        return

    possible_steps = [s for s in borders[starting_point] if s not in path_so_far]
    if possible_steps:
        for s in possible_steps:
            find_path_from(s, path_so_far + [s])
    else:
        dead_end_paths += 1
        if dead_end_paths % 1000000 == 0:
            print('  (%d million dead-end paths so far, in %.2f minutes)' % (dead_end_paths / 1000000, time_so_far()/60))

    if len(path_so_far) == path_length_to_track:        # If we've just finished a branch, document we've finished it
        print('    (fully explored path ' + ' -> '.join(path_so_far), end=' -> ... ')
        explored_paths[path_to_key(path_so_far)] = {
            'success': successful_paths,
            'dead ends': dead_end_paths,
            'time': time_so_far()
            }
        with open(explored_paths_file, mode='w') as json_file:
            json.dump(explored_paths, json_file, indent=4)
        print('  --updated data store!)\n')


def solve_maze():
    """Solve the maze, starting from Gambia."""
    print('Beginning program run!\n')
    find_path_from('GM')


def load_previous_progress() -> None:
    """Loads previous progress data from the progress data file, inferring a few
    things, based on that data, along the way.
    """
    global explored_paths, successful_paths, dead_end_paths, start_time
    try:
        with open(explored_paths_file, mode='r') as json_file:
            explored_paths = json.load(json_file)
        successful_paths = max([i['success'] for i in explored_paths.values()])
        dead_end_paths = max([i['dead ends'] for i in explored_paths.values()])
        total_seconds_elapsed = max([i['time'] for i in explored_paths.values()])
        start_time = datetime.datetime.now() - datetime.timedelta(seconds=total_seconds_elapsed)
        print("\nSuccessfully loaded previous progress data!")
        print("  ... %d successful paths and %d dead end paths in %.3f hours so far.\n\n" % (successful_paths, dead_end_paths, (total_seconds_elapsed / 3600)))
    except Exception as err:            # Everything's already been initialized to being blank at the beginning of the script's run, anyway.
        print("Unable to load previous status data! Starting from scratch ...") 


if __name__ == "__main__":
    sanity_check()
    load_previous_progress()
    solve_maze()
    print('\n\nDONE! There were %d solutions and %d dead ends found.' % (successful_paths, dead_end_paths))
    print('Exploring the map took %.3f hours.' % (time_so_far()/3600))

