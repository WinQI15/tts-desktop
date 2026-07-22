"""
TTS 引擎抽象基类
定义所有 TTS 引擎必须实现的统一接口
"""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class VoiceInfo:
    """音色信息"""
    voice_id: str
    name: str
    language: str = ""
    gender: str = ""
    engine: str = ""
    is_cloned: bool = False
    description: str = ""


@dataclass
class SynthesisResult:
    """合成结果"""
    output_path: str
    duration_seconds: float = 0.0
    word_count: int = 0
    success: bool = True
    error_message: str = ""


class TTSEngine(ABC):
    """TTS 引擎抽象基类

    所有 TTS 引擎必须实现以下方法:
    - get_engine_name(): 返回引擎名称
    - get_available_voices(): 获取可用音色列表
    - synthesize(): 合成语音

    模型文件存储在: {project_root}/models/{engine_key}/
    """

    def __init__(self, models_dir: Optional[str] = None):
        """初始化引擎

        Args:
            models_dir: 模型存储根目录，默认为项目下的 models/
        """
        self._models_dir = models_dir

    @property
    def models_dir(self) -> str:
        """模型存储根目录"""
        if self._models_dir:
            return self._models_dir
        return str(Path(__file__).parent.parent.parent / "models")

    @property
    def engine_models_dir(self) -> str:
        """本引擎的模型目录: models/<engine_key>/"""
        return os.path.join(self.models_dir, self.get_engine_key())

    def get_engine_key(self) -> str:
        """获取引擎键名（用于 models/ 子目录名）"""
        return self.get_engine_name().lower().replace(" ", "_").replace("-", "_")

    def get_all_voices(self) -> list[VoiceInfo]:
        """获取所有音色（预设 + 已克隆）"""
        voices = self.get_available_voices()

        # 附加已克隆音色
        store = self._get_cloned_voice_store()
        if store:
            cloned = store.get_voices_for_engine(self.get_engine_key())
            for cv in cloned:
                voices.append(VoiceInfo(
                    voice_id=cv["id"],
                    name=cv["name"],
                    engine=self.get_engine_name(),
                    is_cloned=True,
                    description=f"克隆音色 · {cv.get('created_at', '')[:10]}",
                ))
        return voices

    def _get_cloned_voice_store(self):
        """懒加载克隆音色管理器"""
        try:
            from ..cloned_voice_store import get_cloned_voice_store
            return get_cloned_voice_store(os.path.join(self.models_dir, "cloned_voices.json"))
        except Exception:
            return None

    def is_model_downloaded(self) -> bool:
        """模型权重文件是否已下载到本地"""
        model_dir = Path(self.engine_models_dir)
        if not model_dir.exists():
            return False
        files = [f for f in model_dir.rglob("*") if f.is_file()
                 and "__pycache__" not in str(f)]
        return len(files) > 0

    @abstractmethod
    def get_engine_name(self) -> str:
        """获取引擎名称"""
        pass

    @abstractmethod
    def get_available_voices(self) -> list[VoiceInfo]:
        """获取可用音色列表"""
        pass

    @abstractmethod
    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: str = "output.mp3",
        rate: str = "+0%",
        **kwargs
    ) -> SynthesisResult:
        """合成语音

        Args:
            text: 要合成的文本
            voice_id: 音色ID
            output_path: 输出文件路径
            rate: 语速调节，如 "+10%" 或 "-20%"

        Returns:
            SynthesisResult: 合成结果
        """
        pass

    def clone_voice(
        self,
        reference_audio: str,
        text: Optional[str] = None
    ) -> Optional[str]:
        """克隆音色（可选实现）

        从参考音频学习音色特征，创建新的音色

        Args:
            reference_audio: 参考音频文件路径
            text: 参考音频对应的文本（可选，提升克隆质量）

        Returns:
            克隆后的音色ID，不支持则返回 None
        """
        return None

    def download_model(self, model_name: str = "default") -> bool:
        """下载模型（可选实现）

        Args:
            model_name: 模型名称

        Returns:
            是否下载成功
        """
        return False

    def supports_voice_cloning(self) -> bool:
        """是否支持音色克隆"""
        return False

    def requires_gpu(self) -> bool:
        """是否需要 GPU"""
        return False

    def is_available(self) -> bool:
        """引擎是否可用（依赖是否安装）"""
        return True

    def get_missing_deps(self) -> list[str]:
        """获取缺失的依赖列表（供 GUI 显示）

        返回人类可读的缺失项，如 ["pip install kokoro", "需要 Python < 3.13"]
        """
        return []

    def get_warnings(self) -> list[str]:
        """获取警告信息（不阻止使用，仅在界面提示）"""
        return []

    def get_info(self) -> dict:
        """获取引擎信息"""
        return {
            "name": self.get_engine_name(),
            "supports_cloning": self.supports_voice_cloning(),
            "requires_gpu": self.requires_gpu(),
            "available": self.is_available(),
            "model_downloaded": self.is_model_downloaded(),
            "models_dir": self.engine_models_dir,
        }
