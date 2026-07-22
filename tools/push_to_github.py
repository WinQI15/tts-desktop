# -*- coding: utf-8 -*-
"""
推送到 GitHub — 使用 Contents API 逐文件上传（纯 Python）
"""
import os, sys, json, base64
import urllib.request, urllib.error
from urllib.parse import quote


def api(method, path, token, data=None):
    url = f"{API_BASE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
    if body:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        return e.code, msg[:300]


REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_USER = "WinQI15"
REPO_NAME = "tts-desktop"
API_BASE = "https://api.github.com"


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        token = input("GitHub Token: ").strip()
    if not token:
        print("需要 Token"); sys.exit(1)

    print(f"推送 → github.com/{GITHUB_USER}/{REPO_NAME}\n")

    # 1. 创建仓库（不 auto_init，避免初始 commit 冲突）
    status, data = api("GET", f"/repos/{GITHUB_USER}/{REPO_NAME}", token)
    if status == 200:
        print("仓库已存在")
    else:
        status, data = api("POST", "/user/repos", token, {
            "name": REPO_NAME,
            "description": "TTS Desktop - 多引擎文本转语音桌面程序",
            "private": False,
        })
        if status == 201:
            print("仓库已创建")
        else:
            print(f"创建失败: {data}"); sys.exit(1)

    # 2. 扫描文件
    skip = {".git", "__pycache__", "vendor", ".cache"}
    files = []
    for root, dirs, fnames in os.walk(REPO_DIR):
        dirs[:] = [d for d in dirs if d not in skip]
        for fn in fnames:
            fp = os.path.join(root, fn)
            sz = os.path.getsize(fp)
            if sz > 3_000_000:
                print(f"  跳过 {os.path.relpath(fp, REPO_DIR)} ({sz/1e6:.1f}MB)")
                continue
            with open(fp, "rb") as f:
                content = f.read()
            rel = os.path.relpath(fp, REPO_DIR).replace("\\", "/")
            if rel.startswith("models/OmniVoice/"):
                if fn.endswith(".safetensors"):
                    print(f"  跳过 {rel} (模型权重)")
                    continue
            files.append({"path": rel, "content": content})

    print(f"\n上传 {len(files)} 个文件:\n")

    ok = 0
    for i, f in enumerate(files):
        # ★ URL 编码路径中空格等特殊字符
        safe_path = quote(f["path"], safe="")
        b64 = base64.b64encode(f["content"]).decode()
        status, data = api("PUT",
            f"/repos/{GITHUB_USER}/{REPO_NAME}/contents/{safe_path}", token,
            {"message": f"Add {f['path']}", "content": b64})
        if status in (201, 200):
            ok += 1
            print(f"  [{i+1}/{len(files)}] ✓ {f['path']}")
        else:
            print(f"  [{i+1}/{len(files)}] ✗ {f['path']} → {data[:120]}")

    print(f"\n完成: {ok}/{len(files)} 个文件")
    if ok == len(files):
        print(f"✓ https://github.com/{GITHUB_USER}/{REPO_NAME}")


if __name__ == "__main__":
    main()
