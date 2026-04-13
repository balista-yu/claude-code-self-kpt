#!/bin/bash
# =============================================================================
# Claude Code KPT System Installer
# ~/.claude/ にKPT自己改善システムをインストールする
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "=== Claude Code KPT System Installer ==="
echo ""

# 1. ディレクトリ作成
echo "[1/6] Creating directories..."
mkdir -p "$CLAUDE_DIR/hooks"
mkdir -p "$CLAUDE_DIR/skills/weekly-kpt"
mkdir -p "$CLAUDE_DIR/skills/apply-kpt"
mkdir -p "$CLAUDE_DIR/scripts"
mkdir -p "$CLAUDE_DIR/kpt-data/work-logs"
mkdir -p "$CLAUDE_DIR/kpt-data/kpt"

# 2. hookスクリプト配置
echo "[2/6] Installing SessionEnd hook..."
cp "$SCRIPT_DIR/.claude/hooks/session-end-analyze.sh" "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/session-end-analyze.sh"

# 3. スキル配置
echo "[3/6] Installing skills..."
cp "$SCRIPT_DIR/.claude/skills/weekly-kpt/SKILL.md" "$CLAUDE_DIR/skills/weekly-kpt/"
cp "$SCRIPT_DIR/.claude/skills/apply-kpt/SKILL.md" "$CLAUDE_DIR/skills/apply-kpt/"

# 4. ビューア配置
echo "[4/6] Installing dashboard viewer..."
cp "$SCRIPT_DIR/.claude/scripts/kpt-viewer.py" "$CLAUDE_DIR/scripts/"

# 5. settings.json マージ
echo "[5/6] Updating settings.json..."
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

if [ -f "$SETTINGS_FILE" ]; then
  # 既存のsettings.jsonがある場合
  if command -v jq &> /dev/null; then
    # jqがあればマージ
    if jq -e '.hooks.SessionEnd' "$SETTINGS_FILE" > /dev/null 2>&1; then
      echo "  SessionEnd hook already exists in settings.json. Skipping merge."
      echo "  Please manually add the hook if needed."
    else
      # SessionEnd hookを追加
      TEMP=$(mktemp)
      jq '.hooks.SessionEnd = [{"hooks": [{"type": "command", "command": "bash $HOME/.claude/hooks/session-end-analyze.sh", "timeout": 10}]}]' \
        "$SETTINGS_FILE" > "$TEMP" && mv "$TEMP" "$SETTINGS_FILE"
      echo "  Merged SessionEnd hook into existing settings.json"
    fi
  else
    echo "  WARNING: jq not found. Cannot merge settings.json automatically."
    echo "  Please manually add the following to $SETTINGS_FILE:"
    echo '  "SessionEnd": [{"hooks": [{"type": "command", "command": "bash $HOME/.claude/hooks/session-end-analyze.sh", "timeout": 10}]}]'
  fi
else
  # 新規作成
  cp "$SCRIPT_DIR/.claude/settings.json" "$SETTINGS_FILE"
  echo "  Created new settings.json"
fi

# 6. CLAUDE.md 追記
echo "[6/6] Updating CLAUDE.md..."
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"

if [ -f "$CLAUDE_MD" ]; then
  if grep -q "KPT自己改善システム" "$CLAUDE_MD" 2>/dev/null; then
    echo "  KPT section already exists in CLAUDE.md. Skipping."
  else
    echo "" >> "$CLAUDE_MD"
    cat "$SCRIPT_DIR/CLAUDE.md.append" >> "$CLAUDE_MD"
    echo "  Appended KPT rules to existing CLAUDE.md"
  fi
else
  cp "$SCRIPT_DIR/CLAUDE.md.append" "$CLAUDE_MD"
  echo "  Created new CLAUDE.md"
fi

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Installed to: $CLAUDE_DIR/"
echo ""
echo "Files:"
echo "  $CLAUDE_DIR/hooks/session-end-analyze.sh   (SessionEnd hook)"
echo "  $CLAUDE_DIR/skills/weekly-kpt/SKILL.md      (/weekly-kpt command)"
echo "  $CLAUDE_DIR/skills/apply-kpt/SKILL.md       (/apply-kpt command)"
echo "  $CLAUDE_DIR/scripts/kpt-viewer.py            (Dashboard viewer)"
echo "  $CLAUDE_DIR/kpt-data/                        (Data directory)"
echo ""
echo "Usage:"
echo "  - Sessions are auto-analyzed on exit (no action needed)"
echo "  - Run /weekly-kpt in Claude Code for weekly KPT review"
echo "  - Run /apply-kpt to apply Try items"
echo "  - Run: python3 ~/.claude/scripts/kpt-viewer.py  for dashboard"
echo ""
echo "Dependency check:"
if command -v jq &> /dev/null; then
  echo "  jq: OK"
else
  echo "  jq: NOT FOUND (required for hook). Install: brew install jq / apt install jq"
fi
if command -v claude &> /dev/null; then
  echo "  claude: OK"
else
  echo "  claude: NOT FOUND (required for hook analysis)"
fi
