#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Helper code for guessing words in the hacking mini-game in Fred Snyder's
Focal Shift, an entry in IFComp 2024. This mini-game gives you eight (or 24?)
tries to guess a six-letter word, giving feedback after each guess whether the
letter is each position was correct, (alphabetically) too high, or
(alphabetically) too low. This is based loosely on my Wordle-related code,
which can be found at https://github.com/patrick-brian-mooney/wordle.

This script is part of Patrick Mooney's collection of interactive fiction-
related utilities, and is copyright 2024 by Patrick Mooney. It is released
under the GPL, either version 3 or (at your option) any later version. See the
file LICENSE for a copy of this license.
"""

import collections

from pathlib import Path
from typing import Container, List, Tuple

import re

import sys


word_list_file = Path('/home/patrick/Documents/programming/resources/word-lists/dwyl/words_alpha.txt')

word_list_text = word_list_file.read_text()
known_english_words = [w.strip() for w in word_list_text.split('\n') if w.strip()]
known_six_letter_words = {w for w in known_english_words if len(w) == 6}
word_list_text = '\n'.join(sorted(known_six_letter_words))     # these are the only words we're ever interested in


def get_best_guess(constraints: List[Tuple[str, ...]],
                   exclude: Container[str] = (),
                   verbose: bool = True) -> List[str]:
    """The 'best guess' is considered to be the legal, actual-word guess where each
    letter falls closest to the middle of the range of allowable characters, thereby
    narrowing the range for each letter as much as possible with each move.

    Other strategies are possible, but this seems like a fairly good one.
    """
    def allowable(word: str) -> bool:
        """Returns True if the word is a plausible guess (i.e., if the already-known
        constraints mean it could possibly be the solution), or False if the already-
        known constraints rule it out.
        """
        for char, boundaries in zip(word, constraints):
            if not (boundaries[0] <= char <= boundaries[1]):
                return False
        return True

    def score_of(word: str) -> float:
        """The 'score" for a guess is a measure of how far each character deviates from the
        midpoint of the possible range. Lower scores are better. We derive the score by
        multiplying the "distance" of each letter of a word from the midpoint of the
        allowable range for that character position. The "distance" is one more than the
        number of letters between that character and the allowable midpoint; we add one
        to the (raw) distance because otherwise any character that happens to exactly
        hit the midpoint letter has a zero distance, which drops the score for the
        entire word to the lowest possible score of zero, which is not a good thing.
        """
        score = 1
        for pos, c in enumerate(word):
            score *= (1 + abs(ord(c) - middles[pos]))
        return score

    middles = [(ord(i[1])-ord(i[0]))/2 + ord(i[0]) for i in constraints]
    scores = collections.defaultdict(list)
    for word in (w for w in known_six_letter_words if w not in exclude):
        if allowable(word):
            scores[score_of(word)].append(word)
    lowest_score = min(scores.keys())
    if verbose:
        print(f"Examined {len(known_six_letter_words)} words, worst score was  {max(scores.keys())}, best score was"
              f" {lowest_score}. {len(scores[lowest_score])} guess(es) had the low score.")
    return scores[lowest_score]


def further_constrain(constraints: List[Tuple[str, ...]],
                      guess: str,
                      feedback: str) -> List[Tuple[str, str]]:
    """Given a list of pre-existing CONSTRAINTS, the GUESS the user most recently
    made, the GUESS the user most recently made, and the FEEDBACK that the system
    provided, returns a new set of constraints that restricts the possibility space
    for solutions at least as much (and hopefully more), based on the information
    that the machine revealed in the response to the current guess.

    CONSTRAINTS is a list of six tuples, where each tuple is of the format
        (lowest possible letter, highest possible letter); bounds are inclusive.

    FEEDBACK is a string where each character is (a) a letter, indicating that that
    letter has been found definitively for that position; or (b) a - (minus sign),
    indicating that the correct letter for that position is lower (earlier in the
    alphabet) than the letter in that position in the player's guess was; or else
    (c) + (a plus sign), indicating that the correct letter for that position is
    higher than the letter in that position in the player's guess.
    """
    for i, ((lower, upper), g_char, f_char) in enumerate(zip(constraints, guess.lower().strip(), feedback.strip())):
        if f_char not in '+-' and not f_char.isalpha():
            raise ValueError(f"Feedback string {feedback} contains character {f_char}, which is not valid!")
        if f_char.isalpha():
            constraints[i] = (f_char, f_char)
        elif f_char == "-":     # we have an upper bound on the character in this position, possibly lower than before.
            constraints[i] = (lower, min(g_char, upper))
        else:                   # f_char is "+"; we have found a lower bound.
            constraints[i] = (max (g_char, lower), upper)

    return constraints


def hack() -> None:
    constraints = [('a', 'z') for i in range (1, 7)]
    max_tries = int(input("Number of attempts allowed? "))
    for i in range(1, 1+max_tries):
        exclusions = list()
        print(f'\n\n\nGuess #{i}')
        consent = None
        while not consent:
            rec = get_best_guess(constraints, exclusions)
            print(f"Recommendations: {rec}")
            while consent not in ['y', 'n']:
                consent = input("Reject these suggestions and try again? [Y/N] ").strip().casefold()
            if consent == 'y':
                exclusions.extend(rec)
                consent = None

        guess = input("\nYour guess? ")
        feedback = None
        while feedback is None:
            feedback = input("Was it successful? [Y/N] ")
            if feedback.strip().casefold()[0] not in {'n', 'y'}:
                feedback = None
            if feedback.strip().casefold()[0] == 'y':
                print("Excellent!")
                sys.exit()

        feedback = input("Feedback from machine? ").strip()
        constraints = further_constrain(constraints, guess, feedback)


if __name__ == "__main__":
    hack()

