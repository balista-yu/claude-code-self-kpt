#!/bin/bash
# =============================================================================
# kpt-redact.sh のフィクスチャテスト
# Usage: bash test/test-redact.sh
#
# 注意: フィクスチャのトークンリテラルは GitHub Push Protection に検出される
# ため、プレフィックスと本体を分割連結して擬似生成する。
# =============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REDACT="$SCRIPT_DIR/.claude/hooks/kpt-redact.sh"
PASS=0
FAIL=0

# トークンフィクスチャ生成ヘルパー（プレフィックスと本体を分割してリテラル検出を回避）
mk() { printf '%s%s' "$1" "$2"; }

check() {
  local name="$1" input="$2" expected="$3"
  local got
  got=$(printf '%s' "$input" | bash "$REDACT") || {
    echo "FAIL: $name (redact exited non-zero)"
    FAIL=$((FAIL+1))
    return
  }
  if [ "$got" = "$expected" ]; then
    echo "PASS: $name"
    PASS=$((PASS+1))
  else
    echo "FAIL: $name"
    echo "  input:    $input"
    echo "  expected: $expected"
    echo "  got:      $got"
    FAIL=$((FAIL+1))
  fi
}

echo "=== kpt-redact.sh tests ==="

# --- 既知トークンパターン ---
check "Anthropic key"            "$(mk 'sk-ant-' 'api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123')" "[REDACTED_ANTHROPIC_KEY]"
check "OpenAI project key"       "$(mk 'sk-proj-' 'abcdefghijklmnopqrstuvwxyz0123')"      "[REDACTED_OPENAI_KEY]"
check "GitHub classic (ghp_)"    "$(mk 'ghp_' 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ZXYW')" "[REDACTED_GITHUB_TOKEN]"
check "GitHub OAuth (gho_)"      "$(mk 'gho_' 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ZXYW')" "[REDACTED_GITHUB_TOKEN]"
check "GitHub user-server (ghu_)" "$(mk 'ghu_' 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ZXYW')" "[REDACTED_GITHUB_TOKEN]"
check "GitHub server-server (ghs_)" "$(mk 'ghs_' 'AbCdEfGhIjKlMnOpQrStUvWxYz0123456789ZXYW')" "[REDACTED_GITHUB_TOKEN]"
check "GitHub fine-grained PAT"  "$(mk 'github_pat_' '11ABCDEFG0abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJ_ab')" "[REDACTED_GITHUB_TOKEN]"
check "AWS access key"           "$(mk 'AKIA' 'IOSFODNN7EXAMPLE')"                        "[REDACTED_AWS_ACCESS_KEY]"
check "AWS STS temp key"         "$(mk 'ASIA' 'IOSFODNN7EXAMPLE')"                        "[REDACTED_AWS_ACCESS_KEY]"
check "Google API key"           "$(mk 'AIza' 'SyA-abcdefghijklmnopqrstuvwxyz0123456')"   "[REDACTED_GOOGLE_API_KEY]"
check "Stripe live secret"       "$(mk 'sk_live_' 'abcdefghijklmnopqrstuvwx')"            "[REDACTED_STRIPE_KEY]"
check "Stripe test publishable"  "$(mk 'pk_test_' 'abcdefghijklmnopqrstuvwx')"            "[REDACTED_STRIPE_KEY]"
check "JWT"                      "$(mk 'eyJ' 'hbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abc')" "[REDACTED_JWT]"
check "Slack bot token"          "$(mk 'xoxb-' '1234567890-aBcDeFgHiJkL')"                "[REDACTED_SLACK_TOKEN]"
check "Slack user token"         "$(mk 'xoxp-' '1234567890-aBcDeFgHiJkLmNoPqR')"          "[REDACTED_SLACK_TOKEN]"

# --- 代入（大小混在 / クォート別） ---
check "password double-quoted"   'password="supersecretvalue"'                  'password=[REDACTED]'
check "API_KEY uppercase"        'API_KEY="verylongsecret12345"'                'API_KEY=[REDACTED]'
check "Password colon"           'Password: "supersecrethere"'                  'Password=[REDACTED]'
check "token single-quoted"      "TOKEN='anothersecretlongone'"                 "TOKEN=[REDACTED]"
check "api-key mixed case"       'Api-Key="abcdefghijklmnop"'                   'Api-Key=[REDACTED]'

# --- 複数行 PRIVATE KEY ---
multi_in=$'-----BEGIN RSA PRIVATE KEY-----\nxxxxxxx\nyyyyyyy\n-----END RSA PRIVATE KEY-----'
check "PRIVATE KEY block"        "$multi_in" "[REDACTED_PRIVATE_KEY]"

ec_in=$'-----BEGIN EC PRIVATE KEY-----\naaaa\n-----END EC PRIVATE KEY-----'
check "EC PRIVATE KEY block"     "$ec_in" "[REDACTED_PRIVATE_KEY]"

# --- Slack greedy 回避: 後続の非トークン text は残る ---
check "Slack token not greedy"   "$(mk 'xoxb-' '1234567890-aBcDeFgHiJkL') and more text" "[REDACTED_SLACK_TOKEN] and more text"

# --- インライン混在 ---
check "Anthropic inline in prose" "use the token $(mk 'sk-ant-' 'api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ01234567') here" \
                                  "use the token [REDACTED_ANTHROPIC_KEY] here"

# --- 正常テキストは保持 ---
check "plain text untouched"     "this is normal text with nothing to redact"   "this is normal text with nothing to redact"
check "short password kept"      'pwd="abc"'                                    'pwd="abc"'
check "random base64-like kept"  "randomBase64StringNotAJWTOrKey"               "randomBase64StringNotAJWTOrKey"

echo ""
echo "=== Result: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ]
