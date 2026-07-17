# Profile card assets

- `backgrounds/*.png`: 背景画像のみ。UI枠や文字を焼き込まない。
- `overlays/glass_overlay.png`: 全背景で共通使用するプロフィールUI素材。
- `cogs/member_onboarding.py`: 背景→共通UI→可変文字/アバターの順で合成。

現行レイアウト:
1. PROFILE
2. ABOUT ME / ABOUT ME+ / RANKING
3. BADGES

旧4分割レイアウト、旧「好きなこと」下段、旧レガシー描画関数は削除済み。
