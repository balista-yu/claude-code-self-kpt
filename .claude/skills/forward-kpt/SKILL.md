---
name: forward-kpt
description: Claude Code自身の「向き直り」。過去反省ではなく、意図的な実験（Experiment）を週次で仕込む。成功したExperimentは次回KPTで Try昇格される。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Write, AskUserQuestion
---

# Claude Code 向き直り（Forward-KPT）

`/weekly-kpt` は過去の反省ベース。このスキルは **「次に何を試すか」を能動的に仕込む** ためのもの。
主語は「自分（Claude Code）」です。攻めの一手を週次で1〜2件、仮説検証形式で設定する。

## Step 1: スコープ確認

ユーザーに確認:
- 「どのプロジェクトで試す？（現在のプロジェクト / グローバル / 特定プロジェクト）」
- 「Experiment期間は？（デフォルト: 1週間）」
- 「同時進行は最大2件まで。既に進行中があれば表示するのでその上で追加するか確認する。」

## Step 2: 進行中Experimentの確認

`~/.claude/kpt-data/experiments/` から現在進行中のファイルを読み込む:
- ファイル名パターン: `experiment_YYYY-WXX.md`
- status: `in_progress` のものをカウント
- 2件以上あれば「新規追加できません、先に `/weekly-kpt` で判定してください」と返す

## Step 3: 実験候補の提案

以下のソースから候補を生成:

1. **過去のProblem** `~/.claude/kpt-data/kpt/` 最新数週から、まだ未解決のProblemを抽出
   → 「このProblemを解消する新アプローチを試す」型のExperiment候補
2. **触れてない技術領域** `activity-logs/` のプロジェクト別頻度から、長期間触れてないスキルを抽出
   → 「久しぶりのXXXをリハビリ的に試す」型
3. **ユーザーの興味軸** ユーザーから直接ヒアリング（「何に挑戦したい？」）

3〜5件の候補をリスト表示。ユーザーに選ばせる（1〜2件）。

## Step 4: Experiment定義

選ばれた候補ごとに、以下を埋めてユーザーに確認:

```markdown
- **Title**: （短い名前）
- **Hypothesis**: 何を試す／仮説（例: 「大きな変更の前に AskUserQuestion を先行させるとユーザー承認率が上がる」）
- **Success Criteria**: 何で成功と判断するか（測定可能な形で）
  - 例: 「同カテゴリの指摘が前週比 50% 以上減少」
  - 例: 「該当アクションを週内で 3 回以上自発的に実施」
- **Duration**: 1週 / 2週（デフォルト1週）
- **Measurement Source**: 何で測るか
  - `session-reviews` / `activity-logs` / `自己申告（KPT時に振り返り）` のいずれか
- **Risk**: 失敗したときの副作用（例: 応答が遅くなる可能性）
```

## Step 5: 保存

`~/.claude/kpt-data/experiments/experiment_YYYY-WXX.md` に追記形式で保存:

```markdown
# Experiments: YYYY年 第XX週

## E1: （Title）
- status: in_progress
- started: YYYY-MM-DD
- duration: 1週
- hypothesis: ...
- success_criteria: ...
- measurement: ...
- risk: ...
- scope: （プロジェクト名 or global）

## E2: ...
```

同週のファイルが既にあれば追記、なければ新規作成。

## Step 6: CLAUDE.md への意識付け追記

Experiment 期間中、Claude Code 自身が常に意識できるよう、対象 CLAUDE.md に一時セクションを追記:

グローバルExperiment → `~/.claude/CLAUDE.md`
プロジェクトExperiment → `./CLAUDE.md`

追記フォーマット（`<!-- FORWARD-KPT-EXPERIMENTS -->` コメントで囲む。次回 `/weekly-kpt` 時に自動削除するため）:

```markdown
<!-- FORWARD-KPT-EXPERIMENTS:START -->
## 今週の Experiment（自動更新セクション）
- **E1**: （Hypothesis を1行要約）
  - 成功条件: （Success Criteria 要約）
- **E2**: ...

※ このセクションは `/weekly-kpt` 実行時に自動判定・削除されます。
<!-- FORWARD-KPT-EXPERIMENTS:END -->
```

既存の `<!-- FORWARD-KPT-EXPERIMENTS:START -->` 〜 `:END -->` ブロックがあれば上書き。

## Step 7: ユーザーへの案内

```
## Experiment 開始
| # | Title | Hypothesis | 成功条件 | 期間 |
|---|-------|-----------|---------|------|
| E1 | ... | ... | ... | 1週 |

- 保存先: ~/.claude/kpt-data/experiments/experiment_YYYY-WXX.md
- CLAUDE.md に意識付けセクション追記済み
- 次回 `/weekly-kpt` で自動判定されます
```

## 注意事項

- **同時進行は最大2件**: 発散防止のため厳守
- **測定できないExperimentは作らない**: 「なんとなく頑張る」系は拒否、Success Criteriaを数字で書かせる
- **Experiment ≠ Try**: Try は確実に実装する改善、Experiment は仮説検証。混同しない
- **CLAUDE.md追記は一時的**: `/weekly-kpt` 完了時に自動削除されるため、コメントマーカーを必ず使う
