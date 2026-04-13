#!/bin/bash
# =============================================================================
# Claude Code Self-Improvement KPT System — Installer
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"

echo "=== Claude Code Self-Improvement KPT ==="
echo ""

# 1. ディレクトリ
echo "[1/6] Creating directories..."
mkdir -p "$CLAUDE_DIR/hooks"
mkdir -p "$CLAUDE_DIR/skills/weekly-kpt"
mkdir -p "$CLAUDE_DIR/skills/apply-kpt"
mkdir -p "$CLAUDE_DIR/scripts"
mkdir -p "$CLAUDE_DIR/kpt-data/activity-logs"
mkdir -p "$CLAUDE_DIR/kpt-data/session-reviews"
mkdir -p "$CLAUDE_DIR/kpt-data/kpt"

# 2. Hooks
echo "[2/6] Installing hooks..."
cp "$SCRIPT_DIR/.claude/hooks/kpt-activity-log.sh" "$CLAUDE_DIR/hooks/"
cp "$SCRIPT_DIR/.claude/hooks/kpt-session-analyze.sh" "$CLAUDE_DIR/hooks/"
chmod +x "$CLAUDE_DIR/hooks/kpt-activity-log.sh"
chmod +x "$CLAUDE_DIR/hooks/kpt-session-analyze.sh"

# 3. Skills
echo "[3/6] Installing skills..."
cp "$SCRIPT_DIR/.claude/skills/weekly-kpt/SKILL.md" "$CLAUDE_DIR/skills/weekly-kpt/"
cp "$SCRIPT_DIR/.claude/skills/apply-kpt/SKILL.md" "$CLAUDE_DIR/skills/apply-kpt/"

# 4. Dashboard
echo "[4/6] Installing dashboard..."
cp "$SCRIPT_DIR/.claude/scripts/kpt-viewer.py" "$CLAUDE_DIR/scripts/"

# 5. settings.json
echo "[5/6] Updating settings.json..."
SETTINGS="$CLAUDE_DIR/settings.json"

if [ -f "$SETTINGS" ]; then
  if command -v jq &> /dev/null; then
    TEMP=$(mktemp)
    # Stop hook追加
    if ! jq -e '.hooks.Stop' "$SETTINGS" > /dev/null 2>&1; then
      jq '.hooks.Stop = [{"matcher":"","hooks":[{"type":"command","command":"bash $HOME/.claude/hooks/kpt-activity-log.sh"}]}]' "$SETTINGS" > "$TEMP" && mv "$TEMP" "$SETTINGS"
      echo "  + Added Stop hook"
    else
      echo "  Stop hook already exists, skipping"
    fi
    # SessionEnd hook追加
    TEMP=$(mktemp)
    if ! jq -e '.hooks.SessionEnd' "$SETTINGS" > /dev/null 2>&1; then
      jq '.hooks.SessionEnd = [{"hooks":[{"type":"command","command":"bash $HOME/.claude/hooks/kpt-session-analyze.sh","timeout":10}]}]' "$SETTINGS" > "$TEMP" && mv "$TEMP" "$SETTINGS"
      echo "  + Added SessionEnd hook"
    else
      echo "  SessionEnd hook already exists, skipping"
    fi
  else
    echo "  WARNING: jq not found. Please merge settings.json manually."
    echo "  See: $SCRIPT_DIR/.claude/settings.json"
  fi
else
  cp "$SCRIPT_DIR/.claude/settings.json" "$SETTINGS"
  echo "  Created new settings.json"
fi

# 6. CLAUDE.md
echo "[6/6] Updating CLAUDE.md..."
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ]; then
  if grep -q "自己改善システム" "$CLAUDE_MD" 2>/dev/null; then
    echo "  Already configured, skipping"
  else
    echo "" >> "$CLAUDE_MD"
    cat "$SCRIPT_DIR/CLAUDE.md.append" >> "$CLAUDE_MD"
    echo "  Appended self-improvement rules"
  fi
else
  cp "$SCRIPT_DIR/CLAUDE.md.append" "$CLAUDE_MD"
  echo "  Created CLAUDE.md"
fi

echo ""
echo "=== Done ==="
echo ""
echo "What happens now:"
echo "  1. Every Claude response → activity logged (Stop hook)"
echo "  2. Every session end → self-analysis generated (SessionEnd hook)"
echo "  3. Weekly: run /weekly-kpt in Claude Code"
echo "  4. Then: run /apply-kpt to auto-implement improvements"
echo "  5. Dashboard: python3 ~/.claude/scripts/kpt-viewer.py"
echo ""

# Dependency check
echo "Dependencies:"
if command -v jq &> /dev/null; then echo "  jq: OK"; else echo "  jq: MISSING (brew install jq / apt install jq)"; fi
if command -v claude &> /dev/null; then echo "  claude: OK"; else echo "  claude: MISSING"; fi
echo ""
