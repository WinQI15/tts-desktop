# 开源依赖致谢 / Open Source Acknowledgments

TTS Desktop 基于以下开源项目构建，特此致谢。

---

## 直接依赖 (Direct Dependencies)

| 包名 | 版本 | 许可证 | 用途 | 仓库 |
|------|------|--------|------|------|
| [PyQt5](https://riverbankcomputing.com/software/pyqt/) | ≥5.15 | GPL v3 / 商业 | GUI 框架 | [riverbankcomputing/pyqt5](https://www.riverbankcomputing.com/software/pyqt/) |
| [edge-tts](https://github.com/rany2/edge-tts) | ≥6.1 | GPL v3 | Microsoft Edge 在线 TTS | [rany2/edge-tts](https://github.com/rany2/edge-tts) |
| [ebooklib](https://github.com/aerkalov/ebooklib) | ≥0.18 | AGPL v3 | EPUB 文件读取 | [aerkalov/ebooklib](https://github.com/aerkalov/ebooklib) |
| [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) | ≥4.12 | MIT | HTML/XML 解析 | [Beautiful Soup](https://code.launchpad.net/beautifulsoup) |
| [lxml](https://lxml.de/) | ≥4.9 | BSD-3-Clause | 快速 XML/HTML 解析 | [lxml/lxml](https://github.com/lxml/lxml) |
| [pydub](https://github.com/jiaaro/pydub) | ≥0.25 | MIT | 音频处理（合并/转换/变速） | [jiaaro/pydub](https://github.com/jiaaro/pydub) |
| [soundfile](https://github.com/bastibe/python-soundfile) | ≥0.12 | BSD-3-Clause | WAV/FLAC 读写 | [bastibe/python-soundfile](https://github.com/bastibe/python-soundfile) |
| [onnxruntime](https://onnxruntime.ai/) | ≥1.15 | MIT | ONNX 模型推理 | [microsoft/onnxruntime](https://github.com/microsoft/onnxruntime) |
| [tokenizers](https://github.com/huggingface/tokenizers) | ≥0.19 | Apache 2.0 | 文本分词 | [huggingface/tokenizers](https://github.com/huggingface/tokenizers) |
| [torch](https://pytorch.org/) | ≥2.0 | BSD-3-Clause | 深度学习框架 | [pytorch/pytorch](https://github.com/pytorch/pytorch) |
| [transformers](https://huggingface.co/docs/transformers/) | ≥4.40 | Apache 2.0 | HuggingFace 模型推理 | [huggingface/transformers](https://github.com/huggingface/transformers) |
| [safetensors](https://github.com/huggingface/safetensors) | ≥0.4 | Apache 2.0 | 安全模型序列化 | [huggingface/safetensors](https://github.com/huggingface/safetensors) |
| [accelerate](https://huggingface.co/docs/accelerate/) | ≥0.30 | Apache 2.0 | 分布式推理加速 | [huggingface/accelerate](https://github.com/huggingface/accelerate) |
| [huggingface_hub](https://huggingface.co/docs/huggingface_hub/) | ≥0.20 | Apache 2.0 | HuggingFace 模型下载 | [huggingface/huggingface_hub](https://github.com/huggingface/huggingface_hub) |
| [audioop-lts](https://github.com/AbstractUmbra/audioop-lts) | ≥0.2 | MIT | audioop 替代（Python 3.13） | [AbstractUmbra/audioop-lts](https://github.com/AbstractUmbra/audioop-lts) |

---

## AI 模型 (Pre-trained Models)

| 模型 | 许可证 | 参数 | 来源 |
|------|--------|------|------|
| [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice) | Apache 2.0 | 600M | Xiaomi — 646 语言零样本 TTS |
| [eustlb/higgs-audio-v2-tokenizer](https://huggingface.co/eustlb/higgs-audio-v2-tokenizer) | MIT | 769MB | Higgs Audio Tokenizer V2 |

> 注：模型权重不包含在本仓库中，运行时通过 HuggingFace Hub 自动下载到 `models/OmniVoice/`。

---

## 外部工具 (External Tools)

| 工具 | 版本 | 许可证 | 用途 |
|------|------|--------|------|
| [FFmpeg](https://ffmpeg.org/) | N-125299 | LGPL v2.1+ / GPL v2+ | 音频编解码与格式转换 |

> 注：FFmpeg 二进制不包含在本仓库中，需用户手动安装或通过 `tools/` 脚本下载。运行时自动检测 `PATH` 或 `vendor/ffmpeg/bin/`。

---

## 传递依赖 (Transitive Dependencies)

以下为上述直接依赖引入的传递依赖，同样感谢其作者：

| 包名 | 许可证 |
|------|--------|
| numpy | BSD-3-Clause |
| scipy | BSD-3-Clause |
| Pillow | MIT-CMU |
| aiohttp | Apache 2.0 |
| certifi | MPL 2.0 |
| charset-normalizer | MIT |
| idna | BSD-3-Clause |
| urllib3 | MIT |
| requests | Apache 2.0 |
| filelock | Public Domain |
| fsspec | BSD-3-Clause |
| Jinja2 | BSD-3-Clause |
| MarkupSafe | BSD-3-Clause |
| packaging | Apache 2.0 / BSD-2-Clause |
| psutil | BSD-3-Clause |
| PyYAML | MIT |
| regex | Apache 2.0 |
| tqdm | MPL 2.0 / MIT |
| typing_extensions | Python-2.0 |

---

## 特别感谢

- **Microsoft** — Edge TTS 服务，提供 322+ 免费在线音色
- **Xiaomi** — OmniVoice 模型，646 语言零样本 TTS
- **HuggingFace** — 模型托管与分发平台
- **PyTorch** — 深度学习框架
- **Qt Project** — PyQt5 GUI 框架

---

所有商标和注册商标均为其各自所有者的财产。
