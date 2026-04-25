# Claude Code 自己改善システム (demo virtual-dotclaude)

これは demo 用の virtual `~/.claude/CLAUDE.md` 模擬ファイル。
週次KPTの Try 実装判定ロジックを本番と同じように動作させるため、前週 Try の反映状態を再現する。

## セッション開始時
- `~/.claude/kpt-data/kpt/` の最新KPTを確認し、Try項目を意識すること
- 特に前回Problemに挙がった項目は繰り返さないよう注意すること

## KPT運用
- `/weekly-kpt` で自分自身の週次振り返りを実行（推奨: 毎週金曜）
- `/apply-kpt` でTry項目をhook/skill/CLAUDE.mdに実装
- `/forward-kpt` で「攻めの一手」Experimentを週次で仕込む
- 改善は hook化 > skill化 > CLAUDE.mdルール の優先順位で

<!-- KPT W16 T2: コミット粒度ルール追記 (2026-04-13) -->
## コミット運用ルール
- コミットは論理単位ごとに分割する
- リファクタは「責務分離」「命名整理」「テスト修正」を別コミットで作成する
- 作業完了後にまとめて1コミットにしない
