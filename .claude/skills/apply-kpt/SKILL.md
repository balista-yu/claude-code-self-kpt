---
name: apply-kpt
description: 最新のKPT結果のTry項目を実際にhook/skill/CLAUDE.mdに実装する。Claude Codeの自己改善を実行するコマンド。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

# KPT Try項目の自動実装

最新のKPT結果のTry項目を **実際にコードとして実装** します。
これがこのシステムの核心です。振り返るだけでなく、自分自身を改善します。

## Step 1: 最新KPTの読み込み

`~/.claude/kpt-data/kpt/` から最新のKPTファイルを読み、Try項目を一覧表示。
各Tryの優先度と種別を確認し、ユーザーに「どれを実装しますか？（全部 / 選択）」と確認。

## Step 2: 実装（種別ごと）

### hook化する場合
1. `~/.claude/hooks/`（グローバル）or `.claude/hooks/`（プロジェクト）にスクリプト作成
2. 対応する `settings.json` にhook設定を追加
3. 実装時の注意:
   - 再帰防止（`CLAUDE_SESSION_ANALYSIS` 等の環境変数チェック）
   - SessionEnd hookはバックグラウンド実行（`nohup ... & disown`）
   - Stop hookは軽量に（重い処理はNG）
   - PreToolUse hookは `exit 0`（許可）/ `exit 2`（ブロック）で制御
   - パスは `$HOME` ベースで（グローバルの場合）

### skill化する場合
1. `~/.claude/skills/<name>/SKILL.md`（グローバル）or `.claude/skills/<name>/SKILL.md`（プロジェクト）を作成
2. frontmatter設定:
   - `name`: スラッシュコマンド名
   - `description`: いつ使うかの説明
   - `disable-model-invocation: true` → 手動呼び出し専用にする場合
   - `allowed-tools`: 必要なツールを列挙

### CLAUDE.mdルール追加の場合
1. 対象の CLAUDE.md を読んで既存ルールとの重複チェック
2. ルールの追加理由をコメントで併記（例: `<!-- KPT W16 P2: コミット粒度の問題が3回発生 -->`）
3. グローバル → `~/.claude/CLAUDE.md` / プロジェクト → `./CLAUDE.md`

## Step 3: 実装結果の報告

```
## 実装完了
| # | Try | 種別 | 適用先 | ファイル |
|---|-----|------|--------|---------|
| T1 | PRテンプレチェック | hook | グローバル | ~/.claude/hooks/pr-template-check.sh |
| T2 | テスト実行確認 | hook | プロジェクト | .claude/hooks/test-check.sh |
| T3 | コミット粒度ルール | CLAUDE.md | プロジェクト | ./CLAUDE.md |
```

## Step 4: KPTファイル更新

反映したTry項目に `[✅ 実装済み YYYY-MM-DD]` マークを付与。

## Step 5: 動作確認の案内

hook を追加した場合:
- 「次回セッションから自動で動作します」
- 「動作確認するには: `echo '{"tool_name":"Write"}' | bash ~/.claude/hooks/xxx.sh`」

skill を追加した場合:
- 「`/skill-name` で呼び出せます」

CLAUDE.md を更新した場合:
- 「次のプロンプトから反映されます」
