"""
TTS 模型管理器
统一管理所有 TTS 引擎，提供统一的调用接口
"""
import logging
from typing import Optional, Callable

from .base import TTSEngine, VoiceInfo, SynthesisResult

logger = logging.getLogger(__name__)


class ModelManager:
    """TTS 模型管理器

    职责:
    - 注册和管理多个 TTS 引擎
    - 管理本地模型下载目录
    - 提供统一的引擎切换接口
    - 代理合成请求到当前活跃引擎

    模型存储:
        所有本地模型下载到 {project_root}/models/{engine_key}/
    """

    def __init__(self, models_dir: Optional[str] = None):
        self._engines: dict[str, TTSEngine] = {}
        self.active_engine: Optional[TTSEngine] = None
        self._engine_classes: dict[str, type] = {}
        self._models_dir: Optional[str] = models_dir

    @property
    def models_dir(self) -> Optional[str]:
        """模型存储根目录"""
        return self._models_dir

    def set_models_dir(self, path: str):
        """设置模型存储根目录"""
        self._models_dir = path

    def register_engine_class(self, name: str, engine_class: type):
        """注册引擎类

        Args:
            name: 引擎名称（用于 models/ 子目录）
            engine_class: 引擎类（TTSEngine 的子类）
        """
        self._engine_classes[name] = engine_class

    def load_engine(self, engine_name: str) -> bool:
        """加载并激活指定引擎

        Args:
            engine_name: 引擎名称

        Returns:
            是否加载成功
        """
        # 如果已经加载过，直接切换
        if engine_name in self._engines:
            self.active_engine = self._engines[engine_name]
            logger.info(f"切换到引擎: {engine_name}")
            return True

        # 尝试实例化新引擎
        if engine_name in self._engine_classes:
            try:
                engine_cls = self._engine_classes[engine_name]
                engine = engine_cls(models_dir=self._models_dir)
                if engine.is_available():
                    self._engines[engine_name] = engine
                    self.active_engine = engine
                    logger.info(f"加载引擎成功: {engine_name}")
                    return True
                else:
                    logger.warning(f"引擎 {engine_name} 不可用（依赖未安装或模型未下载）")
                    return False
            except Exception as e:
                logger.error(f"加载引擎 {engine_name} 失败: {e}")
                return False

        logger.warning(f"未注册的引擎: {engine_name}")
        return False

    def get_available_engines(self) -> list[dict]:
        """获取所有已注册引擎的信息"""
        result = []
        for name, cls in self._engine_classes.items():
            info = {
                "name": name,
                "loaded": name in self._engines,
                "active": self.active_engine is not None
                and self.active_engine.get_engine_key() == name,
            }
            if name in self._engines:
                info.update(self._engines[name].get_info())
            else:
                info["available"] = True
            result.append(info)
        return result

    def get_active_engine_name(self) -> Optional[str]:
        """获取当前活跃引擎名称"""
        if self.active_engine:
            return self.active_engine.get_engine_name()
        return None

    def download_model(
        self,
        engine_name: str,
        progress_callback: Optional[Callable[[str, int], None]] = None,
        model_name: str = "default"
    ) -> bool:
        """下载模型权重文件到本地 models/ 目录

        优先使用引擎自身的 download_model 方法（如果实现了），
        否则使用通用的 model_downloader。

        Args:
            engine_name: 引擎名称
            progress_callback: 进度回调 func(message, percent)
            model_name: 模型名称

        Returns:
            是否下载成功
        """
        # 检查引擎是否已加载
        if engine_name not in self._engines:
            # 尝试加载（如果依赖可用）
            if not self.load_engine(engine_name):
                # 引擎无法加载（依赖未安装），但可能仍然可以下载模型
                logger.info(f"引擎 {engine_name} 未加载，使用通用下载")

        # 先尝试引擎自身的下载方法
        if engine_name in self._engines:
            engine = self._engines[engine_name]
            if engine.download_model(model_name):
                return True

        # 使用通用下载器
        from ..model_downloader import download_model as generic_download
        return generic_download(engine_name, progress_callback)

    def get_available_voices(self) -> list[VoiceInfo]:
        """获取当前引擎的音色列表（含克隆音色）"""
        if self.active_engine:
            return self.active_engine.get_all_voices()
        return []

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        output_path: str = "output.mp3",
        **kwargs
    ) -> SynthesisResult:
        """合成语音

        Args:
            text: 要合成的文本
            voice_id: 音色ID
            output_path: 输出文件路径
            **kwargs: 其他参数（如 rate）

        Returns:
            SynthesisResult: 合成结果
        """
        if self.active_engine is None:
            return SynthesisResult(
                output_path=output_path,
                success=False,
                error_message="没有活跃的 TTS 引擎，请先选择一个模型"
            )

        return self.active_engine.synthesize(
            text=text,
            voice_id=voice_id,
            output_path=output_path,
            **kwargs
        )

    def clone_voice(
        self,
        reference_audio: str,
        text: Optional[str] = None
    ) -> Optional[str]:
        """克隆音色

        Args:
            reference_audio: 参考音频文件路径
            text: 参考音频对应的文本

        Returns:
            克隆后的音色ID
        """
        if self.active_engine is None:
            logger.error("没有活跃的 TTS 引擎")
            return None

        if not self.active_engine.supports_voice_cloning():
            logger.warning(f"当前引擎 {self.active_engine.get_engine_name()} 不支持音色克隆")
            return None

        return self.active_engine.clone_voice(reference_audio, text)
