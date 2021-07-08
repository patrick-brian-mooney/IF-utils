# IF-utils
Small collection of utilities related to interactive fiction.

## `all_lowercase_names.py`
Converts all filename extensions in a directory to lowercase, after first checking that doing so will not clobber any existing files. This is occasionally useful for Linux users trying to play AGT games in `agility`.

Usage: `all_lowercase_names.py [dirname]`. If `dirname` is not specified, operates on the current working directory.

## `ap2zc.py`
Extracts the Infocom story files (usually .z3 or .z5) from raw (256-byte sector) Apple II disk images.

Usage: `ap2zc.py INPUT_FILE_NAME`

## `text_rotate.py`
Given a phrase, transforms it as ROT-1, ROT-2, ROT-3, ... ROT-25, to help with rotational decoding.

Usage: `text_rotate.py "A phrase to transform"`

## `check_anagram.py`

Checks to see if two (or more) phrases are anagrams of each other.

Usage: `check_anagram.py "a phrase" "another phrase" [...]`


## `transcript_utils/visual_transcript/`
A series of scripts intended to help process postprocess screencast videos of textual IF when standard transcripting is not possible. Run in numerical order to create a series of frames as `.png` files that have had duplicate frames largely removed from short sequences.


## `specific_games/`
A set of folders contains scripts that do various things with specific games. See their own README files for more info.

<footer>This file last updated 17 Sept 2019.</footer>