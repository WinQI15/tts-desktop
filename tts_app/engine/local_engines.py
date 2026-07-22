"""
本地 TTS 引擎实现

存储结构:
    models/
    └── OmniVoice/       # k2-fsa/OmniVoice 权重（~2.3GB）
"""
import sys
import os
import logging
from typing import Optional

from .base import TTSEngine, VoiceInfo, SynthesisResult

logger = logging.getLogger(__name__)

PY313 = sys.version_info >= (3, 13)


def _check_import(module_name: str, install_hint: str) -> tuple[bool, str]:
    """检查模块是否可导入"""
    import importlib.util
    spec = importlib.util.find_spec(module_name)
    if spec is not None:
        return True, ""
    return False, install_hint


def _check_gpu() -> str:
    """检查 GPU 可用性"""
    ok, _ = _check_import("torch", "")
    if not ok:
        return ""
    try:
        import torch
        if not torch.cuda.is_available():
            return "⚠ 未检测到 GPU（CPU 推理极慢）"
    except Exception:
        pass
    return ""


# ============================================================
# OmniVoice — 600+ 语言零样本 TTS（小米）
# ============================================================

class OmniVoiceEngine(TTSEngine):
    """OmniVoice — 多语言零样本 TTS

    600+ 语言，零样本音色克隆，600M 参数。
    需要 GPU（CUDA），模型约 2.3GB。
    
    ★ 模型缓存：首次 synthesize() 加载模型到 self._cached_model，
      后续调用直接复用（避免分块合成时重复加载导致 OOM）。
    """

    ENGINE_NAME = "OmniVoice"
    ENGINE_KEY = "omnivoice"

    def __init__(self, models_dir: Optional[str] = None):
        super().__init__(models_dir=models_dir)
        self._cached_model = None   # 缓存的 OmniVoice 模型实例
        self._cached_tokenizer = None
        self._cached_extractor = None
        self._cached_audio_tok = None

    def get_engine_name(self) -> str:
        return self.ENGINE_NAME

    def get_engine_key(self) -> str:
        return self.ENGINE_KEY

    def unload_model(self):
        """释放缓存的模型（释放 GPU 显存）"""
        if self._cached_model is not None:
            import gc, torch
            self._cached_model = None
            self._cached_tokenizer = None
            self._cached_extractor = None
            self._cached_audio_tok = None
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("OmniVoice 模型已从缓存中释放")

    def _get_or_load_model(self):
        """获取缓存的模型，如果未加载则加载"""
        if self._cached_model is not None:
            return self._cached_model, self._cached_tokenizer, \
                   self._cached_extractor, self._cached_audio_tok

        import torch
        from omnivoice import OmniVoice

        logger.info("正在加载 OmniVoice 模型...")
        model = OmniVoice.from_pretrained(
            self.engine_models_dir,
            device_map="cuda:0",
            dtype=torch.float16,
        )
        model.eval()

        # 缓存模型及子组件
        self._cached_model = model
        self._cached_tokenizer = getattr(model, "text_tokenizer", None)
        self._cached_extractor = getattr(model, "feature_extractor", None)
        self._cached_audio_tok = getattr(model, "audio_tokenizer", None)

        logger.info("OmniVoice 模型加载完成并缓存")
        return self._cached_model, self._cached_tokenizer, \
               self._cached_extractor, self._cached_audio_tok

    def supports_voice_cloning(self) -> bool:
        return True

    def requires_gpu(self) -> bool:
        return True

    def is_available(self) -> bool:
        return len(self.get_missing_deps()) == 0

    def get_missing_deps(self) -> list[str]:
        missing = []
        if not _check_import("torch", "pip install torch torchaudio")[0]:
            missing.append("pip install torch torchaudio")
        if not _check_import("omnivoice", "pip install omnivoice")[0]:
            missing.append("pip install omnivoice")
        if not _check_import("transformers", "pip install transformers")[0]:
            missing.append("pip install transformers")
        if not _check_import("soundfile", "pip install soundfile")[0]:
            missing.append("pip install soundfile")
        if not self.is_model_downloaded():
            missing.append("模型未下载 — 请点击「下载模型」")
        try:
            import torch
            if not torch.cuda.is_available():
                missing.append("❌ 需要 NVIDIA GPU (CUDA)，CPU 不可用")
        except Exception:
            missing.append("❌ 需要 NVIDIA GPU (CUDA)，CPU 不可用")
        return missing

    def get_warnings(self) -> list[str]:
        return []

    def is_model_downloaded(self) -> bool:
        """检查模型是否已下载 — 需 model.safetensors + config.json"""
        model_dir = self.engine_models_dir
        return os.path.isfile(os.path.join(model_dir, "model.safetensors")) and \
               os.path.isfile(os.path.join(model_dir, "config.json"))

    PRESET_VOICES_DIR = "models/preset_voices"

    def get_available_voices(self) -> list[VoiceInfo]:
        voices = []
        # 加载 preset_voices 目录中的参考音频
        presets_dir = self.PRESET_VOICES_DIR
        if os.path.isdir(presets_dir):
            for f in sorted(os.listdir(presets_dir)):
                if f.endswith(".wav"):
                    name = os.path.splitext(f)[0].replace("_", " ").title()
                    voices.append(VoiceInfo(
                        voice_id=f"preset_{f}",
                        name=f"🎤 {name}",
                        engine=self.ENGINE_NAME,
                        description="预设参考音色",
                    ))
        return voices

    def _get_preset_ref(self, voice_id: str) -> tuple[str, str] | None:
        """获取预设音色的参考音频路径和文本"""
        if voice_id and voice_id.startswith("preset_"):
            fname = voice_id.replace("preset_", "")
            path = os.path.join(self.PRESET_VOICES_DIR, fname)
            if os.path.exists(path):
                # 用音色名作为参考文本
                ref_text = f"This is a reference audio sample."
                return path, ref_text
        return None

    def synthesize(
        self, text: str, voice_id: Optional[str] = None,
        output_path: str = "output.wav", rate: str = "+0%", **kwargs
    ) -> SynthesisResult:
        if not self.is_available():
            return SynthesisResult(
                output_path=output_path, success=False,
                error_message=f"{self.ENGINE_NAME} 不可用。"
                              f"请确保依赖已安装且模型已下载"
            )
        try:
            import torch
            import soundfile as sf

            # 确保输出目录存在
            out_dir = os.path.dirname(output_path) or "."
            os.makedirs(out_dir, exist_ok=True)

            # ★ 使用缓存模型，避免重复加载
            model, _, _, _ = self._get_or_load_model()

            # 获取参考音频（预设音色 或 克隆音色）
            ref_audio = kwargs.get("ref_audio", None)
            ref_text = kwargs.get("ref_text", text)

            preset = self._get_preset_ref(voice_id)
            if preset:
                ref_audio, ref_text = preset

            with torch.no_grad():
                audio_list = model.generate(
                    text=text,
                    ref_audio=ref_audio,
                    ref_text=ref_text,
                )
                audio = audio_list[0]

            # 写入音频（中文路径兼容：失败时用临时文件再移动）
            try:
                sf.write(output_path, audio, 24000)
            except Exception:
                import tempfile, shutil
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.close()
                try:
                    sf.write(tmp.name, audio, 24000)
                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                    shutil.move(tmp.name, output_path)
                finally:
                    if os.path.exists(tmp.name):
                        os.remove(tmp.name)
            return SynthesisResult(
                output_path=output_path, word_count=len(text), success=True
            )
        except Exception as e:
            logger.error(f"{self.ENGINE_NAME} 合成失败: {e}")
            return SynthesisResult(
                output_path=output_path, success=False,
                error_message=f"合成失败: {str(e)}"
            )

    def clone_voice(self, reference_audio: str, text: Optional[str] = None) -> Optional[str]:
        """注册参考音频为克隆音色"""
        if not self.is_available():
            return None
        voice_id = f"omnivoice_{hash(reference_audio) & 0xFFFF:04x}"
        return voice_id

    def download_model(self, model_name: str = "default") -> bool:
        from ..model_downloader import download_model
        return download_model("omnivoice")

    def get_info(self) -> dict:
        info = super().get_info()
        info["description"] = "OmniVoice — 600+语言，GPU 零样本克隆，600M 参数"
        info["model_size"] = "~2.3GB"
        info["pip_install"] = "pip install torch torchaudio transformers soundfile omnivoice"
        return info
