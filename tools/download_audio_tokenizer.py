# -*- coding: utf-8 -*-
"""下载 OmniVoice 所需的 audio tokenizer 到本地"""
import os
import sys

# 添加 vendor 到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
VENDOR_DIR = os.path.join(PROJECT_ROOT, "vendor")
sys.path.insert(0, VENDOR_DIR)

# 抑制 HuggingFace 警告
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

from huggingface_hub import snapshot_download

target = os.path.join(PROJECT_ROOT, "models", "OmniVoice", "audio_tokenizer")
repo = "eustlb/higgs-audio-v2-tokenizer"

if os.path.isdir(target) and os.listdir(target):
    print(f"audio_tokenizer 已存在: {target}")
else:
    print(f"正在下载 {repo} ...")
    print(f"目标路径: {target}")
    snapshot_download(
        repo_id=repo,
        local_dir=target,
        local_dir_use_symlinks=False,
        resume_download=True,
        max_workers=4,
        token=False,
    )
    print("下载完成!")
