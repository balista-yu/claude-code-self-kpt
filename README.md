# Claude Code KPT 自己改善システム（Global版）

Claude Codeが自分自身の仕事を週次KPTで振り返り、自動的に改善し続ける仕組み。
`~/.claude/` に配置するので、**全プロジェクトで自動的に動作**します。

## 全体像

```
日々の開発作業（どのプロジェクトでも）
    ↓ [SessionEnd hook: 自動]
セッション作業ログ生成 (~/.claude/kpt-data/work-logs/)
    ↓ [週1回: /weekly-kpt]
KPT分析・生成 (~/.claude/kpt-data/kpt/)
    ↓ [/apply-kpt]
~/.claude/ or .claude/ に改善を反映
    ↓
翌週のClaude Codeが改善される
```

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

## 使い方

### 日常（何もしなくてOK）

セッション終了時にhookが自動で作業ログを生成。10KB未満の短いセッションはスキップ。
分析にはHaikuモデルを使用するのでコストは最小限。

### 週次KPT（週1回）

Claude Codeで
```
/weekly-kpt
```
→ 今週の作業ログを全部読んでKPT分析してくれる。プロジェクト横断も可。

KPT結果を見て、反映したいなら
```
/apply-kpt
```
→ Try項目をhook/skill/CLAUDE.mdに実装してくれる。

### ダッシュボード

```bash
python3 ~/.claude/scripts/kpt-viewer.py
```
→ http://localhost:8765 でプロジェクト別の指摘推移やTop Issuesが見れる。

## ファイル構成

```
~/.claude/
├── hooks/
│   └── session-end-analyze.sh     # SessionEnd hook
├── skills/
│   ├── weekly-kpt/SKILL.md        # /weekly-kpt
│   └── apply-kpt/SKILL.md         # /apply-kpt
├── scripts/
│   └── kpt-viewer.py              # ダッシュボード
├── kpt-data/
│   ├── work-logs/                 # 作業ログ（自動生成）
│   │   └── 2026-04-14_153022_abc12345.md
│   └── kpt/                       # KPT結果
│       └── 2026-W16.md
├── settings.json                  # hook設定
└── CLAUDE.md                      # グローバルルール
```

## 仕組みの詳細

### SessionEnd Hook
- セッション終了時にバックグラウンドで`claude -p --model haiku`を実行
- トランスクリプトからuser/assistantの発言を抽出し分析
- 再帰防止（分析セッション自体は分析しない）
- 10KB未満のセッションはスキップ
- プロジェクト名（cwdのディレクトリ名）を自動記録

### 週次KPT
- 作業ログ + git log + 前回KPT を材料に分析
- プロジェクト単体 or 全プロジェクト横断を選択可能
- 前回Tryの達成状況も追跡

### Apply KPT
- Try項目の適用先を自動判定（グローバル or プロジェクト）
- hook化 > スキル化 > CLAUDE.mdルール追加 の優先順位

## カスタマイズ

| 変更したいこと | 編集するファイル |
|---|---|
| 作業ログのフォーマット | `~/.claude/hooks/session-end-analyze.sh` 内のプロンプト |
| KPTのフォーマット | `~/.claude/skills/weekly-kpt/SKILL.md` のStep 3 |
| ダッシュボードのポート | `~/.claude/scripts/kpt-viewer.py` の `PORT` |
| 分析に使うモデル | hookスクリプトの `--model haiku` を変更 |
| スキップする最小ファイルサイズ | hookスクリプトの `10240` を変更 |
