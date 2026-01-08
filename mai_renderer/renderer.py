"""
Main renderer orchestrator - combines chart loading, timing, and audio rendering
"""

import json
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from pprint import pprint
import sys
from pathlib import Path
from typing import Optional, cast, List
from mai_renderer.chart_loader import ChartLoader, Chart
from mai_renderer.sound_timing import SoundTimingGenerator
from mai_renderer.audio_processor import AudioProcessor
from mai_renderer.config import SOUND_EFFECTS
from mai_renderer.majdataview_ipc import (
    MajdataViewIPC,
    EditorPlayMethod,
    EditorComboIndicator,
)


class SimaiNoteType(Enum):
    """Simai note type enumeration"""

    Tap = 0
    Slide = 1
    Hold = 2
    Touch = 3
    TouchHold = 4


@dataclass
class SimaiNote:
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
    noteType: SimaiNoteType = SimaiNoteType.Tap
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
class SimaiTimingPoint:
    """Represents a timing point (note group) in Simai format"""

    currentBpm: float = -1.0
    havePlayed: bool = False
    HSpeed: float = 1.0
    noteList: List[SimaiNote] = field(default_factory=list)
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
class Majson:
    """Represents a complete Maimai chart in JSON format"""

    artist: str = "default"
    designer: str = "default"
    difficulty: str = "EASY"
    diffNum: int = 0
    level: str = "1"
    timingList: List[SimaiTimingPoint] = field(default_factory=list)
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


def generate_majson(chart: Chart, diff_num: int = 0, level: str = "1") -> Majson:
    """
    Generate Majson from parsed Chart object

    Args:
        chart: Chart object from ChartLoader
        diff_num: Difficulty index (0-6)
        level: Level as string (e.g., "1", "10+")

    Returns:
        Majson object ready for JSON serialization
    """
    majson = Majson(
        title=chart.metadata.title,
        artist=chart.metadata.artist,
        designer=chart.metadata.designer,
        diffNum=diff_num,
        difficulty=Majson.get_difficulty_text(diff_num),
        level=level,
    )

    # Get timing points for this difficulty
    if diff_num not in chart.difficulty_charts:
        return majson

    timing_points = chart.difficulty_charts[diff_num]

    # Convert timing points
    for timing_point in timing_points:
        simai_tp = SimaiTimingPoint(
            time=timing_point.time,
            currentBpm=timing_point.bpm,
            rawTextPositionX=timing_point.raw_text_position_x,
            rawTextPositionY=timing_point.raw_text_position_y,
        )

        # Convert notes
        for note_data in timing_point.notes:
            note_type_map = {
                "tap": SimaiNoteType.Tap,
                "hold": SimaiNoteType.Hold,
                "slide": SimaiNoteType.Slide,
                "touch": SimaiNoteType.Touch,
                "touch_hold": SimaiNoteType.TouchHold,
            }

            # Build noteContent from NoteData
            note_content = _build_note_content(note_data)

            # Calculate slide start time (when slide animation begins)
            # = timing point time + wait time before slide starts
            slide_start_time = timing_point.time + note_data.slide_wait_time if note_data.note_type == "slide" else 0.0

            # prev = None
            if note_data.is_no_slide_head:
                print(prev)
            prev = note_data, note_content

            simai_note = SimaiNote(
                noteType=note_type_map.get(note_data.note_type, SimaiNoteType.Tap),
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


class Renderer:
    """Main rendering orchestrator"""

    def __init__(self, maidata_dir: str, sfx_dir: str):
        """
        Initialize renderer

        Args:
            maidata_dir: Directory containing maidata.txt and track audio
            sfx_dir: Directory containing sound effect WAV files
        """
        self.maidata_dir = Path(maidata_dir)
        self.sfx_dir = Path(sfx_dir)
        self.chart = None
        self.audio_processor = AudioProcessor(sfx_dir)

    def load_chart(self, maidata_file: str = "maidata.txt") -> bool:
        """
        Load chart from maidata.txt

        Args:
            maidata_file: Filename of maidata file (default: maidata.txt)

        Returns:
            True if successful
        """
        maidata_path = self.maidata_dir / maidata_file

        if not maidata_path.exists():
            print(f"Error: Chart file not found: {maidata_path}")
            return False

        try:
            self.chart = ChartLoader.load_chart(str(maidata_path))
            print(f"Loaded chart: {self.chart.metadata.title}")
            return True
        except Exception as e:
            print(f"Error loading chart: {e}")
            return False

    def initialize_audio(self) -> bool:
        """
        Initialize audio processor

        Returns:
            True if successful
        """
        if not self.sfx_dir.exists():
            print(f"Error: Sound effects directory not found: {self.sfx_dir}")
            return False

        # Load all sound banks
        effect_names = list(SOUND_EFFECTS.values())
        effect_names = [name.replace(".wav", "") for name in effect_names]

        success = self.audio_processor.load_sound_banks(effect_names)
        if not success:
            print("Warning: Some sound files could not be loaded")

        return True

    def find_bgm(self) -> Optional[str]:
        """
        Find BGM file (track.ogg or track.mp3)

        Returns:
            Path to BGM file or None if not found
        """
        for pattern in ["track.ogg", "track.mp3"]:
            bgm_path = self.maidata_dir / pattern
            if bgm_path.exists():
                return str(bgm_path)

        print("Error: BGM file not found (track.ogg or track.mp3)")
        return None

    def generate_majdata_json(self, diff_num: int = 0, level: str = "1") -> bool:
        """
        Generate majdata.json from loaded chart

        Args:
            diff_num: Difficulty index (0-6)
            level: Level as string

        Returns:
            True if successful
        """
        if self.chart is None:
            print("Error: No chart loaded")
            return False

        try:
            majson = generate_majson(self.chart, diff_num=diff_num, level=level)
            output_path = self.maidata_dir / "majdata.json"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(majson.to_json())
            print(f"Generated majdata.json to: {output_path}")
            return True
        except Exception as e:
            print(f"Error generating majdata.json: {e}")
            return False

    def render(
        self,
        output_file: str = "out.wav",
        start_time: float = 0.0,
        include_op: bool = True,
        delay_seconds: float = 5.0,
        volumes: Optional[dict] = None,
        diff_num: int = 0,
        level: str = "1",
    ) -> bool:
        """
        Render chart with sound effects

        Args:
            output_file: Output WAV filename
            start_time: Start time in seconds (for partial renders)
            include_op: Include opening/intro sounds
            delay_seconds: Delay before chart starts
            volumes: Dict of volume levels for each sound type
            diff_num: Difficulty index (0-6) for majdata.json
            level: Level as string for majdata.json

        Returns:
            True if successful
        """
        if self.chart is None:
            print("Error: No chart loaded")
            return False

        if not self.initialize_audio():
            return False

        # Find BGM
        bgm_path = self.find_bgm()
        if not bgm_path:
            return False

        # Generate majdata.json
        if not self.generate_majdata_json(diff_num=diff_num, level=level):
            return False

        pprint(self.chart.difficulty_charts[diff_num][0].notes[:8])
        # exit()
        # Generate sound effect timings
        print("Generating sound effect timings...")
        timings = SoundTimingGenerator.generate(
            self.chart, start_time=start_time, include_op=include_op, diff_num=diff_num
        )
        print(f"Generated {len(timings)} sound effect timings")

        # Render audio
        output_path = self.maidata_dir / output_file
        print(f"Rendering audio to: {output_path}")

        success = self.audio_processor.render_with_effects(
            bgm_path,
            timings,
            str(output_path),
            delay_seconds=delay_seconds,
            volumes=volumes or {},
        )

        if success:
            print("Render complete!")
        else:
            print("Render failed!")

        return success

    def record_with_view(
        self,
        json_path: str,
        start_time: float = 0.0,
        note_speed: float = 7.5,
        touch_speed: float = 7.5,
        audio_speed: float = 1.0,
        background_cover: float = 0.6,
        combo_status: EditorComboIndicator = EditorComboIndicator.Combo,
        smooth_slide: bool = False,
        editor_play_method: EditorPlayMethod = EditorPlayMethod.Classic,
    ) -> bool:
        """
        Send recording request to MajdataView

        Args:
            json_path: Path to the majdata.json file
            start_time: Time to start playback (in seconds)
            note_speed: Note speed (default 7.5)
            touch_speed: Touch speed (default 7.5)
            audio_speed: Audio playback speed (default 1.0)
            background_cover: Background cover opacity (0.0-1.0, default 0.6)
            combo_status: Combo indicator type
            smooth_slide: Enable smooth slide animation
            editor_play_method: Editor play method

        Returns:
            True if request was successful, False otherwise
        """
        return MajdataViewIPC.send_record_request(
            json_path=json_path,
            start_time=start_time,
            note_speed=note_speed,
            touch_speed=touch_speed,
            audio_speed=audio_speed,
            background_cover=background_cover,
            combo_status=combo_status,
            smooth_slide=smooth_slide,
            editor_play_method=editor_play_method,
        )

    def stop_view_recording(self) -> bool:
        """
        Send stop request to MajdataView

        Returns:
            True if request was successful, False otherwise
        """
        return MajdataViewIPC.send_stop_request()


def main():
    """Command-line entry point"""
    from tap import Tap

    class RecordArgs(Tap):
        """Arguments for record subcommand"""

        sfx_dir: str = "SFX"  # Directory containing sound effects
        difficulty: int = 0  # Difficulty index (0-6)
        note_speed: float = 7.5  # Note speed for recording
        touch_speed: float = 7.5  # Touch speed for recording
        audio_speed: float = 1.0  # Audio speed for recording
        background_cover: float = 0.6  # Background cover opacity (0-1)
        smooth_slide: bool = False  # Enable smooth slide animation
        combo_status: EditorComboIndicator = EditorComboIndicator.Combo  # Combo indicator type
        play_method: EditorPlayMethod = EditorPlayMethod.DJAuto  # Play method
        no_op: bool = False  # Exclude opening/intro sounds

    class Args(Tap):
        maidata_dir: str  # Directory containing maidata.txt and track audio
        sfx_dir: str = "SFX"  # Directory containing sound effects
        output: str = "out.wav"  # Output WAV filename
        difficulty: int = 0  # Difficulty index (0-6)
        no_op: bool = False  # Exclude opening/intro sounds
        delay: float = 5.0  # Delay before chart starts in seconds

        def configure(self):
            self.add_subparsers(dest="command")
            self.add_subparser("record", RecordArgs, help="Record with MajdataView")

    # Parse arguments
    args = Args().parse_args()

    # Determine absolute SFX directory
    if os.path.isabs(args.sfx_dir):
        sfx_dir = args.sfx_dir
    else:
        sfx_dir = os.path.join(os.getcwd(), args.sfx_dir)

    # Create renderer and load chart
    renderer = Renderer(args.maidata_dir, sfx_dir)

    if not renderer.load_chart():
        return 1

    # Validate difficulty exists
    if args.difficulty not in renderer.chart.difficulty_charts:
        available = sorted(renderer.chart.difficulty_charts.keys())
        difficulty_names = [Majson.get_difficulty_text(i) for i in available]
        print(f"Error: Difficulty {args.difficulty} ({Majson.get_difficulty_text(args.difficulty)}) not found in chart")
        print(f"Available difficulties: {', '.join(f'{i}={difficulty_names[j]}' for j, i in enumerate(available))}")
        return 1

    # Infer level from chart
    level = renderer.chart.metadata.levels[args.difficulty] or "1"

    if args.command == "record":  # type: ignore
        args = cast(RecordArgs, args)
        # Record with MajdataView
        json_path = os.path.join(args.maidata_dir, "majdata.json")  # type: ignore
        # if not os.path.exists(json_path):
        #    print(f"Error: majdata.json not found at {json_path}")
        #    return 1

        # Render with fixed output and delay for recording
        if not renderer.render(
            output_file="out.wav", include_op=not args.no_op, delay_seconds=5.0, diff_num=args.difficulty, level=level
        ):
            return 1

        success = renderer.record_with_view(
            json_path=json_path,
            start_time=0.0,
            note_speed=args.note_speed,
            touch_speed=args.touch_speed,
            audio_speed=args.audio_speed,
            background_cover=args.background_cover,
            combo_status=args.combo_status,
            smooth_slide=args.smooth_slide,
            editor_play_method=args.play_method,
        )

        if success:
            print("Recording request sent to MajdataView")
        else:
            print("Failed to send recording request")
            return 1
    else:
        # Normal audio rendering
        if not renderer.render(
            output_file=args.output,
            include_op=not args.no_op,
            delay_seconds=args.delay,
            diff_num=args.difficulty,
            level=level,
        ):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
