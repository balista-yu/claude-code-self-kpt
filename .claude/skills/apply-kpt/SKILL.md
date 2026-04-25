---
name: apply-kpt
description: 最新のKPT結果のTry項目を実際にhook/skill/CLAUDE.mdに実装する。Claude Codeの自己改善を実行するコマンド。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Write, Edit, AskUserQuestion
---

# KPT Try項目の自動実装

最新のKPT結果のTry項目を **実際にコードとして実装** します。
これがこのシステムの核心です。振り返るだけでなく、自分自身を改善します。

## 引数

- `demo` — demo モード。読み先を `~/.claude/kpt-data/.demo/` に切り替え、実装も **`./demo/out/<timestamp>/` に書き出すだけ**（実ファイル改変なし）
- 引数なし — 本番モード。実ファイルを書き換える

## Step 0: 読み先・書き出し先の決定

| 対象 | 本番 | demo |
|------|------|------|
| KPT データルート (`$KPT_ROOT`) | `~/.claude/kpt-data/` | `~/.claude/kpt-data/.demo/` |
| hook/skill/CLAUDE.md 実装先 | `~/.claude/` 配下 or `./` | `./demo/out/<YYYY-MM-DD_HHMMSS>/` 配下 |

demo モードでは実装ごとに以下のサブディレクトリに書き出す:
```
./demo/out/<ts>/
├── hooks/              # 新規 hook スクリプト
├── skills/             # 新規 skill (skill名/SKILL.md)
├── CLAUDE.md.diff      # CLAUDE.md への追記内容（差分）
├── settings.json.diff  # settings.json への追記内容（差分）
└── summary.md          # 何を何に書き出したかの一覧
```

## Step 1: 最新KPTの読み込み + refine 判定

`$KPT_ROOT/kpt/` から最新のKPTファイルを読み、Try項目を一覧化する。

各 Try に **`[🎯 refined ...]` マーカー** があるか確認し、判定を分類する:
- `[🎯 refined ... 採用 ...]` or `[🎯 refined ... 形を変える→... ...]` → **実装対象**
- `[🎯 refined ... 保留 ...]` or `[🎯 refined ... 却下 ...]` → **スキップ**
- マーカーなし → **未 refine**

### 未 refine Try の扱い

**1件も refined マーカーが無い**場合、AskUserQuestion で確認:

```
Q: refine-kpt が未実施です。どうしますか？
options:
  - /refine-kpt を先に実行（推奨）
  - 全Tryを対象にそのまま続行
  - 中断
```

**一部のみ未 refine** の場合は refined 済みのみを実装対象とし、「未 refine Try は skip しました」とログ表示。

「形を変える」Try は マーカーの `形を変える→<変換後種別>` を優先して実装する。

## Step 2: 実装対象の確認

実装対象 Try を一覧表示し、「どれを実装しますか？（全部 / 選択）」と AskUserQuestion。

## Step 3: 実装（種別ごと）

### hook化する場合
1. **本番**: `~/.claude/hooks/`（グローバル）or `.claude/hooks/`（プロジェクト）にスクリプト作成 + `settings.json` にhook設定を追加
2. **demo**: `./demo/out/<ts>/hooks/<name>.sh` に書き出し + `./demo/out/<ts>/settings.json.diff` に追記内容を書く
3. 実装時の注意:
   - 再帰防止（`CLAUDE_SESSION_ANALYSIS` 等の環境変数チェック）
   - SessionEnd hookはバックグラウンド実行（`nohup ... & disown`）
   - Stop hookは軽量に（重い処理はNG）
   - PreToolUse hookは `exit 0`（許可）/ `exit 2`（ブロック）で制御
   - パスは `$HOME` ベースで（グローバルの場合）

### skill化する場合
1. **本番**: `~/.claude/skills/<name>/SKILL.md`（グローバル）or `.claude/skills/<name>/SKILL.md`（プロジェクト）を作成
2. **demo**: `./demo/out/<ts>/skills/<name>/SKILL.md` に書き出し
3. frontmatter設定:
   - `name`: スラッシュコマンド名
   - `description`: いつ使うかの説明
   - `disable-model-invocation: true` → 手動呼び出し専用にする場合
   - `allowed-tools`: 必要なツールを列挙

### CLAUDE.mdルール追加の場合
1. **本番**: 対象の CLAUDE.md を読んで既存ルールとの重複チェック → 追記（グローバル = `~/.claude/CLAUDE.md` / プロジェクト = `./CLAUDE.md`）
2. **demo**: `./demo/out/<ts>/CLAUDE.md.diff` に追記予定の内容だけを書き出す（既存ファイルには触らない）
3. ルールの追加理由をコメントで併記（例: `<!-- KPT W16 P2: コミット粒度の問題が3回発生 -->`）

## Step 4: 実装結果の報告

本番モード:
```
## 実装完了
| # | Try | 種別 | 適用先 | ファイル |
|---|-----|------|--------|---------|
| T1 | PRテンプレチェック | hook | グローバル | ~/.claude/hooks/pr-template-check.sh |
```

demo モード:
```
## demo 書き出し完了（実ファイル改変なし）
| # | Try | 種別 | 書き出し先 |
|---|-----|------|------------|
| T1 | PRテンプレチェック | hook | ./demo/out/2026-04-25_150000/hooks/pr-template-check.sh |

全ファイルリスト: ./demo/out/2026-04-25_150000/summary.md
```

## Step 5: KPTファイル更新

反映したTry項目に `[✅ 実装済み YYYY-MM-DD]` マークを追記（`[🎯 refined ...]` マーカーの次行に追加）。
demo モード時も KPT ファイル（`$KPT_ROOT/kpt/YYYY-WXX.md`）は更新する。

## Step 6: 動作確認の案内

hook を追加した場合（本番）:
- 「次回セッションから自動で動作します」
- 「動作確認するには: `echo '{"tool_name":"Write"}' | bash ~/.claude/hooks/xxx.sh`」

skill を追加した場合（本番）:
- 「`/skill-name` で呼び出せます」

CLAUDE.md を更新した場合（本番）:
- 「次のプロンプトから反映されます」

demo モードの場合:
- 「実ファイルは変更していません。`./demo/out/<ts>/` の書き出し内容を確認してください」
- 「本番適用したい場合は `/apply-kpt` を引数なしで再実行してください」
