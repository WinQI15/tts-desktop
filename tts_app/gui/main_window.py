"""
TTS 桌面程序主界面
基于 PyQt5 构建，包含完整的 EPUB 导入、音色管理、文本合成等功能
"""
import os
import sys
import logging
import tempfile
import subprocess
import platform
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QSlider, QProgressBar,
    QFileDialog, QMessageBox, QSplitter, QStatusBar,
    QApplication, QFrame, QSizePolicy, QSpacerItem,
    QInputDialog,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QThreadPool, QRunnable,
    QObject, pyqtSlot,
)
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor

from ..engine import (
    ModelManager, TTSEngine, EdgeTTSEngine,
    OmniVoiceEngine,
    VoiceInfo, SynthesisResult,
)
from ..epub_parser import EpubParser
from ..audio_processor import AudioExporter
from ..model_downloader import (
    MODELS_DIR as DEFAULT_MODELS_DIR,
    get_downloaded_models, get_model_info, get_models_dir_size,
    MODEL_REGISTRY,
)
from ..cloned_voice_store import get_cloned_voice_store

logger = logging.getLogger(__name__)


# ============================================================
# 样式表
# ============================================================

APP_STYLESHEET = """
QMainWindow {
    background-color: #f5f6fa;
}

QGroupBox {
    font-size: 13px;
    font-weight: bold;
    color: #2c3e50;
    border: 1px solid #dcdde1;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: #2c3e50;
}

QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: bold;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #2980b9;
}

QPushButton:pressed {
    background-color: #1a6daa;
}

QPushButton:disabled {
    background-color: #bdc3c7;
    color: #7f8c8d;
}

QPushButton#browseBtn, QPushButton#refreshBtn, QPushButton#playBtn {
    background-color: #ecf0f1;
    color: #2c3e50;
    border: 1px solid #bdc3c7;
    font-weight: normal;
}

QPushButton#browseBtn:hover, QPushButton#refreshBtn:hover, QPushButton#playBtn:hover {
    background-color: #dfe6e9;
}

QPushButton#generateBtn {
    background-color: #27ae60;
    font-size: 14px;
    padding: 10px 32px;
}

QPushButton#generateBtn:hover {
    background-color: #219a52;
}

QPushButton#cloneBtn {
    background-color: #e67e22;
}

QPushButton#cloneBtn:hover {
    background-color: #d35400;
}

QPushButton#exportBtn {
    background-color: #8e44ad;
}

QPushButton#exportBtn:hover {
    background-color: #7d3c98;
}

QComboBox {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 13px;
    min-height: 16px;
    color: #2c3e50;
}

QComboBox:hover {
    border-color: #3498db;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: white;
    border: 1px solid #bdc3c7;
    selection-background-color: #3498db;
    selection-color: white;
    padding: 4px;
}

QLineEdit {
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 13px;
    color: #2c3e50;
}

QLineEdit:focus {
    border-color: #3498db;
}

QTextEdit {
    background-color: white;
    border: 1px solid #dcdde1;
    border-radius: 6px;
    padding: 10px;
    font-size: 14px;
    line-height: 1.6;
    color: #2c3e50;
    selection-background-color: #3498db;
}


QTreeWidget {
    background-color: white;
    border: 1px solid #dcdde1;
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
    color: #2c3e50;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 8px;
    border-radius: 3px;
}
QTreeWidget::item:hover {
    background-color: #ebf5fb;
}
QTreeWidget::item:selected {
    background-color: #3498db;
    color: white;
}

QSlider::groove:horizontal {
    border: none;
    height: 6px;
    background-color: #dcdde1;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #3498db;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background-color: #2980b9;
}

QSlider::sub-page:horizontal {
    background-color: #3498db;
    border-radius: 3px;
}

QProgressBar {
    border: 1px solid #dcdde1;
    border-radius: 6px;
    text-align: center;
    font-size: 12px;
    color: #2c3e50;
    background-color: #ecf0f1;
    min-height: 22px;
}

QProgressBar::chunk {
    background-color: #27ae60;
    border-radius: 5px;
}

QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #dcdde1;
    color: #7f8c8d;
    font-size: 12px;
    padding: 2px 8px;
}

QSplitter::handle {
    background-color: #dcdde1;
    width: 2px;
}

QLabel {
    color: #2c3e50;
    font-size: 13px;
}
"""


# ============================================================
# 下载工作线程
# ============================================================

class DownloadWorkerSignals(QObject):
    """下载线程信号"""
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str, int)   # message, percent


class DownloadWorker(QRunnable):
    """后台模型下载工作线程"""

    def __init__(self, engine_name: str, progress_callback=None):
        super().__init__()
        self.engine_name = engine_name
        self._progress_cb = progress_callback
        self.signals = DownloadWorkerSignals()

    def run(self):
        try:
            from ..model_downloader import download_model

            def progress(msg: str, pct: int):
                self.signals.progress.emit(msg, pct)

            success = download_model(self.engine_name, progress)
            if success:
                self.signals.finished.emit(True, f"模型 {self.engine_name} 下载完成")
            else:
                self.signals.finished.emit(False, f"模型 {self.engine_name} 下载失败")
        except Exception as e:
            self.signals.finished.emit(False, f"下载出错: {str(e)}")


# ============================================================
# 合成工作线程
# ============================================================

# 文本分块阈值（字符数）
_CHUNK_MAX_CHARS = 400
_CHUNK_MIN_CHARS = 80


def _split_text_for_progress(text: str) -> list[str]:
    """按句拆分文本为多个块，用于逐块合成并反馈进度。

    拆分策略：
    1. 先按换行分段
    2. 每段按句末标点（。！？!?.）切分
    3. 过短的句子合并到相邻块，过长的句子按逗号再切
    4. 确保每块 _CHUNK_MIN_CHARS ~ _CHUNK_MAX_CHARS 字符
    """
    text = text.strip()
    if not text:
        return [""]

    total_len = len(text)

    # 短文本不分块
    if total_len <= _CHUNK_MAX_CHARS:
        return [text]

    # 按换行分段
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # 按句末标点切分
    sentences = []
    for para in paragraphs:
        # 在句末标点后切分，保留标点在前一句末尾
        buf = ""
        for ch in para:
            buf += ch
            if ch in "。！？!?":
                s = buf.strip()
                if s:
                    sentences.append(s)
                buf = ""
        if buf.strip():
            sentences.append(buf.strip())

    # 合并过短的句子，确保每块在 _CHUNK_MIN_CHARS ~ _CHUNK_MAX_CHARS
    chunks = []
    current = ""
    for s in sentences:
        if not current:
            current = s
        elif len(current) + len(s) + 1 <= _CHUNK_MAX_CHARS:
            current += s
        else:
            if current:
                chunks.append(current)
            # 如果单句超过上限，按逗号再切
            if len(s) > _CHUNK_MAX_CHARS:
                sub_chunks = _split_long_sentence(s)
                chunks.extend(sub_chunks)
            else:
                current = s
                continue
            current = ""
    if current:
        chunks.append(current)

    # 如果拆分后没有块（极端情况），返回原文
    return chunks if chunks else [text]


def _split_long_sentence(sentence: str) -> list[str]:
    """将超长单句按逗号/分号切分"""
    result = []
    buf = ""
    for ch in sentence:
        buf += ch
        if ch in "，,；;：" and len(buf) >= _CHUNK_MIN_CHARS:
            result.append(buf.strip())
            buf = ""
    if buf.strip():
        # 如果剩余部分太短，合并到最后一块
        if result and len(buf) < _CHUNK_MIN_CHARS:
            result[-1] += buf.strip()
        else:
            result.append(buf.strip())
    return result


def _concat_audio_files(
    input_paths: list[str],
    output_path: str,
) -> bool:
    """将多个音频文件合并为一个（使用 ffmpeg 或 pydub）"""
    if len(input_paths) == 0:
        return False
    if len(input_paths) == 1:
        import shutil
        shutil.copy(input_paths[0], output_path)
        return True

    # 方案1: 用 ffmpeg concat demuxer（最快，不重新编码）
    try:
        import subprocess, tempfile
        # 写 concat 列表文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            for p in input_paths:
                # ffmpeg concat 需要绝对路径或转义路径
                escaped = p.replace("\\", "/")
                f.write(f"file '{escaped}'\n")
            list_path = f.name

        fmt = os.path.splitext(output_path)[1].lstrip(".").lower() or "mp3"
        # WAV 默认 pcm_s16le 兼容性最好
        codec_args = ["-acodec", "pcm_s16le"] if fmt == "wav" else ["-acodec", "libmp3lame"]
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_path,
        ] + codec_args + [output_path]
        subprocess.run(cmd, capture_output=True, check=True, timeout=120)
        os.unlink(list_path)
        return True
    except Exception:
        pass

    # 方案2: pydub 回退
    try:
        from pydub import AudioSegment
        merged = AudioSegment.empty()
        for p in input_paths:
            merged += AudioSegment.from_file(p)
        fmt = os.path.splitext(output_path)[1].lstrip(".").lower() or "mp3"
        merged.export(output_path, format=fmt)
        return True
    except Exception:
        pass

    return False


class SynthesisWorkerSignals(QObject):
    """合成线程信号"""
    finished = pyqtSignal(object)  # SynthesisResult
    error = pyqtSignal(str)
    progress = pyqtSignal(int)     # 0-100 百分比


class SynthesisWorker(QRunnable):
    """后台语音合成工作线程（分块 + 进度反馈）

    对长文本按句拆分为 80-400 字符的块，逐块合成。
    每块完成时发出 progress 信号（0-90%），合并音频后发 100%。
    单块失败不丢弃已成功块，会尝试合并部分结果。

    安全策略:
    - 分块 > 8 或短文本（<=400 字）→ 整段一次合成
    - 单块失败 → 跳过该块，合并其余成功块
    - 合并失败 → 用第一个成功块作为输出
    - 全部分块失败 → 回退为整段一次合成
    """

    MAX_CHUNKS = 8  # 超过此数量回退为整段合成

    def __init__(self, model_manager: ModelManager, text: str,
                 voice_id: str, output_path: str, rate: str = "+0%"):
        super().__init__()
        self.model_manager = model_manager
        self.text = text
        self.voice_id = voice_id
        self.output_path = output_path
        self.rate = rate
        self.signals = SynthesisWorkerSignals()

    def run(self):
        import tempfile, shutil, time

        # 短文本或分块过多 → 退化为整段一次合成
        chunks = _split_text_for_progress(self.text)
        if len(chunks) == 1 or len(chunks) > self.MAX_CHUNKS:
            self._run_single_shot()
            return

        total = len(chunks)
        temp_files = []

        try:
            self.signals.progress.emit(10)

            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue  # 跳过空块

                ext = os.path.splitext(self.output_path)[1] or ".mp3"
                tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                tmp.close()

                # 单块合成（失败时重试一次）
                result = self._synthesize_chunk(chunk, tmp.name)
                if not result.success:
                    # 重试一次
                    logger.warning(
                        f"分块 {i+1}/{total} 首次失败: {result.error_message}，重试中..."
                    )
                    time.sleep(0.5)
                    result = self._synthesize_chunk(chunk, tmp.name)
                    if not result.success:
                        logger.error(
                            f"分块 {i+1}/{total} 重试仍失败，跳过此块"
                        )
                        try:
                            os.remove(tmp.name)
                        except Exception:
                            pass
                        continue  # 跳过失败块，继续下一个

                temp_files.append(tmp.name)

                # 进度: 10% ~ 90%（最后 10% 留给合并）
                pct = 10 + int((i + 1) / total * 80)
                self.signals.progress.emit(pct)

                # Edge TTS 分块间加延迟，避免频率限制
                if i < total - 1:
                    engine_name = self.model_manager.get_active_engine_name() or ""
                    if "edge" in engine_name.lower():
                        time.sleep(0.3)

            if not temp_files:
                # 全部分块失败 → 回退为整段合成
                logger.warning("所有分块失败，回退为整段一次合成")
                self._run_single_shot()
                return

            # 合并所有成功分块
            self.signals.progress.emit(92)
            if not _concat_audio_files(temp_files, self.output_path):
                # 合并失败 → 用第一个成功块
                shutil.copy(temp_files[0], self.output_path)
                logger.warning("音频合并失败，使用第一个分块作为输出")

            self.signals.progress.emit(100)
            self.signals.finished.emit(SynthesisResult(
                output_path=self.output_path,
                word_count=len(self.text),
                success=True,
            ))

        except Exception as e:
            logger.exception(f"SynthesisWorker 异常: {e}")
            self.signals.error.emit(
                f"合成过程出错: {str(e)}\n\n请尝试减少文本长度后重试"
            )
        finally:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.remove(f)
                except Exception:
                    pass

    def _synthesize_chunk(self, text: str, output_path: str) -> SynthesisResult:
        """合成单个分块（不抛异常）"""
        try:
            return self.model_manager.synthesize(
                text=text,
                voice_id=self.voice_id,
                output_path=output_path,
                rate=self.rate,
            )
        except Exception as e:
            return SynthesisResult(
                output_path=output_path,
                success=False,
                error_message=str(e),
            )

    def _run_single_shot(self):
        """整段一次合成（不回退到分块）"""
        import tempfile, shutil

        try:
            self.signals.progress.emit(10)

            ext = os.path.splitext(self.output_path)[1] or ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp.close()

            result = self.model_manager.synthesize(
                text=self.text,
                voice_id=self.voice_id,
                output_path=tmp.name,
                rate=self.rate,
            )

            if not result.success:
                self.signals.error.emit(
                    result.error_message or "语音合成失败"
                )
                try:
                    os.remove(tmp.name)
                except Exception:
                    pass
                return

            self.signals.progress.emit(90)
            shutil.move(tmp.name, self.output_path)
            self.signals.progress.emit(100)

            self.signals.finished.emit(SynthesisResult(
                output_path=self.output_path,
                word_count=len(self.text),
                success=True,
            ))

        except Exception as e:
            logger.exception(f"单次合成异常: {e}")
            self.signals.error.emit(f"合成失败: {str(e)}")


# ============================================================
# 批量合成工作线程（按章节生成）
# ============================================================

class BatchSynthesisSignals(QObject):
    """批量合成信号"""
    chapter_done = pyqtSignal(int, str)     # chapter_index, output_path
    all_done = pyqtSignal(list)              # list of output_paths
    error = pyqtSignal(int, str)             # chapter_index, error
    progress = pyqtSignal(int, int, str)     # current, total, chapter_title


class BatchSynthesisWorker(QRunnable):
    """按章节批量合成语音"""

    def __init__(self, model_manager, chapters: list[dict],
                 voice_id: str, output_dir: str, rate: str = "+0%"):
        super().__init__()
        self.model_manager = model_manager
        self.chapters = chapters
        self.voice_id = voice_id
        self.output_dir = output_dir
        self.rate = rate
        self.signals = BatchSynthesisSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        total = len(self.chapters)

        for i, ch in enumerate(self.chapters):
            if self._cancelled:
                break

            # 生成安全的文件名：第N章_标题.mp3
            chapter_num = i + 1
            title = self._sanitize_filename(ch["title"])
            fname = f"第{chapter_num:02d}章_{title}.mp3"
            output_path = os.path.join(self.output_dir, fname)

            # 发送进度
            self.signals.progress.emit(i + 1, total, ch["title"])

            # 合成
            try:
                result = self.model_manager.synthesize(
                    text=ch["content"],
                    voice_id=self.voice_id,
                    output_path=output_path,
                    rate=self.rate,
                )
                if result.success:
                    results.append(output_path)
                    self.signals.chapter_done.emit(i, output_path)
                else:
                    self.signals.error.emit(i,
                        f"第{chapter_num}章失败: {result.error_message}")
                    results.append(None)
            except Exception as e:
                self.signals.error.emit(i, f"第{chapter_num}章异常: {str(e)}")
                results.append(None)

        self.signals.all_done.emit(results)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名中的非法字符"""
        import re
        name = re.sub(r'[\\/:*?"<>|]', '_', name)
        name = name.strip()
        # 截断过长的标题
        if len(name) > 60:
            name = name[:57] + "..."
        return name


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):
    """TTS 程序主窗口"""

    WINDOW_TITLE = "文本转语音程序 - Text-to-Speech Desktop"
    WINDOW_WIDTH = 1000
    WINDOW_HEIGHT = 750

    # 默认引擎列表
    DEFAULT_ENGINES = {
        "edge_tts": "Edge TTS (免费在线, 300+ 音色)",
        "separator_1": "──────── 本地模型 ────────",
        "omnivoice": "OmniVoice (600+ 语言, GPU)",
    }

    def __init__(self, models_dir: str = None):
        super().__init__()
        self._models_dir = models_dir or str(DEFAULT_MODELS_DIR)
        self.model_manager = ModelManager(models_dir=self._models_dir)
        self._init_engines()
        self._book_chapters: list[dict] = []
        self._current_output_path: str = ""
        self._all_voices: list[VoiceInfo] = []
        self._chapters_loaded: bool = False
        self.setup_ui()
        self._connect_signals()
        self._load_initial_state()

    # --------------------------------------------------------
    # 引擎初始化
    # --------------------------------------------------------

    def _init_engines(self):
        """注册所有可用的 TTS 引擎"""
        # 在线引擎
        self.model_manager.register_engine_class("edge_tts", EdgeTTSEngine)

        # 本地引擎
        self.model_manager.register_engine_class("omnivoice", OmniVoiceEngine)

        # 自动加载第一个可用引擎
        for name in self.DEFAULT_ENGINES:
            if name.startswith("separator"):
                continue
            if self.model_manager.load_engine(name):
                logger.info(f"自动加载引擎: {name}")
                break

    # --------------------------------------------------------
    # UI 构建
    # --------------------------------------------------------

    def setup_ui(self):
        """构建用户界面"""
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setGeometry(100, 100, self.WINDOW_WIDTH, self.WINDOW_HEIGHT)
        self.setMinimumSize(800, 600)

        # 应用样式表
        self.setStyleSheet(APP_STYLESHEET)

        # 中央滚动区域
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # ---------- 1. 模型选择区域 ----------
        self._build_model_section(main_layout)

        # ---------- 2. EPUB 导入区域 ----------
        self._build_epub_section(main_layout)

        # ---------- 3. 音色设置区域 ----------
        self._build_voice_section(main_layout)

        # ---------- 4. 文本编辑区域 ----------
        self._build_text_section(main_layout)

        # ---------- 5. 语音参数区域 ----------
        self._build_param_section(main_layout)

        # ---------- 6. 进度条 ----------
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("%p%")  # 显示百分比
        self.progress.setVisible(False)
        main_layout.addWidget(self.progress)

        # ---------- 7. 操作按钮 ----------
        self._build_action_section(main_layout)

        # 弹簧
        main_layout.addStretch()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 请选择模型和音色后开始")

    def _build_model_section(self, layout: QVBoxLayout):
        """构建模型选择区域"""
        group = QGroupBox("TTS 模型选择")
        hbox = QHBoxLayout()
        hbox.setSpacing(12)

        hbox.addWidget(QLabel("选择模型:"))

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(280)
        for key, label in self.DEFAULT_ENGINES.items():
            if key.startswith("separator"):
                self.model_combo.insertSeparator(self.model_combo.count())
            else:
                # 标注模型下载状态
                info = get_model_info(key)
                if info and key != "edge_tts":
                    from ..model_downloader import is_model_downloaded
                    downloaded = is_model_downloaded(key)
                    status = " [已下载]" if downloaded else " [未下载]"
                    label = label + status
                self.model_combo.addItem(label, key)
        hbox.addWidget(self.model_combo)

        self.download_btn = QPushButton("下载模型")
        self.download_btn.setObjectName("browseBtn")
        hbox.addWidget(self.download_btn)

        # 打开模型目录按钮
        self.open_models_dir_btn = QPushButton("打开模型目录")
        self.open_models_dir_btn.setObjectName("browseBtn")
        hbox.addWidget(self.open_models_dir_btn)

        # 引擎信息标签
        self.engine_info_label = QLabel("")
        self.engine_info_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        hbox.addWidget(self.engine_info_label)

        hbox.addStretch()
        group.setLayout(hbox)
        layout.addWidget(group)

    def _build_epub_section(self, layout: QVBoxLayout):
        """构建 EPUB 导入区域"""
        group = QGroupBox("导入 EPUB 书籍")
        hbox = QHBoxLayout()
        hbox.setSpacing(8)

        self.epub_path = QLineEdit()
        self.epub_path.setPlaceholderText("选择 EPUB 文件，或将文件拖放到此处...")
        hbox.addWidget(self.epub_path)

        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setObjectName("browseBtn")
        hbox.addWidget(self.browse_btn)

        self.epub_info_label = QLabel("")
        self.epub_info_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        hbox.addWidget(self.epub_info_label)

        group.setLayout(hbox)
        layout.addWidget(group)

    def _build_voice_section(self, layout: QVBoxLayout):
        """构建音色设置区域"""
        group = QGroupBox("音色设置")
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        # --- 音色选择行 ---
        hbox1 = QHBoxLayout()
        hbox1.setSpacing(8)
        hbox1.addWidget(QLabel("选择音色:"))

        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(420)
        self.voice_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        hbox1.addWidget(self.voice_combo, stretch=1)

        # 语言过滤
        hbox1.addWidget(QLabel("语言:"))
        self.lang_filter = QComboBox()
        self.lang_filter.addItem("全部", "all")
        self.lang_filter.addItem("中文 (zh-CN)", "zh-CN")
        self.lang_filter.addItem("中文 (zh-TW)", "zh-TW")
        self.lang_filter.addItem("中文 (zh-HK)", "zh-HK")
        self.lang_filter.addItem("英语 (en-US)", "en-US")
        self.lang_filter.addItem("英语 (en-GB)", "en-GB")
        self.lang_filter.addItem("日语 (ja-JP)", "ja-JP")
        self.lang_filter.addItem("韩语 (ko-KR)", "ko-KR")
        self.lang_filter.setMinimumWidth(130)
        hbox1.addWidget(self.lang_filter)

        # 性别过滤
        hbox1.addWidget(QLabel("性别:"))
        self.gender_filter = QComboBox()
        self.gender_filter.addItem("全部", "all")
        self.gender_filter.addItem("女声", "Female")
        self.gender_filter.addItem("男声", "Male")
        hbox1.addWidget(self.gender_filter)

        self.refresh_voices_btn = QPushButton("刷新")
        self.refresh_voices_btn.setObjectName("refreshBtn")
        hbox1.addWidget(self.refresh_voices_btn)

        vbox.addLayout(hbox1)

        # --- 语音克隆区域 ---
        clone_group = QGroupBox("语音克隆")
        clone_vbox = QVBoxLayout()
        clone_vbox.setSpacing(6)

        # 参考音频行
        clone_hbox1 = QHBoxLayout()
        clone_hbox1.setSpacing(8)
        self.clone_audio_path = QLineEdit()
        self.clone_audio_path.setPlaceholderText("选择参考音频文件 (MP3/WAV)...")
        clone_hbox1.addWidget(self.clone_audio_path)
        self.clone_browse_btn = QPushButton("浏览")
        self.clone_browse_btn.setObjectName("browseBtn")
        clone_hbox1.addWidget(self.clone_browse_btn)
        clone_vbox.addLayout(clone_hbox1)

        # 参考文本行
        clone_vbox.addWidget(QLabel("参考音频对应文本（可选，可提升克隆还原度）:"))
        self.clone_text_input = QTextEdit()
        self.clone_text_input.setMaximumHeight(60)
        self.clone_text_input.setPlaceholderText("输入参考音频对应的文本内容...")
        clone_vbox.addWidget(self.clone_text_input)

        # 克隆按钮行
        clone_hbox2 = QHBoxLayout()
        clone_hbox2.setSpacing(8)
        self.clone_btn = QPushButton("开始克隆音色")
        self.clone_btn.setObjectName("cloneBtn")
        clone_hbox2.addWidget(self.clone_btn)

        self.manage_cloned_btn = QPushButton("管理")
        self.manage_cloned_btn.setObjectName("browseBtn")
        clone_hbox2.addWidget(self.manage_cloned_btn)

        self.clone_status_label = QLabel("")
        self.clone_status_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        clone_hbox2.addWidget(self.clone_status_label)
        clone_hbox2.addStretch()
        clone_vbox.addLayout(clone_hbox2)

        clone_group.setLayout(clone_vbox)
        vbox.addWidget(clone_group)

        group.setLayout(vbox)
        layout.addWidget(group)

    def _build_text_section(self, layout: QVBoxLayout):
        """构建文本编辑区域"""
        from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QHeaderView

        group = QGroupBox("文本内容")
        vbox = QVBoxLayout()

        splitter = QSplitter(Qt.Horizontal)

        # 章节列表（树形 + 复选框）
        chapter_widget = QWidget()
        chapter_layout = QVBoxLayout(chapter_widget)
        chapter_layout.setContentsMargins(0, 0, 0, 0)

        # 章节标题 + 全选/全不选按钮
        chapter_header = QHBoxLayout()
        chapter_header.addWidget(QLabel("章节列表:"))
        chapter_header.addStretch()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setFixedSize(50, 22)
        self.btn_select_all.setStyleSheet("font-size:11px; padding:1px 4px;")
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_deselect_all = QPushButton("全不选")
        self.btn_deselect_all.setFixedSize(50, 22)
        self.btn_deselect_all.setStyleSheet("font-size:11px; padding:1px 4px;")
        self.btn_deselect_all.clicked.connect(self._on_deselect_all)
        chapter_header.addWidget(self.btn_select_all)
        chapter_header.addWidget(self.btn_deselect_all)
        chapter_layout.addLayout(chapter_header)

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setHeaderLabels(["章节"])
        self.chapter_tree.header().setStretchLastSection(True)
        self.chapter_tree.setMinimumWidth(200)
        self.chapter_tree.setIndentation(20)
        self.chapter_tree.setAnimated(True)
        # 三态复选框：父节点可部分选中
        self.chapter_tree.itemClicked.connect(self._on_tree_item_clicked)
        chapter_layout.addWidget(self.chapter_tree)
        splitter.addWidget(chapter_widget)

        # 文本编辑器
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)

        text_header = QHBoxLayout()
        text_header.addWidget(QLabel("文本编辑:"))
        self.char_count_label = QLabel("字数: 0")
        self.char_count_label.setStyleSheet("color: #95a5a6; font-size: 12px;")
        text_header.addWidget(self.char_count_label)
        text_header.addStretch()
        text_layout.addLayout(text_header)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在此输入或粘贴文本，或从左侧加载 EPUB 章节...")
        text_layout.addWidget(self.text_edit)

        splitter.addWidget(text_widget)
        splitter.setSizes([220, 680])

        vbox.addWidget(splitter)
        group.setLayout(vbox)
        layout.addWidget(group, stretch=2)

    def _build_param_section(self, layout: QVBoxLayout):
        """构建语音参数区域"""
        group = QGroupBox("语音参数")
        hbox = QHBoxLayout()
        hbox.setSpacing(20)

        # 语速
        hbox.addWidget(QLabel("语速:"))
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(100)
        self.speed_slider.setMinimumWidth(150)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(25)
        hbox.addWidget(self.speed_slider)
        self.speed_label = QLabel("100%")
        self.speed_label.setMinimumWidth(40)
        self.speed_label.setStyleSheet("font-weight: bold;")
        hbox.addWidget(self.speed_label)

        hbox.addSpacing(20)

        # 音量（目前 Edge TTS 不直接支持音量调节，作为 UI 占位）
        hbox.addWidget(QLabel("音量:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(50, 200)
        self.volume_slider.setValue(100)
        self.volume_slider.setMinimumWidth(150)
        hbox.addWidget(self.volume_slider)
        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(40)
        self.volume_label.setStyleSheet("font-weight: bold;")
        hbox.addWidget(self.volume_label)

        hbox.addStretch()
        group.setLayout(hbox)
        layout.addWidget(group)

    def _build_action_section(self, layout: QVBoxLayout):
        """构建操作按钮区域"""
        hbox = QHBoxLayout()
        hbox.setSpacing(12)

        # 生成模式选择
        hbox.addWidget(QLabel("生成模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("当前文本", "current")
        self.mode_combo.addItem("全书（单文件）", "full_book")
        self.mode_combo.addItem("按章节生成（多文件）", "per_chapter")
        self.mode_combo.setMinimumWidth(180)
        hbox.addWidget(self.mode_combo)

        hbox.addSpacing(8)

        self.generate_btn = QPushButton("生成语音文件")
        self.generate_btn.setObjectName("generateBtn")
        hbox.addWidget(self.generate_btn)

        self.play_btn = QPushButton("播放")
        self.play_btn.setObjectName("playBtn")
        self.play_btn.setEnabled(False)
        hbox.addWidget(self.play_btn)

        hbox.addStretch()

        self.export_btn = QPushButton("导出音频")
        self.export_btn.setObjectName("exportBtn")
        self.export_btn.setEnabled(False)
        hbox.addWidget(self.export_btn)

        layout.addLayout(hbox)

    # --------------------------------------------------------
    # 信号连接
    # --------------------------------------------------------

    def _connect_signals(self):
        """连接所有 UI 信号"""
        # 模型
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        self.download_btn.clicked.connect(self._on_download_model)
        self.open_models_dir_btn.clicked.connect(self._on_open_models_dir)

        # EPUB
        self.browse_btn.clicked.connect(self._on_browse_epub)

        # 音色
        self.lang_filter.currentIndexChanged.connect(self._on_filter_voices)
        self.gender_filter.currentIndexChanged.connect(self._on_filter_voices)
        self.refresh_voices_btn.clicked.connect(self._on_refresh_voices)

        # 克隆
        self.clone_browse_btn.clicked.connect(self._on_browse_clone_audio)
        self.clone_btn.clicked.connect(self._on_clone_voice)
        self.manage_cloned_btn.clicked.connect(self._on_manage_cloned_voices)

        # 章节
        # (树形复选框已通过 _on_tree_item_clicked 连接)

        # 参数
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"{v}%")
        )
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"{v}%")
        )

        # 文本变化
        self.text_edit.textChanged.connect(self._on_text_changed)

        # 操作
        self.generate_btn.clicked.connect(self._on_generate)
        self.play_btn.clicked.connect(self._on_play)
        self.export_btn.clicked.connect(self._on_export)

    # --------------------------------------------------------
    # 初始状态
    # --------------------------------------------------------

    def _load_initial_state(self):
        """加载初始状态"""
        # 延迟加载音色列表（给 UI 时间渲染）
        QTimer.singleShot(200, self._on_refresh_voices)

        # 更新引擎信息
        QTimer.singleShot(300, self._update_engine_info)

    # --------------------------------------------------------
    # 模型相关回调
    # --------------------------------------------------------

    def _on_model_changed(self, index: int):
        """模型切换"""
        engine_key = self.model_combo.currentData()
        if not engine_key:
            return

        # 检查是否是分隔符
        if engine_key.startswith("separator"):
            return

        self.status_bar.showMessage(f"正在加载 {engine_key}...")
        QApplication.processEvents()

        if self.model_manager.load_engine(engine_key):
            self.status_bar.showMessage(f"已切换到 {engine_key}")
            self._on_refresh_voices()
            self._update_engine_info()

            # 更新下载按钮文字和状态
            self._update_download_btn_state(engine_key)
        else:
            # 加载失败 — 收集详细诊断信息
            missing = self._get_engine_missing_info(engine_key)
            reason_short = missing[0] if missing else "未知原因"
            self.status_bar.showMessage(f"加载 {engine_key} 失败: {reason_short}")

            # 弹窗显示完整缺失列表
            if missing:
                msg = f"引擎「{engine_key}」无法加载，缺少以下内容:\n\n"
                for i, m in enumerate(missing, 1):
                    msg += f"  {i}. {m}\n"
                QMessageBox.warning(self, "引擎不可用", msg)

            self._update_engine_info()
            self._update_download_btn_state(engine_key)

    def _get_engine_missing_info(self, engine_key: str) -> list[str]:
        """获取指定引擎的缺失依赖列表"""
        # 创建临时引擎实例来诊断
        engine_cls = self.model_manager._engine_classes.get(engine_key)
        if engine_cls:
            temp_engine = engine_cls(models_dir=self._models_dir)
            return temp_engine.get_missing_deps()
        return [f"未注册的引擎: {engine_key}"]

    def _update_download_btn_state(self, engine_key: str):
        """根据模型状态更新下载按钮"""
        if engine_key == "edge_tts":
            self.download_btn.setText("无需下载")
            self.download_btn.setEnabled(False)
            return

        from ..model_downloader import is_model_downloaded
        if is_model_downloaded(engine_key):
            self.download_btn.setText("重新下载")
            self.download_btn.setEnabled(True)
        else:
            self.download_btn.setText("下载模型")
            self.download_btn.setEnabled(True)

    def _on_download_model(self):
        """下载模型到本地 models/ 目录"""
        engine_key = self.model_combo.currentData()
        if not engine_key or engine_key == "edge_tts":
            QMessageBox.information(
                self, "提示",
                "Edge TTS 为在线服务，无需下载模型。\n请选择一个本地模型。"
            )
            return

        info = get_model_info(engine_key)
        if not info:
            return

        # 检查是否已下载
        from ..model_downloader import is_model_downloaded
        already_downloaded = is_model_downloaded(engine_key)

        # 确认对话框
        msg = (
            f"模型: {info['description']}\n"
            f"大小: ~{info['size_gb']} GB\n"
            f"保存位置: {self._models_dir}\\{engine_key}\\\n"
            f"来源: HuggingFace ({info['repo_id']})\n"
        )
        if info.get("requires_gpu"):
            msg += "\n⚠ 此模型需要 GPU 支持"
        if already_downloaded:
            msg += "\n\n⚠ 模型已下载，将重新下载覆盖"

        reply = QMessageBox.question(
            self, "确认下载模型", msg,
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # 开始下载
        self.download_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_bar.showMessage(f"正在下载 {engine_key} 模型...")

        worker = DownloadWorker(engine_key)
        worker.signals.progress.connect(self._on_download_progress)
        worker.signals.finished.connect(self._on_download_finished)
        QThreadPool.globalInstance().start(worker)

    def _on_download_progress(self, message: str, percent: int):
        """下载进度更新"""
        self.progress.setValue(percent)
        self.status_bar.showMessage(f"下载中 ({percent}%): {message}")

    def _on_download_finished(self, success: bool, message: str):
        """下载完成"""
        self.download_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.status_bar.showMessage(message)

        if success:
            QMessageBox.information(
                self, "下载完成",
                f"{message}\n\n模型已保存到:\n"
                f"{self._models_dir}\\{self.model_combo.currentData()}\\\n\n"
                f"请重新选择该模型以加载使用。"
            )
            # 更新下拉框状态
            self._refresh_model_combo_labels()
            engine_key = self.model_combo.currentData()
            if engine_key:
                self._update_download_btn_state(engine_key)
        else:
            QMessageBox.critical(
                self, "下载失败",
                f"{message}\n\n请检查:\n"
                "1. 网络连接是否正常\n"
                "2. huggingface_hub 是否安装: pip install huggingface_hub\n"
                "3. 磁盘空间是否充足"
            )

    def _on_open_models_dir(self):
        """在资源管理器中打开模型目录"""
        models_dir = self._models_dir
        try:
            os.startfile(models_dir)
        except Exception as e:
            QMessageBox.warning(self, "提示", f"无法打开目录:\n{str(e)}")

    def _refresh_model_combo_labels(self):
        """刷新下拉框中的模型状态标签"""
        for i in range(self.model_combo.count()):
            key = self.model_combo.itemData(i)
            if not key or key.startswith("separator"):
                continue

            # 找到原始标签
            original = self.DEFAULT_ENGINES.get(key, "")
            if not original:
                continue

            info = get_model_info(key)
            if info and key != "edge_tts":
                from ..model_downloader import is_model_downloaded
                downloaded = is_model_downloaded(key)
                status = " [已下载]" if downloaded else " [未下载]"
                self.model_combo.setItemText(i, original + status)

    def _update_engine_info(self):
        """更新引擎信息显示"""
        engine = self.model_manager.active_engine
        if engine:
            info = engine.get_info()
            desc = info.get("description", "")
            cloning = "支持克隆" if info.get("supports_cloning") else "不支持克隆"

            # 本地模型显示模型目录和下载状态
            extra = ""
            if engine.get_engine_key() != "edge_tts":
                downloaded = info.get("model_downloaded", False)
                extra = " | 模型已下载" if downloaded else " | 模型未下载"

            # 警告信息（GPU 等，不阻塞使用）
            warnings = engine.get_warnings()
            if warnings:
                extra += " | " + " · ".join(warnings[:2])

            self.engine_info_label.setText(f"{desc} | {cloning}{extra}")

            # 更新下载按钮
            self._update_download_btn_state(engine.get_engine_key())
        else:
            self.engine_info_label.setText("未加载引擎")

    # --------------------------------------------------------
    # EPUB 相关回调
    # --------------------------------------------------------

    def _on_browse_epub(self):
        """选择 EPUB 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择书籍文件", "",
            "书籍文件 (*.epub *.pdf *.mobi);;EPUB 电子书 (*.epub);;PDF 文档 (*.pdf);;MOBI/Kindle (*.mobi)"
        )
        if file_path:
            self.epub_path.setText(file_path)
            self._load_epub(file_path)

    def _load_epub(self, file_path: str):
        """加载 EPUB 并提取章节（TOC 目录树 + 复选框）"""
        try:
            from PyQt5.QtWidgets import QTreeWidgetItem

            parser = EpubParser(file_path)
            metadata = parser.get_metadata()
            chapters = parser.extract_chapters()

            # 防止初始填充触发布局变化
            self._chapters_loaded = False
            self._book_chapters = chapters

            # 构建 index → chapter 快速映射
            idx_map = {ch["index"]: ch for ch in chapters}

            # 从 TOC 树构建 QTreeWidget
            self.chapter_tree.clear()
            toc = parser.get_toc_tree()

            if toc:
                self._fill_tree_from_toc(toc, None, idx_map)
            else:
                # 无 TOC → 扁列表
                for ch in chapters:
                    self._add_tree_item(
                        None, ch["title"], ch["index"], Qt.Checked
                    )

            self._chapters_loaded = True

            info = (f"《{metadata['title']}》 - {metadata['author']} | "
                    f"{len(chapters)} 个章节")
            self.epub_info_label.setText(info)
            total_top = self.chapter_tree.topLevelItemCount()
            self.status_bar.showMessage(
                f"已加载《{metadata['title']}》- {len(chapters)} 章节，{total_top} 个一级目录"
            )

        except ImportError as e:
            QMessageBox.critical(self, "缺少依赖", str(e))
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载 EPUB 文件失败:\n{str(e)}")
            logger.error(f"加载 EPUB 失败: {e}")

    def _fill_tree_from_toc(self, toc_nodes: list, parent, idx_map: dict):
        """递归填充 TOC 节点到树控件（index 由解析器通过 href 精确匹配）"""
        from PyQt5.QtWidgets import QTreeWidgetItem

        for node in toc_nodes:
            level = node.get("level", 1)
            title = node["title"]
            index = node.get("index", -1)

            prefix = {1: "📁 ", 2: "📄 ", 3: "  └ "}.get(level, "  ")
            label = f"{prefix}{title}"

            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, index if index >= 0 else None)

            if level == 1:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            flags = item.flags() | Qt.ItemIsUserCheckable
            if node.get("children"):
                flags |= Qt.ItemIsAutoTristate
            item.setFlags(flags)
            item.setCheckState(0, Qt.Checked)
            item.setExpanded(level <= 2)

            if parent is None:
                self.chapter_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

            children = node.get("children", [])
            if children:
                self._fill_tree_from_toc(children, item, idx_map)

    def _add_tree_item(self, parent, title: str, index: int, state):
        """添加单个树节点（扁列表模式）"""
        from PyQt5.QtWidgets import QTreeWidgetItem
        item = QTreeWidgetItem([f"📄 {title}"])
        item.setData(0, Qt.UserRole, index)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, state)
        if parent is None:
            self.chapter_tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

    def _on_tree_item_clicked(self, item, column: int):
        """点击树节点：显示对应章节文本"""
        if item and not self._chapters_loaded:
            return
        index = item.data(0, Qt.UserRole)
        if index is not None and 0 <= index < len(self._book_chapters):
            chapter = self._book_chapters[index]
            self.text_edit.setPlainText(chapter["content"])

    def _on_select_all(self):
        """全选所有章节"""
        for i in range(self.chapter_tree.topLevelItemCount()):
            self._set_tree_check_state(self.chapter_tree.topLevelItem(i), Qt.Checked)

    def _on_deselect_all(self):
        """全不选所有章节"""
        for i in range(self.chapter_tree.topLevelItemCount()):
            self._set_tree_check_state(self.chapter_tree.topLevelItem(i), Qt.Unchecked)

    def _set_tree_check_state(self, item, state):
        """递归设置节点及其子节点的勾选状态"""
        item.setCheckState(0, state)
        for i in range(item.childCount()):
            self._set_tree_check_state(item.child(i), state)

    def _get_checked_chapters(self) -> list[int]:
        """收集所有勾选的章节索引"""
        indices = []
        for i in range(self.chapter_tree.topLevelItemCount()):
            self._collect_checked(self.chapter_tree.topLevelItem(i), indices)
        return sorted(set(indices))

    def _collect_checked(self, item, indices: list):
        """递归收集勾选节点的章节索引"""
        if item.checkState(0) == Qt.Checked or item.checkState(0) == Qt.PartiallyChecked:
            idx = item.data(0, Qt.UserRole)
            if idx is not None:
                indices.append(idx)
            for i in range(item.childCount()):
                self._collect_checked(item.child(i), indices)

    # --------------------------------------------------------
    # 音色相关回调
    # --------------------------------------------------------

    def _on_refresh_voices(self):
        """刷新音色列表"""
        self.status_bar.showMessage("正在获取音色列表...")
        QApplication.processEvents()

        voices = self.model_manager.get_available_voices()
        if not voices:
            self.status_bar.showMessage("未获取到音色，请检查网络连接")
            return

        self._all_voices = voices  # 缓存全部音色
        self._apply_voice_filter()
        self.status_bar.showMessage(f"已加载 {len(voices)} 个音色")

    def _on_filter_voices(self):
        """按语言和性别过滤音色"""
        self._apply_voice_filter()

    def _apply_voice_filter(self):
        """应用音色过滤器"""
        if not hasattr(self, "_all_voices") or not self._all_voices:
            return

        lang_filter = self.lang_filter.currentData()
        gender_filter = self.gender_filter.currentData()

        filtered = self._all_voices

        # 语言过滤
        if lang_filter and lang_filter != "all":
            filtered = [
                v for v in filtered
                if v.language.startswith(lang_filter)
            ]

        # 性别过滤
        if gender_filter and gender_filter != "all":
            filtered = [
                v for v in filtered
                if v.gender == gender_filter
            ]

        self.voice_combo.clear()
        for v in filtered:
            if v.gender:
                display = f"[{v.gender}] {v.name} ({v.language})"
            else:
                display = f"{v.name} ({v.language})"
            # 克隆音色加特殊标记
            if v.is_cloned:
                display = f"🎤 {v.name} [已克隆]"
            self.voice_combo.addItem(display, v.voice_id)

        if self.voice_combo.count() == 0:
            self.voice_combo.addItem("（无匹配音色）", None)

    # --------------------------------------------------------
    # 音色克隆回调
    # --------------------------------------------------------

    def _on_browse_clone_audio(self):
        """选择参考音频"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择参考音频文件", "",
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
        )
        if file_path:
            self.clone_audio_path.setText(file_path)

    def _on_clone_voice(self):
        """克隆音色"""
        audio_path = self.clone_audio_path.text().strip()
        if not audio_path:
            QMessageBox.warning(self, "提示", "请先选择参考音频文件")
            return

        if not os.path.exists(audio_path):
            QMessageBox.warning(self, "提示", "参考音频文件不存在")
            return

        # 检查是否支持
        engine = self.model_manager.active_engine
        if engine and not engine.supports_voice_cloning():
            QMessageBox.information(
                self, "功能不可用",
                f"当前引擎 ({engine.get_engine_name()}) 不支持音色克隆。\n\n"
                "Edge TTS 为在线服务，不支持自定义音色克隆。\n"
                "请切换到支持克隆的本地模型（Fish S2-Pro / DramaBox / Qwen3-TTS）。"
            )
            self.clone_status_label.setText("当前引擎不支持音色克隆")
            return

        # ★ 克隆前先让用户输入音色名称
        engine_key = engine.get_engine_key()
        default_name = f"{engine.get_engine_name()} 克隆音色"
        name, ok = QInputDialog.getText(
            self, "命名克隆音色",
            "请输入克隆音色的名称（后续可在音色列表中选择）:",
            QLineEdit.Normal,
            default_name,
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        ref_text = self.clone_text_input.toPlainText().strip() or None

        self.clone_status_label.setText("正在克隆音色...")
        self.clone_btn.setEnabled(False)
        self.status_bar.showMessage("正在克隆音色...")
        QApplication.processEvents()

        try:
            voice_id = self.model_manager.clone_voice(audio_path, ref_text)
            if voice_id:
                # ★ 持久化保存克隆音色
                store = get_cloned_voice_store()
                store.add_voice(
                    voice_id=voice_id,
                    name=name,
                    engine_key=engine_key,
                    reference_audio=audio_path,
                )

                self.clone_status_label.setText(f"已保存: {name}")
                self.status_bar.showMessage(f"音色「{name}」克隆成功！")
                QMessageBox.information(
                    self, "克隆成功",
                    f"音色克隆成功！\n\n名称: {name}\n引擎: {engine.get_engine_name()}\n\n"
                    f"该音色已保存，可在音色下拉列表中选择使用。"
                )
                # 刷新音色列表（含克隆音色）
                self._on_refresh_voices()
            else:
                self.clone_status_label.setText("克隆失败")
                QMessageBox.critical(self, "失败", "音色克隆失败，请检查音频文件格式")
        except Exception as e:
            self.clone_status_label.setText(f"克隆失败: {str(e)[:40]}")
            QMessageBox.critical(self, "错误", f"音色克隆失败:\n{str(e)}")
            logger.error(f"音色克隆失败: {e}")
        finally:
            self.clone_btn.setEnabled(True)

    def _on_manage_cloned_voices(self):
        """管理已克隆音色（重命名/删除）"""
        store = get_cloned_voice_store()
        all_cloned = store.get_all_voices()

        if not all_cloned:
            QMessageBox.information(self, "管理克隆音色", "暂无已克隆的音色。\n\n克隆音色后将出现在这里，可以重命名或删除。")
            return

        # 构建选项列表
        items = []
        for cv in all_cloned:
            items.append(f"{cv['name']}  [{cv['engine_key']}]  {cv['created_at'][:10]}")

        item, ok = QInputDialog.getItem(
            self, "管理克隆音色",
            f"共 {len(all_cloned)} 个克隆音色。选择一个进行操作:",
            items, 0, False,
        )
        if not ok or not item:
            return

        idx = items.index(item)
        voice = all_cloned[idx]

        # 操作选择
        action, ok2 = QInputDialog.getItem(
            self, f"操作: {voice['name']}",
            "选择操作:",
            ["重命名", "删除", "取消"], 0, False,
        )
        if not ok2 or action == "取消":
            return

        if action == "重命名":
            new_name, ok3 = QInputDialog.getText(
                self, "重命名音色",
                "新名称:", QLineEdit.Normal, voice["name"],
            )
            if ok3 and new_name.strip():
                store.rename_voice(voice["id"], new_name.strip())
                self._on_refresh_voices()
                self.status_bar.showMessage(f"已重命名为: {new_name.strip()}")
        elif action == "删除":
            reply = QMessageBox.question(
                self, "确认删除",
                f"确定要删除克隆音色「{voice['name']}」吗？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                store.remove_voice(voice["id"])
                self._on_refresh_voices()
                self.status_bar.showMessage(f"已删除: {voice['name']}")

    # --------------------------------------------------------
    # 文本相关回调
    # --------------------------------------------------------

    def _on_text_changed(self):
        """文本内容变化时更新字数统计"""
        text = self.text_edit.toPlainText()
        self.char_count_label.setText(f"字数: {len(text)}")

    # --------------------------------------------------------
    # 语音生成
    # --------------------------------------------------------

    def _on_generate(self):
        """生成语音文件（根据模式分发）"""
        voice_id = self.voice_combo.currentData()
        if not voice_id:
            QMessageBox.warning(self, "提示", "请先选择一个音色")
            return

        mode = self.mode_combo.currentData()

        if mode == "current":
            self._generate_current(voice_id)
        elif mode == "full_book":
            self._generate_full_book(voice_id)
        elif mode == "per_chapter":
            self._generate_per_chapter(voice_id)

    # ---- 模式1：当前文本 ----

    def _generate_current(self, voice_id: str):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请先输入文本或点击左侧章节")
            return

        output_path, selected_filter = QFileDialog.getSaveFileName(
            self, "保存音频文件", "output.mp3",
            "MP3 Files (*.mp3);;WAV Files (*.wav);;OGG Files (*.ogg)"
        )
        if not output_path:
            return

        # 确保文件名有合法扩展名（根据所选滤镜补全）
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
        output_path = output_path.strip()

        if not os.path.splitext(output_path)[1]:
            # 无扩展名 → 根据滤镜补
            if "WAV" in selected_filter:
                output_path += ".wav"
            elif "OGG" in selected_filter:
                output_path += ".ogg"
            else:
                output_path += ".mp3"

        rate = self._get_rate()
        self._current_output_path = output_path

        self._set_busy(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        worker = SynthesisWorker(
            self.model_manager, text, voice_id, output_path, rate
        )
        worker.signals.progress.connect(self._on_synthesis_progress)
        worker.signals.finished.connect(self._on_synthesis_finished)
        worker.signals.error.connect(self._on_synthesis_error)
        QThreadPool.globalInstance().start(worker)

    # ---- 模式2：全书（单文件） ----

    def _generate_full_book(self, voice_id: str):
        if not self._book_chapters:
            QMessageBox.warning(self, "提示", "请先导入 EPUB 书籍")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "保存全书音频", "全书.mp3",
            "MP3 Files (*.mp3);;WAV Files (*.wav);;OGG Files (*.ogg)"
        )
        if not output_path:
            return

        # 合并所有章节文本
        full_text = self._build_full_text()
        rate = self._get_rate()
        self._current_output_path = output_path

        self._set_busy(True)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        worker = SynthesisWorker(
            self.model_manager, full_text, voice_id, output_path, rate
        )
        worker.signals.progress.connect(self._on_synthesis_progress)
        worker.signals.finished.connect(self._on_synthesis_finished)
        worker.signals.error.connect(self._on_synthesis_error)
        QThreadPool.globalInstance().start(worker)

    # ---- 模式3：按章节生成 ----

    def _generate_per_chapter(self, voice_id: str):
        if not self._book_chapters:
            QMessageBox.warning(self, "提示", "请先导入 EPUB 书籍")
            return

        # 只合成勾选的章节
        checked = self._get_checked_chapters()
        if not checked:
            QMessageBox.warning(self, "提示", "请在章节列表中勾选至少一个章节")
            return

        chapters_to_synth = [self._book_chapters[i] for i in checked
                            if 0 <= i < len(self._book_chapters)]

        # 选择输出目录
        output_dir = QFileDialog.getExistingDirectory(
            self, "选择章节音频输出目录"
        )
        if not output_dir:
            return

        rate = self._get_rate()
        self._batch_outputs = []
        self._batch_output_dir = output_dir

        self._set_busy(True)
        self.progress.setRange(0, len(chapters_to_synth))
        self.progress.setValue(0)
        self.status_bar.showMessage(
            f"按章节生成中 (0/{len(chapters_to_synth)})..."
        )

        self._batch_worker = BatchSynthesisWorker(
            self.model_manager, chapters_to_synth,
            voice_id, output_dir, rate
        )
        self._batch_worker.signals.progress.connect(self._on_batch_progress)
        self._batch_worker.signals.chapter_done.connect(self._on_chapter_done)
        self._batch_worker.signals.error.connect(self._on_batch_error)
        self._batch_worker.signals.all_done.connect(self._on_batch_all_done)
        QThreadPool.globalInstance().start(self._batch_worker)

    # ---- 批量合成回调 ----

    def _on_batch_progress(self, current: int, total: int, title: str):
        self.progress.setValue(current)
        short_title = title[:25] + "..." if len(title) > 25 else title
        self.status_bar.showMessage(
            f"正在生成: 第{current}/{total}章 {short_title}"
        )

    def _on_chapter_done(self, index: int, output_path: str):
        self._batch_outputs.append(output_path)

    def _on_batch_error(self, index: int, error_msg: str):
        self._batch_outputs.append(None)
        logger.warning(f"章节 {index+1} 生成失败: {error_msg}")

    def _on_batch_all_done(self, results: list):
        self._set_busy(False)
        self.progress.setVisible(False)

        success = [r for r in results if r is not None]
        failed = len(results) - len(success)

        if success:
            self._current_output_path = success[0]
            self.play_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

        msg = f"按章节生成完成！\n\n成功: {len(success)} 章\n"
        if failed:
            msg += f"失败: {failed} 章\n"
        msg += f"\n文件保存在:\n{self._batch_output_dir}\n\n是否打开文件夹？"

        reply = QMessageBox.information(
            self, "批量生成完成", msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            os.startfile(self._batch_output_dir)

        self.status_bar.showMessage(
            f"按章节生成完成: {len(success)}/{len(results)} 章 → {self._batch_output_dir}"
        )

    # ---- 辅助方法 ----

    def _get_rate(self) -> str:
        """从滑块获取 Edge TTS 语速参数"""
        sv = self.speed_slider.value()
        if sv == 100:
            return "+0%"
        elif sv > 100:
            return f"+{sv - 100}%"
        else:
            return f"-{100 - sv}%"

    def _set_busy(self, busy: bool):
        """设置 UI 忙碌状态"""
        self.generate_btn.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.status_bar.showMessage("正在生成语音文件，请稍候...")
            # 启动进度动画（QTimer 模拟等待进度，核心引擎无中间回调）
            # 先停掉旧 timer（如果有的话，比如连续点击生成）
            if hasattr(self, '_synth_anim_timer') and self._synth_anim_timer is not None:
                self._synth_anim_timer.stop()
            self._synth_anim_target = 0
            self._synth_anim_timer = QTimer(self)
            self._synth_anim_timer.timeout.connect(self._on_synth_anim_tick)
            self._synth_anim_timer.start(400)  # 每 400ms 加 1%
        else:
            self.progress.setRange(0, 100)
            if hasattr(self, '_synth_anim_timer') and self._synth_anim_timer is not None:
                self._synth_anim_timer.stop()
                self._synth_anim_timer = None

    def _on_synth_anim_tick(self):
        """进度动画: 自动推进到 95%，超过 70% 后减速"""
        if not hasattr(self, '_synth_anim_timer') or self._synth_anim_timer is None:
            return
        if self.progress.maximum() != 100:
            self._synth_anim_timer.stop()
            return
        current = self.progress.value()
        target = getattr(self, '_synth_anim_target', 0)

        # 上限 95%（最后 5% 留给真实"合并→完成"信号）
        ceiling = max(target, 95)
        if current < ceiling:
            self.progress.setValue(current + 1)
            # 同步更新状态栏（否则卡在旧的 "10%" 不动）
            pct = current + 1
            if pct >= 90:
                self.status_bar.showMessage("正在生成语音... 请稍候")
            else:
                self.status_bar.showMessage(f"正在生成语音... {pct}%")

        # 超过 70% 后减速：每 tick 间隔从 400ms 翻倍到 800ms
        if current >= 70 and self._synth_anim_timer.interval() < 800:
            self._synth_anim_timer.setInterval(800)
        if current >= ceiling:
            self._synth_anim_timer.stop()

    def _build_full_text(self) -> str:
        """拼接全书文本"""
        parts = []
        for ch in self._book_chapters:
            num = ch["index"] + 1 if ch.get("index") is not None else 0
            parts.append(
                f"第{num}章 {ch['title']}\n\n{ch['content']}"
            )
        return "\n\n".join(parts)

    def _on_synthesis_progress(self, pct: int):
        """更新合成进度（优先显示真实进度，动画仅在无信号时补充）"""
        # 同步动画目标值（取真实进度和动画目标的最大值）
        anim_target = getattr(self, '_synth_anim_target', 0)
        self._synth_anim_target = max(anim_target, pct)
        # 直接跳到真实进度（不等待动画）
        self.progress.setValue(pct)
        if pct < 10:
            self.status_bar.showMessage("准备合成...")
        elif pct < 90:
            self.status_bar.showMessage(f"正在生成语音... {pct}%")
        elif pct < 100:
            self.status_bar.showMessage("正在合并音频...")
        else:
            self.status_bar.showMessage("合成完成 100%")

    def _on_synthesis_finished(self, result: SynthesisResult):
        """单个合成完成"""
        self._set_busy(False)
        self.progress.setVisible(False)

        if result.success:
            self.status_bar.showMessage(
                f"生成完成: {result.output_path} ({result.word_count} 字符)"
            )
            self.play_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

            reply = QMessageBox.information(
                self, "生成完成",
                f"语音文件已生成！\n\n"
                f"文件: {os.path.basename(result.output_path)}\n"
                f"字数: {result.word_count}\n\n"
                f"是否立即播放？",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._on_play()
        else:
            self.status_bar.showMessage(f"生成失败: {result.error_message}")
            QMessageBox.critical(self, "生成失败", result.error_message)

    def _on_synthesis_error(self, error_msg: str):
        """合成出错"""
        self._set_busy(False)
        self.progress.setVisible(False)
        self.status_bar.showMessage(f"生成失败: {error_msg}")
        QMessageBox.critical(self, "生成失败", f"语音合成出错:\n{error_msg}")

    # --------------------------------------------------------
    # 播放与导出
    # --------------------------------------------------------

    def _on_play(self):
        """播放生成的音频"""
        if not self._current_output_path or not os.path.exists(self._current_output_path):
            QMessageBox.warning(self, "提示", "请先生成语音文件")
            return

        self._play_audio(self._current_output_path)

    def _play_audio(self, file_path: str):
        """使用系统默认播放器播放音频"""
        try:
            system = platform.system()
            if system == "Windows":
                os.startfile(file_path)
            elif system == "Darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as e:
            QMessageBox.warning(self, "播放失败", f"无法播放音频:\n{str(e)}")
            logger.error(f"播放失败: {e}")

    def _on_export(self):
        """导出/转换为其他格式"""
        if not self._current_output_path or not os.path.exists(self._current_output_path):
            QMessageBox.warning(self, "提示", "请先生成语音文件")
            return

        # 选择导出格式
        output_path, selected_filter = QFileDialog.getSaveFileName(
            self, "导出音频", "output.wav",
            "WAV Files (*.wav);;MP3 Files (*.mp3);;OGG Files (*.ogg);;M4A Files (*.m4a)"
        )
        if not output_path:
            return

        try:
            if AudioExporter.is_available():
                AudioExporter.convert_format(
                    self._current_output_path, output_path
                )
                self.status_bar.showMessage(f"已导出: {output_path}")
                QMessageBox.information(self, "导出成功",
                                        f"音频已导出到:\n{output_path}")
            else:
                # pydub 不可用，提示安装
                QMessageBox.warning(
                    self, "缺少依赖",
                    "导出功能需要安装 pydub 和 ffmpeg。\n\n"
                    "请运行:\n"
                    "  pip install pydub\n"
                    "并安装 ffmpeg: https://ffmpeg.org/download.html"
                )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出音频失败:\n{str(e)}")
            logger.error(f"导出失败: {e}")
