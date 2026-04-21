#!/bin/bash
# =============================================================================
# Secret Redaction Filter (stdin → stdout)
# 配置先: ~/.claude/hooks/kpt-redact.sh
#
# ディスク書き込みおよび Anthropic API 送信の前段で、既知の機密パターン
# を [REDACTED_*] トークンに置換する。防御の第一層であり、完全な検出を
# 保証するものではない（ディスク暗号化等の併用を推奨）。
# =============================================================================

set -euo pipefail

# 1. PRIVATE KEY ブロック（複数行）を単一行マーカーに潰す
# 2. その後、単一行パターンを順次置換する（sed -E / POSIX ERE）
sed -E '
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,/-----END [A-Z ]*PRIVATE KEY-----/{
    /-----BEGIN [A-Z ]*PRIVATE KEY-----/c\
[REDACTED_PRIVATE_KEY]
    d
  }
' | sed -E \
    -e 's/sk-ant-[A-Za-z0-9_-]{20,}/[REDACTED_ANTHROPIC_KEY]/g' \
    -e 's/sk-proj-[A-Za-z0-9_-]{20,}/[REDACTED_OPENAI_KEY]/g' \
    -e 's/github_pat_[A-Za-z0-9_]{50,}/[REDACTED_GITHUB_TOKEN]/g' \
    -e 's/gh[pousr]_[A-Za-z0-9]{36,}/[REDACTED_GITHUB_TOKEN]/g' \
    -e 's/(AKIA|ASIA)[0-9A-Z]{16}/[REDACTED_AWS_ACCESS_KEY]/g' \
    -e 's/AIza[0-9A-Za-z_-]{35,}/[REDACTED_GOOGLE_API_KEY]/g' \
    -e 's/(sk|pk|rk)_(live|test)_[0-9a-zA-Z]{24,}/[REDACTED_STRIPE_KEY]/g' \
    -e 's/eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/[REDACTED_JWT]/g' \
    -e 's/xox[baprs]-[A-Za-z0-9-]{10,200}/[REDACTED_SLACK_TOKEN]/g' \
    -e 's/(password|secret|api[-_]?key|token)[[:space:]]*[:=][[:space:]]*"[^"]{8,}"/\1=[REDACTED]/gI' \
  | sed -E "s/(password|secret|api[-_]?key|token)[[:space:]]*[:=][[:space:]]*'[^']{8,}'/\1=[REDACTED]/gI"
