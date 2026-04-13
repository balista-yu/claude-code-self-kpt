#!/bin/bash
# =============================================================================
# Session End Auto-Analyzer (Global Version)
# セッション終了時にトランスクリプトを自動分析し、作業ログを生成する
# 配置先: ~/.claude/hooks/session-end-analyze.sh
# =============================================================================

# 再帰防止
if [ "$CLAUDE_SESSION_ANALYSIS" = "1" ]; then
  exit 0
fi

INPUT=$(cat)

# バックグラウンドで実行（SessionEnd hookはプロセス終了で殺されるため）
(
  TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
  SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
  CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

  # トランスクリプトが存在しない場合はスキップ
  if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
  fi

  # 10KB未満の短いセッションはスキップ
  if [ "$(uname)" = "Darwin" ]; then
    FILE_SIZE=$(stat -f%z "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
  else
    FILE_SIZE=$(stat -c%s "$TRANSCRIPT_PATH" 2>/dev/null || echo 0)
  fi
  [ "${FILE_SIZE:-0}" -lt 10240 ] && exit 0

  # プロジェクト名を抽出（cwdの末尾ディレクトリ名）
  PROJECT_NAME=$(basename "$CWD" 2>/dev/null || echo "unknown")

  # グローバル出力ディレクトリ
  LOG_DIR="$HOME/.claude/kpt-data/work-logs"
  mkdir -p "$LOG_DIR"

  TODAY=$(date +%Y-%m-%d)
  TIMESTAMP=$(date +%H%M%S)
  OUTPUT_FILE="${LOG_DIR}/${TODAY}_${TIMESTAMP}_${SESSION_ID:0:8}.md"

  # 一時ファイル
  PROMPT_FILE=$(mktemp)
  ANALYSIS_PROMPT=$(mktemp)

  # トランスクリプトからユーザーとアシスタントの発言を抽出
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

  # 分析プロンプト
  cat > "$ANALYSIS_PROMPT" << PROMPT_END
あなたはClaude Codeのセッション分析AIです。以下のセッションログを分析し、指定のフォーマットで作業ログを生成してください。

プロジェクト: ${PROJECT_NAME}
作業ディレクトリ: ${CWD}

## 出力フォーマット（Markdownで出力）

# セッション作業ログ

## メタ情報
- プロジェクト: ${PROJECT_NAME}
- 日時: ${TODAY} ${TIMESTAMP}

## 概要
（1-2文でこのセッションで行った作業を要約）

## 実施内容
- （具体的に何をしたか箇条書き）

## アプローチ・判断
- （どのような設計判断やアプローチを取ったか）

## ユーザー指摘事項
- （ユーザーが修正を求めた箇所、やり直しを指示した箇所）
- （指摘がなければ「特になし」）

## 詰まった点・課題
- （エラーが出た、何度もやり直した箇所）
- （なければ「特になし」）

## 改善提案
### 提案1: （タイトル）
- 種別: hook / skill / CLAUDE.mdルール / ワークフロー
- 概要: （何をどう改善するか）
- 期待効果: （これにより何が良くなるか）

重要な注意点:
- ユーザー指摘事項は特に正確に記録すること（KPTのProblemの材料になる）
- 改善提案は「CLAUDE.mdにルール追加」だけでなく、hook化やスキル化も積極的に提案すること
- 簡潔に、しかし振り返りに必要な情報は漏らさず記録すること

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
