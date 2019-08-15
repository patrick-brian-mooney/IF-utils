#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A quick hack to help solve the Mexico-map puzzle in beta version 1.62 of Greg
Boettcher's Nothing But Mazes (2019).

This script is copyright 2019 by Patrick Mooney. You may use it for any purpose
whatsoever provided that this copyright notice, unchanged, accompanies the
script.
"""


import datetime, os, sys


# Set up basic parameters.
start_time = datetime.datetime.now()
successful_paths, dead_end_paths = 0, 0

solutions_file = os.path.join(os.getcwd(), 'successful_paths_Mexico.txt')

# And data for the problem set.
borders = {
    'Baja California Sur': ['Baja California',],
    'Baja California': ['Baja California Sur', 'Sonora'],
    'Sonora': ['Baja California', 'Chihuahua', 'Sinaloa'],
    'Chihuahua': ['Sonora', 'Sinaloa', 'Durango', 'Coahuila'],
    'Coahuila': ['Chihuahua', 'Durango', 'Zacatecas', 'Nuevo Leon'],
    'Nuevo Leon': ['Coahuila', 'San Luis Potosi', 'Tamaulipas'],
    'Tamaulipas': ['Nuevo Leon', 'San Luis Potosi', 'Veracruz'],
    'San Luis Potosi': ['Nuevo Leon', 'Tamaulipas', 'Veracruz', 'Hidalgo', 'Queretaro', 'Guanajuato', 'Jalisco', 'Zacatecas'],
    'Zacatecas': ['Coahuila', 'San Luis Potosi', 'Jalisco', 'Aguascalientes', 'Nayarit', 'Durango'],
    'Aguascalientes': ['Zacatecas', 'Jalisco'],
    'Durango': ['Chihuahua', 'Coahuila', 'Zacatecas', 'Nayarit', 'Sinaloa'],
    'Sinaloa': ['Sonora', 'Chihuahua', 'Durango', 'Nayarit'],
    'Nayarit': ['Sinaloa', 'Durango', 'Zacatecas', 'Jalisco'],
    'Jalisco': ['Nayarit', 'Zacatecas', 'Aguascalientes', 'San Luis Potosi', 'Guanajuato', 'Michoacan', 'Colima'],
    'Colima': ['Jalisco', 'Michoacan'],
    'Michoacan': ['Colima', 'Jalisco', 'Guanajuato', 'Queretaro', 'Mexico', 'Guerrero'],
    'Guanajuato': ['San Luis Potosi', 'Queretaro', 'Michoacan', 'Jalisco'],
    'Queretaro': ['San Luis Potosi', 'Hidalgo', 'Mexico', 'Michoacan', 'Guanajuato'],
    'Mexico': ['Hidalgo', 'Tlaxcala', 'Puebla', 'Morelos', 'Distrito Federal', 'Guerrero', 'Michoacan', 'Queretaro'],
    'Hidalgo': ['San Luis Potosi', 'Veracruz', 'Puebla', 'Tlaxcala', 'Mexico', 'Queretaro'],
    'Tlaxcala': ['Puebla', 'Mexico', 'Hidalgo'],
    'Puebla': ['Veracruz', 'Oaxaca', 'Guerrero', 'Morelos', 'Mexico', 'Tlaxcala', 'Hidalgo'],
    'Morelos': ['Mexico', 'Distrito Federal', 'Puebla', 'Guerrero'],
    'Distrito Federal': ['Mexico', 'Morelos'],
    'Guerrero': ['Michoacan', 'Mexico', 'Morelos', 'Puebla', 'Oaxaca'],
    'Oaxaca': ['Guerrero', 'Puebla', 'Veracruz', 'Chiapas'],
    'Veracruz': ['Tamaulipas', 'San Luis Potosi', 'Hidalgo', 'Puebla', 'Oaxaca', 'Chiapas', 'Tabasco'],
    'Chiapas': ['Oaxaca', 'Veracruz', 'Tabasco'],
    'Tabasco': ['Veracruz', 'Chiapas', 'Campeche'],
    'Campeche': ['Tabasco', 'Yucatan', 'Quintana Roo'],
    'Quintana Roo': ['Campeche', 'Yucatan'],
    'Yucatan': ['Campeche', 'Quintana Roo'],
}


def time_so_far() -> float:
    """Convenience function that returns the number of seconds since the run started."""
    return (datetime.datetime.now() - start_time).total_seconds()


def find_path_from(starting_point:str, path_so_far:list=None) -> None:
    """Recursively checks all exits not yet visited to see whether they lead to a
    solution. If it finds one, it prints it. If there are no so-far-unvisited exits,
    it just returns, allowing other branches to be explored.
    """
    global successful_paths, dead_end_paths
    if not path_so_far: path_so_far = [starting_point]
    unvisited_states = [s for s in borders if s not in path_so_far]
    if not unvisited_states:
        successful_paths += 1        
        print("Solution #%d found! ... in %.3f seconds." % (successful_paths, time_so_far()))
        print('    ' + ' -> '.join(path_so_far) + '\n')
        with open(solutions_file, mode="at") as success_file:
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


def solve_maze() -> None:
    """Solve the maze, starting from Baja California Sur."""
    find_path_from('Baja California Sur')


def sanity_check() -> None:
    """Check some basic parameters for the input data."""
    error = False
    for state, neighbors in borders.items():
        assert isinstance(neighbors, list), "ERROR: State %s has a NEIGHBORS that is not a list!" % state
        assert state not in neighbors, "ERROR: %s is marked as its own neighbor!" % state
        for n in neighbors:
            if n not in borders:
                print("ERROR! state %s has a neighbor, %s, that isn't defined as a state!" % (state, n))
                error = True
            elif state not in borders[n]:
                    print("ERROR! %s is a neighbor to %s, but %s is not a neighbor to %s!" % (state, n, n, state))
                    error = True
    if error:
        print("Unable to validate data!")
        sys.exit(1)
    else:
        print("No obvious data validation errors! Continuing...")


if __name__ == "__main__":
    sanity_check()
    solve_maze()
    print('\n\nDONE! There were %d solutions and %d dead ends found.' % (successful_paths, dead_end_paths))
    print('Exploring the map took %.3f hours.' % (time_so_far()/3600))
