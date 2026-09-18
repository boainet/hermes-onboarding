#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方法论内容同步核查器 (pre-commit hook 第 3 层)
规则: methodology 里每个方法论条目标题, 方法论 skill 文件(longyi-methodology-skill.md)里必须有对应(关键词匹配)。
      skill 缺任一方法论条目 -> 拦截, 防止"改了 methodology 忘同步方法论 skill"。
用法: 与 check_version.sh 一起被 pre-commit 调用, 或独立运行。
注: 方法论从 guide 抽离为独立 skill 文件后, 校验目标从 guide 改为 longyi-methodology-skill.md。
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

METHOD = Path(REPO) / "hermes_onboarding_methodology.md"
# 方法论已抽离为独立 skill 文件, 校验其与 methodology 同步
SKILL = Path(REPO) / "longyi-methodology-skill.md"
README = Path(REPO) / "README.md"

# 方法论条目标题: "- **标题**:" 或 "- **标题**（"
# 提取方法论标题(只取长期进化章节, 排除定位/深度协作等非方法论节)
METHOD_SEC_START = "## 长期进化"
METHOD_SEC_END = "## "  # 下一个二级标题

def extract_method_titles(path):
    """从 methodology 提取方法论条目标题(长期进化章节内)"""
    text = path.read_text(encoding="utf-8")
    # 截取长期进化章节: 从"## 长期进化"到下一个同级结束标题(如"## 附注")或文件尾
    start = text.find(METHOD_SEC_START)
    if start == -1:
        return []
    # 长期进化是最后一个二级章节, 子章节用 "## ①/②..." 但都以 "## " 开头。
    # 为避免把子章节当结束符, 找"## "后跟"非数字/非①"的结束标题, 或直接到文件尾。
    tail = text[start + len(METHOD_SEC_START):]
    # 结束标题特征: "## " + 汉字(非 ① ② ③ 等编号), 且非"长期进化"自身子标题
    # 简化: 取到文件尾(长期进化是最后一个大节, 后面无其他 ## 大节)
    end = len(text)
    # 若存在"## 附注"等明确结束节, 优先用它
    for anchor in ["## 附注", "## 附录", "## FAQ"]:
        idx = text.find(anchor, start + len(METHOD_SEC_START))
        if idx != -1:
            end = idx
            break
    sec = text[start:end]
    titles = []
    for line in sec.splitlines():
        m = re.match(r"^- \*\*(.+?)\*\*", line.strip())
        if m:
            titles.append(m.group(1))
    return titles

def keyword_of(title):
    """标题转关键词: 取核心短语, 去括号注释与修饰, 保证能匹配 guide 的对应标题。
    策略: 取标题开头到第一个中文标点/顿号/冒号前的部分(如 '独立判断，不顺拐' -> '独立判断'),
         保留空格(如 'token 是钱'、'跨 session 验证' 需原样匹配, 删空格反而失配)。
         括号注释(如'（长任务拆会话时必写）')去掉。
    """
    # 去掉括号注释, 如 "任务交接清单（长任务拆会话时必写）" -> "任务交接清单"
    core = re.split(r"[（(]", title)[0]
    # 取开头到第一个中文标点/顿号/冒号前
    core = re.split(r"[，,、：:]", core)[0]
    return core

def main():
    titles = extract_method_titles(METHOD)
    if not titles:
        return 0

    guide_text = SKILL.read_text(encoding="utf-8")
    missing = []
    for t in titles:
        kw = keyword_of(t)
        if len(kw) < 3:  # 太短的标题不强制(如"复现""数据"会误报)
            continue
        if kw not in guide_text:
            missing.append(t)

    if missing:
        print("[pre-commit] ✗ methodology 与 方法论 skill 不同步, 缺:")
        for m in missing:
            print(f"    - {m}")
        print("[pre-commit] 方法论 skill 未同步 methodology 的方法论, 提交已阻止")
        print("[pre-commit] 修复: 把缺失条目同步进 longyi-methodology-skill.md")
        return 1

    print("[pre-commit] ✓ methodology ↔ 方法论 skill 内容同步")
    return 0

if __name__ == "__main__":
    sys.exit(main())
