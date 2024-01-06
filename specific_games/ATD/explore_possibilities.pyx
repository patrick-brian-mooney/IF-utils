#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#cython: language_level=3
"""A quick hack to explore the possibility space in All Things Devours, a piece
of interactive fiction published by Toby Ord (under the name "half sick of
shadows") in 2004. ATD is a tight little puzzle game involving time-travel;
part of its appeal is how tightly interlocked the elements of the various
puzzles are with each other and how solutions to one puzzle put constraints on
other puzzles. At the same time, having played through to a solution, it's easy
to wonder how many other ways the puzzles could be solved. This script is an
attempt to explore that question.

(N.B. This docstring is clearly out of date. This is no longer much of a quick
hack, even if it started off that way once.)

It "plays" ATD repeatedly, making all possible sequences of moves, looking for
those that result in successful outcomes and reporting them. It's also
interested in overcoming a technical limitation of the original, the maximum-
simultaneous-time-travel hard limit of 2; this script plays a hacked version of
ATD that has room for up to 16 different simultaneous interactions. (SURELY
there couldn't be room for THAT MANY simultaneous copies moving around the map
at the same time.) (N.B. Or rather, it will, once the initial run with the
unmodified copy has been completed.)

This script is copyright 2019-23 by Patrick Mooney. It is released under the
GPL, either version 3 or (at your option) any later version. See the file
LICENSE for a copy of this license.
"""


import argparse
import datetime
import json
import os

from pathlib import Path

import pickle
import pprint
import shlex, signal, string, sys
import tarfile, threading, time, typing
import uuid

import mod.terp_connection as tc


module_docstring = __doc__

# Global statistics; these are overwritten when restoring state from previous runs.
dead_ends = 0
successes = 0
moves = 0
script_run_start = datetime.datetime.now()
maximum_walkthrough_length = 0

progress_data = dict()

# Force an early checkpointing moment by pretending the last one was five decades ago. We do this because if there's a
# problem with checkpointing, we want it to show up early.
last_checkpoint_time = datetime.datetime(year=1970, month=1, day=1, hour=0, minute=0)
minimum_checkpointing_interval = 10 * 60        # seconds

# Some data used when parsing the game's output and/or making decisions about what commands are allowed.
direction_inverses = {
    'down': 'up',
    'east': 'west',
    'in': 'out',
    'north': 'south',
    'northeast': 'southwest',
    'northwest': 'southeast',
    'out': 'in',
    'south': 'north',
    'southeast': 'northwest',
    'southwest': 'southeast',
    'up': 'down',
}


# These next are routines that determine whether a command is available as a guess that the code can take at a
# particular point in time. Each function is passed one parameter, which is the current command being attempted (the
# function needs to look at the global 'terp state if it wants to know anything else) and returns a boolean value: True
# if the command is  available right now, or False otherwise. Some commands have no real need to be limited and so
# are mapped to always_true().

# Experience has shown that it's faster to limit commands via a filter function or two instead of allowing the 'terp
# to try it and then having to restore from a save file. However, branches should of course only be pruned in advance
# when it's possible to be ABSOLUTELY SURE, in advance, that they're not a viable way to move forward.

# Functions that have no need to look at the current command to know if their action is available can just consume
# it with *pargs syntax, if desired
def always_true(*pargs) -> bool:
    """Utility function for commands that are always available. When we query whether
    the command is available, this function just returns True.
    """
    return True


def only_once(c: str) -> bool:
    """Restrict this command from being used if it's already been used. Initially
    written for EXAMINE BENCHES.
    """
    return c.lower() not in terp_proc.text_walkthrough.lower()


def only_one_timer_command(*pargs) -> bool:
    """Utility function for SET TIMER TO [number] commands. It returns True iff
    no SET TIMER TO [number] command has yet been entered; otherwise, it returns
    False.

    The rationale for this is that SET TIMER TO [number] is essentially a WAIT
    command every time in the game but once. (I suppose it is possible in theory
    that one could set the timer, drop it, run past it again and set it to a higher
    number, and this might even get around the 100-second time limit, but I can't
    manage to see how this could be helpful, given that the prototype is nowhere
    near the Conference Room-to-Outside path that the PC has to take under tight
    time constraints while the timer is ticking. This is maybe a bit iffy, but seems
    logically sound, all in all.) In any case, doing this makes the game's problem
    space much more navigable, so it's going to have to be necessary if a brute-
    force solution to the problem is going to be attempted in the first place.
    """
    return (not "set timer to" in terp_proc.text_walkthrough.lower())


def only_in_prototype(*pargs) -> bool:
    """This function is a filter for for actions that are only productive when the
    Protagonist is inside the time machine prototype. There are a huge number of
    such actions, most of which are SET PANEL TO [number]: these, for instance, are
    only possible inside the Prototype because the panel is not portable.
    """
    return 'prototype' in terp_proc.current_room.lower()


def only_on_balcony(*pargs) -> bool:
    """A filter for SMASH WINDOW: there's only one location where it could possibly be
    useful, so there's only one location where it's allowed.
    """
    return 'balcony' in terp_proc.current_room.lower()


def not_twice_in_a_row(c: str) -> bool:
    """This function prevents the same command from being issued twice consecutively.
    This is useful for many commands, because it eliminates -- well, REDUCES -- the
    "when a command succeeds once, it will generally succeed twice; but the second
    time is essentially a synonym for WAIT" problem.

    Note that "same command" in the paragraph above means "the EXACT SAME command,
    character for character," not "a similar command," nor "a command that means the
    same thing," nor "a command with the same effects."
    """
    return (c.strip().strip(string.punctuation).strip().lower() != terp_proc.last_command.strip().strip(string.punctuation).strip().lower())


def set_panel_filter(*pargs) -> bool:
    """This filter is for SET PANEL TO [number], a set of commands that have some
    comparatively complex requirements: 1. Only in the prototype. 2. Only allowed
    once a successful FIX PROTOTYPE command has been issued (i.e., appears in the
    transcript). 3. Once a SET PANEL command has been executed, no others are
    allowed until after a successful PUSH SILVER BUTTON appears in the transcript
    (i.e., is not a mistake).

    Otherwise, allowing repeated SET PANEL TO commands is equivalent to WAIT.
    """
    if only_in_prototype():
        walkthrough = terp_proc.text_walkthrough.lower().strip()
        if 'fix prototype' not in walkthrough:
            return False
        if 'set panel' not in walkthrough:
            return True
        elif 'push silver' in walkthrough:
            return (walkthrough.rindex('push silver') > walkthrough.rindex('set panel'))
    return False


def must_do_something_before_exiting_prototype(*pargs) -> bool:
    """Another rule to prevent an effective synonym for WAIT: a repeated GET IN/GET
    OUT OF PROTOTYPE cycle. This filter should be attached to EXITing verbs; it
    disallows them if the previous (effective) command is something that means GET
    IN PROTOTYPE, provided that the PC is in the Lab or the Prototype.
    """
    if 'prototype' not in terp_proc.current_room.strip().lower():
        return True
    index = 0
    steps = terp_proc.list_walkthrough
    for i, s in enumerate(steps):               # Find the last occurrence
        if s.strip().lower() in ['enter prototype', 'go in']:
            index = i
    if index == len(steps) - 1:                 # If the last thing we did was get in, prohibit exiting.
        return False
    if index < 1:                               # If there's never been an entering command, allow the exiting command anyway, though it will be a mistake.
        return True
    steps = steps[1+index:]                     # Drop everything up to the last entering command.
    while steps:                                # Now drop WAITs until we hit something else.
        if steps[0].lower().strip() == 'wait':
            steps.pop(0)
        else:
            break                               # If there's anything left after the WAITs after the entering command,
    return bool([i for i in steps if i])        # ... return True to allow the exit command.


def no_exit_when_there_are_synonyms(*pargs) -> bool:
    """Prohibits the EXIT command from being used when there are other synonyms in a
    particular situation. For instance, EXIT is not allowed in Deutsch Lab, because GO
    SOUTH does the same thing. Preventing EXIT in that situation helps to control the
    combinatorial explosion of the game's possibility space.

    In fact, the only place where EXIT *is* allowed is inside the prototype, because
    other directions are synonyms in all other locations.
    """
    if "prototype" not in terp_proc.current_room.strip().lower():
        return False
    return True


def no_pacing_unless_hiding(c: str) -> bool:
    """Prohibits back-and-forth movement unless the first step takes the PC into a
    location where "hiding" from a pastPC or a futurePC is possible. (Actually, what
    it does, to be more specific, is to nip off the option to leave a "hideable
    location" without doing something first -- "do something" here DOES include
    waiting, because we may be (may wind up being) intending to wait for pastPC or
    futurePC to pass nearby. This function does not check for commands that result
    in movement but that do not start with GO: synonyms and movement-as-a-side-
    effect are not considered here.

    This filter is intended for GO [direction] commands. However, so that it can
    also be used with EXIT, it checks first to see whether the first word of the
    command we're checking is GO and, if not returns True automatically: it doesn't
    prevent the execution of non-GO commands, not even EXIT.

    Note that this function prohibits "one-step" but not "multi-step" pacing, which
    is harder to detect (but drives less of a combinatorial explosion anyway, due to
    the time constraints in the game and the fact that multi-step pacing takes more
    in-game time to execute). For instance, it prohibits GO SOUTH immediately after
    GO NORTH, but it doesn't prevent any of the commands in GO UP. GO UP. GO DOWN.
    GO DOWN, provided that the first GO DOWN is issued from a "hideable" location
    (e.g., the second-floor landing).
    """
    if 'command' not in terp_proc.context_history:      # If this is the game's first command, allow it!
        return True
    c = c.lower().strip()
    if not c.startswith("go"):
        return True
    previous_command = terp_proc.last_command.lower().strip()
    if not previous_command.startswith('go'):
        return True
    current_direction = c[2:].strip()                   # The direction we're trying to go.
    previous_direction = previous_command[2:].strip()   # The direction we went on the last turn.
    assert current_direction in direction_inverses, "ERROR: we're trying to GO in an undefined direction!"
    if direction_inverses[current_direction] == previous_direction:
        return terp_proc.room_list[terp_proc.current_room]['hideable']
    return True


def down_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["upstairs landing", "foyer", ]


def north_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["second floor corridor", "upstairs landing", "foyer",
                                                      "basement corridor", "basement landing"]


def northeast_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["first floor corridor", "basement corridor", ]


def northwest_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["conference room", ]


def south_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ['balcony', "second floor corridor", "first floor corridor",
                                                      "foyer", "the deutsch laboratory", "basement corridor", ]


def southeast_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ['balcony', ]


def southwest_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["first floor equipment room", "basement equipment room", ]


def up_filter(*pargs) -> bool:
    """A filter function for a direction, allowing the direction only to be tried in
    rooms that have, or might have, exits in that direction.
    """
    return terp_proc.current_room.lower().strip() in ["foyer", "basement landing", ]


def not_after_exiting(c: str) -> bool:
    """A filter for ENTER PROTOTYPE: don't allow ENTER PROTOTYPE right after getting out
    of it. (This is equivalent to WAIT. WAIT: it's not even possible to hide from
    pastPC and futurePC inside the prototype, since they'll see you through the open
    door in the side of the device.)
    """
    return (terp_proc.last_command.lower().strip() not in ['exit', 'go out',])


def only_after_setting_timer(*pargs) -> bool:
    """A filter for DROP BOMB: it's only allowed after a SET TIMER command. There's no
    real reason to drop the bomb before setting the timer, because the location
    where the bomb needs to be dropped to be effective is nowhere near a through-
    path that works for any other task that needs to be performed while the timer is
    ticking. Preventing DROP BOMB before SET TIMER really prunes down the
    possibility space, though, because of course SET TIMER prunes the possibility
    space a lot on its own by putting another constraint on game timing.
    """
    return ("set timer to" in terp_proc.text_walkthrough.lower())


def only_if_has(c: str, what: str) -> bool:
    """A filter that only allows a command C if the PC currently has WHAT in her
    inventory, where WHAT is a string that will be case-insensitively matched to
    see if it's a partial match for anything in the PC's inventory. This is useful,
    for instance, to prohibit DROP BATTERY when the PC is not carrying a battery.

    Note that the directly calling code only supplies C, the command; WHAT will have
    to be partially applied using (for instance) a lambda.
    """
    return terp_proc.has(what)


def only_in(c: str, where: typing.List[str]) -> bool:
    """Filter function that returns True iff the PC's current room is specified in
    WHERE.
    """
    for w in where:
        assert w.lower().strip() in terp_proc.rooms
    return terp_proc.current_room.lower().strip() in [w.lower().strip() for w in where]


def only_after_fixing_prototype(*pargs) -> bool:
    """Filter function that makes a command available only once the prototype has been
    fixed. We detect this by checking whether FIX PROTOTYPE appears in the text
    walkthrough, i.e. has been successfully executed.
    """
    return 'fix prototype' in terp_proc.text_walkthrough.lower()


# Now that we've defined the filter functions, fill out the command-selection parameters.
# Sure, this could be done more tersely, and has been in earlier versions, but being explicit pays off in clarity.
all_commands = {
    "close deutsch lab":                lambda c: (not_twice_in_a_row(c)) and (only_in(c, ['basement corridor', 'the deutsch laboratory', 'inside the prototype'])),
    "close equipment door":             lambda c: (not_twice_in_a_row(c)) and (only_in(c, ["basement corridor", "basement equipment room", "first floor corridor", "first floor equipment room", "second floor corridor"])),
    "drop battery":                     lambda c: only_if_has(c, 'batt'),
    "drop bomb":                        lambda c: only_after_setting_timer(c) and only_if_has(c, 'explosive') and only_once(c),
    "enter prototype":                  lambda c: (only_after_fixing_prototype(c)) and (not_after_exiting(c)) and (only_in(c, ['the deutsch laboratory'])),
    "examine benches":                  only_once,
    "exit":                             lambda c: (must_do_something_before_exiting_prototype(c)) and (no_exit_when_there_are_synonyms(c)),
    "fix prototype":                    lambda c: (only_if_has(c, 'cable')) and (only_in(c, ['the deutsch laboratory', 'inside the prototype'])),
    "flick switch":                     lambda c: ("equipment" in terp_proc.current_room.lower().strip()),
    "get all":                          not_twice_in_a_row,         # multiple GET saves in-game time.
    "get battery":                      lambda c: (not_twice_in_a_row(c) and ('batt' in terp_proc.context_history['output'])),
    "get battery from flashlight":      lambda c: (not_twice_in_a_row(c)) and (only_if_has(c, 'light')),
    "get cable":                        lambda c: (not_twice_in_a_row(c)) and (not only_if_has(c, 'cable') and ('cable' in terp_proc.context_history['output'])),
    "get cable and battery":            lambda c: (not_twice_in_a_row(c)) and (not only_if_has(c, 'cable') and ('cable' in terp_proc.context_history['output'])),
    "get crowbar":                      lambda c: (not_twice_in_a_row(c)) and (not only_if_has(c, 'crowbar') and ('crow' in terp_proc.context_history['output'])),
    "get flashlight and brass key":     lambda c: (not_twice_in_a_row(c)) and (not only_if_has(c, 'light')) and (not only_if_has('c', 'brass')),
    "get notes":                        lambda c: (not_twice_in_a_row(c) and ('notes' in terp_proc.context_history['output'])),
    "go down":                          lambda c: (down_filter(c)) and no_pacing_unless_hiding(c),
    "go north":                         lambda c: (north_filter(c)) and no_pacing_unless_hiding(c),
    "go northeast":                     lambda c: (northeast_filter(c)) and no_pacing_unless_hiding(c),
    "go northwest":                     lambda c: (northwest_filter(c)) and no_pacing_unless_hiding(c),
    "go south":                         lambda c: (south_filter(c)) and no_pacing_unless_hiding(c),
    "go southeast":                     lambda c: (southeast_filter(c)) and no_pacing_unless_hiding(c),
    "go southwest":                     lambda c: (southwest_filter(c)) and no_pacing_unless_hiding(c),
    "go up":                            lambda c: (up_filter(c)) and no_pacing_unless_hiding(c),
    "lock deutsch lab":                 lambda c: not_twice_in_a_row(c) and only_in(c, ['basement corridor', 'the deutsch laboratory']),
    "lock equipment door":              lambda c: not_twice_in_a_row(c) and (('corridor' in terp_proc.current_room.lower().strip()) or ('equipment' in terp_proc.current_room.lower().strip())),
    "open automatic door":              not_twice_in_a_row,
    "open deutsch door":                lambda c: (not_twice_in_a_row(c)) and only_in(c, ['basement corridor', 'the deutsch laboratory']),
    "push alarm":                       lambda c: (not_twice_in_a_row(c)) and only_in(c, ['foyer']),
    "push basement":                    lambda c: (not_twice_in_a_row(c)) and only_in(c, ['foyer']),
    "push first":                       lambda c: (not_twice_in_a_row(c)) and only_in(c, ['foyer']),
    "push green button":                lambda c: (not_twice_in_a_row(c)) and only_in(c, ['foyer']),
    "push second":                      lambda c: (not_twice_in_a_row(c)) and only_in(c, ['foyer']),
    "push silver button":               lambda c: (not_twice_in_a_row(c)) and only_in(c, ['inside the prototype']),
    "put batteries in flashlight":      lambda c: only_if_has(c, 'light'),
    "put battery in flashlight":        lambda c: only_if_has(c, 'light'),
    "remove battery from flashlight":   lambda c: only_if_has(c, 'light'),
    "smash window":                     only_on_balcony,
    "turn off flashlight":              lambda c: only_if_has(c, 'light'),
    "turn off lights":                  lambda c: ('equipment' in terp_proc.current_room.lower().strip()) and not_twice_in_a_row(c),
    "turn on flashlight":               lambda c: only_if_has(c, 'light'),
    "turn on lights":                   lambda c: ('equipment' in terp_proc.current_room.lower().strip()) and not_twice_in_a_row(c),
    "unlock equipment door":            lambda c: not_twice_in_a_row(c) and (('corridor' in terp_proc.current_room.lower().strip()) or ('equipment' in terp_proc.current_room.lower().strip())),
    "wait":                             always_true,
    "set panel to 5":                   set_panel_filter,
    "set panel to 10":                  set_panel_filter,
    "set panel to 15":                  set_panel_filter,
    "set panel to 20":                  set_panel_filter,
    "set panel to 25":                  set_panel_filter,
    "set panel to 30":                  set_panel_filter,
    "set panel to 35":                  set_panel_filter,
    "set panel to 40":                  set_panel_filter,
    "set panel to 45":                  set_panel_filter,
    "set panel to 50":                  set_panel_filter,
    "set panel to 55":                  set_panel_filter,
    "set panel to 60":                  set_panel_filter,
    "set panel to 65":                  set_panel_filter,
    "set panel to 70":                  set_panel_filter,
    "set panel to 75":                  set_panel_filter,
    "set panel to 80":                  set_panel_filter,
    "set panel to 85":                  set_panel_filter,
    "set panel to 90":                  set_panel_filter,
    "set panel to 95":                  set_panel_filter,
    "set panel to 100":                 set_panel_filter,
    "set panel to 105":                 set_panel_filter,
    "set panel to 110":                 set_panel_filter,
    "set panel to 115":                 set_panel_filter,
    "set panel to 120":                 set_panel_filter,
    "set panel to 125":                 set_panel_filter,
    "set panel to 130":                 set_panel_filter,
    "set panel to 135":                 set_panel_filter,
    "set panel to 140":                 set_panel_filter,
    "set panel to 145":                 set_panel_filter,
    "set panel to 150":                 set_panel_filter,
    "set panel to 155":                 set_panel_filter,
    "set panel to 160":                 set_panel_filter,
    "set panel to 165":                 set_panel_filter,
    "set panel to 170":                 set_panel_filter,
    "set panel to 175":                 set_panel_filter,
    "set panel to 180":                 set_panel_filter,
    "set panel to 185":                 set_panel_filter,
    "set panel to 190":                 set_panel_filter,
    "set panel to 195":                 set_panel_filter,
    "set panel to 200":                 set_panel_filter,
    "set panel to 205":                 set_panel_filter,
    "set panel to 210":                 set_panel_filter,
    "set panel to 215":                 set_panel_filter,
    "set panel to 220":                 set_panel_filter,
    "set panel to 225":                 set_panel_filter,
    "set panel to 230":                 set_panel_filter,
    "set panel to 235":                 set_panel_filter,
    "set panel to 240":                 set_panel_filter,
    "set panel to 245":                 set_panel_filter,
    "set panel to 250":                 set_panel_filter,
    "set panel to 255":                 set_panel_filter,
    "set panel to 260":                 set_panel_filter,
    "set panel to 265":                 set_panel_filter,
    "set panel to 270":                 set_panel_filter,
    "set panel to 275":                 set_panel_filter,
    "set panel to 280":                 set_panel_filter,
    "set panel to 285":                 set_panel_filter,
    "set panel to 290":                 set_panel_filter,
    "set panel to 295":                 set_panel_filter,
    "set panel to 300":                 set_panel_filter,
    "set panel to 305":                 set_panel_filter,
    "set panel to 310":                 set_panel_filter,
    "set panel to 315":                 set_panel_filter,
    "set panel to 320":                 set_panel_filter,
    "set panel to 325":                 set_panel_filter,
    "set panel to 330":                 set_panel_filter,
    "set panel to 335":                 set_panel_filter,
    "set panel to 340":                 set_panel_filter,
    "set panel to 345":                 set_panel_filter,
    "set panel to 350":                 set_panel_filter,
    "set panel to 355":                 set_panel_filter,
    "set panel to 360":                 set_panel_filter,
    "set panel to 365":                 set_panel_filter,
    "set panel to 370":                 set_panel_filter,
    "set panel to 375":                 set_panel_filter,
    "set panel to 380":                 set_panel_filter,
    "set panel to 385":                 set_panel_filter,
    "set panel to 390":                 set_panel_filter,
    "set panel to 395":                 set_panel_filter,
    "set panel to 400":                 set_panel_filter,
    "set panel to 405":                 set_panel_filter,
    "set panel to 410":                 set_panel_filter,
    "set panel to 415":                 set_panel_filter,
    "set panel to 420":                 set_panel_filter,
    "set panel to 425":                 set_panel_filter,
    "set panel to 430":                 set_panel_filter,
    "set panel to 435":                 set_panel_filter,
    "set panel to 440":                 set_panel_filter,
    "set panel to 445":                 set_panel_filter,
    "set panel to 450":                 set_panel_filter,
    "set panel to 455":                 set_panel_filter,
    "set panel to 460":                 set_panel_filter,
    "set panel to 465":                 set_panel_filter,
    "set panel to 470":                 set_panel_filter,
    "set panel to 475":                 set_panel_filter,
    "set panel to 480":                 set_panel_filter,
    "set panel to 485":                 set_panel_filter,
    "set panel to 490":                 set_panel_filter,
    "set panel to 495":                 set_panel_filter,
    "set panel to 500":                 set_panel_filter,
    "set timer to 5":                   only_one_timer_command,
    "set timer to 10":                  only_one_timer_command,
    "set timer to 15":                  only_one_timer_command,
    "set timer to 20":                  only_one_timer_command,
    "set timer to 25":                  only_one_timer_command,
    "set timer to 30":                  only_one_timer_command,
    "set timer to 35":                  only_one_timer_command,
    "set timer to 40":                  only_one_timer_command,
    "set timer to 45":                  only_one_timer_command,
    "set timer to 50":                  only_one_timer_command,
    "set timer to 55":                  only_one_timer_command,
    "set timer to 60":                  only_one_timer_command,
    "set timer to 65":                  only_one_timer_command,
    "set timer to 70":                  only_one_timer_command,
    "set timer to 75":                  only_one_timer_command,
    "set timer to 80":                  only_one_timer_command,
    "set timer to 85":                  only_one_timer_command,
    "set timer to 90":                  only_one_timer_command,
    "set timer to 95":                  only_one_timer_command,
    "set timer to 100":                 only_one_timer_command,
}


# Now that we've specified the data and some basic handling methods ... here are some utility routines.
def get_total_time() -> float:
    """Returns the total number of seconds since the processing run started. Note that
    runs that start by restoring progress data from a previous run also fake the
    SCRIPT_RUN_START time so that this function returns the proper total wall time
    spent running the script to gather the current crop of data.
    """
    return (datetime.datetime.now() - script_run_start).total_seconds()


def is_redundant_strand(which_path: str) -> bool:
    """Checks to see whether WHICH_PATH is redundant relative to the global progress
    store. A path is considered to be redundant if it's not necessary to store it
    because a "further upstream" (shorter) path has already been checkpointed as
    complete in a way that makes it unnecessary to store data showing the WHICH_PATH
    is complete, because that upstream checkpoint-as-complete guarantees that
    WHICH_PATH will never be hit again in the first place. Returns True if
    WHICH_PATH is redundant in this sense, and False if it is not redundant.
    """
    for key in progress_data:
        if (which_path.startswith(key.rstrip('.'))) and (which_path != key):
            return True
    return False


def clean_progress_data() -> None:
    """Eliminate any checkpoints made redundant by the fact that a more-general
    progress checkpoint has been created.

    Note that, despite what that last paragraph said, we always also keep all strands
    of length 4 or less.
    """
    global progress_data
    begin = time.monotonic()
    pruned_dict = {k: v for k, v in progress_data.items() if (k.count('.') <= 4) or (not is_redundant_strand(k))}
    if pruned_dict != progress_data:
        tc.debug_print(f"  (pruned redundant data from the data store in {time.monotonic() - begin} seconds)", 3)
        progress_data = pruned_dict
    else:
        tc.debug_print(f"  (found now redundant data in the data store in {time.monotonic() - begin} seconds)", 3)


class MetadataWriter(threading.Thread):
    """A class whose objects can be created and run as threads to write data to disk
    while returning control to the main program thread. Keeps a queue of data
    waiting to be written; if new data comes in faster than it can be written out,
    older data is abandoned. Since we really only want to write the most recent data
    (plus the second-most-recent data as the .bak file), this helps to ensure
    that we do not queue up thousands of changes that are written only to be
    overwritten later.

    To use, create a new object, save a reference to it in the parent object, and
    call its run() method. Initializing the object requires a reference to the
    parent FrotzTerpConnection, plus the data to be written (a JSON-serialized stream).
    While the runner is running, data can be appended to its queue from the main
    program thread (or any other thread, really). The thread will keep running until
    the queue is empty, at which time the thread quits, blanking out the reference
    to it that the parent_window object holds. Creation and running of threads are
    abstracted away by the FrotzTerpConnection's .write_data() method, which handles the
    whole writing kerfuffle.
    """
    _max_writing_queue_length = 3      # Maximum number of to-write objects tracked.

    def __init__(self, parent: 'ATDTerpConnection',
                 data: typing.Optional[dict] = None):
        if data:
            assert isinstance(data, dict)
        threading.Thread.__init__(self)
        self.parent = parent
        self.to_write = list()          # Unlikely ever to grow all that long, so performance shouldn't be an issue.
        self.mutex = threading.Lock()
        if data:
            self.queue_for_write(data)

    def queue_for_write(self, data: typing.Dict[str, typing.Dict[str, typing.Union[int, float]]]) -> None:
        """Adds DATA (a structured progress record) to the to-write queue. We pickle it on
        adding, then unpickle right before writing, because we want a snapshot of the
        data when it enters the queue, not a reference to data that may continue to
        change, including right while we're serializing it to JSON. Queueing a pickled
        snapshot ensures we're getting a copy of the data, not a reference to it.

        JSON encoding is done by the _write method because it is relatively slow, and
        doing that in the background helps to keep the process responsive when dealing
        with large files.

        Along with the data itself and the completion notification function, we also
        queue a string representing the current time, which helps when monitoring the
        process during debugging.
        """
        tc.debug_print(f"    (queueing checkpoint data for saving, waiting to acquire lock ...)", min_level=4)
        with self.mutex:
            tc.debug_print(f"    (lock acquired ...)", min_level=5)

            # Not only is protocol 5 fastest on my system (for this data, under Python 3.9), it's almost twice as fast
            # as calling it protocol -1, even though -1 means "latest available," which is 5
            self.to_write.append((pickle.dumps(data, protocol=5), datetime.datetime.now().isoformat(' ')))
            if len(self.to_write) > self._max_writing_queue_length:  # Grown too long? Just keep most recent entries.
                sorted_queue = sorted(self.to_write, key=lambda i: i[1])
                tc.debug_print(f"      (pruning save queue ... there are {len(sorted_queue)} entries queued from {sorted_queue[0][2]} to {sorted_queue[-1][2]})", min_level=3)
                self.to_write = self.to_write[-self._max_writing_queue_length:]
                sorted_queue = sorted(self.to_write, key=lambda i: i[1])
                tc.debug_print(f"        (... sorted! Queue now contains {len(sorted_queue)} entries, queued from {sorted_queue[0][2]} to {sorted_queue[-1][2]})", min_level=3)
            tc.debug_print(f"    (checkpoint data queued)", min_level=4)

    def _write(self) -> None:
        """Writes the data that is waiting to be written to disk.

        # FIXME! Currently, we are just dumping the pickled data to disk, not
        serializing it to JSON, because this is much faster, and serializing to JSON
        is slow when we have lots of data in the dictionary. This makes the whole
        process of pickling, queuing, and writing from another thread rather
        unnecessary and overbuilt, but I'm leaving it for now, since we may go back
        later and it does no harm.
        """
        while self.to_write:
            fname = None
            while (fname is None) or (fname.exists()):
                fname = self.parent.progress_checkpoint_file.with_name(str(uuid.uuid4()))
            try:
                try:
                    with self.mutex:
                        data = self.to_write.pop(0)
                except (IndexError,):   # Shouldn't be popping from an empty list: we're the only thread removing data
                    continue            # from the to_write queue. Still, be careful anyway.
                tc.debug_print(f"    (writing individual checkpoint file with temporary name {fname})", min_level=4)
                with open(fname, 'wb') as metadata_file:
                    metadata_file.write(data[0])
                    # metadata_file.write(json.dumps(pickle.loads(data[0]), indent=2, default=str))
                if self.parent.progress_checkpoint_file.exists():
                    new_name = Path(str(self.parent.progress_checkpoint_file) + '.bak')
                    self.parent.progress_checkpoint_file.rename(new_name)
                fname.rename(self.parent.progress_checkpoint_file)
            except (Exception,) as errrr:
                tc.safe_print(f"Unable to write file during checkpointing save! The system said: {errrr}")
            finally:
                if fname.exists():  # If we got this far and the temp file still exists, delete it.
                    fname.unlink()
        tc.debug_print(f"    (all queued checkpoint files written!)", min_level=2)
        self.parent.checkpoint_writer = None

    def run(self) -> None:
        self._write()


class ATDTerpConnection(tc.FrotzTerpConnection):
    """Subclass that customizes FrotzTerpConnection for this particular game in order to
    accomplish the goals of this particular script.
    """
    # The superclass really only requires this to be a list, but in this class it
    # does double duty by using that list as keys to index additional data.
    room_list = {
        "balcony": {"hideable": True},
        "basement corridor": {"hideable": False},
        "basement equipment room": {"hideable": True},
        "basement landing": {"hideable": False},
        "conference room": {"hideable": True},
        "first floor corridor": {"hideable": True},
        "first floor equipment room": {"hideable": True},
        "foyer": {"hideable": False},
        "inside the prototype": {"hideable": False},
        "second floor corridor": {"hideable": True},
        "the deutsch laboratory": {"hideable": False},
        "upstairs landing": {"hideable": True},
    }

    rooms = tuple(room_list.keys())

    mistake_messages = tc.FrotzTerpConnection.mistake_messages + [
        "but it barely leaves a mark.",  "but the glass stays in place.", "but there's no water here",
        "error: overflow in", "error: unknown door status", "for example, with 'set timer to 30'.",
        "if you could do that", "is locked in place.", "is that the best you can", "it is not clear what",
        "nothing happens -- the button must be", "switching on the overhead lights would", "you lack the nerve",
        "that doesn't seem to be something", "that would scarcely", "that's not something you can",
        "the challenge can only be initiated in the first turn", "the challenge has already been initiated",
        "the only exit is", "the only exits are", "the prototype's control panel only accepts", "you have not yet set",
        "the slot emits a small beep and your card is rejected", "the switch clicks, but no light",
        "the window appears to be locked", "the window is already", "there is no obvious way to",
        "there is no way that you could tear them up in time.", "there is nothing here that you could",
        "there is nothing to", "there's not enough water", "there's nothing sensible", "you can't, since",
        "there's nothing suitable to drink", "you would achieve nothing", "this one closes of its own accord.",
        "to set the explosive device, you need to", "try as you might, none of", "you cannot attach the cable to",
        "until you complete the modifications.", "you would have to", "you are not strong enough to break",
        "you can hear nothing but", "you can see clearly enough in the gloom.", "you can't see anything of interest",
        "you cannot get the window open", "you cannot make out any", "you cannot open the door with",
        "you can\u2019t since", "you cannot see what",  "you cannot do that", "you discover nothing of interest",
        "you do not have the key", "you won't be able to", "you don't have anything heavy enough",
        "you don't need to worry about", "you'll have to say which", "your timer only accepts",
        "you will have to be more specific about", "you would need to be near the prototype",
        "you would need you id card to",
    ]

    failure_messages = tc.FrotzTerpConnection.failure_messages + [l.strip().casefold() for l in [
        '*** You have failed ***',]]
    success_messages = tc.FrotzTerpConnection.success_messages + [l.strip().casefold() for l in [
        '*** Success. Final, lasting success. ***',]]

    # Filesystem config options
    base_directory = Path("/home/patrick/Documents/programming/python_projects/IF utils/specific_games/ATD").resolve()
    working_directory = base_directory / 'working'
    progress_checkpoint_file = working_directory / 'progress.pkl'

    story_file_location = (base_directory / "[2004] All Things Devours/devours.z5").resolve()

    save_file_directory = working_directory / 'saves'
    successful_paths_directory = working_directory / 'successful_paths'
    logs_directory = working_directory / 'logs'

    inventory_answer_tag = "You are carrying:".casefold()

    def __init__(self):
        """Opens a connection to a 'terp process that plays ATD. Saves a reference to that
        process. Wraps its STDOUT stream in a nonblocking wrapper. Saves a reference to
        that wrapper. Initializes the command-history data structure. Does other setup.
        """
        tc.FrotzTerpConnection.__init__(self)
        self.checkpoint_writer = None

    def create_progress_checkpoint(self) -> None:
        """Update the dictionary that keeps track of which possible branches of the problem
        space we've already tried. If it's been at least minimum_checkpointing_interval
        seconds, also clean up redundant information in the progress data and write that
        updated dictionary to disk.
        """
        global progress_data
        global last_checkpoint_time

        progress_data[self.text_walkthrough] = {
            'dead ends': dead_ends,
            'successes': successes,
            'total moves': moves,
            'time': get_total_time(),
            'maximum walkthrough length': maximum_walkthrough_length,
        }

        if (datetime.datetime.now() - last_checkpoint_time).seconds >= minimum_checkpointing_interval:
            tc.debug_print("(preparing to save algorithm progress data.)", 2)
            clean_progress_data()

            try:
                self.checkpoint_writer.queue_for_write(data=progress_data)
            except (AttributeError,):       # self.checkpoint_writer is None? Create a new one.
                self.writer = MetadataWriter(parent=self, data=progress_data)
                self.writer.start()
            last_checkpoint_time = datetime.datetime.now()

    def _set_up(self) -> None:
        """Perform some additional checks before calling the superclass method.
        """
        self._validate_directory(self.successful_paths_directory, "successful paths")
        tc.FrotzTerpConnection._set_up(self)

    def _clean_up(self) -> None:
        tc.FrotzTerpConnection._clean_up(self)
        if self.checkpoint_writer:
            tc.debug_print("Waiting on checkpoint writer to finish writing checkpoints ...")
            self.checkpoint_writer.join()
            tc.debug_print("    ... all checkpoints written.")

    def evaluate_context(self, output: str,
                         command: str) -> typing.Dict[str, typing.Union[str, int, bool, Path, typing.List[str]]]:
        """Overrides the superclass method to scrape additional data from the 'terp
        output for data that is specifically meant to be gathered for ATD.

        Additional fields defined here:

          'time'        The ("objective," external) clock time at this point in the
                        story.
        """
        ret = tc.FrotzTerpConnection.evaluate_context(self, output, command)
        output_lines = [l.strip().casefold() for l in output.split('\n')]

        # Next, check to see what time it is, if we can tell. #FIXME! This is ATD-specific!
        for t in [l[l.rfind("4:"):].strip() for l in output_lines if '4:' in l]:        # Time is always 4:xx:yy AM.
            ret['time'] = t

        return ret


terp_proc = None        # we'll reassign this during setup.


def record_solution() -> None:
    """Record the details of a solution in a JSON file. Name it automatically using the
    current date and time and the current run time of the script.
    """
    # The ChainMap stores the steps in most-to-least-recent order, but we want to serialize them in the opposite order.
    solution_steps = list(reversed(terp_proc.context_history.maps))
    found = False
    while not found:
        # FIXME: add current run time to filename.
        p = terp_proc.successful_paths_directory / (datetime.datetime.now().isoformat().replace(':', '_') + '.json')
        found = not p.exists()
    p.write_text(json.dumps(solution_steps, default=str, indent=2, sort_keys=True))
    with tarfile.open(name=str(p).rstrip('json') + 'tar.bz2', mode='w:bz2') as save_file_archive:
        save_file_archive.add(os.path.relpath(p))       # Also add the JSON file, for completeness.
        for c in [m['checkpoint'] for m in terp_proc.context_history.maps if 'checkpoint' in m]:
            if c.exists():
                save_file_archive.add(os.path.relpath(c))
            else:
                tc.debug_print("Warning: unable to add non-existent file %s to archive!" % shlex.quote(str(c)), 2)


def make_moves(depth: int = 0) -> None:
    """Try a move. See if it loses. If not, see if it was useless ("a mistake", "a
    synonym for WAIT"). If either is true, just undo it and move on to the next
    command: there's no point in continuing if either is the case.

    Otherwise, check to see if we won. If we did, document the fact and move along
    to trying other moves to see how they do.

    If we didn't win, lose, or get told we made a mistake, the function calls itself
    again to make another set of moves. Along the way, it does the record-keeping
    that needs to happen for us to be able to report the steps that led to a
    success state, once we stumble into one. One way that it does this is by managing
    "context frames," summaries of the game state that are kept in a chain. Most
    information in them is stored "sparsely," i.e. only if it changed since the
    previous frame (the exception being the 'command' field, which is always filled
    in). These context frames are part of the global interpreter-program connection
    object and can be indexed like a dictionary to look at the current game state,
    or examined individually to see how the state has changed. Storing a "successful
    path" record involves storing each frame sequentially in a JSON file.
    Reconstructing the 'command' fields of each frame in the proper (i.e., reversed)
    order produces a walkthrough for the path in question.

    This function also causes in-game "save" checkpoints to be created for each
    frame automatically, as a side effect that occurs when evaluate_context() is
    running to interpret the game's output.

    Leave the DEPTH parameter set to zero when calling the function to start playing
    the game; the function uses this parameter internally to track how many commands
    deep we are. This is occasionally useful for debugging purposes, and has an
    effect on the visual printing of each step that occurs at debugging verbosity
    levels 3+.
    """
    global successes, dead_ends, moves, maximum_walkthrough_length

    if is_redundant_strand(terp_proc.text_walkthrough):      # If we've tracked that we've been down this path, skip it.
        return

    these_commands = list(all_commands.keys())

    # Make sure we've got a save file to restore from after we try commands.
    if 'checkpoint' not in terp_proc.context_history.maps[0]:
        terp_proc.context_history['checkpoint'] = terp_proc.save_terp_state()
    # Keep a copy of our starting state. Dict() to collapse the ChainMap to a flat state.
    # This data includes a reference to a save state that we'll restore to after every single move.
    starting_frame = dict(terp_proc.context_history)

    for c_num, c in enumerate(these_commands):
        if all_commands[c](c):  # check to see if we're allowed to try this command right now. If so ...
            try:                # make_single_move() produces a checkpoint that will be used by _unroll(), below.
                room_name = terp_proc.current_room
                new_context = terp_proc.make_single_move(c)
                move_result = "VICTORY!!" if new_context['success'] else ('mistake' if new_context['mistake'] else ('failure!' if new_context['failed'] else ''))
                tc.debug_print(' ' * depth + ('move: (%s, %s) -> %s' % (room_name, c.upper(), move_result)), 3)
                # Process the new context.
                if new_context['mistake']:
                    dead_ends += 1
                elif new_context['failed']:
                    dead_ends += 1
                elif new_context['success']:
                    tc.safe_print('Command %s won! Recording ...' % c)
                    record_solution()
                    successes += 1
                    time.sleep(5)   # Let THAT sit there on the debugging screen for a few seconds.
                else:               # If we didn't win, lose, or get told we made a mistake, make another move.
                    maximum_walkthrough_length = max(maximum_walkthrough_length, len(terp_proc.list_walkthrough))
                    make_moves(depth=1+depth)
            except Exception as errrr:
                terp_proc.document_problem("general_exception", data={'error': errrr, 'command': c})
                sys.exit(1)
            finally:
                moves += 1
                total = dead_ends + successes
                if (moves % 1000 == 0) or ((tc.verbosity >= 2) and (moves % 100 == 0)) or ((tc.verbosity >= 4) and (moves % 20 == 0)):
                    tc.safe_print(f"Explored {total} complete paths so far, making {moves} total moves in %.2f hours" % (get_total_time() / 3600))
                terp_proc._restore_terp_to_save_file(starting_frame['checkpoint'])
                terp_proc._drop_history_frame()
    if len(terp_proc.context_history.maps) % 4 == 0:
        terp_proc.create_progress_checkpoint()


def play_game() -> None:
    """Devour all the paths in All Things Devours. Make one set of moves, and the
    make_moves() routine will keep making new ones.
    """
    make_moves()


def processUSR1(*args, **kwargs) -> None:
    """Handle the USR1 signal by cycling through available debugging verbosity levels.
    """
    tc.verbosity = (tc.verbosity + 1) % (1 + tc.maximum_verbosity_level)
    tc.safe_print("\nDebugging verbosity changed to %d" % tc.verbosity)


def processUSR2(*args, **kwargs) -> None:
    """Handle the USR2 signal printing the current progress, then pausing for a moment."""
    tc.safe_print("\nCurrent path length is: %s" % len(terp_proc.list_walkthrough))
    tc.safe_print("Current path is:\n" + terp_proc.text_walkthrough + "\n\n")
    time.sleep(2)


def processSigInt(*args, **kwargs):
    """When ctrl-C is pushed or SIGINT is otherwise received, clean up gracefully.
    """
    try:
        tc.safe_print("Caught Ctrl-C or other SIGINT; cleaning up ...")
        terp_proc._definitely_quit()
        time.sleep(2)
    except NameError:           # If we're getting here without having set everything up, then just bail.
        pass
    tc.safe_print()
    sys.exit(0)


def interpret_command_line() -> None:
    """Sets global variables based on command-line parameters. Also handles other
    aspects of command-line processing, such as responding to --help.
    """
    tc.debug_print("  processing command-line arguments!", 2)
    parser = argparse.ArgumentParser(description=module_docstring)
    parser.add_argument('--verbose', '-v', action='count',
                        help="increase how chatty the script is about what it's doing")
    parser.add_argument('--quiet', '-q', action='count', help="decrease how chatty the script is about what it's doing")
    parser.add_argument('--script', action='store_true')
    args = vars(parser.parse_args())

    if args['script']:
        terp_proc.SCRIPT()              # We didn't start when its __init__() was called. Start now.
    tc.verbosity += args['verbose'] or 0
    tc.verbosity -= args['quiet'] or 0

    tc.debug_print('  command-line arguments are:' + pprint.pformat(args), 2)


def load_progress_data() -> None:
    """Sets global variables based on saved progress data from a previous run of the
    script, if there is any saved progress data from a previous run of the script.
    """
    global dead_ends, successes, script_run_start, moves, maximum_walkthrough_length
    global progress_data

    try:
        with open(terp_proc.progress_checkpoint_file, mode='rb') as pc_file:
            progress_data = pickle.load(pc_file)
            script_run_start = datetime.datetime.now() - datetime.timedelta(seconds=max([t['time'] for t in progress_data.values()]))
            dead_ends = max([t['dead ends'] for t in progress_data.values()])
            successes = max([t['successes'] for t in progress_data.values()])
            moves = max([t['total moves'] for t in progress_data.values()])
            maximum_walkthrough_length = max([t['maximum walkthrough length'] for t in progress_data.values()])
        tc.safe_print("\n\nSuccessfully loaded previous progress data!")
    except Exception as errr:                   # Everything was initialized up top, anyway.
        tc.safe_print("Can't restore progress data: starting from scratch!")
        tc.debug_print("Exception causing inability to read previous data: %s" % errr, 1)


def set_up() -> None:
    """Set up the many fiddly things that the experiment requires,but that aren't
    set up by the FrotzTerpConnection object itself.
    """
    global terp_proc

    tc.debug_print("setting up program run!", 2)

    signal.signal(signal.SIGUSR1, processUSR1)
    signal.signal(signal.SIGUSR2, processUSR2)
    signal.signal(signal.SIGINT, processSigInt)         # Force immediate exit on Ctrl-C, etc.
    tc.debug_print("  signal handlers installed!", 2)

    if len(sys.argv) > 1:
        interpret_command_line()
    else:
        tc.debug_print("  no command-line arguments!", 2)
    tc.debug_print('  final verbosity is: %d' % tc.verbosity, 2)

    terp_proc = ATDTerpConnection()
    load_progress_data()


def main():
    set_up()
    tc.safe_print("\n\n  successfully initiated connection to new 'terp! It said:\n\n" + terp_proc.repeat_last_output() + "\n\n")

    play_game()


# Some testing routines, never called by the main program code.
def experimental_save(data: bytes,
                      base_checkpoint_name: Path = ATDTerpConnection.progress_checkpoint_file,
                      pickle_protocol: int = -1,
                      use_bzip2: bool = True) -> Path:
    """A utility function to be called from the debugger. It is never used by the main
    code. It saves DATA to a compressed, pickled save file, pickled using
    PICKLE_PROTOCOL (the allowable values of which depend on the underlying Python
    version: under 3.8, possible values are 0 through 5. -1 means "highest protocol
    available." If USE_BZIP2 is True (the default), then bzip2 is used to compress
    the files; otherwise, gzip is used. BASE_CHECKPOINT_NAME is the location of the
    save file.

    DATA is already pickled with protocol -1 when it comes in, so it gets unpickled
    and repickled.

    Returns the pathname of the file created.
    """
    if use_bzip2:
        import bz2
        comp_func, ext = bz2.open, '.bz2'
    else:
        import gzip
        comp_func, ext = gzip.open, '.gz'

    fname = Path(str(ATDTerpConnection.progress_checkpoint_file) + str(pickle_protocol) + ext)
    with comp_func(fname, mode='wb') as datafile:
        pickle.dump(pickle.loads(data), datafile, protocol=pickle_protocol)

    return fname


def test_experimental_save() -> None:
    """Test harness to run all meaningful combinations of parameters on
    experimental_save, printing timing data to stdout along the way. Never called
    by the main program code.
    """
    import bz2, gzip        # So the first time we use each compression type, the call doesn't get penalized
    import time

    with open(ATDTerpConnection.progress_checkpoint_file, mode='rb') as pc_file:
        prog_data = pc_file.read()

    for prot in range(-1, 1+pickle.HIGHEST_PROTOCOL):
        for use_bz in (False, True):
            start = time.monotonic()
            fname = experimental_save(prog_data, Path('/tmp/test.pkl'), pickle_protocol=prot, use_bzip2=use_bz)
            print(f"\n\nUsed protocol {prot} and {'bzip2' if use_bz else 'gzip'}, took {time.monotonic() - start} seconds")
            print(f"  ... file is {os.path.getsize(fname)} bytes")


def test_pickle_protocol_speed() -> None:
    """Text harness to test pickling speed under different pickle protocols on my
    system, printing timing data to stdout along the way. Never called by the main
    program code.
    """
    import time
    with open(ATDTerpConnection.progress_checkpoint_file, mode='rb') as pc_file:
        prog_data = pc_file.read()

    for prot in range(-1, 1 + pickle.HIGHEST_PROTOCOL):
        start = time.monotonic()
        _ = pickle.loads(pickle.dumps(prog_data, prot))
        print(f"\n\nUsed protocol {prot}; serialized to memory in {time.monotonic() - start:.4f} seconds")



if __name__ == "__main__":
    if False:
        # test_experimental_save()
        test_pickle_protocol_speed()
        sys.exit()

    tc.safe_print("No self-test code in this module, sorry! explore_ATD.py is a wrapper that runs this code.")
    sys.exit(1)
