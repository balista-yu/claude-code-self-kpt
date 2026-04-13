---
name: apply-kpt
description: 最新のKPT結果のTry項目をCLAUDE.mdやhookに反映する。weekly-kpt実行後に使用。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Write, Edit
---

# KPT Try項目の反映

最新のKPT結果から、Try項目を実際の設定に反映します。

## 手順

### Step 1: 最新KPTの読み込み

`~/.claude/kpt-data/kpt/` から最新のKPTファイルを読み、Try項目を一覧化してください。

### Step 2: 適用先の判定

各Try項目の「適用先」を確認

- **グローバル（~/.claude/）**: 全プロジェクト共通の改善
  - hook → `~/.claude/hooks/`
  - skill → `~/.claude/skills/`
  - CLAUDE.md → `~/.claude/CLAUDE.md`
  - settings.json → `~/.claude/settings.json`

- **プロジェクト（.claude/）**: プロジェクト固有の改善
  - hook → `.claude/hooks/`
  - skill → `.claude/skills/`
  - CLAUDE.md → `./CLAUDE.md`
  - settings.json → `.claude/settings.json`

### Step 3: Try項目の分類と実装

#### hook化する場合
- 適用先ディレクトリにシェルスクリプトまたはNode.jsスクリプトを作成
- 対応する `settings.json` にhook設定を追加
- 再帰防止、バックグラウンド実行、タイムアウト対策を忘れずに
- グローバルhookのパスは `$HOME/.claude/hooks/xxx.sh` を使用

#### スキル化する場合
- 適用先の `skills/<name>/SKILL.md` を作成
- 適切なfrontmatter（name, description, allowed-tools）を設定

#### CLAUDE.mdルール追加の場合
- 適切なCLAUDE.mdのセクションにルールを追加
- 既存ルールとの重複がないか確認
- 「なぜこのルールがあるのか」のコメントも添える（KPTのProblemを参照）

### Step 4: 変更の確認

実施した変更を一覧表示し、ユーザーに確認を求めてください:

```
## 反映内容
1. [hook/グローバル] PR作成時のテンプレートチェック → ~/.claude/hooks/pr-template-check.sh
2. [CLAUDE.md/プロジェクト] コミット粒度のガイドライン追加 → ./CLAUDE.md
3. [skill/グローバル] dependabotレビュー → ~/.claude/skills/dependabot-review/SKILL.md
```

### Step 5: KPTファイルの更新

反映したTry項目のステータスを更新してください（「実装済み」マークを付ける）。
