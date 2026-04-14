# Claude Code Self-Improvement KPT

Claude Codeが **自分自身の仕事** を週次KPTで振り返り、**自分で改善を実装する** システム。

## 仕組み

```
日々の作業（自動）
├─ [Stop hook] 応答ごとの軽量ログ → activity-logs/ (月次JSONL)
└─ [SessionEnd hook] セッション自己分析 → session-reviews/ (ユーザー指摘の検出)

週次振り返り（/weekly-kpt）
└─ ログ + 自己分析 + git log + 前回KPT → KPT生成

自己改善の実装（/apply-kpt）
└─ Try項目を hook / skill / CLAUDE.md に自動実装
```

## 特徴

### 「ユーザー指摘」の自動追跡
SessionEnd hookがトランスクリプトを分析し、ユーザーがClaude Codeに修正を指示した箇所を自動検出・カテゴリ分類する。「PRテンプレート守って」を18回言ってた、みたいなことが数字で分かる。

### Tryの自動実装（/apply-kpt）
KPTのTryを「書いて終わり」にしない。`/apply-kpt` でhookやスキルとして実際に実装する。CLAUDE.mdにルール書いても守れないものはhook化を優先。

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
- `~/.claude/hooks/` にSessionEnd hookを配置
- `~/.claude/skills/` にKPTスキルを配置
- `~/.claude/settings.json` にhook設定をマージ（既存設定があれば安全にマージ）
- `~/.claude/CLAUDE.md` にKPT運用ルールを追記

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

### 改善の実装
```
/apply-kpt
```

### ダッシュボード
```bash
python3 ~/.claude/scripts/kpt-viewer.py
# → http://localhost:8765
```

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
└── kpt/                     # 週次KPT結果
    ├── 2026-W14.md
    └── 2026-W15.md
```

## 依存

- `jq` — hookのJSON処理
- `claude` CLI — SessionEnd hookの分析実行
