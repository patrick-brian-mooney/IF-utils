#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run through the supplied transcript of *The Witch*, an IFComp 2023 game by
Charles Moore, Jr. I haven't been able to finish the game even by following the
walkthrough closely, so I've written this quick hack to follow it exactly and
see whether that works.

This script is copyright 2023 by Patrick Mooney. It is released under the
GPL, either version 3 or (at your option) any later version. See the file
LICENSE for a copy of this license.
"""


import os
from pathlib import Path

import terp_connection as tc


witch_transcript_file = Path("/home/patrick/games/IF/competitions/[2023] IFComp 29/Games/The Witch/Transcript.txt")


class WitchConnection(tc.TerpConnection):
    story_file_location = Path("/home/patrick/games/IF/competitions/[2023] IFComp 29/Games/The Witch/the_witch_1_230924.z5")
    inventory_answer_tag = "you're carrying:"

    rooms = tuple(l.strip().casefold() for l in ("Adagio's Cottage", "Adit", "Along the Stream", "Among the Chairs",
                                                 "Among the Pines", "Among the Rocks", "Back Garden", "Base of Tree",
                                                 "Base of White Tree", "Bottom of Mountain", "Chamber", "Clearing",
                                                 "Courtyard", "Creekside Clearing", "Dark Path", "Eastern Bank",
                                                 "East of Village", "Forest Path", "Great Hall", "Greenhouse",
                                                 "Hallway", "Higher Up a Tree", "In a Peach Tree", "In the Creek",
                                                 "In the Moat", "In the Mountain", "In the Owl's Den", "In the Tree",
                                                 "In the Tree Top", "Jorgen's Cottage", "Junction", "Milpo's Cottage",
                                                 "Mine Entrance", "Narrow Path", "Outside Castle", "Outside Greenhouse",
                                                 "Outside the Chairlift", "Outside the Millhouse", "Palace Walk",
                                                 "Pulcher's Yard", "Royal Bakery", "Royal Bedroom", "Royal Treasury",
                                                 "Scenic Vista", "Side Yard", "Stairs", "Study", "The Birkles' Cottage",
                                                 "The Millhouse", "Up a Tree", "Village Walk", "Western Bank",
                                                 "Western Edge of Town", "Western Path", "Widow's Cottage",
                                                 "Your Cottage", ))

    base_directory = Path(os.path.dirname(__file__)).resolve()
    working_directory = base_directory / 'working'
    save_file_directory = working_directory / 'saves'
    logs_directory = working_directory / 'logs'


terp = WitchConnection()

with open(witch_transcript_file, mode='rt', encoding='utf-8') as trans_file:
    supplied_transcript = trans_file.readlines()

commands = [l.strip().strip('>').strip() for l in supplied_transcript if l.strip().startswith('>')]

for c in commands:
    tc.safe_print(f"> {c}\n")
    tc.safe_print(terp.process_command_and_return_output(c))
