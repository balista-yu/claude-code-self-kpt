#!/bin/bash
# =============================================================================
# Stop Hook: 軽量アクティビティログ
# Claudeが応答するたびに1行JSONLで記録する
# 月次ローテーションでログ肥大化を防止
# 配置先: ~/.claude/hooks/kpt-activity-log.sh
# =============================================================================

# 再帰防止
if [ "$CLAUDE_SESSION_ANALYSIS" = "1" ]; then
  exit 0
fi

INPUT=$(cat)

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
CWD=$(echo "$INPUT" | jq -r '.cwd // "unknown"')
# アシスタントの応答を500文字に切り詰め
ASSISTANT_MSG=$(echo "$INPUT" | jq -r '.last_assistant_message // ""' | head -c 500)

# stop_hook_active なら無限ループ防止
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // "false"')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

# ログディレクトリ
LOG_DIR="$HOME/.claude/kpt-data/activity-logs"
mkdir -p "$LOG_DIR"

# 月次ローテーション
YEAR_MONTH=$(date +"%Y-%m")
LOG_FILE="${LOG_DIR}/activity_${YEAR_MONTH}.jsonl"

# 1行JSONL追記
jq -n \
  --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  --arg date "$(date +"%Y-%m-%d")" \
  --arg time "$(date +"%H:%M:%S")" \
  --arg sid "$SESSION_ID" \
  --arg cwd "$CWD" \
  --arg project "$(basename "$CWD")" \
  --arg msg "$ASSISTANT_MSG" \
  '{timestamp: $ts, local_date: $date, local_time: $time, session_id: $sid, cwd: $cwd, project: $project, message: $msg}' \
  >> "$LOG_FILE"

exit 0
