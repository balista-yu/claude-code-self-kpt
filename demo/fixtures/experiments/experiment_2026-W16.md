# Experiments: 2026年 第16週

## E1: 大きな変更前に AskUserQuestion を先行
- status: in_progress
- started: 2026-04-13
- duration: 1週
- hypothesis: 大きな変更（ファイル複数・構造変更）の前に AskUserQuestion で方針合わせをすれば、手戻り（ユーザー修正指示）が減る
- success_criteria: 該当セッションで「仕様理解」カテゴリの指摘が週内 0 件
- measurement: session-reviews の指摘カテゴリ集計
- risk: 小さい変更でも過剰に確認してテンポが落ちる
- scope: global

## E2: Bash コマンド実行前の説明一文
- status: in_progress
- started: 2026-04-13
- duration: 1週
- hypothesis: Bash 実行前に「何をなぜやるか」の一文を書くと、誤実行時の発見が早まる
- success_criteria: 該当セッションで「誤実行」カテゴリの指摘ゼロ、かつ説明記述を 80% 以上のセッションで実施
- measurement: 自己申告（KPT時に振り返り）
- risk: 冗長化して読みづらくなる

## E3: テスト追加を実装より先にやる（TDD 寄り）
- status: in_progress
- started: 2026-04-13
- duration: 1週
- hypothesis: バグ修正・新機能で、テストを先に書く／先に fail させる運用にすればテスト未実行での push が減る
- success_criteria: 「テスト未実行」カテゴリ指摘が前週比 50% 以上減
- measurement: session-reviews の指摘カテゴリ集計
- risk: 軽微な変更にもオーバーヘッドがかかる
- scope: global
