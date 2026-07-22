"""
文本转语音桌面程序 (Text-to-Speech Desktop)
============================================

主入口文件

功能:
- EPUB 书籍导入与解析
- 多引擎 TTS 语音合成
- 300+ 音色选择与切换
- 语音参数调节（语速等）
- 音频文件导出
- 本地模型下载管理

使用方法:
    python main.py

便携说明:
    所有 Python 依赖已安装到 vendor/ 目录。
    复制整个 tts-desktop/ 文件夹到其他设备即可运行。
"""
import sys
import os
import logging
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.resolve()

# ★ 便携模式：优先从项目内 vendor/ 加载依赖
#   复制到其他设备时无需 pip install，依赖随项目携带
VENDOR_DIR = PROJECT_ROOT / "vendor"
if VENDOR_DIR.is_dir():
    sys.path.insert(0, str(VENDOR_DIR))
    # Windows 下注册 DLL 搜索路径
    # 使用 PATH 环境变量（传统搜索顺序，支持链式依赖），
    # 而非 os.add_dll_directory（SetDefaultDllDirectories 会改变
    # 搜索策略，导致 c10.dll 等 DLL 找不到依赖）
    if sys.platform == "win32":
        _extra_paths = []
        # torch DLL 目录（c10.dll, torch.dll 等）
        torch_lib = VENDOR_DIR / "torch" / "lib"
        if torch_lib.is_dir():
            _extra_paths.insert(0, str(torch_lib))
        # ONNX Runtime DLL
        onnx_lib = VENDOR_DIR / "onnxruntime" / "capi"
        if onnx_lib.is_dir():
            _extra_paths.insert(0, str(onnx_lib))
        # PyQt5 Qt5 DLL
        qt5_dll = VENDOR_DIR / "PyQt5" / "Qt5" / "bin"
        if qt5_dll.is_dir():
            _extra_paths.insert(0, str(qt5_dll))
        # ffmpeg 便携二进制 (ffmpeg.exe + ffprobe.exe)
        ffmpeg_bin = VENDOR_DIR / "ffmpeg" / "bin"
        if ffmpeg_bin.is_dir():
            _extra_paths.insert(0, str(ffmpeg_bin))
        # vendor 根目录
        _extra_paths.insert(0, str(VENDOR_DIR))

        if _extra_paths:
            _sep = ";" if sys.platform == "win32" else ":"
            os.environ["PATH"] = _sep.join(_extra_paths) + _sep + os.environ.get("PATH", "")

# ★ 抑制 HuggingFace Hub 未认证警告（匿名下载完全可用）
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
# 提高 hf hub 日志级别，抑制 HTTP 401 等噪音警告
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub.utils._http").setLevel(logging.ERROR)

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(PROJECT_ROOT))

# ★ 显式设置 pydub 的 ffmpeg/ffprobe 路径（避免 RuntimeWarning）
#    必须在任何 pydub 导入之前执行
_ffmpeg_exe = VENDOR_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"
_ffprobe_exe = VENDOR_DIR / "ffmpeg" / "bin" / "ffprobe.exe"
if _ffmpeg_exe.is_file():
    # pydub 会自动使用这些环境变量
    os.environ.setdefault("FFMPEG_BINARY", str(_ffmpeg_exe))
if _ffprobe_exe.is_file():
    os.environ.setdefault("FFPROBE_BINARY", str(_ffprobe_exe))

# 用环境变量提前告诉 pydub 的路径查找
if _ffmpeg_exe.is_file():
    # 直接把 ffmpeg 目录加在最前面，确保 shutil.which 能找到
    _ffmpeg_dir = str(_ffmpeg_exe.parent)
    _existing_path = os.environ.get("PATH", "")
    if _ffmpeg_dir not in _existing_path:
        os.environ["PATH"] = _ffmpeg_dir + ";" + _existing_path

# ★ 最早期导入 torch/onnxruntime（在模块级，先于任何函数调用）
# 失败不影响启动，仅记录状态
_TORCH_OK = False
_ONNX_OK = False
try:
    import torch as _torch
    _TORCH_OK = True
except Exception:
    pass
try:
    import onnxruntime as _ort
    _ONNX_OK = True
except Exception:
    pass

# 模型存储目录
MODELS_DIR = PROJECT_ROOT / "models"

# 确保 models 目录存在
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("tts-desktop")


def check_dependencies() -> list[str]:
    """检查必要依赖是否安装，返回缺失的依赖列表"""
    missing = []

    # 检查 PyQt5
    try:
        import PyQt5  # noqa: F401
    except ImportError:
        missing.append("PyQt5")

    # 检查 edge_tts
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        missing.append("edge-tts")

    # 可选依赖
    try:
        import ebooklib  # noqa: F401
    except ImportError:
        missing.append("ebooklib (EPUB 导入)")

    try:
        import bs4  # noqa: F401
    except ImportError:
        missing.append("beautifulsoup4 (EPUB 解析)")

    try:
        import pydub  # noqa: F401
    except ImportError:
        missing.append("pydub (音频处理)")

    return missing


def _create_splash(progress_total: int = 8):
    """创建启动闪屏（含进度条 + 状态文字）
    
    返回 (splash, progress_bar, status_label, update_fn)
    """
    from PyQt5.QtWidgets import (
        QSplashScreen, QProgressBar, QVBoxLayout, QWidget, QLabel
    )
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPixmap, QColor, QFont

    # 纯色闪屏 (600x200)
    pix = QPixmap(600, 200)
    pix.fill(QColor("#2c3e50"))

    splash = QSplashScreen(pix)
    splash.setWindowFlags(
        splash.windowFlags() | Qt.WindowStaysOnTopHint
    )

    # 在 splash 上叠加一个透明 widget 承载进度条和文字
    overlay = QWidget(splash)
    overlay.setGeometry(0, 0, 600, 200)
    overlay.setStyleSheet("background: transparent;")

    layout = QVBoxLayout(overlay)
    layout.setContentsMargins(40, 35, 40, 30)
    layout.setSpacing(12)

    # 标题
    title = QLabel("TTS Desktop")
    title.setAlignment(Qt.AlignCenter)
    title.setStyleSheet(
        "color: #ecf0f1; font-size: 24px; font-weight: bold;"
        "font-family: 'Microsoft YaHei';"
    )
    layout.addWidget(title)

    # 状态文字
    status_label = QLabel("正在初始化...")
    status_label.setAlignment(Qt.AlignCenter)
    status_label.setStyleSheet(
        "color: #bdc3c7; font-size: 13px;"
        "font-family: 'Microsoft YaHei';"
    )
    layout.addWidget(status_label)

    layout.addStretch()

    # 进度条
    progress_bar = QProgressBar()
    progress_bar.setRange(0, progress_total)
    progress_bar.setValue(0)
    progress_bar.setTextVisible(True)
    progress_bar.setFormat("%p%")
    progress_bar.setFixedHeight(22)
    progress_bar.setStyleSheet("""
        QProgressBar {
            border: 1px solid #7f8c8d;
            border-radius: 4px;
            background: #34495e;
            color: #ecf0f1;
            font-size: 12px;
            font-family: 'Microsoft YaHei';
        }
        QProgressBar::chunk {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 1, y2: 0,
                stop: 0 #3498db, stop: 1 #2ecc71
            );
            border-radius: 3px;
        }
    """)
    layout.addWidget(progress_bar)

    # 底部提示
    hint = QLabel("便携版 · 多引擎 TTS")
    hint.setAlignment(Qt.AlignCenter)
    hint.setStyleSheet(
        "color: #7f8c8d; font-size: 10px;"
        "font-family: 'Microsoft YaHei';"
    )
    layout.addWidget(hint)

    splash.show()

    def update_progress(step: int, message: str = ""):
        """更新进度条和状态文字"""
        progress_bar.setValue(step)
        if message:
            status_label.setText(message)
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    return splash, progress_bar, status_label, update_progress


def main():
    """主函数"""

    # ── 第 1 步：创建 QApplication（尽早，以便显示闪屏） ──
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtGui import QFont

    app = QApplication(sys.argv)
    app.setApplicationName("TTS Desktop")
    app.setFont(QFont("Microsoft YaHei", 10))

    # ── 启动闪屏 ──
    splash, pbar, slabel, update = _create_splash(progress_total=8)
    update(0, "正在启动 TTS Desktop...")

    # ── 第 2 步：检查依赖 ──
    update(1, "检查依赖模块...")
    missing = check_dependencies()

    if "PyQt5" in missing:
        splash.close()
        print("=" * 60)
        print("  错误: PyQt5 未安装")
        print("  请运行: pip install PyQt5")
        print("=" * 60)
        sys.exit(1)

    if "edge-tts" in missing:
        # 不阻塞启动，仅记录
        logger.warning("edge-tts 未安装，Edge TTS 引擎不可用")

    optional_missing = [m for m in missing if m not in ("PyQt5", "edge-tts")]
    if optional_missing:
        logger.warning(f"可选依赖缺失: {', '.join(optional_missing)}")

    # ── 第 3 步：模型状态 ──
    update(2, "扫描本地模型...")
    try:
        from tts_app.model_downloader import (
            get_downloaded_models, get_models_dir_size, MODEL_REGISTRY
        )
        models_size = get_models_dir_size()
        downloaded = get_downloaded_models()
        logger.info(f"模型目录: {MODELS_DIR} ({models_size}), 已下载: {downloaded}")
    except Exception as e:
        logger.warning(f"扫描模型状态失败: {e}")

    # ── 第 4 步：检查 ffmpeg ──
    update(3, "检查音视频工具 ffmpeg...")
    import shutil
    _ffmpeg_found = shutil.which("ffmpeg")
    if _ffmpeg_found:
        logger.info(f"ffmpeg: {_ffmpeg_found}")
    else:
        ffmpeg_local = VENDOR_DIR / "ffmpeg" / "bin" / "ffmpeg.exe"
        if not ffmpeg_local.is_file():
            logger.warning("ffmpeg 未找到 - 音频导出功能将受限")

    # ── 第 5 步：预加载核心库 ──
    update(4, "加载 PyTorch / ONNX Runtime...")
    _preloaded = []
    for _mod_name in ["torch", "onnxruntime", "soundfile"]:
        try:
            __import__(_mod_name)
            _preloaded.append(_mod_name)
        except Exception as e:
            logger.debug(f"预加载跳过 {_mod_name}: {e}")

    # ── 第 6 步：显式加载 DLL ──
    update(5, "初始化本地 DLL...")
    _dlls_loaded = []
    if sys.platform == "win32" and _TORCH_OK:
        import ctypes
        _dll_candidates = [
            VENDOR_DIR / "torch" / "lib" / "c10.dll",
            VENDOR_DIR / "torch" / "lib" / "torch_cpu.dll",
            VENDOR_DIR / "torch" / "lib" / "torch_python.dll",
            VENDOR_DIR / "onnxruntime" / "capi" / "onnxruntime.dll",
        ]
        for _dll in _dll_candidates:
            if _dll.is_file():
                try:
                    _ = ctypes.CDLL(str(_dll))
                    _dlls_loaded.append(_dll.name)
                except Exception:
                    pass

    # ── 第 7 步：创建主窗口 ──
    update(6, "构建用户界面...")
    from tts_app.gui import MainWindow
    window = MainWindow(models_dir=str(MODELS_DIR))

    # ── 第 8 步：完成 ──
    update(7, "初始化引擎...")
    from PyQt5.QtWidgets import QApplication as _QApp
    _QApp.processEvents()

    # 等主窗口准备好
    update(8, "就绪 ✓")
    window.show()
    splash.finish(window)

    logger.info(f"TTS Desktop 启动成功 (models: {MODELS_DIR})")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
