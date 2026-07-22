"""
Edge TTS 引擎
基于微软 Edge 免费在线 TTS 服务，支持 300+ 音色

特点:
- 免费，无需 API Key
- 支持 40+ 语言，318 种声音
- 无需 GPU
- 响应速度快
"""
import asyncio
import logging
import os
from typing import Optional

from .base import TTSEngine, VoiceInfo, SynthesisResult

logger = logging.getLogger(__name__)

# 延迟导入，因为 edge_tts 可能未安装
_edge_tts_available = False
try:
    import edge_tts  # noqa: F401
    _edge_tts_available = True
except ImportError:
    pass


class EdgeTTSEngine(TTSEngine):
    """Edge TTS 引擎

    使用微软 Edge 浏览器的免费在线 TTS 服务
    """

    ENGINE_NAME = "Edge TTS"

    def __init__(self, models_dir: Optional[str] = None):
        super().__init__(models_dir=models_dir)
        self._voices_cache: Optional[list[VoiceInfo]] = None

    def get_engine_name(self) -> str:
        return self.ENGINE_NAME

    def is_available(self) -> bool:
        """检查 edge_tts 是否已安装"""
        return _edge_tts_available

    def supports_voice_cloning(self) -> bool:
        return False

    def requires_gpu(self) -> bool:
        return False

    def get_available_voices(self) -> list[VoiceInfo]:
        """获取 Edge TTS 可用音色列表"""
        if self._voices_cache is not None:
            return self._voices_cache

        if not _edge_tts_available:
            logger.warning("edge_tts 未安装，无法获取音色列表")
            return []

        voices = []
        try:
            raw_voices = asyncio.run(edge_tts.list_voices())
            for v in raw_voices:
                voice_info = VoiceInfo(
                    voice_id=v["ShortName"],
                    name=v.get("FriendlyName", v["ShortName"]),
                    language=v.get("Locale", ""),
                    gender=v.get("Gender", ""),
                    engine=self.ENGINE_NAME,
                )
                voices.append(voice_info)

            self._voices_cache = voices
            logger.info(f"获取到 {len(voices)} 个 Edge TTS 音色")
        except Exception as e:
            logger.error(f"获取 Edge TTS 音色列表失败: {e}")

        return voices

    def get_voices_by_language(self, lang_prefix: str = "zh") -> list[VoiceInfo]:
        """按语言过滤音色

        Args:
            lang_prefix: 语言前缀，如 "zh" 中文, "en" 英语, "ja" 日语
        """
        all_voices = self.get_available_voices()
        return [
            v for v in all_voices
            if v.language.startswith(lang_prefix)
        ]

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: str = "output.mp3",
        rate: str = "+0%",
        **kwargs
    ) -> SynthesisResult:
        """使用 Edge TTS 合成语音

        Args:
            text: 要合成的文本
            voice_id: 音色 ShortName，如 "zh-CN-XiaoxiaoNeural"
            output_path: 输出文件路径
            rate: 语速，如 "+10%", "-20%", "+0%"

        Returns:
            SynthesisResult
        """
        if not _edge_tts_available:
            return SynthesisResult(
                output_path=output_path,
                success=False,
                error_message="edge_tts 未安装，请运行: pip install edge-tts"
            )

        # 如果没有指定音色，使用默认中文女声
        if voice_id is None:
            voice_id = "zh-CN-XiaoxiaoNeural"

        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        try:
            # ★ 分块合成时共享同一个线程事件循环，避免反复创建/销毁
            #    用 asyncio.run() 每次创建干净的新循环（线程安全）
            asyncio.run(self._synthesize_async(text, voice_id, output_path, rate))
            word_count = len(text)
            logger.info(f"Edge TTS 合成完成: {output_path} ({word_count} 字符)")

            return SynthesisResult(
                output_path=output_path,
                word_count=word_count,
                success=True,
            )
        except Exception as e:
            logger.error(f"Edge TTS 合成失败: {e}")
            return SynthesisResult(
                output_path=output_path,
                success=False,
                error_message=f"合成失败: {str(e)}"
            )

    async def _synthesize_async(
        self,
        text: str,
        voice: str,
        output_path: str,
        rate: str = "+0%"
    ):
        """异步合成语音（中文路径兼容）"""
        import tempfile, shutil

        # 验证路径
        logger.debug(f"Edge TTS 合成: path={repr(output_path)}")
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            logger.debug(f"目标目录不存在，将创建: {out_dir}")

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
        )
        # 先存到临时文件，再移动到目标路径（避免中文路径编码问题）
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            await communicate.save(tmp_path)
            os.makedirs(out_dir or ".", exist_ok=True)
            shutil.move(tmp_path, output_path)
            logger.info(f"Edge TTS 文件已移动到: {output_path}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def get_info(self) -> dict:
        info = super().get_info()
        info.update({
            "description": "微软 Edge 免费在线 TTS，支持 300+ 音色",
            "voice_count": len(self._voices_cache) if self._voices_cache else 0,
        })
        return info
