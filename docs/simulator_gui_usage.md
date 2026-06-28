# 街道シミュレーター GUI版

## 起動方法

一番簡単なのはこれです。

1. ZIPを解凍する
2. `tools/run_land_simulator_gui.bat` をダブルクリック

PowerShellから起動する場合は、Botフォルダで以下を実行します。

```powershell
python tools\simulator_gui.py
```

## できること

- 平原/森/山を選択
- 探索回数を選択
- 開始レベルを指定
- Seedを指定
- 結果を画面で確認
- txt/csvレポートを `tools/sim_reports/` に保存

## 注意

このPhase1版は、遭遇した敵を倒した前提で、報酬・経験値・ドロップ期待値を見るためのツールです。
死亡率、実戦闘勝率、回復アイテム使用量の精密シミュレーションは次フェーズで拡張予定です。
