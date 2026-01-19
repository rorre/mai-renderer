"""
Audio processing and WAV rendering - combines BGM with sound effects

Supports: WAV, OGG, MP3 (requires ffmpeg for OGG/MP3)
"""

import os
import struct
import wave
from pathlib import Path
from typing import Dict, List, Optional, TypedDict
import numpy as np
import soundfile as sf
from scipy import signal


VolumeSettings = TypedDict(
    "VolumeSettings",
    {
        "bgm": float,
        "sfx": float,
    },
    total=False,
)


class AudioProcessor:
    """Handles audio loading, processing, and rendering"""

    def __init__(self, sfx_dir: str, sample_rate: int = 44100):
        """
        Initialize audio processor

        Args:
            sfx_dir: Directory containing sound effect WAV files
            sample_rate: Sample rate in Hz (default 44100)
        """
        self.sfx_dir = sfx_dir
        self.sample_rate = sample_rate
        self.sound_banks: Dict[str, np.ndarray] = {}
        self.frequencies: Dict[str, int] = {}

    def load_audio(self, filepath: str) -> tuple[np.ndarray, int]:
        """
        Load audio file into numpy array, downsampled to 44100Hz

        Supports: WAV, OGG, MP3 (OGG/MP3 require ffmpeg)

        Args:
            filepath: Path to audio file

        Returns:
            Tuple of (audio_data, sample_rate) - always resampled to 44100Hz
        """
        try:
            # Try soundfile first (handles OGG, MP3, WAV, FLAC, etc.)
            audio_data, sample_rate = sf.read(filepath, dtype="float32")

            # Resample to 44100Hz if needed
            if sample_rate != self.sample_rate:
                audio_data = self._resample_audio(audio_data, sample_rate, self.sample_rate)
                sample_rate = self.sample_rate

            # Convert float32 to int16 range
            if audio_data.ndim > 1:
                # If stereo/multi-channel, keep as is
                audio_data = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            else:
                # Mono to int16
                audio_data = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)

            return audio_data, int(sample_rate)

        except Exception as e:
            print(f"Warning: Could not load audio file with soundfile: {filepath}")
            print(f"  Error: {e}")

            # Fallback: try wave module for WAV files
            if filepath.lower().endswith(".wav"):
                try:
                    with wave.open(filepath, "rb") as wav_file:
                        params = wav_file.getparams()
                        frames = wav_file.readframes(params.nframes)
                        audio_data = np.frombuffer(frames, dtype=np.int16)
                        # Resample to 44100Hz if needed
                        if params.framerate != self.sample_rate:
                            audio_float = audio_data.astype(np.float32) / 32768.0
                            audio_float = self._resample_audio(audio_float, params.framerate, self.sample_rate)
                            audio_data = np.clip(audio_float * 32767, -32768, 32767).astype(np.int16)
                        return audio_data, self.sample_rate
                except Exception as e2:
                    print(f"  Fallback WAV load also failed: {e2}")

            return np.array([], dtype=np.int16), self.sample_rate

    def load_sound_banks(self, sound_effect_names: List[str]) -> bool:
        """
        Load all sound effect banks

        Args:
            sound_effect_names: List of sound effect names (without .wav extension)

        Returns:
            True if all loaded successfully
        """
        all_loaded = True

        for name in sound_effect_names:
            filepath = os.path.join(self.sfx_dir, f"{name}.wav")
            audio_data, freq = self.load_audio(filepath)

            if len(audio_data) == 0:
                all_loaded = False
            else:
                self.sound_banks[name] = audio_data
                self.frequencies[name] = freq

        return all_loaded

    def render_with_effects(
        self,
        bgm_path: str,
        sound_timings: List,
        output_path: str,
        delay_seconds: float = 5.0,
        volumes: Optional[VolumeSettings] = None,
    ) -> bool:
        """
        Render final audio with BGM and sound effects combined

        Args:
            bgm_path: Path to BGM file
            sound_timings: List of SoundEffectTiming objects
            output_path: Path to output WAV file
            delay_seconds: Delay before chart starts (in seconds)
            volumes: Dict of volume levels for each sound type

        Returns:
            True if successful
        """
        if volumes is None:
            volumes = {}

        # Load BGM
        bgm_data, bgm_freq = self.load_audio(bgm_path)

        if len(bgm_data) == 0:
            print("Error: Could not load BGM file")
            return False

        # Ensure all sound banks have same frequency as BGM
        self._resample_sound_banks(bgm_freq)

        # Determine if audio is stereo or mono
        is_stereo = bgm_data.ndim > 1
        n_channels = bgm_data.shape[1] if is_stereo else 1

        # Create output buffer with delay
        delay_samples = int(delay_seconds * bgm_freq)
        total_samples = delay_samples + len(bgm_data)

        if is_stereo:
            # Stereo output: shape (total_samples, n_channels)
            output = np.zeros((total_samples, n_channels), dtype=np.float64)
        else:
            # Mono output: shape (total_samples,)
            output = np.zeros(total_samples, dtype=np.float64)

        # Add delayed BGM
        bgm_vol = volumes.get("bgm", 1.0)
        output[delay_samples : delay_samples + len(bgm_data)] = bgm_data.astype(np.float64) * bgm_vol

        # Add track_start sound at beginning of delay
        track_start_data = self.sound_banks.get("track_start", np.array([]))
        if len(track_start_data) > 0:
            print("Adding start")
            track_start_len = min(len(track_start_data), delay_samples)
            if is_stereo and track_start_data.ndim == 1:
                # Expand mono effect to stereo
                track_start_stereo = np.tile(track_start_data[:track_start_len, np.newaxis], (1, n_channels))
                output[:track_start_len] += track_start_stereo.astype(np.float64)
            else:
                output[:track_start_len] += track_start_data[:track_start_len].astype(np.float64)

        # Apply sound effects at their timings
        for timing in sound_timings:
            sample_position = int(timing.time * bgm_freq) + delay_samples

            # Map timing flags to sound effect names and volumes
            effects = self._get_effects_from_timing(timing)
            for effect_name, volume in effects:
                if effect_name in self.sound_banks:
                    effect_data = self.sound_banks[effect_name]
                    effect_vol = volumes.get("sfx", 1.0) * volume

                    # For touch_hold, crop the sound to match the hold duration
                    if effect_name == "touch_hold" and timing.touch_hold_duration > 0:
                        duration_samples = int(timing.touch_hold_duration * bgm_freq)
                        effect_data = effect_data[:duration_samples]

                    # Add effect to output
                    end_pos = min(sample_position + len(effect_data), len(output))
                    effect_len = end_pos - sample_position

                    if is_stereo and effect_data.ndim == 1:
                        # Expand mono effect to stereo
                        effect_stereo = np.tile(effect_data[:effect_len, np.newaxis], (1, n_channels))
                        output[sample_position:end_pos] += effect_stereo.astype(np.float64) * effect_vol
                    else:
                        output[sample_position:end_pos] += effect_data[:effect_len].astype(np.float64) * effect_vol

        # Normalize and clip to 16-bit range
        max_val = np.max(np.abs(output))
        if max_val > 0:
            output = output / max_val * 32767 * 0.95  # Leave some headroom

        output = np.clip(output, -32768, 32767).astype(np.int16)

        # Write output WAV
        return self._write_wav(output_path, output, bgm_freq, n_channels)

    def _resample_audio(self, audio_data: np.ndarray, orig_sample_rate: int, target_sample_rate: int) -> np.ndarray:
        """
        Resample audio to target sample rate using scipy

        Args:
            audio_data: Audio samples (float32)
            orig_sample_rate: Original sample rate
            target_sample_rate: Target sample rate

        Returns:
            Resampled audio data (exact length based on sample rate ratio)
        """
        if orig_sample_rate == target_sample_rate:
            return audio_data

        # Calculate exact output length
        output_length = int(len(audio_data) * target_sample_rate / orig_sample_rate)

        # Use scipy's resample_poly for high-quality resampling
        if audio_data.ndim == 1:
            # Mono
            resampled = signal.resample_poly(audio_data, target_sample_rate, orig_sample_rate)
            # Ensure exact output length
            return resampled[:output_length]
        else:
            # Stereo/multi-channel - resample each channel
            resampled = np.zeros((output_length, audio_data.shape[1]), dtype=np.float32)
            for ch in range(audio_data.shape[1]):
                resampled[:, ch] = signal.resample_poly(audio_data[:, ch], target_sample_rate, orig_sample_rate)[
                    :output_length
                ]
            return resampled

    def _resample_sound_banks(self, target_freq: int):
        """Resample sound banks if they don't match target frequency"""
        for name, audio_data in self.sound_banks.items():
            original_freq = self.frequencies[name]
            if original_freq != target_freq:
                # Convert back to float for resampling
                audio_float = audio_data.astype(np.float32) / 32768.0
                audio_resampled = self._resample_audio(audio_float, original_freq, target_freq)
                # Convert back to int16
                self.sound_banks[name] = np.clip(audio_resampled * 32767, -32768, 32767).astype(np.int16)
                self.frequencies[name] = target_freq

    def _get_effects_from_timing(self, timing) -> List[tuple[str, float]]:
        """
        Extract list of (effect_name, volume_multiplier) from timing object

        Args:
            timing: SoundEffectTiming object

        Returns:
            List of (effect_name, volume) tuples
        """
        effects = []

        if timing.has_answer:
            effects.append(("answer", 1.0))
        if timing.has_judge:
            effects.append(("judge", 1.0))
        if timing.has_judge_break:
            effects.append(("judge_break", 1.0))
        if timing.has_judge_ex:
            effects.append(("judge_ex", 1.0))
        if timing.has_break:
            effects.append(("break", 0.75))  # Break has reduced volume
        if timing.has_hanabi:
            effects.append(("hanabi", 1.0))
        if timing.has_touch_hold:
            effects.append(("touch_hold", 1.0))
        if timing.has_touch:
            effects.append(("touch", 1.0))
        if timing.has_slide:
            effects.append(("slide", 1.0))
        if timing.has_break_slide_start:
            effects.append(("break_slide_start", 1.0))
        if timing.has_break_slide:
            effects.append(("break_slide", 1.0))
        if timing.has_judge_break_slide:
            effects.append(("judge_break_slide", 1.0))
        if timing.has_all_perfect:
            effects.append(("all_perfect", 1.0))
            effects.append(("fanfare", 1.0))
        if timing.has_clock:
            effects.append(("clock", 1.0))

        return effects

    def _write_wav(
        self,
        filepath: str,
        audio_data: np.ndarray,
        sample_rate: int,
        n_channels: int = 2,
    ) -> bool:
        """
        Write audio data to WAV file

        Args:
            filepath: Output file path
            audio_data: Audio samples as numpy array
            sample_rate: Sample rate in Hz
            n_channels: Number of channels (1 for mono, 2 for stereo)

        Returns:
            True if successful
        """
        try:
            with wave.open(filepath, "wb") as wav_file:
                # Set WAV parameters
                wav_file.setnchannels(n_channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)

                wav_file.writeframes(audio_data.tobytes())

            print(f"Successfully wrote audio to: {filepath}")
            print(f"  Format: {n_channels} channel(s), {sample_rate} Hz, 16-bit")
            return True
        except Exception as e:
            print(f"Error writing WAV file: {e}")
            return False
