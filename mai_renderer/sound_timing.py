"""
Sound effect timing management - handles when sound effects should play

Converts note timing into sound effect events based on:
- Note types (tap, hold, slide, touch, touch_hold)
- Note modifiers (break, ex)
- Hold durations and release timing
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from mai_renderer.chart_loader import Chart, TimingPoint


@dataclass
class SoundEffectTiming:
    """Represents when sound effects should be triggered"""

    time: float  # Time in seconds
    note_group_index: int = -1

    # Individual sound effect flags
    has_answer: bool = False
    has_judge: bool = False
    has_judge_break: bool = False
    has_judge_ex: bool = False
    has_break: bool = False
    has_touch: bool = False
    has_hanabi: bool = False
    has_touch_hold: bool = False
    has_slide: bool = False
    has_touch_hold_end: bool = False
    has_all_perfect: bool = False
    has_clock: bool = False
    has_break_slide_start: bool = False
    has_break_slide: bool = False
    has_judge_break_slide: bool = False

    # Duration for looping sounds (in seconds)
    touch_hold_duration: float = 0.0  # Duration of touch_hold sound (used to crop the riser sound)


class SoundTimingGenerator:
    """Generates sound effect timing from chart data"""

    @staticmethod
    def generate(
        chart: Chart, start_time: float = 0.0, include_op: bool = False, diff_num: int = 0
    ) -> List[SoundEffectTiming]:
        """
        Generate sound effect timing list from chart

        Processes notes and generates appropriate sound effects:
        - Tap: answer + judge (or break/ex variant)
        - Hold: answer + judge at start, plus judge at release
        - Slide: answer + slide sound at start, plus judge when touching buttons
        - Touch: answer + touch sound
        - Touch Hold: answer + touch_hold sound at start, touch_hold_end at release

        Args:
            chart: Chart object
            start_time: Start time in seconds (for seek)
            include_op: Include OP/intro sounds
            diff_num: Difficulty index (0-6) to generate sounds for

        Returns:
            Sorted list of SoundEffectTiming objects
        """
        timing_list: Dict[float, SoundEffectTiming] = {}

        # Get timing points for this difficulty
        if diff_num not in chart.difficulty_charts:
            return []

        timing_points = chart.difficulty_charts[diff_num]

        # Add clock sounds if OP is included
        # Broken :(
        # if include_op:
        #     for clock_timing in SoundTimingGenerator._generate_clock_sounds(timing_points):
        #         key = round(clock_timing.time * 1000) / 1000  # Round to millisecond
        #         if key not in timing_list:
        #             timing_list[key] = clock_timing
        #         else:
        #             # Merge with existing timing
        #             existing = timing_list[key]
        #             existing.has_clock = existing.has_clock or clock_timing.has_clock

        # Add sounds for each note group
        for i, timing_point in enumerate(timing_points):
            if timing_point.time < start_time:
                continue

            time_key = round(timing_point.time * 1000) / 1000  # Round to millisecond

            # Get or create timing entry at this time
            if time_key not in timing_list:
                timing_list[time_key] = SoundEffectTiming(time=timing_point.time)

            sound_timing = timing_list[time_key]
            sound_timing.note_group_index = i

            # Generate sounds based on note types
            for note in timing_point.notes:
                if note.note_type == "tap":
                    # Tap: answer + judge
                    sound_timing.has_answer = True
                    SoundTimingGenerator._add_judge_sound(sound_timing, note)
                    # Add hanabi if present
                    if note.is_hanabi:
                        sound_timing.has_hanabi = True

                elif note.note_type == "hold":
                    # Hold start: answer + judge
                    sound_timing.has_answer = True
                    SoundTimingGenerator._add_judge_sound(sound_timing, note)
                    # Add hanabi if present
                    if note.is_hanabi:
                        sound_timing.has_hanabi = True

                    # Hold release: judge at end of hold
                    if note.hold_time > 0:
                        release_time = timing_point.time + note.hold_time
                        release_key = round(release_time * 1000) / 1000

                        if release_key not in timing_list:
                            timing_list[release_key] = SoundEffectTiming(time=release_time)

                        release_timing = timing_list[release_key]
                        # Hold release only has answer + judge (no hanabi)
                        release_timing.has_answer = True
                        if not note.is_break and not note.is_ex:
                            release_timing.has_judge = True

                elif note.note_type == "slide":
                    # Slide: answer at start, judge + slide sound after waiting time
                    sound_timing.has_answer = True
                    SoundTimingGenerator._add_judge_sound(sound_timing, note)

                    # Calculate when slide sound should play (after waiting time)
                    slide_sound_time = timing_point.time + note.slide_wait_time
                    slide_sound_key = round(slide_sound_time * 1000) / 1000

                    # Different sounds for break slides vs normal slides
                    # Note: is_slide_break means the break is on the slide body, not the star head
                    if note.is_slide_break:
                        # Create sound event for break slide start (after wait time)
                        if slide_sound_key not in timing_list:
                            timing_list[slide_sound_key] = SoundEffectTiming(time=slide_sound_time)

                        slide_sound_timing = timing_list[slide_sound_key]
                        slide_sound_timing.has_break_slide_start = True

                        # Break slide has additional sounds at end
                        if note.slide_time > 0:
                            slide_end_time = (
                                note.slide_start_time + note.slide_time
                                if note.slide_start_time > 0
                                else timing_point.time + note.slide_wait_time + note.slide_time
                            )
                            slide_end_key = round(slide_end_time * 1000) / 1000

                            if slide_end_key not in timing_list:
                                timing_list[slide_end_key] = SoundEffectTiming(time=slide_end_time)

                            slide_end_timing = timing_list[slide_end_key]
                            slide_end_timing.has_break_slide = True
                            slide_end_timing.has_judge_break_slide = True
                    else:
                        # Create sound event for normal slide sound (after wait time)
                        if slide_sound_key not in timing_list:
                            timing_list[slide_sound_key] = SoundEffectTiming(time=slide_sound_time)

                        slide_sound_timing = timing_list[slide_sound_key]
                        slide_sound_timing.has_slide = True

                elif note.note_type == "touch":
                    # Touch: answer + touch sound (no delay, plays immediately)
                    sound_timing.has_answer = True
                    sound_timing.has_touch = True
                    # Add hanabi if present
                    if note.is_hanabi:
                        sound_timing.has_hanabi = True

                elif note.note_type == "touch_hold":
                    # Touch hold start: answer + touch + touch_hold (if duration > 0)
                    sound_timing.has_answer = True
                    sound_timing.has_touch = True
                    # Only set touch_hold if the hold duration is > 0 (else it's a tap like hexagon)
                    if note.hold_time > 0:
                        sound_timing.has_touch_hold = True
                        # Store the duration so the audio processor can crop the riser sound
                        sound_timing.touch_hold_duration = note.hold_time

                    # Touch hold end: answer + touch_hold_end (and hanabi if present)
                    if note.hold_time > 0:
                        release_time = timing_point.time + note.hold_time
                        release_key = round(release_time * 1000) / 1000

                        if release_key not in timing_list:
                            timing_list[release_key] = SoundEffectTiming(time=release_time)

                        release_timing = timing_list[release_key]
                        release_timing.has_answer = True
                        release_timing.has_touch_hold_end = True
                        # Hanabi plays at the release time for touch hold
                        if note.is_hanabi:
                            release_timing.has_hanabi = True

        # Convert dict to sorted list
        result = sorted(timing_list.values(), key=lambda x: x.time)
        return result

    @staticmethod
    def _add_judge_sound(sound_timing: SoundEffectTiming, note) -> None:
        """
        Add appropriate judge sound based on note modifiers

        Args:
            sound_timing: SoundEffectTiming to update
            note: NoteData to check for modifiers
        """
        if note.is_break:
            sound_timing.has_break = True
            sound_timing.has_judge_break = True
        elif note.is_ex:
            sound_timing.has_judge_ex = True
        else:
            sound_timing.has_judge = True

    @staticmethod
    def _generate_clock_sounds(timing_points: List) -> List[SoundEffectTiming]:
        """Generate clock count sounds from timing points"""
        clock_sounds = []

        # Get BPM of first note
        first_bpm = 120.0
        if timing_points:
            first_bpm = timing_points[0].bpm

        # Default clock count (can be extended to parse from metadata if needed)
        # FIXME: How do we know from the simai data?
        clock_cnt = 4
        clock_interval = 60.0 / first_bpm

        for i in range(clock_cnt):
            # FIXME: This is completely wrong, need to backtrack to 4 beats before first timing beat
            clock_timing = SoundEffectTiming(time=i * clock_interval, has_clock=True)
            clock_sounds.append(clock_timing)

        return clock_sounds
