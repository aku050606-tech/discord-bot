# BOTORI Profile UI v2

プロフィール画像は `assets/profile/backgrounds/` のテーマ画像と、`cogs/member_onboarding.py` の描画レイヤーを合成して生成します。

## 収録テーマ
DEVI / SAKURA / CYBER / SPACE / OCEAN / FANTASY / CITY / HELL / SNOW / FOREST

## 再生成
背景素材を調整した場合は次を実行してください。

```bash
python tools/generate_profile_assets.py
```

既存プロフィールは Discord の `/admin` → メンバー管理 → プロフィール一括更新で反映できます。
