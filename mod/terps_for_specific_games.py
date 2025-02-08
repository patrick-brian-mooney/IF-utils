#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A collection of subclasses of the TerpConnection classes, each specialized (or
semi-specialized) for interacting with specific games.
"""
from pathlib import Path

from mod import terp_connection as tc

if __name__ == "__main__":
    import sys
    print("Sorry, no self-test code here!")
    sys.exit(1)


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

    inventory_answer_tag = "You are carrying:".casefold()

    # Filesystem config options
    base_directory = Path("/home/patrick/Documents/programming/python_projects/IF utils/specific_games/ATD").resolve()
    working_directory = base_directory / 'working'

    story_file_location = (base_directory / "[2004] All Things Devours/devours.z5").resolve()

    save_file_directory = working_directory / 'saves'
    successful_paths_directory = working_directory / 'successful_paths'
    logs_directory = working_directory / 'logs'
