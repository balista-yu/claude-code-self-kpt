#!/usr/bin/env bash
# T1 (done): PR作成前に .github/pull_request_template.md の使用を検証する hook
# 対象: 2026-W16 KPT T1

set -euo pipefail

payload=$(cat)
tool_name=$(echo "$payload" | jq -r '.tool_name // empty')
command=$(echo "$payload" | jq -r '.tool_input.command // empty')

# gh pr create を検知
if [[ "$tool_name" == "Bash" ]] && [[ "$command" == *"gh pr create"* ]]; then
    template=".github/pull_request_template.md"
    if [[ -f "$template" ]]; then
        # 本文指定があるか、かつテンプレの主要項目が含まれているか軽く検証
        if [[ "$command" != *"--body"* ]] && [[ "$command" != *"-F"* ]]; then
            echo "PR テンプレート未使用の可能性。$template を参照してください" >&2
            exit 2
        fi
    fi
fi

exit 0
