#!/bin/bash
# =============================================================================
# Claude Code Self-Improvement KPT System — Uninstaller
# =============================================================================
# 既存設定を壊さず、本システムで追加した hook / skill / スクリプト / CLAUDE.md
# ブロックのみを除去する。データディレクトリはデフォルト保持。
#
# Usage:
#   ./uninstall.sh                 # 設定とファイルを削除、kpt-data は残す
#   ./uninstall.sh --purge-data    # データも含めて全削除
# =============================================================================

set -euo pipefail

CLAUDE_DIR="$HOME/.claude"
PURGE_DATA=0

for arg in "$@"; do
  case "$arg" in
    --purge-data) PURGE_DATA=1 ;;
    -h|--help)
      grep -E '^# ( |$)' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--purge-data]" >&2
      exit 1
      ;;
  esac
done

echo "=== Claude Code Self-Improvement KPT — Uninstaller ==="
echo ""

# 0. バックアップ
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$CLAUDE_DIR/backup-$TIMESTAMP"
echo "[0/6] Creating backup at $BACKUP_DIR ..."
mkdir -p "$BACKUP_DIR"
[ -f "$CLAUDE_DIR/settings.json" ] && cp "$CLAUDE_DIR/settings.json" "$BACKUP_DIR/settings.json"
[ -f "$CLAUDE_DIR/CLAUDE.md" ] && cp "$CLAUDE_DIR/CLAUDE.md" "$BACKUP_DIR/CLAUDE.md"

# 1. settings.json から KPT 関連 hook エントリのみ除去
echo "[1/6] Cleaning settings.json ..."
SETTINGS="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS" ] && command -v jq &> /dev/null; then
  TEMP=$(mktemp)
  jq '
    def strip_kpt:
      map(
        .hooks |= (map(select((.command // "") | test("kpt-.*\\.sh") | not)))
      )
      | map(select((.hooks // []) | length > 0));

    if .hooks.Stop       then .hooks.Stop       |= strip_kpt else . end
    | if .hooks.SessionEnd then .hooks.SessionEnd |= strip_kpt else . end
    | if (.hooks.Stop // [])       | length == 0 then del(.hooks.Stop)       else . end
    | if (.hooks.SessionEnd // []) | length == 0 then del(.hooks.SessionEnd) else . end
    | if (.hooks // {}) == {} then del(.hooks) else . end
  ' "$SETTINGS" > "$TEMP" && mv "$TEMP" "$SETTINGS"
  echo "  - Removed KPT hook entries (Stop / SessionEnd)"
elif [ -f "$SETTINGS" ]; then
  echo "  WARNING: jq not found. Please remove KPT hook entries manually from $SETTINGS"
fi

# 2. Hooks
echo "[2/6] Removing hooks ..."
rm -f "$CLAUDE_DIR/hooks/kpt-activity-log.sh"
rm -f "$CLAUDE_DIR/hooks/kpt-session-analyze.sh"
rm -f "$CLAUDE_DIR/hooks/kpt-redact.sh"

# 3. Skills
echo "[3/6] Removing skills ..."
rm -rf "$CLAUDE_DIR/skills/weekly-kpt"
rm -rf "$CLAUDE_DIR/skills/apply-kpt"
rm -rf "$CLAUDE_DIR/skills/forward-kpt"
rm -rf "$CLAUDE_DIR/skills/refine-kpt"

# 4. Dashboard script
echo "[4/6] Removing dashboard script ..."
rm -f "$CLAUDE_DIR/scripts/kpt-viewer.py"
rm -rf "$CLAUDE_DIR/scripts/__pycache__" 2>/dev/null || true

# 5. CLAUDE.md から自己改善ブロック除去
echo "[5/6] Cleaning CLAUDE.md ..."
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ] && grep -q '^# Claude Code 自己改善システム$' "$CLAUDE_MD"; then
  TEMP=$(mktemp)
  # `# Claude Code 自己改善システム` から次の H1 手前まで（見つからなければ EOF まで）を削除。
  # 末尾に残る連続空行は pending にバッファし、次に非空行が来た時だけ吐き出すことで除去する。
  awk '
    /^# Claude Code 自己改善システム$/ { in_block=1; next }
    in_block && /^# / && !/^# Claude Code 自己改善システム$/ { in_block=0 }
    !in_block {
      if ($0 == "") { pending=pending "\n" }
      else { printf "%s", pending; pending=""; print }
    }
  ' "$CLAUDE_MD" > "$TEMP"
  mv "$TEMP" "$CLAUDE_MD"
  echo "  - Removed self-improvement block"
  if [ ! -s "$CLAUDE_MD" ]; then
    rm -f "$CLAUDE_MD"
    echo "  - Removed empty CLAUDE.md"
  fi
else
  echo "  - No KPT block found, skipping"
fi

# 6. データ
echo "[6/6] Data directory ..."
if [ "$PURGE_DATA" = "1" ]; then
  rm -rf "$CLAUDE_DIR/kpt-data"
  echo "  - Purged $CLAUDE_DIR/kpt-data (--purge-data)"
else
  if [ -d "$CLAUDE_DIR/kpt-data" ]; then
    echo "  - Preserved $CLAUDE_DIR/kpt-data (use --purge-data to delete)"
  fi
fi

echo ""
echo "=== Done ==="
echo ""
echo "Backup: $BACKUP_DIR"
echo "  - settings.json / CLAUDE.md の変更前スナップショット"
echo ""
if [ "$PURGE_DATA" != "1" ]; then
  echo "Data retained: $CLAUDE_DIR/kpt-data"
  echo "  - 完全削除したい場合: ./uninstall.sh --purge-data"
  echo ""
fi
