# TTS Desktop — 文本转语音桌面程序

> 多引擎 TTS 桌面应用 · Edge TTS（在线 322 音色）+ OmniVoice（本地 646 语言零样本克隆）

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 功能

- **多引擎支持** — Edge TTS（免费在线，322 音色）和 OmniVoice（本地 GPU，646 语言）
- **音色克隆** — OmniVoice 零样本音色克隆，一键复刻任意声音
- **EPUB 书籍导入** — 直接导入 EPUB 电子书，按章节批量生成有声书
- **语速调节** — 滑杆控制语速 (±50%)
- **多格式导出** — MP3 / WAV / OGG / M4A / FLAC
- **音频后处理** — 合并、音量归一化、静音裁切
- **中文本地化** — 完整中文界面

## 安装

### 快速开始（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/WinQI15/tts-desktop.git
cd tts-desktop

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 ffmpeg（音频处理必需）
# Windows: 下载 https://ffmpeg.org/download.html 放到 vendor/ffmpeg/bin/
#   (或运行 tools/download_ffmpeg.py)
# macOS:   brew install ffmpeg
# Linux:   sudo apt install ffmpeg

# 4. 启动
python main.py
```

### 便携模式（免 pip）

```bash
# 将所有依赖安装到项目内 vendor/ 目录
pip install --target vendor/ -r requirements.txt

# 复制整个 tts-desktop/ 到其他设备即可运行
python main.py
```

### 本地模型（可选，OmniVoice 需要 NVIDIA GPU）

```bash
# 在应用内点击「下载模型」按钮，或：
python tools/download_audio_tokenizer.py
```

模型说明见 [models/README.md](models/README.md)。

## 使用

### 基本流程

1. **选择引擎** — 顶部下拉切换 Edge TTS（在线）或 OmniVoice（本地 GPU）
2. **选择音色** — 从 322+ 音色中选择，或使用预设/克隆音色
3. **输入文本** — 直接输入或导入 EPUB 电子书
4. **调节语速** — 滑杆控制
5. **生成语音** — 点击「生成语音」按钮
6. **导出/播放** — 支持多种音频格式

### EPUB 有声书

1. 点击「导入电子书」→ 选择 .epub 文件
2. 在左侧章节列表勾选需要合成的章节
3. 生成模式选择「当前文本」「全书单文件」或「按章节分文件」
4. 点击生成

### 音色克隆（OmniVoice）

1. 切换到 OmniVoice 引擎
2. 选择参考音频文件（WAV/MP3）
3. 输入音色名称
4. 点击「克隆音色」

## 项目结构

```
tts-desktop/
├── main.py                    # 程序入口
├── requirements.txt           # Python 依赖
├── TTS Desktop.bat            # Windows 启动脚本
├── tts_app/                   # 核心模块
│   ├── engine/                # TTS 引擎
│   │   ├── base.py            # 引擎抽象基类
│   │   ├── edge_tts_engine.py # Edge TTS 引擎
│   │   ├── local_engines.py   # OmniVoice 引擎
│   │   └── model_manager.py   # 引擎管理器
│   ├── gui/
│   │   └── main_window.py     # PyQt5 主界面
│   ├── audio_processor.py     # 音频后处理
│   ├── epub_parser.py         # EPUB 解析
│   ├── model_downloader.py    # 模型下载
│   └── cloned_voice_store.py  # 克隆音色管理
├── models/                    # 模型存储（自动下载）
│   ├── preset_voices/         # 预设音色样本
│   └── README.md
├── tools/                     # 辅助脚本
│   ├── download_audio_tokenizer.py
│   ├── generate_preset_voices.py
│   └── extract_ffmpeg.py
└── vendor/                    # 便携依赖（git 排除，通过 pip 安装）
```

## 系统要求

| 引擎 | 最低配置 | 推荐配置 |
|------|----------|----------|
| Edge TTS | Python 3.10+ | 无 GPU 需求 |
| OmniVoice | Python 3.10+, CUDA GPU | NVIDIA GPU ≥6GB VRAM |

模型下载：OmniVoice 约 3.1 GB（模型 + 音频分词器）。

## 开源致谢

本项目依赖以下开源项目，详见 [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md)。

## License

MIT License — 详见 [LICENSE](LICENSE)。
