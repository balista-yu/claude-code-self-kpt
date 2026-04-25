---
name: refine-kpt
description: 週次KPTで出た Try 項目を、apply-kpt に進む前にユーザーと壁打ちして「採用 / 形を変える / 保留 / 却下」を仕分ける。書きっぱの Try を実装フェーズに持ち込ませないためのゲート。
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash, Edit, AskUserQuestion
---

# Claude Code 自己改善KPT — Try すり合わせ（Refine）

`/weekly-kpt` で生成された Try 項目を、**実装に進める前にユーザーと一緒に仕分ける** ための skill。
`/weekly-kpt` → `/refine-kpt` → `/apply-kpt` の中間ステップとして機能する。

## 引数

- `demo` — demo モード。読み先を `~/.claude/kpt-data/.demo/` に切り替える。実データには触らない
- 引数なし — 本番モード。`~/.claude/kpt-data/` を対象

## Step 1: 読み先決定

引数 `demo` が指定されていれば以下に切替、そうでなければ本番パス:

| 対象 | 本番 | demo |
|------|------|------|
| KPT データルート | `~/.claude/kpt-data/` | `~/.claude/kpt-data/.demo/` |

以降の処理では上記を `$KPT_ROOT` と表記する。

## Step 2: 最新KPTファイルの特定

`$KPT_ROOT/kpt/` 配下で **今週のファイル** (`YYYY-WXX.md` で最大番号) を特定して読む。
週番号は `date +%G-W%V` で取得（ただし demo モードでは `2026-W17` を想定しているのでファイル側の週番号を優先）。

## Step 3: Try 項目の抽出

KPT ファイルから `## Try` セクションを正規表現で抽出し、各 Try（`### T1:` 〜）の:
- タイトル
- 種別 (hook / skill / CLAUDE.mdルール / ワークフロー)
- 対象Problem
- 優先度
- 既に `[🎯 refined ...]` マーカーがあるか

をパースする。

既に全Try が refined 済みなら「全Tryが refine 済みです。再実行しますか？（上書き）」と確認。

## Step 4: 各 Try を対話で仕分け

Try ごとに AskUserQuestion を 1〜3 問発行する。

### 質問 1（必須）: 判定

```
Q: T1「PRテンプレチェックを hook 化」をどうしますか？
options:
  - ✅ 採用 — このまま apply-kpt で実装する
  - 🔄 形を変える — 種別や手段を変えて採用
  - ⏸ 保留 — Stale Tries に回す
  - ❌ 却下 — 不要と判断
```

### 質問 2（「形を変える」時のみ）: 変換先

```
Q: T1 をどう形を変えますか？
options:
  - hook → skill
  - hook → CLAUDE.mdルール
  - skill → hook
  - CLAUDE.mdルール → hook
```

### 質問 3（「採用」「形を変える」時のみ）: 成功基準・副作用メモ

これはフリーテキスト。ユーザーに直接タイプしてもらう（AskUserQuestion ではなく通常の対話で確認）。
- 「成功基準は？（例: 来週の同カテゴリ指摘が 0 件）」
- 「懸念される副作用は？ なければ none で OK」

### 質問 2'（「保留」「却下」時のみ）: 理由

- 「保留/却下の理由を一言でお願い」

## Step 5: KPT 本体にインライン追記

各 Try 項目の末尾（次の `###` 見出し直前）に、以下のフォーマットで 1 行追記する。

```markdown
[🎯 refined YYYY-MM-DD: 採用 / <種別（変換後含む）> / 成功基準: <...> / 副作用: <...>]
```

判定ごとのフォーマット例:

```markdown
[🎯 refined 2026-04-25: 採用 / hook / 成功基準: PR差し戻し 0件/週 / 副作用: none]
[🎯 refined 2026-04-25: 形を変える→skill / 成功基準: 粒度違反 50%減 / 副作用: コミット時のオーバーヘッド]
[🎯 refined 2026-04-25: 保留 / 理由: 今週は hook 化を優先したい]
[🎯 refined 2026-04-25: 却下 / 理由: P3 は T1 で間接的に解消見込み]
```

既存の `[🎯 refined ...]` 行が同 Try にあれば **その行を置き換える**（追記ではなく上書き）。

実装には Edit tool を使用し、Try セクション文字列を old_string / new_string で差し替える。

## Step 6: サマリ表示

全 Try の仕分けが終わったら、以下の表をユーザーに提示する:

```
## Refine 完了

| Try | 元種別 | 判定 | 最終種別 | 成功基準 |
|-----|--------|------|----------|----------|
| T1 | hook | ✅ 採用 | hook | PR差し戻し 0件/週 |
| T2 | CLAUDE.md | 🔄 形を変える | hook | 粒度違反 50%減 |
| T3 | skill | ⏸ 保留 | - | (理由: 来週に回す) |

採用: 2件 / 形を変える: 0件 / 保留: 1件 / 却下: 0件

次のアクション:
  /apply-kpt            # 採用分を実装（本番）
  /apply-kpt demo       # demo/out/ に仮実装
```

## 注意

- **判定はインライン追記のみ**。別ファイルは作らない（シングルファイル運用）
- **保留・却下の Try も KPT 本体に追記を残す**。後から経緯を追えるように
- demo モード時でも追記先は demo 側の KPT ファイル（`~/.claude/kpt-data/.demo/kpt/YYYY-WXX.md`）
- refine 後の KPT ファイルは apply-kpt が判定に使うため、マーカー書式は厳守する
