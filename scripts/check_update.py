#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙翼 Hermes 配置包 - 用户端自进化检测脚本模板
功能: 检测 GitHub 是否有新版配置包, 输出比对结果。Hermes 可调用此脚本或参考其逻辑。
用法:
    python3 check_update.py            # 检测是否有新版
    python3 check_update.py --repo boainet/hermes-onboarding   # 指定仓库
行为:
    - 读本地当前版本 (从 ~/.hermes/ 或本目录查 onboarding_version)
    - 查 GitHub 最新版本 (tags / releases)
    - 有新版输出 NEW_VERSION:<版本号> (供 Hermes 检测到后提示用户确认)
    - 无新版输出 UP_TO_DATE
此脚本只检测, 不做任何写操作 (零副作用)。更新动作由用户确认后 Hermes 走增量合并。
"""
import json
import os
import subprocess
import sys
import urllib.request

DEFAULT_REPO = "boainet/hermes-onboarding"


def get_local_version():
    """读取本地已应用的配置包版本号 (从 onboarding_version 文件, 无则 None)"""
    candidates = [
        os.path.expanduser("~/.hermes/onboarding_version"),
        os.path.expanduser("~/.config/hermes/onboarding_version"),
        "onboarding_version.txt",
    ]
    for c in candidates:
        if os.path.exists(c):
            with open(c, encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
    return None


def get_latest_version(repo):
    """查 GitHub 最新版本(优先 releases, 退化 tags, 再退化默认分支 README)"""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "hermes-onboarding"}
    # 1. releases/latest
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases/latest", headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            tag = data.get("tag_name", "")
            if tag:
                return tag.lstrip("v")
    except Exception:
        pass
    # 2. tags 列表
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/tags", headers=headers
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
            if data:
                return data[0].get("name", "").lstrip("v")
    except Exception:
        pass
    # 3. 默认分支 README 里的版本号(仓库不打 tag 时也能检测)
    try:
        req = urllib.request.Request(
            f"https://raw.githubusercontent.com/{repo}/main/README.md",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode()
            import re
            m = re.search(r"v\d+\.\d+", text)
            if m:
                return m.group(0).lstrip("v")
    except Exception:
        pass
    return None


def version_tuple(v):
    """把 v3.7 转 (3,7) 用于比较"""
    v = str(v).strip().lstrip("vV")
    parts = []
    for seg in v.split("."):
        try:
            parts.append(int(seg))
        except ValueError:
            break
    return tuple(parts)


def main():
    repo = DEFAULT_REPO
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--repo" and i + 1 < len(args):
            repo = args[i + 1]

    local = get_local_version()
    latest = get_latest_version(repo)

    if latest is None:
        print("CHECK_FAILED")  # 网络/仓库不可达, 不打扰用户, Hermes 静默重试
        return 0

    # 无本地版本号(新装还没写 onboarding_version): 视为已是最新, 不误报升级
    if local is None:
        print("UP_TO_DATE")
        return 0

    lv, lv2 = version_tuple(local), version_tuple(latest)
    if lv and lv2 and lv2 > lv:
        print(f"NEW_VERSION:{latest}")  # 有新版, Hermes 应提示用户确认
        return 0
    print("UP_TO_DATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
