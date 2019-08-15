# IF-utils
Small collection of utilities related to interactive fiction.

## ap2zc.py
Extracts the Infocom story files (usually .z3 or .z5) from raw (256-byte sector) Apple II disk images. Usage: `ap2zc.py INPUT_FILE_NAME`

## visual_transcript_*.py
A series of scripts intended to help process postprocess screencast videos of textual IF when standard transcripting is not possible. Run in numerical order to create a series of frames as `.png` files that have had duplicate frames largely removed from short sequences.