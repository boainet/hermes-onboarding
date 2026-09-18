#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
龙翼 Hermes 配置包 - 用户端贡献方法论检测脚本模板
功能: 检测本地"待贡献方法论队列"是否有未推送条目, 输出供 monitor 唤醒 agent 执行推送。
用法:
    python3 feedback_contrib.py            # 检测是否有待贡献方法论
行为:
    - 读本地待贡献队列 (默认 ~/.hermes/feedback_pending.json, 可 --queue 指定)
    - 有 status=pending 的条目 -> 输出条目标题列表 (供 Hermes 检测到后推送)
    - 无待贡献条目 -> 空输出 (静默, 不唤醒 agent, 省 token)
此脚本只检测, 不做任何写操作 (零副作用)。推送动作由 Hermes agent 执行。
⚠️ monitor 输出必须确定性(不含时间戳/随机), 否则每 tick 都误判变化 -> 每条 pending 输出其 title 固定, 推送后清除才改变输出。
"""
import json
import os
import sys

DEFAULT_QUEUE = os.path.expanduser("~/.hermes/feedback_pending.json")


def get_pending_items(queue_path):
    """读取待贡献队列中 status=pending 的条目.
    返回 (items, broken): items 为 dict 列表, broken=True 表示队列损坏."""
    if not os.path.exists(queue_path):
        return [], False
    try:
        with open(queue_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return [], False
        return [it for it in data if isinstance(it, dict) and it.get("status") == "pending"], False
    except Exception:
        # 队列损坏: broken=True, 触发 agent 排查 (不输出空避免误判为无待贡献)
        return [], True


def main():
    queue = DEFAULT_QUEUE
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--queue" and i + 1 < len(args):
            queue = args[i + 1]

    items, broken = get_pending_items(queue)
    if broken:
        print("QUEUE_BROKEN")  # 固定哨兵, 唤醒 agent 排查损坏队列
        return 0
    if not items:
        return 0  # 空输出 -> 无待贡献, 静默

    # 有待贡献: 输出每条 title (确定性, 按加入顺序固定), 供 agent 推送
    for it in items:
        title = it.get("title") or "(无标题)"
        print(f"PENDING:{title}")
    return 0


if __name__ == "__main__":
    main()
