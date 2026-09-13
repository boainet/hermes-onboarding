#!/usr/bin/env bash
# 版本号一致性 + 内容变更必升版本校验 (pre-commit hook)
# 规则:
#   1. README / guide 两处版本号必须一致 (版本号只在展示+机制处, 不在给人看的methodology和脚本)
#   2. 若 guide 的内容较上一次 commit 有变更, 但版本号未变 -> 拦截
# 用法: 复制到 .git/hooks/pre-commit (本地生效)

set -u

REPO="$(git rev-parse --show-toplevel)"
FILES=("README.md" "hermes_onboarding_guide.md")

fail=0

# 1. README / guide 版本号一致性
declare -A VER
for f in "${FILES[@]}"; do
  p="$REPO/$f"
  if [ ! -f "$p" ]; then
    echo "[pre-commit] 缺失: $f"
    fail=1
    continue
  fi
  # 提取版本号 (兼容 badge 链接 与 版本: 两种格式, 取最新/最大版本号 — README 可能含历史版本 changelog)
  # 用 sort -V (GNU 版本号排序) 取最大。不能用 sort -t. -k1 -k2 -n: 版本号含字母v, -n 数字排序把 v 当0 会拿错号(曾升 v4 取到 v3.9)
  ver=$(grep -oE 'v[0-9]+\.[0-9]+' "$p" | sort -V | tail -1)
  VER["$f"]="$ver"
  echo "[pre-commit] $f -> $ver"
done

base=""
for f in "${FILES[@]}"; do
  v="${VER[$f]:-}"
  if [ -z "$v" ]; then
    echo "[pre-commit] ✗ $f 无版本号"
    fail=1
    continue
  fi
  if [ -z "$base" ]; then
    base="$v"
  elif [ "$v" != "$base" ]; then
    echo "[pre-commit] ✗ 版本不一致: $f = $v, 应为 $base"
    fail=1
  fi
done

# 2. 内容变更必升版本 (guide 是机制核心, 改动必须升版本; methodology/脚本无版本号不校验)
for f in hermes_onboarding_guide.md; do
  old_ver=$(git show "HEAD:$f" 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+' | sort -V | tail -1 || echo "")
  new_ver="${VER[$f]:-}"
  changed=$(git diff --name-only HEAD 2>/dev/null | grep -qx "$f" && echo yes || echo no)
  if [ "$changed" = "yes" ] && [ -n "$old_ver" ] && [ "$new_ver" = "$old_ver" ]; then
    echo "[pre-commit] ✗ $f 内容变更但版本号未升 ($old_ver -> $new_ver), 请先升版本号"
    fail=1
  fi
done

# 3. 方法论内容同步核查 (methodology 每个方法论条目标题, guide 必须有对应)
if [ "$fail" -eq 0 ] && [ -x "$REPO/scripts/check_sync.py" ]; then
  python3 "$REPO/scripts/check_sync.py" || fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo "[pre-commit] ✗ 版本校验未通过, 提交已阻止"
  exit 1
fi
echo "[pre-commit] ✓ 版本校验通过"
exit 0
