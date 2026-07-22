# -*- coding: utf-8 -*-
"""
生成缺失的预设音色参考音频文件
使用 Edge TTS 生成标准中文语音样本
"""
import asyncio
import os
import sys

# 添加 vendor 到路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
VENDOR_DIR = os.path.join(PROJECT_ROOT, "vendor")
sys.path.insert(0, VENDOR_DIR)

PRESET_DIR = os.path.join(PROJECT_ROOT, "models", "preset_voices")

# Edge TTS 音色映射: 文件名 -> (Voice, 朗读文本)
VOICE_MAP = {
    "zh_female_xiaochen.wav":   ("zh-CN-XiaochenNeural",   "你好，我是晓辰，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_female_xiaohan.wav":    ("zh-CN-XiaohanNeural",    "你好，我是晓涵，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_female_xiaomeng.wav":   ("zh-CN-XiaomengNeural",   "你好，我是晓梦，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_female_xiaomo.wav":     ("zh-CN-XiaomoNeuralMax",  "你好，我是晓墨，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_female_xiaorui.wav":    ("zh-CN-XiaoruiNeural",    "你好，我是晓睿，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_female_xiaoshuang.wav": ("zh-CN-XiaoshuangNeural", "你好，我是晓双，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_male_yunhao.wav":       ("zh-CN-YunhaoNeural",     "你好，我是云浩，这是我的声音样本。今天天气真好，适合出去走走。"),
    "zh_male_yunye.wav":        ("zh-CN-YunyeNeural",      "你好，我是云野，这是我的声音样本。今天天气真好，适合出去走走。"),
}


async def generate_one(filename: str, voice: str, text: str) -> bool:
    """使用 Edge TTS 生成单个音频文件"""
    try:
        import edge_tts

        output_path = os.path.join(PRESET_DIR, filename)
        # 先输出到临时文件
        tmp_path = output_path + ".tmp.mp3"

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmp_path)

        # 转换为 WAV（使用 Python 内置 wave 模块，不依赖 pydub）
        _convert_mp3_to_wav(tmp_path, output_path)

        # 删除临时 MP3
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        size_kb = os.path.getsize(output_path) / 1024
        print(f"  ✓ {filename} ({size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"  ✗ {filename}: {e}")
        return False


def _convert_mp3_to_wav(mp3_path: str, wav_path: str):
    """使用 ffmpeg 将 MP3 转为 24kHz 16bit 单声道 WAV"""
    import subprocess

    # 尝试使用系统 ffmpeg
    # 将 vendor/ffmpeg/bin 加入 PATH
    ffmpeg_bin = os.path.join(PROJECT_ROOT, "vendor", "ffmpeg", "bin")
    env = os.environ.copy()
    if os.path.isdir(ffmpeg_bin):
        env["PATH"] = ffmpeg_bin + os.pathsep + env.get("PATH", "")

    cmd = [
        "ffmpeg", "-y", "-i", mp3_path,
        "-acodec", "pcm_s16le", "-ac", "1", "-ar", "24000",
        wav_path
    ]
    subprocess.run(cmd, capture_output=True, env=env, check=True)


async def main():
    print("开始生成预设音色参考音频...")
    print(f"输出目录: {PRESET_DIR}\n")

    os.makedirs(PRESET_DIR, exist_ok=True)

    success = 0
    failed = 0

    for filename, (voice, text) in VOICE_MAP.items():
        filepath = os.path.join(PRESET_DIR, filename)
        # 如果文件已存在且非空，跳过
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"  - {filename} (已存在，跳过)")
            success += 1
            continue

        ok = await generate_one(filename, voice, text)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n完成: {success} 成功, {failed} 失败")


if __name__ == "__main__":
    asyncio.run(main())
