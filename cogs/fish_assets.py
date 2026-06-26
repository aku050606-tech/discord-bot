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
# 注: card_url は魚名だけで引く（エリア非依存）。同名魚（アカメ等が湖・川両方に存在）も
#     同じカードを共用するので接頭辞なしスラッグで登録する。
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
    # 湖 legend
    "幻のイトウ": "lake_legend_huchen",
    "ガーパイク": "lake_legend_gar",
    "黄金のコイ": "lake_legend_golden_carp",
    # 湖 super_rare
    "ダントウボウ": "lake_super_dantoubou",
    "アロワナ": "lake_super_arowana",
    # 湖・川 共用 super_rare（同名なので接頭辞なしで共用）
    "アカメ": "akame",
    "ビワコオオナマズ": "biwa_catfish",
    "オオウナギ": "giant_eel",
    # 川 super_rare
    "ベルーガ幼魚": "river_super_beluga_juvenile",
    "タイメン": "river_super_taimen",
    "オオカワウソ": "river_super_giant_otter",
    # 川 legend
    "ゴライアスタイガーフィッシュ": "river_legend_goliath_tigerfish",
    "ベルーガ": "river_legend_beluga",
    "ブルシャーク": "river_legend_bull_shark",
}

# ── エリアボス → カード（通常時）──
BOSS_CARD = {
    "lake":  "lake_boss_nessie",
    "river": "river_boss_kraken",
    "sea":   "sea_boss_megalodon",
}

# ── 赤い月の主（血月ボス）→ カード ──
BLOODMOON_BOSS_CARD = {
    "lake":  "lake_bloodmoon_eye",
    "river": "river_bloodmoon_serpent",
    "sea":   "sea_bloodmoon_king",
}

# 下位共通カード（全エリア兼用）。ドット版生成済み（.png）。
LOW_SHARED = {
    "common": "low_common", "uncommon": "low_uncommon", "rare": "low_rare",
}

def scene_url(effect_key: str):
    slug = EFFECT_SCENE.get(effect_key)
    return f"{RAW_BASE}scenes/{slug}.jpg" if slug else None

def shadow_url():
    return f"{RAW_BASE}cards/shadow_premium.jpg"

def nushi_url():
    """ぬし演出：水中にでかい影が潜む情景。"""
    return f"{RAW_BASE}scenes/scene_nushi.jpg"

def trash_bag_url():
    """通常ゴミの結果カード（ゴミ袋）。"""
    return f"{RAW_BASE}cards/trash_bag.png"

def treasure_map_url():
    """宝の地図を引いた時の結果カード。"""
    return f"{RAW_BASE}cards/treasure_map.png"

def storm_chest_url():
    """嵐の宝箱の結果カード。"""
    return f"{RAW_BASE}cards/storm_chest.png"

def boss_card_url(area: str, is_blood_moon: bool = False):
    """エリアボス／血月ボスの結果カード。無ければ None（画像なし）。"""
    table = BLOODMOON_BOSS_CARD if is_blood_moon else BOSS_CARD
    slug = table.get(area)
    return f"{RAW_BASE}cards/{slug}.png" if slug else None


def card_url(fish_name: str, rarity: str):
    """個別カード優先 → 下位共通 → なければ None（テキストのみ）。"""
    slug = CARD_SLUG_BY_NAME.get(fish_name)
    if slug:
        return f"{RAW_BASE}cards/{slug}.png"
    low = LOW_SHARED.get(rarity)
    if low:
        return f"{RAW_BASE}cards/{low}.png"
    return None
