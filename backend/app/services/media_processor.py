from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess

from ..config import Settings


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class VideoAnalysis:
    transcript: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    frame_paths: list[str] = field(default_factory=list)
    speech_density: float = 0


class MediaProcessingError(RuntimeError):
    pass


class MediaProcessor:
    def __init__(self, settings: Settings):
        self.settings = settings

    def analyze_video(self, video_path: str | None, transcript_hint: str = "") -> VideoAnalysis:
        if not video_path:
            text = transcript_hint or "视频没有可用文件，系统只能根据平台文本和标题生成低置信度草稿。"
            return VideoAnalysis(
                transcript=text,
                segments=[TranscriptSegment(start=0, end=8, text=text)],
                frame_paths=[],
                speech_density=0.2 if transcript_hint else 0,
            )
        path = Path(video_path)
        if not path.exists():
            raise MediaProcessingError(f"视频文件不存在：{video_path}")
        audio_path = self._extract_audio(path)
        return self._transcribe(audio_path, path)

    def _extract_audio(self, video_path: Path) -> Path:
        audio_dir = self.settings.storage_root / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / f"{video_path.stem}.wav"
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise MediaProcessingError(result.stderr.strip() or "ffmpeg 抽取音频失败")
        return audio_path

    def _transcribe(self, audio_path: Path, video_path: Path) -> VideoAnalysis:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise MediaProcessingError("未安装 faster-whisper，请安装 backend 的 asr 依赖。") from exc

        model = self._create_whisper_model(WhisperModel)
        segments, _info = model.transcribe(
            str(audio_path),
            language="zh",
            vad_filter=True,
            word_timestamps=True,
        )
        parsed = [
            TranscriptSegment(start=float(item.start), end=float(item.end), text=item.text.strip())
            for item in segments
            if item.text.strip()
        ]
        transcript = "\n".join(item.text for item in parsed)
        frame_paths = self._extract_frames(video_path, parsed)
        duration = max((item.end for item in parsed), default=0)
        speech_seconds = sum(max(0, item.end - item.start) for item in parsed)
        density = speech_seconds / duration if duration else 0
        return VideoAnalysis(
            transcript=transcript,
            segments=parsed,
            frame_paths=frame_paths,
            speech_density=density,
        )

    def _create_whisper_model(self, whisper_model_cls):
        try:
            return whisper_model_cls(
                self.settings.asr_model,
                device=self.settings.asr_device,
                compute_type=self.settings.asr_compute_type,
            )
        except Exception as exc:  # noqa: BLE001 - backend should recover from missing CUDA when possible.
            if self.settings.asr_device.lower() == "cpu":
                raise MediaProcessingError(f"ASR 模型加载失败：{exc}") from exc
            try:
                return whisper_model_cls(self.settings.asr_model, device="cpu", compute_type="int8")
            except Exception as fallback_exc:  # noqa: BLE001
                raise MediaProcessingError(f"ASR 模型加载失败：{fallback_exc}") from fallback_exc

    def _extract_frames(self, video_path: Path, segments: list[TranscriptSegment]) -> list[str]:
        frame_dir = self.settings.storage_root / "frames" / video_path.stem
        frame_dir.mkdir(parents=True, exist_ok=True)
        timestamps = [max(0, segment.start + 0.5) for segment in segments[:8]] or [1, 4, 8]
        paths: list[str] = []
        for index, timestamp in enumerate(timestamps):
            output_path = frame_dir / f"frame_{index:02d}.jpg"
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(timestamp),
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "3",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and output_path.exists():
                paths.append(str(output_path))
        return paths
