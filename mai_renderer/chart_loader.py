"""
Loads maidata.txt chart files and parses them into a structured format.
Follows the simai notation specification: https://w.atwiki.jp/simai/pages/1003.html
"""

from dataclasses import dataclass, field
from typing import Optional, List
import re


@dataclass
class NoteData:
    """Represents a single note in the chart"""

    note_type: str  # 'tap', 'hold', 'slide', 'touch', 'touch_hold'
    position: int  # 1-8 for buttons, 0 for extra, for touch: sensor position
    note_content: str = ""  # Original simai notation string (e.g., "1", "2h[3:4]", "3-5[8:3]")
    hold_time: float = 0.0  # For hold notes and touch_hold notes
    is_break: bool = False  # b Break tap note
    is_ex: bool = False  # x EX note
    is_hanabi: bool = False  # Fireworks effect
    is_star_tap: bool = False  # $ notation for star-shaped tap
    is_fake_rotate: bool = False  # $$ for rotating star-shaped tap
    is_no_slide_head: bool = False  # ! or ? for slides without approaching star
    is_slide_no_head_fade: bool = False  # ? specifically (fade in)
    is_slide_break: bool = False  # Break on slide body (vs break on star head)
    slide_start_time: float = 0.0  # For slide notes
    slide_time: float = 0.0  # The slide time from start to end
    slide_wait_time: float = 0.0  # Waiting time before slide sound plays
    slide_end_position: int = 0  # For slide notes: destination position
    slide_direction: str = ""  # Slide direction character: - ^ v < > V p q s z w
    touch_area: str = ""  # For touch notes: A, B, C, D, E


@dataclass
class TimingPoint:
    """Represents a timing point (note group) in the chart"""

    time: float  # Time in seconds
    bpm: float
    notes: List[NoteData] = field(default_factory=list)
    raw_text_position_y: int = 0
    raw_text_position_x: int = 0


@dataclass
class ChartMetadata:
    """Metadata about the chart"""

    title: str = "default"
    artist: str = "default"
    designer: str = "default"
    first_beat_time: float = 0.0  # Time in seconds before first beat
    levels: List[str] = field(default_factory=lambda: [""] * 7)
    other_commands: str = ""


@dataclass
class Chart:
    """Complete chart data"""

    metadata: ChartMetadata
    # difficulty_charts: dict mapping difficulty index (0-6) to List[TimingPoint]
    difficulty_charts: dict[int, list[TimingPoint]] = field(default_factory=dict)


class ChartLoader:
    """Loads and parses maidata.txt files following simai notation spec"""

    @staticmethod
    def load_chart(filepath: str) -> Chart:
        """
        Load a maidata.txt file

        Args:
            filepath: Path to maidata.txt

        Returns:
            Chart object containing all parsed data
        """
        with open(filepath, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        metadata = ChartMetadata()
        chart = Chart(metadata=metadata)

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Parse metadata
            if line.startswith("&title="):
                metadata.title = ChartLoader._get_value(line)
                i += 1
                continue

            if line.startswith("&artist="):
                metadata.artist = ChartLoader._get_value(line)
                i += 1
                continue

            if line.startswith("&des="):
                metadata.designer = ChartLoader._get_value(line)
                i += 1
                continue

            if line.startswith("&first="):
                metadata.first_beat_time = float(ChartLoader._get_value(line))
                i += 1
                continue

            if line.startswith("&lv_"):
                # Parse level
                match = re.match(r"&lv_(\d)=(.+)", line)
                if match:
                    level_idx = int(match.group(1)) - 1
                    if 0 <= level_idx < 7:
                        metadata.levels[level_idx] = match.group(2)
                i += 1
                continue

            if line.startswith("&inote_"):
                # Parse chart notes for a specific difficulty
                match = re.match(r"&inote_(\d)=", line)
                if match:
                    diff_idx = int(match.group(1)) - 1  # Convert 1-indexed to 0-indexed
                    chart_text = ChartLoader._get_value(line) + "\n"
                    i += 1
                    # Read until next metadata line
                    while i < len(lines):
                        if lines[i].startswith("&"):
                            break
                        chart_text += lines[i]
                        i += 1

                    # Parse the notes
                    timing_points = ChartLoader._parse_simai(chart_text, metadata.first_beat_time)

                    # Store by difficulty index
                    if 0 <= diff_idx < 7:
                        chart.difficulty_charts[diff_idx] = timing_points
                continue

            if line.startswith("&"):
                # Other metadata
                metadata.other_commands += line.strip() + "\n"

            i += 1

        return chart

    @staticmethod
    def _get_value(line: str) -> str:
        """Extract value from metadata line"""
        idx = line.find("=")
        if idx >= 0:
            return line[idx + 1 :]
        return ""

    @staticmethod
    def _parse_simai(simai_text: str, first_beat_time: float) -> List[TimingPoint]:
        """
        Parse Simai format note data according to official spec.

        Key elements:
        - (BPM) - Set BPM
        - {beats} - Set time division
        - , - Advance time by one beat unit
        - Note positions: 1-8 (8 buttons), E (extra/right side), A-E (touch areas)
        - Note modifiers: h (hold), slide marks (-^v<>Vpqszw), b (break), x (ex), f (fireworks), $ (star tap)
        - / - Separate notes in EACH (simultaneous notes)
        - || - Comment line

        Args:
            simai_text: The simai format chart text
            first_beat_time: Initial time offset in seconds

        Returns:
            List of TimingPoint objects
        """
        timing_points = []
        current_bpm = 120.0
        current_time = first_beat_time
        beats = 4  # Time division
        y_pos = 0
        x_pos = 0

        i = 0
        while i < len(simai_text):
            char = simai_text[i]

            # Track position
            if char == "\n":
                y_pos += 1
                x_pos = 0
                i += 1
                continue

            x_pos += 1

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
                except ValueError:
                    pass
                i += 1  # Skip '}'
                continue

            # Advance time (comma)
            if char == ",":
                current_time += 60.0 / current_bpm * (4.0 / beats)
                i += 1
                continue

            # Check for end-of-difficulty marker (E followed by newline)
            if char == "E" and (i + 1 >= len(simai_text) or simai_text[i + 1] == "\n"):
                # This is end-of-difficulty, not a note - skip it
                i += 1
                continue

            # Parse note group
            if ChartLoader._is_note_start(simai_text, i):
                note_group_start_x = x_pos - 1
                notes, new_i = ChartLoader._parse_note_group(simai_text, i, current_bpm)

                if notes:
                    timing_point = TimingPoint(
                        time=current_time,
                        bpm=current_bpm,
                        notes=notes,
                        raw_text_position_y=y_pos,
                        raw_text_position_x=note_group_start_x,
                    )
                    timing_points.append(timing_point)

                i = new_i
                continue

            i += 1

        return timing_points

    @staticmethod
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

    @staticmethod
    def _parse_note_group(simai_text: str, start_pos: int, current_bpm: float) -> tuple:
        """
        Parse a note group which may contain:
        - Single note: 1, 2h[3:4], A5f, etc.
        - EACH (multiple notes separated by /): 1/8h[2:1], 2-5[8:3]/3-6[8:3], etc.

        Returns:
            Tuple of (notes list, new position in text)
        """
        notes = []
        i = start_pos

        # Check if this is an EACH group (contains /)
        # We need to look ahead to see if there's a / before the comma
        lookahead = i
        paren_depth = 0
        has_slash = False
        while lookahead < len(simai_text) and simai_text[lookahead] not in ",\n":
            if simai_text[lookahead] == "[":
                paren_depth += 1
            elif simai_text[lookahead] == "]":
                paren_depth -= 1
            elif simai_text[lookahead] == "/" and paren_depth == 0:
                has_slash = True
                break
            lookahead += 1

        if has_slash:
            # EACH notation
            while i < len(simai_text) and simai_text[i] not in ",\n":
                if simai_text[i] == "/":
                    i += 1
                    continue
                if simai_text[i] in " \t\r":
                    i += 1
                    continue

                # Parse single note (may return list for multiple slides)
                parsed_notes, new_i = ChartLoader._process_single_group(simai_text, i, current_bpm)
                if parsed_notes:
                    # Handle both single notes and lists of notes
                    if isinstance(parsed_notes, list):
                        notes.extend(parsed_notes)
                    else:
                        notes.append(parsed_notes)
                    i = new_i
                else:
                    break
        else:
            # Single note (may contain pseudo-EACH with backticks)
            # Extract everything until comma
            group_end = i
            while group_end < len(simai_text) and simai_text[group_end] not in ",\n":
                group_end += 1

            group_text = simai_text[i:group_end]

            # Split by backticks for pseudo-EACH
            segments = group_text.split("`")
            for segment in segments:
                segment = segment.strip()
                if segment:
                    # Parse note (may return list for multiple slides)
                    parsed = ChartLoader._parse_note(segment, current_bpm)
                    if parsed:
                        if isinstance(parsed, list):
                            notes.extend(parsed)
                        else:
                            notes.append(parsed)

            i = group_end

        return notes, i

    @staticmethod
    def _process_single_group(simai_text: str, start_pos: int, current_bpm: float) -> tuple:
        """
        Parse a single note from position in simai_text.
        Examples: 1, 2h[3:4], 3-5[8:3], A5f, Chf[1:2], 4$, 5$$, 5bx, etc.

        Returns:
            Tuple of (list of NoteData objects, new position in original text)

        For multiple slides (with * separator), returns a list where:
        - First slide is normal (with star tap head)
        - Subsequent slides are marked with is_no_slide_head = True
        """
        # Extract note text from simai_text until we hit a delimiter
        i = start_pos
        note_text = ""

        while i < len(simai_text) and simai_text[i] not in ",/\n ":
            note_text += simai_text[i]
            i += 1

        if note_text:
            notes = ChartLoader._parse_note(note_text, current_bpm)
            return notes, i
        return None, i

    @staticmethod
    def _parse_note(note_str: str, current_bpm: float) -> Optional:
        """
        Parse a note string and expand multiple slides into separate notes.

        For multiple slides (with * separator), returns a list where:
        - First slide is normal (with star tap head)
        - Subsequent slides are marked with is_no_slide_head = True

        For other notes, returns a single NoteData or None.

        Args:
            note_str: The note string to parse
            current_bpm: Current BPM for timing calculation

        Returns:
            Single NoteData, list of NoteData objects for multiple slides, or None
        """
        # First, check if this is a slide with multiple tracks
        if "-" in note_str or any(c in note_str for c in "^v<>Vpqszw"):
            # Might be a slide - check for * separator
            if "*" in note_str:
                return ChartLoader._parse_multiple_slides(note_str, current_bpm)

        # Not a multiple slide, parse normally
        return ChartLoader._parse_note_from_string(note_str, current_bpm)

    @staticmethod
    def _parse_multiple_slides(note_str: str, current_bpm: float) -> Optional[List[NoteData]]:
        """
        Parse a multiple slide notation and return a list of slide notes.

        First slide: normal (with star tap head)
        Subsequent slides: marked with is_no_slide_head = True

        Example: "1-4[4:3]*-6[8:5]" returns:
        - Slide 1: pos=1, direction=-, end=4, time=4:3, no_head=False
        - Slide 2: pos=1, direction=-, end=6, time=8:5, no_head=True

        Args:
            note_str: The note string with * separators
            current_bpm: Current BPM

        Returns:
            List of NoteData objects, or None if parsing fails
        """
        if "*" not in note_str:
            raise ValueError("Multiple slides not does not exist for the value:", note_str)

        # Parse the first slide normally
        first_slide = ChartLoader._parse_note_from_string(note_str, current_bpm)
        if not first_slide or first_slide.note_type != "slide":
            raise ValueError("Invalid multiple slides:", note_str)

        slides = [first_slide]

        # Now parse subsequent slides from the same string
        # Find all * separators and extract subsequent slide definitions
        parts = note_str.split("*")
        if len(parts) <= 1:
            return slides  # No * found, shouldn't happen

        # Get the position of the first slide
        base_position = first_slide.position
        base_wait_time = first_slide.slide_wait_time
        first_slide.note_content = parts[0]

        # Parse each subsequent slide
        for part in parts[1:]:
            part = part.strip()
            if not part:
                continue

            # Parse the slide track part (e.g., "-6[8:5]")
            # Extract end position and timing
            slide_duration, slide_wait = ChartLoader._parse_slide_track_from_string(part, current_bpm)

            if slide_duration is not None:
                # Create a new slide note
                subsequent_slide = NoteData(
                    note_type="slide",
                    position=base_position,
                    note_content=str(base_position) + part,
                    slide_time=slide_duration,
                    slide_wait_time=base_wait_time,
                    slide_end_position=ChartLoader._extract_end_position(part),
                    is_no_slide_head=True,  # Subsequent slides have no head
                )
                slides.append(subsequent_slide)

        return slides if len(slides) > 1 else None

    @staticmethod
    def _parse_slide_track_from_string(track_str: str, current_bpm: float) -> tuple:
        """
        Parse a slide track string (without position) and return (duration, wait_time).

        Example: "-6[8:5]" -> (duration, wait_time)

        Args:
            track_str: Slide track string like "-6[8:5]" or "q7[2:1]"
            current_bpm: Current BPM

        Returns:
            Tuple of (slide_duration, wait_time) or (None, None) if parsing fails
        """
        # Find the bracket
        bracket_pos = track_str.find("[")
        if bracket_pos == -1:
            # No bracket, just the shape and end position
            return 0.0, 60.0 / current_bpm

        # Extract timing bracket
        bracket_end = track_str.find("]", bracket_pos)
        if bracket_end == -1:
            return None, None

        timing_str = track_str[bracket_pos + 1 : bracket_end]

        try:
            slide_duration, wait_time = ChartLoader._parse_slide_timing(timing_str, current_bpm)
            return slide_duration, wait_time
        except ValueError:
            return None, None

    @staticmethod
    def _extract_end_position(track_str: str) -> int:
        """
        Extract the end position from a slide track string.

        Example: "-6[8:5]" -> 6
        Example: "q7[2:1]" -> 7

        Args:
            track_str: Slide track string

        Returns:
            End position or 0 if not found
        """
        # Find the last digit before the bracket
        bracket_pos = track_str.find("[")
        if bracket_pos == -1:
            # No bracket, find the last digit
            bracket_pos = len(track_str)

        last_digit = 0
        for i in range(bracket_pos):
            if track_str[i].isdigit():
                last_digit = int(track_str[i])

        return last_digit

    @staticmethod
    def _parse_note_from_string(note_str: str, current_bpm: float) -> Optional[NoteData]:
        """
        Parse a complete note string like "1", "2h[3:4]", "3-5[8:3]", "A5f", etc.
        """
        note_str = note_str.strip()
        if not note_str:
            return None

        note = NoteData(note_type="tap", position=0, note_content=note_str)
        i = 0

        # Determine note type: button (1-8, E) or touch (A-E)
        if note_str[i] in "ABCDE":
            # Touch note
            note.touch_area = note_str[i]
            i += 1

            # Parse optional touch position (B7, E8, etc.)
            while i < len(note_str) and note_str[i].isdigit():
                note.position = note.position * 10 + int(note_str[i])
                i += 1

            note.note_type = "touch"
        else:
            # Button note
            note.position = int(note_str[i])
            i += 1

        # Parse modifiers in any order: h, b, x, f, $, @, !, ?
        has_hold = False
        has_slide = False
        dollar_count = 0

        while i < len(note_str) and note_str[i] != "[":
            char = note_str[i]

            if char == "h":
                # Hold modifier
                has_hold = True
                if note.note_type == "touch":
                    note.note_type = "touch_hold"
                else:
                    note.note_type = "hold"
                i += 1

            elif char == "b":
                # Break modifier
                # For slides, check if this is the final 'b' after all brackets
                # For other notes, process it here
                if note.note_type == "slide":
                    # This should only be set after parsing slides, but mark it anyway
                    # The final 'b' check happens in _skip_past_all_slide_tracks
                    note.is_slide_break = True
                else:
                    note.is_break = True
                i += 1

            elif char == "x":
                # EX modifier
                note.is_ex = True
                i += 1

            elif char == "f":
                # Fireworks modifier
                note.is_hanabi = True
                i += 1

            elif char == "$":
                # Star-shaped tap (can be single or double $$)
                dollar_count += 1
                note.is_star_tap = True
                if dollar_count == 2:
                    note.is_fake_rotate = True
                i += 1

            elif char == "@":
                # @ modifier: normal tap (cancels star-shaped tap from slide)
                # This is for slides: 1@-5[8:1] means normal tap at 1
                i += 1

            elif char == "!" or char == "?":
                # Slide without approaching star
                note.is_no_slide_head = True
                if char == "?":
                    note.is_slide_no_head_fade = True
                i += 1

            elif char == "-" or char in "^v<>Vpqszw":
                # Slide mark - rest of notation is slide definition
                # Handle both simple slides and multiple/chaining slides
                has_slide = True
                note.note_type = "slide"

                # Parse the first slide track
                first_track_duration, first_track_wait, end_pos = ChartLoader._parse_slide_track(
                    note_str, i, current_bpm
                )

                # For now, we store the first track's values
                # In a full implementation with multiple tracks, we'd store all tracks
                note.slide_time = first_track_duration
                note.slide_wait_time = first_track_wait
                note.slide_end_position = end_pos

                # Find where the slide parsing ends (after the bracket and any modifiers)
                # We need to skip past all slide tracks and find the final position
                i, is_break = ChartLoader._skip_past_all_slide_tracks(note_str, i)

                # Set break flag if found
                if is_break:
                    note.is_slide_break = True

                break

            else:
                i += 1

        # Parse hold duration if needed
        if has_hold and not has_slide and i < len(note_str) and note_str[i] == "[":
            i += 1
            hold_str = ""
            while i < len(note_str) and note_str[i] != "]":
                hold_str += note_str[i]
                i += 1

            try:
                note.hold_time = ChartLoader._parse_beat_value(hold_str, current_bpm)
            except ValueError:
                note.hold_time = 0.0

            # Skip the ]
            if i < len(note_str):
                i += 1

        # Check for break modifier after bracket (for holds and other notes)
        if i < len(note_str) and note_str[i] == "b":
            if note.note_type == "hold" or note.note_type == "touch_hold":
                note.is_break = True
            elif note.note_type != "slide":
                # For taps and touches, set break flag
                note.is_break = True

        # Default hold time for hold notes without duration bracket
        if has_hold and note.hold_time == 0.0:
            # Pseudo hold: instant judgment, treated as [1280:1] internally
            note.hold_time = ChartLoader._parse_beat_value("1280:1", current_bpm)

        return note

    @staticmethod
    def _parse_slide_track(note_str: str, start_pos: int, current_bpm: float) -> tuple:
        """
        Parse a single slide track from a note string.

        A slide track looks like: -4[8:3] or ^5[160#8:3]
        This is the direction character, optional shape characters, end position, and timing bracket.

        Args:
            note_str: The full note string
            start_pos: Position in note_str where the slide direction character is
            current_bpm: Current BPM for timing calculation

        Returns:
            Tuple of (slide_duration, wait_time, end_position) in seconds
        """
        i = start_pos
        end_position = 0

        # Skip past direction and shape characters
        if i < len(note_str) and note_str[i] in "-^v<>Vpqszw":
            i += 1

        # Skip any additional shape characters (e.g., 'pp' for grand p-shape, 'qq' for grand q-shape)
        while i < len(note_str) and note_str[i] in "pqVvzs":
            i += 1

        # Find the end position (last digit before [ or * or end of string)
        last_digit_pos = -1
        temp_i = i
        while temp_i < len(note_str) and note_str[temp_i] not in "[*":
            if note_str[temp_i].isdigit():
                last_digit_pos = temp_i
                end_position = int(note_str[temp_i])
            temp_i += 1

        # Skip to after the end position
        if last_digit_pos >= 0:
            i = last_digit_pos + 1

        # Skip any @ modifiers on the end position
        if i < len(note_str) and note_str[i] == "@":
            i += 1

        # Parse slide timing in brackets if present
        slide_duration = 0.0
        wait_time = 60.0 / current_bpm  # Default: 1 beat at current BPM

        if i < len(note_str) and note_str[i] == "[":
            i += 1
            timing_str = ""
            while i < len(note_str) and note_str[i] != "]":
                timing_str += note_str[i]
                i += 1

            if timing_str:
                try:
                    slide_duration, wait_time = ChartLoader._parse_slide_timing(timing_str, current_bpm)
                except ValueError:
                    pass

        return slide_duration, wait_time, end_position

    @staticmethod
    def _skip_past_all_slide_tracks(note_str: str, start_pos: int) -> tuple:
        """
        Skip past all slide tracks in a note string, including multiple slides with * separator.
        Also checks for the 'b' (break) modifier after the final bracket.

        Examples:
        - "1-4[8:3]" -> position after ]
        - "1-4[8:3]*-6[8:3]" -> position after final ]
        - "1-4[8:3]b" -> position after b
        - "1-4q7-2[1:2]" -> position after ] (chaining)

        Args:
            note_str: The full note string
            start_pos: Position where the first slide direction character is

        Returns:
            Tuple of (position_after_parsing, is_break) where is_break indicates if 'b' was found
        """
        i = start_pos
        is_break = False

        # Process first slide track
        while i < len(note_str) and note_str[i] in "-^v<>Vpqszw":
            i += 1

        # Skip any additional shape characters
        while i < len(note_str) and note_str[i] in "pqVvzs":
            i += 1

        # Now we're in the middle of the first track - skip to the bracket or next marker
        while i < len(note_str) and note_str[i] not in "[*":
            i += 1

        # Skip bracket and its contents (if present)
        if i < len(note_str) and note_str[i] == "[":
            i += 1
            while i < len(note_str) and note_str[i] != "]":
                i += 1
            if i < len(note_str):
                i += 1  # Skip the ]

        # Handle multiple slide tracks (separated by *)
        while i < len(note_str) and note_str[i] == "*":
            i += 1  # Skip *

            # Parse the next slide track
            # Skip direction and shape characters
            while i < len(note_str) and note_str[i] in "-^v<>Vpqszw":
                i += 1

            # Skip any additional shape characters
            while i < len(note_str) and note_str[i] in "pqVvzs":
                i += 1

            # Skip to the bracket or next separator
            while i < len(note_str) and note_str[i] not in "[*":
                i += 1

            # Skip bracket and its contents (if present)
            if i < len(note_str) and note_str[i] == "[":
                i += 1
                while i < len(note_str) and note_str[i] != "]":
                    i += 1
                if i < len(note_str):
                    i += 1  # Skip the ]

        # Handle the 'b' modifier for break slides (comes after all brackets)
        is_break = "b" in note_str
        return i, is_break

    @staticmethod
    def _parse_beat_value(beat_str: str, current_bpm: float = 120.0) -> float:
        """
        Parse beat value from Simai bracket notation.

        Notation [divide:count] means:
            time_in_seconds = (60 / BPM) * 4 / divide * count

        Examples:
            "4:5" with 120 BPM -> (60/120) * 4 / 4 * 5 = 2.5 seconds
            "8:3" with 120 BPM -> (60/120) * 4 / 8 * 3 = 0.75 seconds
            "1:1" with 120 BPM -> (60/120) * 4 / 1 * 1 = 2 seconds (one whole note)

        Args:
            beat_str: String like "4:5" or "1280:1"
            current_bpm: Current BPM for conversion

        Returns:
            Float value in seconds
        """
        beat_str = beat_str.strip()
        time_one_beat = 60.0 / current_bpm

        if ":" in beat_str:
            parts = beat_str.split(":")
            if len(parts) == 2:
                try:
                    divide = float(parts[0])
                    count = float(parts[1])
                    return time_one_beat * 4.0 / divide * count
                except ValueError:
                    return 0.0

        return 0.0

    @staticmethod
    def _parse_slide_timing(timing_str: str, current_bpm: float = 120.0) -> tuple:
        """
        Parse slide timing notation.

        Slide timing format examples from spec:
        - "8:3" -> wait=1 beat (default), duration=3/8 beats
        - "160#8:3" -> wait=1 beat at 160 BPM, duration=3/8 beats at 160 BPM
        - "160#2" -> wait=1 beat at 160 BPM, duration=2 seconds
        - "3##1.5" -> wait=3 seconds, duration=1.5 seconds
        - "3##8:3" -> wait=3 seconds, duration=3/8 beats at current BPM
        - "3##160#8:3" -> wait=3 seconds, duration=3/8 beats at 160 BPM

        Args:
            timing_str: The timing notation string
            current_bpm: Current BPM for default values

        Returns:
            Tuple of (slide_duration, wait_time) in seconds
        """
        timing_str = timing_str.strip()
        time_one_beat = 60.0 / current_bpm

        # Default: wait 1 beat at current BPM, then slide
        wait_time = time_one_beat
        slide_duration = 0.0

        # Check for ## separator (explicit wait time in seconds)
        if "##" in timing_str:
            parts = timing_str.split("##", 1)
            wait_str = parts[0].strip()
            duration_str = parts[1].strip() if len(parts) > 1 else ""

            # Parse wait time (in seconds)
            try:
                wait_time = float(wait_str)
            except ValueError:
                wait_time = time_one_beat

            # Parse duration
            if duration_str:
                if "#" in duration_str:
                    # BPM specified for duration: "160#8:3"
                    bpm_parts = duration_str.split("#", 1)
                    try:
                        bpm = float(bpm_parts[0])
                        beat_part = bpm_parts[1] if len(bpm_parts) > 1 else ""
                        if ":" in beat_part:
                            slide_duration = ChartLoader._parse_beat_value(beat_part, bpm)
                        else:
                            # Direct seconds value
                            slide_duration = float(beat_part)
                    except ValueError:
                        slide_duration = 0.0
                else:
                    # No BPM, check if beat notation or seconds
                    if ":" in duration_str:
                        slide_duration = ChartLoader._parse_beat_value(duration_str, current_bpm)
                    else:
                        try:
                            slide_duration = float(duration_str)
                        except ValueError:
                            slide_duration = 0.0

        # Check for # separator (BPM specification)
        elif "#" in timing_str:
            parts = timing_str.split("#", 1)
            bpm_str = parts[0].strip()
            duration_str = parts[1].strip() if len(parts) > 1 else ""

            # Parse BPM for wait time
            try:
                bpm = float(bpm_str)
                wait_time = 60.0 / bpm  # 1 beat at specified BPM
            except ValueError:
                wait_time = time_one_beat

            # Parse slide duration
            if duration_str:
                if ":" in duration_str:
                    # Beat notation at the BPM we just parsed
                    slide_duration = ChartLoader._parse_beat_value(duration_str, bpm)
                else:
                    # Try as seconds first
                    try:
                        slide_duration = float(duration_str)
                    except ValueError:
                        slide_duration = 0.0

        else:
            # Simple format: just duration, default wait 1 beat
            if ":" in timing_str:
                slide_duration = ChartLoader._parse_beat_value(timing_str, current_bpm)
            else:
                try:
                    slide_duration = float(timing_str)
                except ValueError:
                    slide_duration = 0.0

        return slide_duration, wait_time
