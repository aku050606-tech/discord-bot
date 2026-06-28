# 街道シミュレーターの見方

## まず見る場所
`tools/sim_reports/plain_1000_seed1_v4_xptable.txt` に、平原1000探索のサンプル結果を入れています。

## 自分で実行する方法
PowerShellでBotフォルダに移動してから実行します。

```powershell
cd "C:\Users\aku05\Desktop\discord bot\discord-bot"
python tools\simulate_land.py --area plain --runs 1000 --seed 1
```

## 表示される項目
- 最終Lv：1000探索後にどこまで上がったか
- 総XP：探索全体で得た経験値
- イベント：雑魚戦/中ボス/大ボス/ストーリーなどの発生回数
- イベント内サブ結果：イベント中に追加で起きたアイテム/戦闘/コインなど
- 消耗品：落ちた消耗品数
- 装備ドロップ：落ちた装備数

## 今回の注意
このシミュレーターはイベント・サブ抽選・戦闘報酬・アイテムドロップを含みます。
HP推移や実戦の死亡率はまだ簡易扱いです。
