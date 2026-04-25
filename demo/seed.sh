#!/usr/bin/env bash
# =============================================================================
# demo seed: fixtures を ~/.claude/kpt-data/.demo/ に展開する
# =============================================================================
# 本番データ（~/.claude/kpt-data/ 配下のトップレベル）には一切触らない。
#
# fixtures は 2026-W16 を前週 / 2026-W17 を今週と見立てた固定タイムラインで
# 構築されている。`LAST_WEEK` / `THIS_WEEK_DONE` もその前提に紐づくため、
# fixture のシナリオ日付を変える際は本スクリプトも合わせて更新する必要がある。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
DEMO_DIR="${KPT_DEMO_DIR:-$HOME/.claude/kpt-data/.demo}"

# fixture のタイムラインに紐づく日付（2026-W16 前提）。変更時はシナリオ全体と整合を取る
LAST_WEEK="2026-04-13 00:00"
THIS_WEEK_DONE="2026-04-21 10:00"

# 前週に存在していたファイル (find -newer の基準側に置く)
LAST_WEEK_FILES=(
    "kpt/2026-W16.md"
    "experiments/experiment_2026-W16.md"
    "virtual-dotclaude/hooks/kpt-activity-log.sh"
    "virtual-dotclaude/hooks/kpt-session-analyze.sh"
    "virtual-dotclaude/skills/weekly-kpt/SKILL.md"
    "virtual-dotclaude/skills/apply-kpt/SKILL.md"
    "virtual-dotclaude/skills/forward-kpt/SKILL.md"
    "virtual-dotclaude/settings.json"
)

# 今週の Try 実装ぶん (T1: done, T2: partial として検出される)
THIS_WEEK_FILES=(
    "virtual-dotclaude/hooks/pr-template-check.sh"
    "virtual-dotclaude/CLAUDE.md"
)

FORCE=0
CLEAN=0

usage() {
    cat <<'EOF'
demo seed: fixtures を ~/.claude/kpt-data/.demo/ に展開する。
本番データには一切触らない。

使い方:
  ./demo/seed.sh           # 展開（既存の .demo があれば差し替え確認）
  ./demo/seed.sh --force   # 確認なしで上書き
  ./demo/seed.sh --clean   # .demo ディレクトリを削除して終了
EOF
}

for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --clean) CLEAN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $arg" >&2; usage >&2; exit 1 ;;
    esac
done

if [[ "$CLEAN" == "1" ]]; then
    if [[ -d "$DEMO_DIR" ]]; then
        rm -rf "$DEMO_DIR"
        echo "✓ removed: $DEMO_DIR"
    else
        echo "nothing to clean: $DEMO_DIR"
    fi
    exit 0
fi

if [[ ! -d "$FIXTURES_DIR" ]]; then
    echo "ERROR: fixtures directory not found: $FIXTURES_DIR" >&2
    exit 1
fi

if [[ -d "$DEMO_DIR" ]] && [[ "$FORCE" != "1" ]]; then
    printf "既存の %s を上書きします。続行しますか？ [y/N] " "$DEMO_DIR"
    read -r reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "aborted."; exit 0 ;;
    esac
fi

rm -rf "$DEMO_DIR"
mkdir -p "$DEMO_DIR"

# fixtures を丸ごとコピー
cp -R "$FIXTURES_DIR/." "$DEMO_DIR/"

# タイムスタンプを調整:
#   LAST_WEEK_FILES は前週基準として touch
#   THIS_WEEK_FILES は今週の実装差分として touch
# → weekly-kpt skill の find -newer ロジックで done/partial/not-done が自然に分岐する
apply_mtime() {
    local when="$1"; shift
    local rel
    for rel in "$@"; do
        local path="$DEMO_DIR/$rel"
        if [[ ! -e "$path" ]]; then
            echo "ERROR: fixture file missing: $rel" >&2
            exit 1
        fi
        touch -d "$when" "$path"
    done
}

apply_mtime "$LAST_WEEK" "${LAST_WEEK_FILES[@]}"
apply_mtime "$THIS_WEEK_DONE" "${THIS_WEEK_FILES[@]}"

# 実行権限（hooks ディレクトリ配下のシェルスクリプト）
shopt -s nullglob
for sh in "$DEMO_DIR/virtual-dotclaude/hooks/"*.sh; do
    chmod +x "$sh"
done
shopt -u nullglob

echo "✓ demo fixtures deployed to: $DEMO_DIR"
echo ""
echo "次のステップ:"
echo "  /weekly-kpt demo       # 今週分の KPT を生成"
echo "  /refine-kpt demo       # Try をすり合わせ"
echo "  /apply-kpt demo        # demo/out/<ts>/ に仮実装を書き出し"
