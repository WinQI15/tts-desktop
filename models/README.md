# 本地 TTS 模型

本目录存储运行时下载的 AI 模型和预设音色。

```
models/
├── OmniVoice/                  # k2-fsa/OmniVoice (~2.3 GB, 自动下载)
│   ├── model.safetensors       # 主模型权重
│   ├── tokenizer.json          # 文本分词器
│   └── audio_tokenizer/        # eustlb/higgs-audio-v2-tokenizer (~769 MB)
├── preset_voices/              # 预设音色参考样本 (23 个 WAV)
│   ├── zh_female_*.wav         # 中文女声
│   ├── zh_male_*.wav           # 中文男声
│   ├── en_*.wav                # 英文
│   └── zh_cantonese_*.wav      # 粤语/台湾腔
└── cloned_voices.json          # 用户克隆音色数据（本地自动生成）
```

## OmniVoice

- **仓库**: [k2-fsa/OmniVoice](https://huggingface.co/k2-fsa/OmniVoice)
- **参数**: 600M
- **语言**: 646 种
- **许可证**: Apache 2.0
- **依赖**: `pip install omnivoice torch transformers soundfile`

### 下载

在应用界面中点击「下载模型」按钮即可自动下载，约 3.1 GB（含音频分词器）。

也可手动下载：

```bash
# 主模型
huggingface-cli download k2-fsa/OmniVoice --local-dir models/OmniVoice/

# 音频分词器
huggingface-cli download eustlb/higgs-audio-v2-tokenizer --local-dir models/OmniVoice/audio_tokenizer/
```

## 预设音色

`preset_voices/` 目录中的 23 个 WAV 文件作为 OmniVoice 音色克隆重参考音频。

使用 Edge TTS 重新生成真实语音样本：

```bash
python tools/generate_preset_voices.py
```
