import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pprint import pprint
from typing import Optional, List
from mai_renderer.simai.loader import Chart


class MajdataSimaiNoteType(Enum):
    """Simai note type enumeration"""

    Tap = 0
    Slide = 1
    Hold = 2
    Touch = 3
    TouchHold = 4


@dataclass
class MajdataSimaiNote:
    """Represents a single note in Simai format"""

    holdTime: float = 0.0
    isBreak: bool = False
    isEx: bool = False
    isFakeRotate: bool = False
    isForceStar: bool = False
    isHanabi: bool = False
    isSlideBreak: bool = False
    isSlideNoHead: bool = False
    noteContent: Optional[str] = None
    noteType: MajdataSimaiNoteType = MajdataSimaiNoteType.Tap
    slideStartTime: float = 0.0
    slideTime: float = 0.0
    startPosition: int = 1
    touchArea: str = " "

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        d = asdict(self)
        d["noteType"] = self.noteType.name
        return d


@dataclass
class MajdataSimaiTimingPoint:
    """Represents a timing point (note group) in Simai format"""

    currentBpm: float = -1.0
    havePlayed: bool = False
    HSpeed: float = 1.0
    noteList: List[MajdataSimaiNote] = field(default_factory=list)
    notesContent: str = ""
    rawTextPositionX: int = 0
    rawTextPositionY: int = 0
    time: float = 0.0

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        d = asdict(self)
        d["noteList"] = [note.to_dict() for note in self.noteList]
        return d


@dataclass
class MajdataMajson:
    """Represents a complete Maimai chart in JSON format"""

    artist: str = "default"
    designer: str = "default"
    difficulty: str = "EASY"
    diffNum: int = 0
    level: str = "1"
    timingList: List[MajdataSimaiTimingPoint] = field(default_factory=list)
    title: str = "default"

    @staticmethod
    def get_difficulty_text(index: int) -> str:
        """Convert difficulty index to text"""
        difficulty_map = {
            0: "EASY",
            1: "BASIC",
            2: "ADVANCED",
            3: "EXPERT",
            4: "MASTER",
            5: "Re:MASTER",
            6: "ORIGINAL",
        }
        return difficulty_map.get(index, "DEFAULT")

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        return {
            "artist": self.artist,
            "designer": self.designer,
            "difficulty": self.difficulty,
            "diffNum": self.diffNum,
            "level": self.level,
            "timingList": [tp.to_dict() for tp in self.timingList],
            "title": self.title,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


def _build_note_content(note_data) -> str:
    """
    Build simai notation string from NoteData, cleaning up modifiers.

    Removes modifiers from the original note_content string:
    - Removes "!" and "?" (slide no-head markers)
    - Removes "b" (break marker)
    - Removes "$" (star-shaped tap markers)
    - Removes "x" (EX marker)

    This matches the behavior of SimaiProcess.cs getSingleNote()
    """
    content = note_data.note_content
    if not content:
        return ""

    # Remove modifiers in order, matching SimaiProcess.cs logic
    content = content.replace("!", "")
    content = content.replace("?", "")
    content = content.replace("b", "")
    content = content.replace("$", "")
    content = content.replace("x", "")

    return content


def generate_majson(chart: Chart, diff_num: int = 0, level: str = "1") -> MajdataMajson:
    """
    Generate Majson from parsed Chart object

    Args:
        chart: Chart object from ChartLoader
        diff_num: Difficulty index (0-6)
        level: Level as string (e.g., "1", "10+")

    Returns:
        Majson object ready for JSON serialization
    """
    majson = MajdataMajson(
        title=chart.metadata.title,
        artist=chart.metadata.artist,
        designer=chart.metadata.designer,
        diffNum=diff_num,
        difficulty=MajdataMajson.get_difficulty_text(diff_num),
        level=level,
    )

    # Get timing points for this difficulty
    if diff_num not in chart.difficulty_charts:
        return majson

    timing_points = chart.difficulty_charts[diff_num]

    # Convert timing points
    for timing_point in timing_points:
        simai_tp = MajdataSimaiTimingPoint(
            time=timing_point.time,
            currentBpm=timing_point.bpm,
        )

        # Convert notes
        for note_data in timing_point.notes:
            note_type_map = {
                "tap": MajdataSimaiNoteType.Tap,
                "hold": MajdataSimaiNoteType.Hold,
                "slide": MajdataSimaiNoteType.Slide,
                "touch": MajdataSimaiNoteType.Touch,
                "touch_hold": MajdataSimaiNoteType.TouchHold,
            }

            # Build noteContent from NoteData
            note_content = _build_note_content(note_data)

            # Calculate slide start time (when slide animation begins)
            # = timing point time + wait time before slide starts
            slide_start_time = timing_point.time + note_data.slide_wait_time if note_data.note_type == "slide" else 0.0

            simai_note = MajdataSimaiNote(
                noteType=note_type_map.get(note_data.note_type, MajdataSimaiNoteType.Tap),
                startPosition=note_data.position,
                holdTime=note_data.hold_time,
                isBreak=note_data.is_break,
                isEx=note_data.is_ex,
                isHanabi=note_data.is_hanabi,
                isSlideNoHead=note_data.is_no_slide_head,
                isSlideBreak=note_data.is_slide_break,
                slideTime=note_data.slide_time,
                slideStartTime=slide_start_time,
                touchArea=note_data.touch_area or " ",
                noteContent=note_content,
            )
            simai_tp.noteList.append(simai_note)

        majson.timingList.append(simai_tp)

    return majson
