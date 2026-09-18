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
        # 大条目内嵌子句: 段落中 "**子标题**：" 且前面是句子边界(。；！？或行首)
        # 如 "④-1 执行机制自动化" 内的 "**自监控告警**：..." —— 这些是方法论子句,
        # 抽离为 skill 独立条目时必须有对应, 否则会像"自监控告警"一样漏检。
        for sm in re.finditer(r"(?:^|[。；！？])\s*\*\*([^*]{2,40}?)\*\*[：:]", line):
            sub = sm.group(1).strip()
            if sub and not sub.startswith("④") and not sub.startswith("①") and not sub.startswith("②") and not sub.startswith("③"):
                titles.append(sub)
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

# 高频虚词/连接词: 标题措辞变体(如 methodology 说"高频 tick"、skill 说"的调度要用高频 tick")
# 时, 机械子串匹配会误报。归一化去掉这些词后再比, 容忍措辞差异、仍能抓真缺。
STOPWORDS = ["的", "了", "要", "该", "和", "与", "看", "别", "应", "须", "都", "得", "才", "也",
             "能", "会", "可", "就", "给", "把", "被", "于", "之", "其", "此", "且", "并"]

def normalized(s):
    """去虚词归一化(仅对 >=4 字的稳定片段, 避免过度删导致误匹配)"""
    return re.sub(r"[%s]" % "".join(STOPWORDS), "", s)

def matches(title, guide_text):
    """判断 methodology 标题是否在 skill 文本中有对应: 先精确子串, 再归一化子串(容忍措辞变体)。
    归一化要求标题去虚词后剩余 >=4 字(太短不归一, 防误报)。"""
    kw = keyword_of(title)
    if len(kw) < 3:
        return True  # 太短不强制
    if kw in guide_text:
        return True
    nk = normalized(kw)
    ng = normalized(guide_text)
    if len(nk) >= 4 and nk in ng:
        return True
    # 已知措辞变体白名单: methodology 子句标题 -> skill 里真实存在的对应关键词。
    # 用于 methodology 是大条目内嵌子句、skill 是独立详细条目且措辞略异的情况
    # (如 methodology"分层判据" ↔ skill"分层存的判据")。机械匹配难覆盖的变体在这登记。
    ALIASES = {
        "分层判据": "分层存的判据",
        "monitor 类 job 高频 tick": "高频 tick",
        "判断\"变更要不要提炼\"看条目抽象层级不看技能出处": "抽象层级",
    }
    if title in ALIASES and ALIASES[title] in guide_text:
        return True
    return False

def main():
    titles = extract_method_titles(METHOD)
    if not titles:
        return 0

    guide_text = SKILL.read_text(encoding="utf-8")
    missing = []
    for t in titles:
        if not matches(t, guide_text):
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
