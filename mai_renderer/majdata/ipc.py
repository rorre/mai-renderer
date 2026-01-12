"""
IPC module for communicating with MajdataView for recording

Sends control requests via HTTP POST to localhost:8013 to trigger recording
"""

import json
import requests
from enum import Enum


class EditorControlMethod(Enum):
    """Control methods for MajdataView"""

    Start = 0
    Stop = 1
    OpStart = 2
    Pause = 3
    Continue = 4
    Record = 5


class EditorPlayMethod(Enum):
    """Play methods for MajdataView"""

    Classic = 0
    DJAuto = 1
    Random = 2
    Disabled = 3


class EditorComboIndicator(Enum):
    """Combo indicator types"""

    None_ = 0
    Combo = 1
    ScoreClassic = 2
    AchievementClassic = 3
    AchievementDownClassic = 4
    AchievementDeluxe = 11
    AchievementDownDeluxe = 12
    ScoreDeluxe = 13
    CScoreDedeluxe = 101
    CScoreDownDedeluxe = 102


class MajdataViewIPC:
    """Handle IPC communication with MajdataView"""

    MAJDATAVIEW_URL = "http://localhost:8013/"

    @staticmethod
    def send_record_request(
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
        Send a record request to MajdataView

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
        request_data = {
            "control": EditorControlMethod.Record.value,
            "jsonPath": json_path,
            "startAt": 0,  # Start timestamp (not used in Record mode)
            "startTime": start_time,
            "noteSpeed": note_speed,
            "touchSpeed": touch_speed,
            "audioSpeed": audio_speed,
            "backgroundCover": background_cover,
            "comboStatusType": combo_status.value,
            "smoothSlideAnime": smooth_slide,
            "editorPlayMethod": editor_play_method.value,
        }

        try:
            json_str = json.dumps(request_data)
            response = requests.post(MajdataViewIPC.MAJDATAVIEW_URL, data=json_str, timeout=5)

            if response.status_code == 200:
                print(f"Successfully sent record request to MajdataView")
                return True
            else:
                print(f"Failed to send record request: HTTP {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to MajdataView on localhost:8013")
            print("Please ensure MajdataView is running")
            return False
        except Exception as e:
            print(f"Error sending record request: {e}")
            return False

    @staticmethod
    def send_stop_request() -> bool:
        """
        Send a stop request to MajdataView

        Returns:
            True if request was successful, False otherwise
        """
        request_data = {"control": EditorControlMethod.Stop.value}

        try:
            json_str = json.dumps(request_data)
            response = requests.post(MajdataViewIPC.MAJDATAVIEW_URL, data=json_str, timeout=5)

            if response.status_code == 200:
                print("Successfully sent stop request to MajdataView")
                return True
            else:
                print(f"Failed to send stop request: HTTP {response.status_code}")
                return False

        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to MajdataView on localhost:8013")
            return False
        except Exception as e:
            print(f"Error sending stop request: {e}")
            return False
