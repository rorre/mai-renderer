# Maimai Renderer

I need a maimai renderer that can work on Linux

**You need MajdataView to be running to record.** It's trivial to port MajdataView to Linux. I'll post some of my changes in a fork later.

## EVERYTHING HERE IS VIBE CODED!!!!!!!!

It probably doesn't work properly, though tbh the code for the parsing isn't that bad... I wouldn't have gone parsing it character by character though

```
usage: main.py --maidata_dir MAIDATA_DIR [--sfx_dir SFX_DIR] [--output OUTPUT] [--difficulty DIFFICULTY] [--no_op] [--delay DELAY] [-h] {record} ...

positional arguments:
  {record}
    record              Record with MajdataView

options:
  --maidata_dir MAIDATA_DIR
                        (str, required) Directory containing maidata.txt and track audio
  --sfx_dir SFX_DIR     (str, default=SFX) Directory containing sound effects
  --output OUTPUT       (str, default=out.wav) Output WAV filename
  --difficulty DIFFICULTY
                        (int, default=0) Difficulty index (0-6)
  --no_op               (bool, default=False) Exclude opening/intro sounds
  --delay DELAY         (float, default=5.0) Delay before chart starts in seconds
  -h, --help            show this help message and exit
```

```
usage: main.py record [--sfx_dir SFX_DIR] [--difficulty DIFFICULTY] [--note_speed NOTE_SPEED] [--touch_speed TOUCH_SPEED] [--audio_speed AUDIO_SPEED]
                      [--background_cover BACKGROUND_COVER] [--smooth_slide] [--combo_status COMBO_STATUS] [--play_method PLAY_METHOD] [--no_op] [-h]

Arguments for record subcommand

options:
  --sfx_dir SFX_DIR     (str, default=SFX) Directory containing sound effects
  --difficulty DIFFICULTY
                        (int, default=0) Difficulty index (0-6)
  --note_speed NOTE_SPEED
                        (float, default=7.5) Note speed for recording
  --touch_speed TOUCH_SPEED
                        (float, default=7.5) Touch speed for recording
  --audio_speed AUDIO_SPEED
                        (float, default=1.0) Audio speed for recording
  --background_cover BACKGROUND_COVER
                        (float, default=0.6) Background cover opacity (0-1)
  --smooth_slide        (bool, default=False) Enable smooth slide animation
  --combo_status COMBO_STATUS
                        (<enum 'EditorComboIndicator'>, default=EditorComboIndicator.Combo) Combo indicator type
  --play_method PLAY_METHOD
                        (<enum 'EditorPlayMethod'>, default=EditorPlayMethod.DJAuto) Play method
  --no_op               (bool, default=False) Exclude opening/intro sounds
  -h, --help            show this help message and exit
```
