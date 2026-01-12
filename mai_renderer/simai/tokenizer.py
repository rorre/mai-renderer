from dataclasses import dataclass
from typing import Generator, Iterator, Literal, Protocol


class SimaiToken(Protocol):
    type: Literal["bpm", "division", "notes", "advance"]


@dataclass
class BPM(SimaiToken):
    value: float
    type: Literal["bpm"] = "bpm"  # type: ignore


@dataclass
class Division(SimaiToken):
    value: int
    type: Literal["division"] = "division"  # type: ignore


@dataclass
class NoteGroup(SimaiToken):
    value: str
    type: Literal["notes"] = "notes"  # type: ignore


@dataclass
class AdvanceTime(SimaiToken):
    type: Literal["advance"] = "advance"  # type: ignore


def _is_note_start(text: str, pos: int) -> bool:
    """Check if position starts a note or note group"""
    if pos >= len(text):
        return False
    char = text[pos]
    # Button notes (1-8, E for extra)
    if char in "12345678E":
        return True
    # Touch notes (A-E)
    if char in "ABCDE":
        return True
    return False


def tokenize_simai(simai_text: str) -> Iterator[SimaiToken]:
    """
    Tokenize Simai format note data according to official spec.

    Key elements:
    - (BPM) - Set BPM
    - {beats} - Set time division
    - , - Advance time by one beat unit
    - Note positions: 1-8 (8 buttons), A-E (touch areas)
    - Note modifiers: h (hold), slide marks (-^v<>Vpqszw), b (break), x (ex), f (fireworks), $ (star tap)
    - / - Separate notes in EACH (simultaneous notes)
    - || - Comment line

    Args:
        simai_text: The simai format chart text
        first_beat_time: Initial time offset in seconds

    Returns:
        List of SimaiToken
    """
    i = 0
    while i < len(simai_text):
        char = simai_text[i]

        # Track position
        if char == "\n":
            i += 1
            continue

        # Skip comments (||...)
        if char == "|" and i + 1 < len(simai_text) and simai_text[i + 1] == "|":
            while i < len(simai_text) and simai_text[i] != "\n":
                i += 1
            continue

        # Skip whitespace
        if char in " \t\r":
            i += 1
            continue

        # Parse BPM (120.5)
        if char == "(":
            i += 1
            bpm_str = ""
            while i < len(simai_text) and simai_text[i] != ")":
                bpm_str += simai_text[i]
                i += 1
            try:
                current_bpm = float(bpm_str)
                yield BPM(current_bpm)
            except ValueError:
                pass
            i += 1  # Skip ')'
            continue

        # Parse time division {4}
        if char == "{":
            i += 1
            beats_str = ""
            while i < len(simai_text) and simai_text[i] != "}":
                beats_str += simai_text[i]
                i += 1
            try:
                beats = int(beats_str)
                yield Division(beats)
            except ValueError:
                pass
            i += 1  # Skip '}'
            continue

        # Advance time (comma)
        if char == ",":
            yield AdvanceTime()
            i += 1
            continue

        # Check for end-of-difficulty marker (E followed by newline)
        if char == "E" and (i + 1 >= len(simai_text) or simai_text[i + 1] == "\n"):
            # This is end-of-difficulty, not a note - skip it
            i += 1
            continue

        # Parse note group
        if _is_note_start(simai_text, i):
            end_i = min(simai_text.index(",", i), simai_text.index("\n", i))
            simai_group = simai_text[i:end_i]
            yield NoteGroup(simai_group)
            i = end_i
            continue

        i += 1
