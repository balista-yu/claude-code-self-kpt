#!/usr/bin/env bash
# demo seed: fixtures を ~/.claude/kpt-data/.demo/ に展開する。
# 本番データ（~/.claude/kpt-data/ 配下のトップレベル）には一切触らない。
#
# 使い方:
#   ./demo/seed.sh           # 展開（既存の .demo があれば差し替え確認）
#   ./demo/seed.sh --force   # 確認なしで上書き
#   ./demo/seed.sh --clean   # .demo ディレクトリを削除して終了

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
DEMO_DIR="${KPT_DEMO_DIR:-$HOME/.claude/kpt-data/.demo}"

FORCE=0
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        --clean) CLEAN=1 ;;
        -h|--help)
            sed -n '2,9p' "${BASH_SOURCE[0]}"
            exit 0
            ;;
        *) echo "unknown option: $arg" >&2; exit 1 ;;
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
#   前週KPT (2026-W16.md) と virtual-dotclaude 内の既存ファイルは「先週以前」に設定
#   前週 Try 実装ぶん（pr-template-check.sh / CLAUDE.md）は「今週」に設定
#   → weekly-kpt skill の find -newer ロジックで done/partial/not-done が自然に分岐する
LAST_WEEK="2026-04-13 00:00"   # 前週KPT ファイルの作成日
THIS_WEEK_DONE="2026-04-21 10:00"  # 今週実装された T1 / T2

# 前週基準ファイル（find -newer の基準）
touch -d "$LAST_WEEK" "$DEMO_DIR/kpt/2026-W16.md"
touch -d "$LAST_WEEK" "$DEMO_DIR/experiments/experiment_2026-W16.md"

# virtual-dotclaude の既存ファイル（前週以前に存在していたもの）
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/hooks/kpt-activity-log.sh"
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/hooks/kpt-session-analyze.sh"
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/skills/weekly-kpt/SKILL.md"
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/skills/apply-kpt/SKILL.md"
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/skills/forward-kpt/SKILL.md"
touch -d "$LAST_WEEK" "$DEMO_DIR/virtual-dotclaude/settings.json"

# 今週実装ぶん (T1: done, T2: partial)
touch -d "$THIS_WEEK_DONE" "$DEMO_DIR/virtual-dotclaude/hooks/pr-template-check.sh"
touch -d "$THIS_WEEK_DONE" "$DEMO_DIR/virtual-dotclaude/CLAUDE.md"

# 実行権限
chmod +x "$DEMO_DIR/virtual-dotclaude/hooks/"*.sh

echo "✓ demo fixtures deployed to: $DEMO_DIR"
echo ""
echo "次のステップ:"
echo "  /weekly-kpt demo       # 今週分の KPT を生成"
echo "  /refine-kpt demo       # Try をすり合わせ"
echo "  /apply-kpt demo        # demo/out/<ts>/ に仮実装を書き出し"
