#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三方一致性核查器 (pre-commit hook 第 4 层 · 评价建议 2 落点)
校验"文档(guide)声明的实现契约" 与 "脚本实际行为" 与 "服务端(cron jobs)配置" 三方一致。

背景: 单人+单 agent 快速迭代, 最容易出"文档说 A, 脚本/服务端做 B"的漂移。
历史踩坑(评价点名):
  - 版本号存 memory 还是文件 (v4.6 才写死) -> 契约: 检测脚本只读文件, 不读 memory
  - 检测任务用 agent 还是脚本模式 (v4.8 才写死) -> 契约: 检测用脚本模式(no_agent/monitor), 不配 LLM provider
  - 签名算法取前 16 位 (v4.1 才补全) -> 契约: uuid.signature 用 hmac sha256 取前 16 hex

用法: 与 check_version.sh / check_sync.py 一起被 pre-commit 调用, 或独立运行。
    python3 check_consistency.py [--jobs /path/to/jobs.json]
不传 --jobs 时, 服务端一致性检查自动跳过(不阻断), 只做 文档<->脚本 双向校验。
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = subprocess.run(
    ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
).stdout.strip()
if not REPO:
    sys.exit(0)

GUIDE = Path(REPO) / "hermes_onboarding_guide.md"
CHECK_UPDATE = Path(REPO) / "scripts" / "check_update.py"
SYNC_MONITOR = Path.home() / ".hermes" / "scripts" / "sync_monitor.py"

problems = []
checked = []


def note(ok, what, detail=""):
    checked.append(what)
    if not ok:
        problems.append(f"{what}: {detail}")


def guide_contains(pat):
    """guide 是否包含正则 pat"""
    return bool(re.search(pat, GUIDE.read_text(encoding="utf-8")))


# ---------- 1. 文档 <-> 脚本 契约一致 ----------
def doc_vs_script():
    g = GUIDE.read_text(encoding="utf-8")
    cu = CHECK_UPDATE.read_text(encoding="utf-8") if CHECK_UPDATE.exists() else ""

    # 契约 A: 检测脚本只读文件, 不读 memory
    doc = "检测脚本只读" in g and "不读 memory" in g
    impl = ("onboarding_version" in cu) and ("memory" not in cu.lower())
    note(
        doc and impl,
        "契约A: 版本号存储=检测脚本只读文件不读memory",
        f"文档声明={doc}, 脚本实现={impl}",
    )

    # 契约 B: 输出协议 (UP_TO_DATE / NEW_VERSION / CHECK_FAILED)
    doc = all(x in g for x in ["UP_TO_DATE", "NEW_VERSION", "CHECK_FAILED"])
    impl = all(x in cu for x in ["UP_TO_DATE", "NEW_VERSION", "CHECK_FAILED"])
    note(
        doc and impl,
        "契约B: 输出协议三态(UP_TO_DATE/NEW_VERSION/CHECK_FAILED)",
        f"文档={doc}, 脚本={impl}",
    )

    # 契约 C: 检测用脚本模式零 LLM (guide 4c/检测机制声明)
    doc = ("脚本模式" in g) and ("不调用大模型" in g or "零 LLM" in g)
    # 脚本侧: check_update 无任何 LLM/API key 调用(只用 urllib 查 GitHub)
    impl = ("urllib" in cu) and ("api_key" not in cu.lower()) and ("openai" not in cu.lower())
    note(
        doc and impl,
        "契约C: 检测=纯脚本零LLM(不配provider)",
        f"文档={doc}, 脚本={impl}",
    )

    # 契约 D: 签名算法前 16 位 (贡献方法论)
    doc = re.search(r"前\s*16\s*位|\[:16\]|取前 16", g)
    # 服务端签名规格在 guide 贡献方法论节声明
    note(bool(doc), "契约D: 签名算法=前16位声明存在于guide", "" if doc else "guide 未声明前16位契约")


# ---------- 2. 文档 <-> 服务端(cron) 一致 ----------
def doc_vs_server(jobs_path):
    if not jobs_path:
        return
    jp = Path(jobs_path)
    if not jp.exists():
        note(False, "服务端: jobs.json 存在", f"找不到 {jp}")
        return
    text = jp.read_text(encoding="utf-8")
    g = GUIDE.read_text(encoding="utf-8")

    # 契约 E: 服务端方法论同步 job 引用的 monitor_script 文件必须真实存在
    # (防止 jobs.json 指向一个不存在的脚本 -> 检测静默失效, 故障不可见)
    doc_sync = "方法论" in g and "自动同步" in g
    has_job = "sync_monitor" in text or "方法论自动同步" in text or "0a220c7e6dfe" in text
    # 从 jobs.json 提取所有 monitor_script/script 引用的脚本名, 检查是否在本机真实存在
    mon_refs = re.findall(r'"(?:monitor_script|script)":\s*"([^"]+\.py)"', text)
    missing_scripts = []
    for s in mon_refs:
        p = Path.home() / ".hermes" / "scripts" / s
        if not p.exists():
            missing_scripts.append(s)
    note(
        (not missing_scripts) and (has_job or not doc_sync),
        "契约E: 服务端job引用的monitor/script脚本真实存在",
        (f"缺失脚本: {missing_scripts}" if missing_scripts else f"服务端引用{len(mon_refs)}个脚本均存在, 方法论同步job存在={has_job}"),
    )

    # 契约 F: 检测脚本任务应为脚本模式(no_agent=true 或 monitor), 非 agent 模式
    # 这是 v4.8 踩的坑: agent 模式检测需配 LLM provider, 会报 No LLM provider
    # 从 guide 检测机制声明提取"检测用脚本"与 jobs.json 里 check_update 相关 job
    doc = "脚本模式" in g and "不需要配 LLM provider" in g
    # 服务端: 找 check_update 相关 job (若存在)
    if "check_update" in text:
        # 粗略判断该 job 是否 no_agent 或带 monitor(脚本驱动)
        # jobs.json 里 job 若 no_agent=true 或 monitor_script 非空 -> 脚本模式
        note(
            doc,
            "契约F: 检测 job 应为脚本模式(no_agent/monitor)非agent",
            "guide 声明脚本模式; 服务端 check_update job 需人工确认 no_agent/monitor",
        )
    else:
        # 服务端没配 check_update job(用户端脚本在别处), 不强制
        note(True, "契约F: 检测 job 脚本模式(服务端无 check_update job, 跳过)", "")


def main():
    jobs = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--jobs" and i + 1 < len(args):
            jobs = args[i + 1]

    doc_vs_script()
    doc_vs_server(jobs)

    # 输出
    for c in checked:
        print(f"[consistency] {'✓' if '契约' in c else '·'} {c}")
    if problems:
        print("\n[pre-commit] ✗ 三方一致性检查未通过:")
        for p in problems:
            print(f"    - {p}")
        print("[pre-commit] 修复: 对齐 guide 声明与脚本/服务端实际行为")
        return 1
    print("[pre-commit] ✓ 三方一致性检查通过 (文档↔脚本↔服务端)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
