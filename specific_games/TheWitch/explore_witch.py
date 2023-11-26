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


import json
import os
from pathlib import Path
import typing

from mod import terp_connection as tc

witch_transcript_file = Path("/home/patrick/games/IF/competitions/[2023] IFComp 29/Games/The Witch/Transcript.txt")


class WitchConnection(tc.FrotzTerpConnection):
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

    def _generate_save_name(self) -> Path:
        """Generate a filename for an auto-save file from the 'terp. Can be overridden
        by subclasses. By default, just use a UUID4. Subclasses may want to generate
        more human-meaningful names.
        """
        try:
            return (self.save_file_directory / f"{len(self.context_history.maps):03d}")
        except (AttributeError,):
            return (self.save_file_directory / "000 - beginning")

    def _get_score_and_winnability(self, output_lines: typing.List[str]
                                   ) -> typing.Tuple[typing.Union[int, None], typing.Union[bool, None]]:
        """Returns a tuple (score, winnable), where score is the current game score
        and winnable is whether the game self-evaluates as winnable at that point.

        OUTPUT_LINES is assumed to already be in casefold case.

        Either component of the tuple will be None if we cannot get the answer from
        the 'terp.
        """
        score, winnable = None, None

        # the score appears in the location line. Let's find that line and dig the score out.
        for l in output_lines:
            if l.startswith(self.rooms):
                location_line = l
                components = [part for part in location_line.split() if part]
                if 'score:' not in components:
                    continue
                score_component = components[1 + components.index('score:')]
                try:
                    score = int(score_component.strip())
                    break
                except (IndexError,):
                    pass

        # OK, let's get the game's own evaluation of whether it's winnable at this point.
        score_text = self._get_score_text().strip().casefold()
        if "the game is winnable from this point" in score_text:
            winnable = True
        elif "game is *not* winnable from this point" in score_text:
            winnable = False

        return score, winnable

    def evaluate_context(self, output: str,
                         command: str) -> typing.Dict[str, typing.Union[str, int, bool, Path, typing.List[str]]]:
        """Overrides the superclass method to scrape additional data from the 'terp
        output for data that is specifically meant to be gathered for The Witch.

        Additional fields defined here:

          'score'       The current game score.
          'winnable'    Whether the game self-evaluates as winnable.
        """
        ret = tc.FrotzTerpConnection.evaluate_context(self, output, command)
        output_lines = [l.strip().casefold() for l in output.split('\n')]

        # Check to see what time it is, if we can tell.
        ret['score'], ret['winnable'] = self._get_score_and_winnability(output_lines)

        return ret


terp = WitchConnection()

with open(witch_transcript_file, mode='rt', encoding='utf-8') as trans_file:
    supplied_transcript = trans_file.readlines()

commands = [l.strip().strip('>').strip() for l in supplied_transcript if l.strip().startswith('>')]

for c in commands:
    tc.safe_print(f"\n\n> {c}\n")
    tc.safe_print(terp.make_single_move(c)['output'])

with open(terp.base_directory / 'game log.json', mode='wt', encoding='utf-8') as json_file:
    data = list()
    while terp.context_history.maps:
        data = data + [dict(terp.context_history)]
        terp.context_history.maps = terp.context_history.maps[1:]
    json_file.write(json.dumps(list(reversed(data)), ensure_ascii=True, indent=2, default=str, sort_keys=True))
