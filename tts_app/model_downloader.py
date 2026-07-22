"""
模型下载管理器
负责从 HuggingFace / ModelScope 下载 TTS 模型权重到本地 models/ 目录

模型存储结构:
    models/
    ├── f5_tts/           # F5-TTS 模型权重
    ├── kokoro/            # Kokoro 模型权重
    ├── chattts/           # ChatTTS 模型权重
    ├── xtts_v2/           # XTTS-v2 模型权重
    └── voxcpm/            # VoxCPM 模型权重

每个引擎在 models/ 下有自己的子目录，存储从 HuggingFace 下载的完整模型文件。
"""
import os
import logging
from pathlib import Path
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ============================================================
# 模型目录管理
# ============================================================

# 项目根目录（tts-desktop/）
_PROJECT_ROOT = Path(__file__).parent.parent

# 模型存储根目录
MODELS_DIR = _PROJECT_ROOT / "models"

# HuggingFace 模型仓库映射
# key: 引擎名, value: (repo_id, 模型大小估算, 说明)
MODEL_REGISTRY = {
    "omnivoice": {
        "repo_id": "k2-fsa/OmniVoice",
        "size_gb": 2.3,
        "description": "OmniVoice — 600+语言零样本 TTS，600M 参数，支持音色克隆",
        "requires_gpu": True,
    },
}


def get_models_dir() -> Path:
    """获取模型存储根目录"""
    return MODELS_DIR


def get_engine_models_dir(engine_name: str) -> Path:
    """获取指定引擎的模型目录"""
    return MODELS_DIR / engine_name


def ensure_models_dir(engine_name: str = "") -> Path:
    """确保模型目录存在，返回目录路径"""
    if engine_name:
        dir_path = MODELS_DIR / engine_name
    else:
        dir_path = MODELS_DIR
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def is_model_downloaded(engine_name: str) -> bool:
    """检查指定引擎的模型是否已下载

    判断标准：模型目录存在且包含文件
    """
    model_dir = get_engine_models_dir(engine_name)
    if not model_dir.exists():
        return False

    # 检查目录中是否有实际文件（不只是空目录）
    files = list(model_dir.rglob("*"))
    # 排除 __pycache__ 等
    real_files = [f for f in files if f.is_file()
                  and "__pycache__" not in str(f)]
    return len(real_files) > 0


def get_downloaded_models() -> list[str]:
    """获取已下载的模型列表"""
    downloaded = []
    if MODELS_DIR.exists():
        for engine_name in MODEL_REGISTRY:
            if is_model_downloaded(engine_name):
                downloaded.append(engine_name)
    return downloaded


def get_model_info(engine_name: str) -> Optional[dict]:
    """获取模型注册信息"""
    return MODEL_REGISTRY.get(engine_name)


def get_models_dir_size() -> str:
    """计算 models/ 目录总大小（人类可读）"""
    if not MODELS_DIR.exists():
        return "0 MB"

    total = 0
    for f in MODELS_DIR.rglob("*"):
        if f.is_file():
            total += f.stat().st_size

    if total < 1024 * 1024:
        return f"{total / 1024:.1f} KB"
    elif total < 1024 * 1024 * 1024:
        return f"{total / (1024 * 1024):.1f} MB"
    else:
        return f"{total / (1024 * 1024 * 1024):.1f} GB"


# ============================================================
# 模型下载
# ============================================================

def download_model(
    engine_name: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
    force: bool = False,
) -> bool:
    """从 HuggingFace 下载模型到本地 models/ 目录

    Args:
        engine_name: 引擎名称（如 "f5_tts", "kokoro"）
        progress_callback: 进度回调 func(message, percent)
        force: 是否强制重新下载（即使已存在）

    Returns:
        是否下载成功
    """
    model_info = MODEL_REGISTRY.get(engine_name)
    if not model_info:
        logger.error(f"未知的模型: {engine_name}")
        if progress_callback:
            progress_callback(f"错误: 未知的模型 '{engine_name}'", 0)
        return False

    repo_id = model_info["repo_id"]
    target_dir = get_engine_models_dir(engine_name)
    target_dir_str = str(target_dir)

    # 检查是否已下载
    already_downloaded = is_model_downloaded(engine_name)
    if already_downloaded and not force:
        # 模型已存在，但仍需确保 audio_tokenizer 就位
        if engine_name == "omnivoice":
            _download_audio_tokenizer(target_dir, progress_callback)
        logger.info(f"模型 {engine_name} 已存在: {target_dir_str}")
        if progress_callback:
            progress_callback(f"模型已存在: {target_dir_str}", 100)
        return True

    # 确保目录存在
    ensure_models_dir(engine_name)

    # 尝试使用 huggingface_hub 下载
    if progress_callback:
        progress_callback(f"正在连接 HuggingFace...", 5)

    try:
        from huggingface_hub import snapshot_download

        if progress_callback:
            progress_callback(f"正在下载 {repo_id}...", 10)

        # 下载到本地目录（token=False 禁用认证，避免未认证警告）
        snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir_str,
            local_dir_use_symlinks=False,
            resume_download=True,
            max_workers=4,
            token=False,
        )

        # ★ OmniVoice 额外依赖: audio_tokenizer
        #   必须下载到 models/OmniVoice/audio_tokenizer/，否则每次加载
        #   引擎时都会从 HuggingFace 重新下载 (~806MB)
        if engine_name == "omnivoice":
            _download_audio_tokenizer(target_dir, progress_callback)

        logger.info(f"模型下载完成: {engine_name} -> {target_dir_str}")
        if progress_callback:
            progress_callback(f"下载完成！保存在: {target_dir_str}", 100)
        return True

    except ImportError:
        logger.warning("huggingface_hub 未安装")
        if progress_callback:
            progress_callback(
                "需要安装 huggingface_hub: pip install huggingface_hub",
                0
            )
        return False

    except Exception as e:
        logger.error(f"下载模型失败: {e}")
        if progress_callback:
            progress_callback(f"下载失败: {str(e)[:100]}", 0)
        return False


def _download_audio_tokenizer(
    model_dir: Path,
    progress_callback: Optional[Callable[[str, int], None]] = None,
):
    """下载 OmniVoice 需要的 audio tokenizer 到模型子目录
    
    eustlb/higgs-audio-v2-tokenizer (~806MB)
    """
    tokenizer_dir = model_dir / "audio_tokenizer"
    if tokenizer_dir.is_dir() and any(tokenizer_dir.iterdir()):
        logger.info("audio_tokenizer 已存在，跳过下载")
        return

    repo_id = "eustlb/higgs-audio-v2-tokenizer"
    try:
        from huggingface_hub import snapshot_download
        if progress_callback:
            progress_callback(f"正在下载 audio tokenizer ({repo_id})...", 15)
        logger.info(f"下载 audio tokenizer: {repo_id} -> {tokenizer_dir}")
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(tokenizer_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            max_workers=4,
            token=False,
        )
        logger.info("audio_tokenizer 下载完成")
    except Exception as e:
        logger.warning(f"audio_tokenizer 下载失败 (非致命): {e}")


def download_model_generic(
    engine_name: str,
    repo_id: str,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> bool:
    """通用的模型下载函数（支持自定义 repo_id）

    Args:
        engine_name: 引擎名称
        repo_id: HuggingFace repo ID
        progress_callback: 进度回调

    Returns:
        是否下载成功
    """
    target_dir = get_engine_models_dir(engine_name)
    target_dir_str = str(target_dir)
    ensure_models_dir(engine_name)

    try:
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir_str,
            local_dir_use_symlinks=False,
            resume_download=True,
            token=False,
        )

        logger.info(f"模型下载完成: {engine_name} -> {target_dir_str}")
        return True

    except ImportError:
        logger.warning("huggingface_hub 未安装")
        return False
    except Exception as e:
        logger.error(f"下载模型失败: {e}")
        return False
