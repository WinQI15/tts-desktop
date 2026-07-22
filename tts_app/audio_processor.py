"""
音频后处理模块
提供音频合并、格式转换、语速调整、音量归一化等功能
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# 延迟导入
_pydub_available = False
try:
    from pydub import AudioSegment
    _pydub_available = True
except ImportError:
    pass


class AudioExporter:
    """音频导出与后处理

    功能:
    - 合并多个音频文件
    - 格式转换（MP3, WAV, OGG 等）
    - 语速调整
    - 音量归一化
    - 添加静音间隔
    """

    SUPPORTED_FORMATS = {
        "mp3": "MP3 格式",
        "wav": "WAV 无损格式",
        "ogg": "OGG Vorbis 格式",
        "m4a": "M4A/AAC 格式",
        "flac": "FLAC 无损格式",
    }

    @staticmethod
    def is_available() -> bool:
        """检查 pydub 是否可用"""
        return _pydub_available

    @staticmethod
    def merge_chapters(
        chapter_audios: list[str],
        output_path: str,
        silence_ms: int = 1500,
        add_chapter_markers: bool = False
    ) -> bool:
        """合并多个章节音频为一个文件

        Args:
            chapter_audios: 章节音频文件路径列表
            output_path: 输出文件路径
            silence_ms: 章节间静音间隔（毫秒）
            add_chapter_markers: 是否添加章节标记（MP3 章节）

        Returns:
            是否成功
        """
        if not _pydub_available:
            raise ImportError("pydub 未安装，请运行: pip install pydub")

        if not chapter_audios:
            logger.warning("没有音频文件可合并")
            return False

        try:
            merged = AudioSegment.empty()
            silence = AudioSegment.silent(duration=silence_ms)

            for i, audio_path in enumerate(chapter_audios):
                if not os.path.exists(audio_path):
                    logger.warning(f"音频文件不存在: {audio_path}")
                    continue

                audio = AudioSegment.from_file(audio_path)
                merged += audio

                # 在章节间添加静音（最后一个不加）
                if i < len(chapter_audios) - 1:
                    merged += silence

            # 导出
            fmt = os.path.splitext(output_path)[1].lstrip(".").lower()
            merged.export(output_path, format=fmt)
            logger.info(f"合并完成: {output_path} ({len(merged) / 1000:.1f} 秒)")
            return True

        except Exception as e:
            logger.error(f"合并音频失败: {e}")
            return False

    @staticmethod
    def convert_format(
        input_path: str,
        output_path: str,
        bitrate: str = "192k"
    ) -> bool:
        """音频格式转换

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            bitrate: 比特率，如 "192k", "320k"

        Returns:
            是否成功
        """
        if not _pydub_available:
            raise ImportError("pydub 未安装，请运行: pip install pydub")

        try:
            audio = AudioSegment.from_file(input_path)
            fmt = os.path.splitext(output_path)[1].lstrip(".").lower()
            audio.export(output_path, format=fmt, bitrate=bitrate)
            logger.info(f"格式转换完成: {output_path}")
            return True
        except Exception as e:
            logger.error(f"格式转换失败: {e}")
            return False

    @staticmethod
    def adjust_speed(
        input_path: str,
        output_path: str,
        speed_factor: float = 1.0
    ) -> bool:
        """调整语速

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            speed_factor: 速度因子，1.0=原速，1.5=1.5倍速，0.75=0.75倍速

        Returns:
            是否成功
        """
        if not _pydub_available:
            raise ImportError("pydub 未安装，请运行: pip install pydub")

        try:
            audio = AudioSegment.from_file(input_path)
            # pydub 的 speedup 改变播放速度同时保持音高
            adjusted = audio.speedup(playback_speed=speed_factor)
            fmt = os.path.splitext(output_path)[1].lstrip(".").lower()
            adjusted.export(output_path, format=fmt)
            logger.info(f"语速调整完成: {output_path} (x{speed_factor})")
            return True
        except Exception as e:
            logger.error(f"语速调整失败: {e}")
            return False

    @staticmethod
    def normalize_volume(
        input_path: str,
        output_path: Optional[str] = None
    ) -> bool:
        """音量归一化

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（默认覆盖输入）

        Returns:
            是否成功
        """
        if not _pydub_available:
            raise ImportError("pydub 未安装，请运行: pip install pydub")

        output_path = output_path or input_path

        try:
            audio = AudioSegment.from_file(input_path)
            normalized = audio.normalize()
            fmt = os.path.splitext(output_path)[1].lstrip(".").lower()
            normalized.export(output_path, format=fmt)
            logger.info(f"音量归一化完成: {output_path}")
            return True
        except Exception as e:
            logger.error(f"音量归一化失败: {e}")
            return False

    @staticmethod
    def trim_silence(
        input_path: str,
        output_path: str,
        silence_thresh: int = -50,
        min_silence_len: int = 1000
    ) -> bool:
        """裁切首尾静音

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            silence_thresh: 静音阈值 (dBFS)
            min_silence_len: 最小静音长度 (ms)

        Returns:
            是否成功
        """
        if not _pydub_available:
            raise ImportError("pydub 未安装，请运行: pip install pydub")

        try:
            audio = AudioSegment.from_file(input_path)

            # 去除开头静音
            start_trim = _detect_leading_silence(audio, silence_thresh)
            # 去除结尾静音
            end_trim = _detect_leading_silence(audio.reverse(), silence_thresh)

            duration = len(audio)
            trimmed = audio[start_trim:duration - end_trim]

            fmt = os.path.splitext(output_path)[1].lstrip(".").lower()
            trimmed.export(output_path, format=fmt)
            logger.info(
                f"静音裁切完成: 前 {start_trim}ms / 后 {end_trim}ms"
            )
            return True
        except Exception as e:
            logger.error(f"静音裁切失败: {e}")
            return False

    @staticmethod
    def get_audio_info(file_path: str) -> dict:
        """获取音频文件信息

        Returns:
            dict: 包含 duration_seconds, channels, sample_width, frame_rate
        """
        if not _pydub_available:
            return {}

        try:
            audio = AudioSegment.from_file(file_path)
            return {
                "duration_seconds": len(audio) / 1000.0,
                "channels": audio.channels,
                "sample_width": audio.sample_width,
                "frame_rate": audio.frame_rate,
                "format": os.path.splitext(file_path)[1].lstrip("."),
                "file_size": os.path.getsize(file_path),
            }
        except Exception as e:
            logger.error(f"获取音频信息失败: {e}")
            return {}


def _detect_leading_silence(audio_segment, silence_threshold: int = -50) -> int:
    """检测开头的静音长度（毫秒）"""
    trim_ms = 0
    chunk_size = 10  # 每次检测 10ms

    while trim_ms < len(audio_segment):
        chunk = audio_segment[trim_ms:trim_ms + chunk_size]
        if chunk.dBFS > silence_threshold:
            break
        trim_ms += chunk_size

    return trim_ms
