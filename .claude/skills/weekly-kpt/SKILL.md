---
name: weekly-kpt
description: Claude Code自身の週次KPT。自分の仕事を振り返り、自分を改善するためのKeep/Problem/Tryを生成する。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Write
---

# Claude Code 自己改善KPT

あなたはこれから **自分自身の仕事** を振り返ります。
主語は「自分（Claude Code）」です。人間の振り返りではなく、AIとしての自己改善が目的です。

## Step 1: スコープ確認

ユーザーに確認:
- 「このプロジェクトだけ振り返る？ それとも全プロジェクト横断で？」
- 「対象期間は？（デフォルト: 直近1週間）」

## Step 2: 材料収集

以下の情報をすべて収集:

1. **セッション自己分析**: `~/.claude/kpt-data/session-reviews/` から対象期間分を読む
   - プロジェクト絞り込みが必要ならファイル内の「プロジェクト:」でフィルタ
2. **アクティビティログ**: `~/.claude/kpt-data/activity-logs/activity_YYYY-MM.jsonl` から対象期間分を読む
   - `jq` で対象日付・プロジェクトでフィルタ
3. **Gitログ**: `git log --oneline --since="1 week ago"` を実行（現在プロジェクト）
4. **前回のKPT**: `~/.claude/kpt-data/kpt/` の最新ファイルを読む
5. **現在のルール**: `~/.claude/CLAUDE.md` と `./CLAUDE.md` を読む
6. **Try実装差分**: `~/.claude/` 配下の前週期間中の変更を検出
   - `git -C ~/.claude log --since="<対象期間開始>" --until="<対象期間終了>" --name-status` で変更ファイル一覧
   - `~/.claude` が git管理でない場合のフォールバック:
     - 基準ファイル = **前回KPTファイル**（`~/.claude/kpt-data/kpt/YYYY-WXX.md` の前週版）
     - 前回KPTが無い初回実行時は基準ファイル = **対象期間開始日の00:00タイムスタンプのダミー**（`touch -d "<対象期間開始> 00:00" /tmp/.kpt-since` 等で作成）
     - `find ~/.claude/hooks ~/.claude/skills ~/.claude/CLAUDE.md ~/.claude/settings.json -newer <基準ファイル> -type f`
   - 対象: `hooks/*.sh`, `skills/**/SKILL.md`, `CLAUDE.md`, `settings.json`
7. **進行中のExperiment**: `~/.claude/kpt-data/experiments/` から対象期間の未判定Experimentを読む（`/forward-kpt` で作成されたもの）

## Step 3: 分析

自分自身の視点で以下を分析:

- **繰り返し同じ指摘を受けていないか**: カテゴリ別に集計（コード品質、仕様理解、テスト、コミット等）
- **どんなタスクなら自分はうまくやれるか**: 指摘なしセッションの共通点
- **どんなタスクで自分はミスしやすいか**: 指摘が多いセッションの共通点
- **ルールを書いたのに守れてないものはないか**: CLAUDE.mdのルール vs 実際の指摘

### Step 3-a: Try実装率の自動判定

前回KPTの各Try項目に対して、Step 2-6で収集した差分とマッチングして判定:

判定ラベル:
- **done**: Try文言と意味的に一致する変更が `~/.claude/` 配下に存在する
- **partial**: 一部のみ実装（例: hook化と書いたがCLAUDE.mdルールだけ追加された）
- **not-done**: 対応する変更なし

マッチング基準:
- Try種別が「hook」→ `hooks/` 配下の新規/変更ファイルを確認
- Try種別が「skill」→ `skills/<name>/SKILL.md` の新規/変更を確認
- Try種別が「CLAUDE.mdルール」→ `CLAUDE.md` の追記内容を確認
- ファイル名・スクリプト内容・ルール文言が Try の目的と一致するか自己判断

未達成（not-done / partial）Tryは Step 4 の「Stale Tries」に自動繰り越し。

### 「要検討」フラグの運用ルール

放置週数が3週以上の Try は「要検討」フラグを立てる。立てた後の扱いは以下:

- **翌週 `/weekly-kpt` で必ずユーザーに確認**: 「このTryは3週放置されてます。以下どうしますか？」
  1. **削除** — 不要と判断。Stale Triesからも消す
  2. **形を変えて再挑戦** — hook化→skill化など別手段に変換して新Tryとして再登録
  3. **別Tryで達成済み** — 類似Tryで目的達成済み。達成として終了
  4. **継続保持** — 来週もそのまま持ち越し（ただし要検討フラグは維持）
- **自動削除はしない**: ユーザー判断なしに消さない（意図せぬ情報消失防止）
- **KPT出力時の表示**: 要検討フラグ付きTryは Stale Tries 表に `⚠️ 要検討` アイコン付きで表示

### Step 3-b: Experiment 結果の判定

進行中Experimentがあれば、各Experimentについて:
- **Success Criteria** と実データ（session-reviews / activity-logs）を照合
- **成功** → Try昇格候補（恒常化）として Step 4 の Try に入れる
- **失敗** → Problem として記録、根本原因分析
- **継続** → 期間延長 or 条件見直しを提案

## Step 4: KPT生成

`~/.claude/kpt-data/kpt/YYYY-WXX.md` に出力:

```markdown
# Claude Code 自己改善KPT: YYYY年 第XX週

## 分析期間
YYYY-MM-DD 〜 YYYY-MM-DD

## スコープ
- 対象: （プロジェクト名 or 全プロジェクト横断）
- セッション数: X件
- うち指摘なし: X件（XX%）

## 前回Tryの達成率
**達成率: X/Y (XX%)**

| Try項目 | 種別 | 実施状況 | 実装先 | 効果 |
|---------|------|---------|--------|------|
| （前回のTry） | hook/skill/rule | done/partial/not-done | （ファイルパス or なし） | （指摘が減ったか等） |

## Experiment結果
進行中だったExperimentの判定:

| Experiment | Hypothesis | 結果 | 次アクション |
|------------|-----------|------|-------------|
| （Experiment名） | （仮説） | success/fail/continue | Try昇格 / Problem化 / 延長 |

## Keep（自分がうまくやれたこと）
### K1: （タイトル）
- 具体例: （どのセッションでどう成功したか）
- なぜうまくいったか: （再現のためのポイント）
- 指摘なし率: XX%

## Problem（自分が繰り返し間違えたこと）
### P1: （タイトル）
- カテゴリ: コード品質 / 仕様理解 / テスト / コミット / etc
- 発生回数: X回
- 具体例: （どんな指摘を受けたか）
- 根本原因: （なぜ繰り返すのか。ルールがない？ルールはあるけど守れてない？）
- CLAUDE.mdにルールあるか: あり→守れてない / なし

## Try（来週の自己改善アクション）
### T1: （タイトル）
- 種別: hook / skill / CLAUDE.mdルール / ワークフロー
- 適用先: グローバル / プロジェクト固有
- 具体的な実装内容: （何をどう変えるか）
- 対象Problem: P1
- 優先度: 高/中/低
- 注: CLAUDE.mdルール追加は「hook/skillでは対応困難な場合のみ」

## Stale Tries（放置されているTry）
過去KPTから、未達成のまま残っているTryを一覧化:
| 初出 | Try項目 | 放置週数 | 対応案 |
|------|---------|---------|--------|

## 統計
- 総セッション数: X
- 指摘なし率: XX%（前週: XX% / 変化: +X%）
- 最頻出指摘カテゴリ: （カテゴリ名 X回）
- 改善トレンド: （良くなってる / 横ばい / 悪化）
- Try達成率: XX%（前週: XX% / 変化: +X%）
- Experiment成功率: X/Y
```

## Step 5: Experiment 結果の反映

Step 3-b で判定した Experiment について、以下を実行:

1. **`~/.claude/kpt-data/experiments/experiment_YYYY-WXX.md` の status を更新**
   - success / fail / continue
   - 判定日と根拠を追記
2. **CLAUDE.md の一時セクション削除**
   - `~/.claude/CLAUDE.md` と `./CLAUDE.md` から
     `<!-- FORWARD-KPT-EXPERIMENTS:START -->` 〜 `<!-- FORWARD-KPT-EXPERIMENTS:END -->` ブロックを削除
   - `continue` のものが残る場合は、該当 E だけ残して他は削除

## Step 6: ユーザーへの提案

KPT結果を提示した後:
- 「Tryの中ですぐ実装できるものがあります。`/apply-kpt` で反映しますか？」と確認
- 特にProblemの発生回数が多いものは強く推奨
- 「ルールはあるのに守れてない」Problemは **必ず** hook化を提案
- 「今週は攻めの一手を `/forward-kpt` で仕込みますか？」と案内（過去反省だけで終わらせない）
