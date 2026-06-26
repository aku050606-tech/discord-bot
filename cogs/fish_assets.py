"""釣り演出の画像URL解決。
情景(scene)・プレミア影(shadow)・結果カード(card)を GitHub raw URL で返す。
画像が用意されてない魚は None を返す＝呼び出し側でテキストのみにフォールバック。
"""

RAW_BASE = "https://raw.githubusercontent.com/aku050606-tech/discord-bot/main/assets/fish/"

# ── 演出プールの key → 情景画像（緊張度でグループ化）──
# S0…ゴミ感 / S1静か / S2小当たり / S3確かな引き / S4大物 / S5怪物級
# C1きらめき(レア+確定) / C2黄金(SR+確定) / C3虹(レジェ確定)
EFFECT_SCENE = {
    "trash_certain": "scene_s0",
    "trash_lean":    "scene_s1",
    "common_1": "scene_s2", "common_2": "scene_s1",
    "common_3": "scene_s2", "common_4": "scene_s1",
    "random_1": "scene_s2", "random_2": "scene_s2",
    "uncommon_1": "scene_s2", "uncommon_2": "scene_s3", "uncommon_3": "scene_s3",
    "rare_1": "scene_s3", "rare_2": "scene_s3", "rare_3": "scene_s3",
    "sr_1": "scene_s4", "sr_2": "scene_s4", "sr_3": "scene_s4",
    "sr_4": "scene_s4", "sr_5": "scene_s4",
    "legend_1": "scene_s5", "legend_2": "scene_s5", "legend_3": "scene_s5",
    "premium_rare": "scene_c1",
    "golden":       "scene_c2",
    "rainbow":      "scene_c3",
}

# ── 魚名 → 個別カードのスラッグ（用意できてる分だけ。無い魚はテキストのみ）──
CARD_SLUG_BY_NAME = {
    # 海 legend
    "ホホジロザメ": "sea_legend_great_white",
    "シーラカンス": "sea_legend_coelacanth",
    "ラブカ": "sea_legend_frilled_shark",
    # 海 super_rare
    "リュウグウノツカイ": "sea_super_oarfish",
    "チョウチンアンコウ": "sea_super_anglerfish",
    "ダイオウイカ": "sea_super_giant_squid",
    "タカアシガニ": "sea_super_spider_crab",
    "メガマウスザメ": "sea_super_megamouth",
}

# 下位共通カード（全エリア兼用）。用意できてる拡張子で。今はまだドット版未生成なら None 運用可。
LOW_SHARED = {
    # "common": "low_common", "uncommon": "low_uncommon", "rare": "low_rare",
}

def scene_url(effect_key: str):
    slug = EFFECT_SCENE.get(effect_key)
    return f"{RAW_BASE}scenes/{slug}.jpg" if slug else None

def shadow_url():
    return f"{RAW_BASE}cards/shadow_premium.jpg"

def card_url(fish_name: str, rarity: str):
    """個別カード優先 → 下位共通 → なければ None（テキストのみ）。"""
    slug = CARD_SLUG_BY_NAME.get(fish_name)
    if slug:
        return f"{RAW_BASE}cards/{slug}.png"
    low = LOW_SHARED.get(rarity)
    if low:
        return f"{RAW_BASE}cards/{low}.jpg"
    return None
