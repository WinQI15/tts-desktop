# -*- coding: utf-8 -*-
"""解压 ffmpeg.zip 并将 ffmpeg.exe 和 ffprobe.exe 放到 vendor/ffmpeg/bin/"""
import os
import sys
import zipfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

ZIP_PATH = os.path.join(PROJECT_ROOT, "vendor", "ffmpeg", "ffmpeg.zip")
BIN_DIR = os.path.join(PROJECT_ROOT, "vendor", "ffmpeg", "bin")

if not os.path.exists(ZIP_PATH):
    print(f"错误: 找不到 {ZIP_PATH}")
    sys.exit(1)

os.makedirs(BIN_DIR, exist_ok=True)

print(f"解压 {ZIP_PATH} ...")

with zipfile.ZipFile(ZIP_PATH, 'r') as zf:
    # 找到 bin/ 目录
    bin_names = [n for n in zf.namelist() if n.endswith('/bin/') or '/bin/' in n]
    if bin_names:
        # 提取第一层目录名
        root_dir = bin_names[0].split('/')[0]
        print(f"  根目录: {root_dir}")
        
        # 只提取 bin/ 目录下的文件
        bin_prefix = f"{root_dir}/bin/"
        for name in zf.namelist():
            if name.startswith(bin_prefix) and not name.endswith('/'):
                # 提取文件到 vendor/ffmpeg/bin/
                basename = name[len(bin_prefix):]
                dest = os.path.join(BIN_DIR, basename)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with zf.open(name) as src:
                    with open(dest, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                size_kb = os.path.getsize(dest) / 1024
                print(f"  ✓ {basename} ({size_kb:.1f} KB)")

print("\n验证:")
for exe in ["ffmpeg.exe", "ffprobe.exe"]:
    path = os.path.join(BIN_DIR, exe)
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f"  ✓ {exe} ({size_mb:.1f} MB)")
    else:
        print(f"  ✗ {exe} 未找到!")

# 删除 zip 文件
print(f"\n清理临时文件: {ZIP_PATH}")
os.remove(ZIP_PATH)
print("完成!")
