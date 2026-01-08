"""
Configuration and constants for the renderer
"""

# Sound effects
SOUND_EFFECTS = {
    "answer": "answer.wav",
    "judge": "judge.wav",
    "judge_break": "judge_break.wav",
    "judge_ex": "judge_ex.wav",
    "break": "break.wav",
    "hanabi": "hanabi.wav",
    "touch_hold": "touch_hold.wav",
    "track_start": "track_start.wav",
    "slide": "slide.wav",
    "touch": "touch.wav",
    "all_perfect": "all_perfect.wav",
    "fanfare": "fanfare.wav",
    "clock": "clock.wav",
    "break_slide_start": "break_slide_start.wav",
    "break_slide": "break_slide.wav",
    "judge_break_slide": "judge_break_slide.wav",
}

# Sound effect timing flags
SOUND_EFFECT_FLAGS = {
    "hasAnswer": "answer",
    "hasJudge": "judge",
    "hasJudgeBreak": "judge_break",
    "hasJudgeEx": "judge_ex",
    "hasBreak": "break",
    "hasHanabi": "hanabi",
    "hasTouchHold": "touch_hold",
    "hasTouch": "touch",
    "hasSlide": "slide",
    "hasBreakSlideStart": "break_slide_start",
    "hasBreakSlide": "break_slide",
    "hasJudgeBreakSlide": "judge_break_slide",
    "hasAllPerfect": ["all_perfect", "fanfare"],
    "hasClock": "clock",
}

# Volume defaults
DEFAULT_VOLUMES = {
    "bgm": 1.0,
    "answer": 1.0,
    "judge": 1.0,
    "judge_ex": 1.0,
    "hanabi": 1.0,
    "touch": 1.0,
    "slide": 1.0,
    "break": 1.0,
    "break_slide": 1.0,
}

# Delay for Record mode (5 seconds)
RECORD_MODE_DELAY = 5.0

# Audio parameters
WAV_CHANNELS = 2
WAV_BIT_DEPTH = 16
