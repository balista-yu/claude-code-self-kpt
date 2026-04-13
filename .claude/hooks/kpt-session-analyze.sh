#!/bin/bash
# =============================================================================
# SessionEnd Hook: ユーザー指摘分析
# セッション終了時にトランスクリプトを分析し、
# Claude Code自身が「何を間違えたか」「何を指摘されたか」を記録する
# 配置先: ~/.claude/hooks/kpt-session-analyze.sh
# =============================================================================

# 再帰防止
if [ "$CLAUDE_SESSION_ANALYSIS" = "1" ]; then
  exit 0
fi

INPUT=$(cat)

# バックグラウンド実行（SessionEndはプロセス終了で殺されるため）
(
  TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
  SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
  CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

  if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
  fi

  # 10KB未満はスキップ
  if [ "$(uname)" = "Darwin" ]; then
    FILE_SIZE=$(stat -f%z "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
  else
    FILE_SIZE=$(stat -c%s "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
  fi
  [ "${FILE_SIZE:-0}" -lt 10240 ] && exit 0

  PROJECT_NAME=$(basename "$CWD" 2>/dev/null || echo "unknown")

  # 月次ローテーション
  YEAR_MONTH=$(date +"%Y-%m")
  LOG_DIR="$HOME/.claude/kpt-data/session-reviews"
  mkdir -p "$LOG_DIR"

  TODAY=$(date +%Y-%m-%d)
  TIMESTAMP=$(date +%H%M%S)
  OUTPUT_FILE="${LOG_DIR}/${YEAR_MONTH}/${TODAY}_${TIMESTAMP}_${SESSION_ID:0:8}.md"
  mkdir -p "$(dirname "$OUTPUT_FILE")"

  # トランスクリプトから発言を抽出
  PROMPT_FILE=$(mktemp)
  ANALYSIS_PROMPT=$(mktemp)

  jq -r '
    select(.type == "user" or .type == "assistant") |
    if .type == "user" then
      "## USER:\n" + (
        if (.message | type) == "string" then .message
        elif (.message | type) == "array" then
          [.message[] | select(.type == "text") | .text] | join("\n")
        elif (.message.content | type) == "string" then .message.content
        elif (.message.content | type) == "array" then
          [.message.content[] | select(.type == "text") | .text] | join("\n")
        else "(non-text content)"
        end
      )
    else
      "## ASSISTANT:\n" + (
        if (.message.content | type) == "string" then
          .message.content[:500]
        elif (.message.content | type) == "array" then
          [.message.content[] | select(.type == "text") | .text[:500]] | join("\n")
        else "(tool use)"
        end
      )
    end
  ' "$TRANSCRIPT_PATH" 2>/dev/null > "$PROMPT_FILE"

  cat > "$ANALYSIS_PROMPT" << PROMPT_END
あなたはClaude Codeの自己分析AIです。
以下はClaude Codeのセッションログです。**Claude Code自身の視点**で振り返り、自分が何を間違えたか、何を改善すべきかを分析してください。

プロジェクト: ${PROJECT_NAME}

## 出力フォーマット（Markdownで出力、余計な前置き不要）

# 自己分析: ${PROJECT_NAME} (${TODAY})

## 概要
（1-2文で何をしたか）

## 自己評価
- 指摘なしで完了したタスク数: X
- ユーザーから修正指示を受けたタスク数: X

## ユーザー指摘事項（自分が間違えた・不十分だったこと）
各指摘を以下の形式で記録:
- **[カテゴリ]** 指摘内容
  - 自分がやったこと: （何をしたか）
  - ユーザーの修正指示: （何を言われたか）
  - 根本原因: （なぜ間違えたか）

カテゴリ例: コード品質 / 仕様理解 / テスト / コミット / PR / 命名規則 / アーキテクチャ / スコープ逸脱 / 指示の読み落とし

指摘がなければ「指摘なし — このセッションはスムーズに完了」と記載。

## 自己改善アクション
- **[hook化推奨]** （hookで防げるミス）
- **[skill化推奨]** （パターン化できる成功体験）
- **[CLAUDE.mdルール]** （本当にルールで防げるもののみ）

注意:
- 主語は「自分（Claude Code）」。「ユーザーがXXした」ではなく「自分がXXを間違えた」と書く
- CLAUDE.mdルール追加は最終手段。hook化・skill化を優先して提案すること
- 指摘がなかったセッションでも、うまくいった理由を分析すること

以下がセッションログです:
PROMPT_END

  cat "$ANALYSIS_PROMPT" "$PROMPT_FILE" > "${PROMPT_FILE}.combined"

  export CLAUDE_SESSION_ANALYSIS=1
  claude -p --model haiku --no-session-persistence \
    < "${PROMPT_FILE}.combined" > "$OUTPUT_FILE" 2>/dev/null

  rm -f "$PROMPT_FILE" "$ANALYSIS_PROMPT" "${PROMPT_FILE}.combined"

) </dev/null &>/dev/null &
disown

exit 0
