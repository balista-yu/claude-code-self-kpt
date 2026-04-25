# Claude Code Self-Improvement KPT

Claude Codeが **自分自身の仕事** を週次KPTで振り返り、**自分で改善を実装する** システム。

## 仕組み

```
日々の作業（自動）
├─ [Stop hook] 応答ごとの軽量ログ → activity-logs/ (月次JSONL)
└─ [SessionEnd hook] セッション自己分析 → session-reviews/ (ユーザー指摘の検出)

週次振り返り（/weekly-kpt）
└─ ログ + 自己分析 + git log + 前回KPT + Experiment判定 → KPT生成
   └─ Try実装率を前週差分から自動判定（書きっぱ防止）

Tryすり合わせ（/refine-kpt）
└─ 生成された Try を 採用 / 形を変える / 保留 / 却下 に仕分け
   └─ KPT本体にインラインで判定マーカーを追記

向き直り（/forward-kpt）
└─ Experiment（仮説検証型の攻めの一手）を週次で仕込む
   └─ 成功したExperimentは次回KPTでTry昇格

自己改善の実装（/apply-kpt）
└─ refine 済みの「採用」Tryのみを hook / skill / CLAUDE.md に自動実装
```

## 特徴

### 「ユーザー指摘」の自動追跡
SessionEnd hookがトランスクリプトを分析し、ユーザーがClaude Codeに修正を指示した箇所を自動検出・カテゴリ分類する。「PRテンプレート守って」を18回言ってた、みたいなことが数字で分かる。

### Tryの自動実装（/apply-kpt）
KPTのTryを「書いて終わり」にしない。`/apply-kpt` でhookやスキルとして実際に実装する。CLAUDE.mdにルール書いても守れないものはhook化を優先。

### Try すり合わせゲート（/refine-kpt）
`/weekly-kpt` と `/apply-kpt` の間に挟む壁打ち skill。AI が勝手に生成した Try をそのまま実装に回さず、ユーザーと対話で 採用 / 形を変える / 保留 / 却下 を仕分ける。判定は KPT 本体に `[🎯 refined YYYY-MM-DD: ...]` マーカーでインライン追記される。apply-kpt は採用分だけを実装対象にする。

### Try実装率の自動トラッキング
`/weekly-kpt` は前週KPTのTryが実際に `~/.claude/` 配下に実装されたかを差分ベースで判定する。未達成のTryは自動で翌週に繰り越し、3週以上放置されたものは「要検討」フラグ化される。

### 向き直り要素（/forward-kpt）
過去反省ベースのKPTだけでは "守り" に偏る。`/forward-kpt` で **Hypothesis × Success Criteria** 形式の Experiment を週次で最大2件仕込み、次回KPTで自動判定。成功したものはTryに昇格される。

### 月次ログローテーション
アクティビティログは `activity_YYYY-MM.jsonl`、自己分析は `session-reviews/YYYY-MM/` に月次で分割。放置しても肥大化しない。

### プロジェクト横断
`~/.claude/` にグローバル配置。全プロジェクトのデータが自動で集まる。KPTはプロジェクト単体でも全横断でも実行可能。

## Getting Start

1. Clone the repository

```
$ git clone https://github.com/balista-yu/claude-code-self-kpt.git
```

2. インストール

```bash
chmod +x install.sh
./install.sh
```

これだけ。インストーラーが以下を自動でやります
- 既存の `settings.json` / `CLAUDE.md` を `~/.claude/backup-YYYYMMDD-HHMMSS/` に退避
- `~/.claude/hooks/` にSessionEnd hookを配置
- `~/.claude/skills/` にKPTスキルを配置
- `~/.claude/settings.json` にhook設定をマージ（既存設定があれば安全にマージ）
- `~/.claude/CLAUDE.md` にKPT運用ルールを追記

### アンインストール

```bash
./uninstall.sh                 # 設定とファイルを削除、kpt-data は残す
./uninstall.sh --purge-data    # データも含めて全削除
```

`uninstall.sh` は以下を実施する:

- `~/.claude/backup-YYYYMMDD-HHMMSS/` に `settings.json` / `CLAUDE.md` を退避
- `settings.json` から **KPT 関連 hook エントリのみ** を `jq` で除去（他の Stop / SessionEnd hook は保持）
- `~/.claude/hooks/kpt-*.sh` を削除
- `~/.claude/skills/{weekly-kpt,apply-kpt,forward-kpt,refine-kpt}/` を削除
- `~/.claude/scripts/kpt-viewer.py` を削除
- `~/.claude/CLAUDE.md` から自己改善システムブロックを除去（他セクションは保持）
- **データディレクトリ `~/.claude/kpt-data/` はデフォルト残す**（`--purge-data` 指定時のみ削除）

### 依存ツール

- `jq` — hookのトランスクリプト解析で使用
- `claude` CLI — hookの分析セッションで使用

```bash
# jqのインストール（未インストールの場合）
brew install jq          # macOS
sudo apt install jq      # Ubuntu/Debian
```

### 日常（何もしない）
hookが全自動で動く。

### 週次KPT
```
/weekly-kpt
```

### Try すり合わせ
```
/refine-kpt
```

### 改善の実装
```
/apply-kpt
```

### 向き直り（Experiment仕込み）
```
/forward-kpt
```

### Demo（記事再現用・実データに触れず動作確認）

実運用データを使いたくないときに、同梱の fixtures を使ってワークフロー全体を動かせる。`demo` 引数を渡した skill は読み先を `~/.claude/kpt-data/.demo/` に切り替え、実データや `~/.claude/` 配下を一切変更しない。

```bash
# 1. ダミーデータを ~/.claude/kpt-data/.demo/ に展開
./demo/seed.sh

# 2. KPT 生成
/weekly-kpt demo

# 3. Try を仕分け
/refine-kpt demo

# 4. 採用 Try を ./demo/out/<ts>/ に仮実装（実ファイルは改変しない）
/apply-kpt demo

# 後片付け
./demo/seed.sh --clean
```

demo fixtures は 2026-W16（前週）のKPT + 2026-W17（今週）分の session-reviews / activity-logs / experiments を同梱。PRテンプレ無視 3回 / コミット粒度 2回 / テスト未実行 2回 / 指摘なし 1回 の分布で、前週 Try 3件が done / partial / not-done に自然に分岐するように仕込んである。

### ダッシュボード
```bash
python3 ~/.claude/scripts/kpt-viewer.py
# → http://localhost:8765
```

タブ構成:
- **Overview**: 統計、カテゴリ、プロジェクト分布、セッション散布図、燃えてるカテゴリアラート
- **Heatmaps**: カテゴリ×週ヒートマップ、曜日×時間帯ヒートマップ
- **Experiments**: `/forward-kpt` の実験カンバン（In Progress / Success / Continue / Fail）
- **Tries**: Try寿命タイムライン（実装済み/pending）
- **Costs**: SessionEnd hook の Haiku 呼び出し実測（月次トークン・コスト・直近セッション）
- **Self-Reviews / KPT Archive**: 生データ閲覧

### 手動でセッション分析をテスト
```bash
TRANSCRIPT=$(find ~/.claude/projects/ -maxdepth 2 -name "*.jsonl" | head -1)

echo '{"transcript_path":"'"$TRANSCRIPT"'","session_id":"test","cwd":"'"$(pwd)"'"}' \
  | bash ~/.claude/hooks/kpt-session-analyze.sh

sleep 15 && ls -la ~/.claude/kpt-data/session-reviews/
```

## データ構成

```
~/.claude/kpt-data/
├── activity-logs/           # Stop hook: 応答ごとの軽量ログ
│   ├── activity_2026-03.jsonl
│   └── activity_2026-04.jsonl
├── session-reviews/         # SessionEnd hook: 自己分析
│   ├── 2026-03/
│   │   └── 2026-03-28_153022_abc12345.md
│   └── 2026-04/
│       └── 2026-04-14_091500_def67890.md
├── kpt/                     # 週次KPT結果
│   ├── 2026-W14.md
│   └── 2026-W15.md
├── experiments/             # /forward-kpt: 週次Experiment
│   ├── experiment_2026-W14.md
│   └── experiment_2026-W15.md
├── cost-logs/               # SessionEnd hook: Haiku 呼び出しの usage / cost 実測
│   ├── cost_2026-03.jsonl
│   └── cost_2026-04.jsonl
└── .demo/                   # demo モード時のみ展開される fixtures（本番データと完全分離）
    ├── session-reviews/
    ├── activity-logs/
    ├── kpt/
    ├── experiments/
    └── virtual-dotclaude/   # ~/.claude/ 相当を demo 側でエミュレート
```

## Data Flow

本システムが扱うデータの流れを明示する。

### ローカルに残るデータ（`~/.claude/kpt-data/` 配下）

- `activity-logs/activity_YYYY-MM.jsonl` — Stop hook が書く応答ごとの軽量ログ。**API 送信なし、ローカルファイル書き込みのみ**。
- `session-reviews/YYYY-MM/*.md` — SessionEnd hook が Claude Haiku に transcript を要約させた自己分析結果。
- `cost-logs/cost_YYYY-MM.jsonl` — SessionEnd hook の Haiku 呼び出しごとの usage / cost（input/output/cache tokens, `total_cost_usd`, duration）を JSONL で蓄積。
- `kpt/*.md` — `/weekly-kpt` が生成する週次 KPT 全文。
- `experiments/*.md` — `/forward-kpt` が仕込む週次 Experiment。

### Anthropic API に送信されるデータ

- **SessionEnd hook** が transcript（ユーザー / assistant の発言抜粋）を整形し、**Claude Haiku** に自己分析プロンプトとして送信する（`.claude/hooks/kpt-session-analyze.sh`）。
- 送信内容は session review に書き戻されるため、ローカルに残るデータと内容が対応する。

### API 送信されないデータ

- Stop hook の activity-log はローカルファイルに JSONL を追記するだけで、API 呼び出しを一切行わない。

## Privacy & Security

会話に誤って貼り付けた API キー / トークンをディスク書き込みと Anthropic API 送信の**前段**で自動 redaction する。対応パターンは Anthropic / OpenAI / GitHub / AWS / Google / Stripe / Slack / JWT / PRIVATE KEY ブロック / `password=...` 形式の代入。詳細は `.claude/hooks/kpt-redact.sh` 冒頭コメントを参照。

redaction が失敗した場合は fail-closed — 未 redact データを送信せず、マーカー（`[REDACTION_FAILED]` / `ABORTED`）を残して後から検知可能にする。

既知パターンの第一層防御にすぎず、独自形式のキーや短い認証情報は捉えられない。**フルディスク暗号化 (FileVault / BitLocker / LUKS) の併用を強く推奨する**。

## Cost Tracking

推測値ではなく**実測値**で管理する。SessionEnd hook は `claude -p --output-format json` で Haiku を呼び、応答 JSON の `usage` / `total_cost_usd` / `duration_ms` を `~/.claude/kpt-data/cost-logs/cost_YYYY-MM.jsonl` に記録する。

ダッシュボードの **Costs タブ** で以下を確認できる：

- 累積: total cost (USD) / hook invocations / input / output / cache read / cache creation
- 月次ブレークダウン（month × sessions × tokens × cost）
- 直近 50 セッションの per-call 内訳（project / tokens / cost / duration）

```bash
python3 ~/.claude/scripts/kpt-viewer.py  # → http://localhost:8765 → Costs タブ
```

> **注意**: `total_cost_usd` は Anthropic API 単価に基づく計算値であり、Pro / Max 定額プラン利用時は実課金ではなく「API 換算した場合の目安」として読むこと。課金自体は利用プランに従う。

### hook を一時的に無効化する

API 呼び出しを止めたい場合、`~/.claude/settings.json` から `hooks.SessionEnd` エントリを削除する。Stop hook（activity-log）は API を呼ばないため、SessionEnd だけ外す運用も可能。

## 依存

- `jq` — hookのJSON処理
- `claude` CLI — SessionEnd hookの分析実行
