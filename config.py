# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全体設定ファイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VC_REWARD_COINS = 100
VC_REWARD_INTERVAL = 300
CHAT_REWARD_COINS = 1
PVP_FEE_RATE = 0.10

SLOT_BET = 60

# 日付ベースでシードを固定してランダムに台設定を割り当て（1日1回更新）
def get_daily_machines():
    from datetime import date
    seed = int(str(date.today()).replace("-", ""))
    rng = __import__('random').Random(seed)
    settings = []
    for _ in range(10):
        settings.append(rng.randint(1, 6))
    return settings

SLOT_MACHINES_NORMAL  = [1,2,2,3,3,3,4,4,5,6]
SLOT_MACHINES_BONUS   = [2,3,3,4,4,4,5,5,6,6]
SLOT_MACHINES_NEWYEAR = [3,4,4,4,5,5,5,6,6,6]

SLOT_BONUS_DAYS     = [7,17,27,11,22]
SLOT_BONUS_WEEKDAYS = [5,6]
SLOT_NEWYEAR_DATES  = [(12,29),(12,30),(12,31),(1,1),(1,2),(1,3)]

SLOT_SETTINGS = {
    1: {"payout":0.94,"bonus_prob":1/108,"replay_prob":1/2.4,"bell_prob":1/7.0,
        "cherry_prob":1/28,"suika_prob":1/45,"weak_chance_prob":1/130,
        "strong_cherry_prob":1/380,"strong_chance_prob":1/500,
        "cherry_bonus_rate":0.022,"strong_cherry_bonus_rate":0.11,
        "suika_bonus_rate":0.032,"weak_chance_bonus_rate":0.06,
        "strong_chance_bonus_rate":0.19,"bell_bonus_rate":0.005,
        "replay_bonus_rate":0.002},
    2: {"payout":0.98,"bonus_prob":1/103,"replay_prob":1/2.4,"bell_prob":1/7.0,
        "cherry_prob":1/27,"suika_prob":1/44,"weak_chance_prob":1/125,
        "strong_cherry_prob":1/360,"strong_chance_prob":1/470,
        "cherry_bonus_rate":0.024,"strong_cherry_bonus_rate":0.12,
        "suika_bonus_rate":0.036,"weak_chance_bonus_rate":0.065,
        "strong_chance_bonus_rate":0.205,"bell_bonus_rate":0.0055,
        "replay_bonus_rate":0.0025},
    3: {"payout":1.01,"bonus_prob":1/98,"replay_prob":1/2.3,"bell_prob":1/6.8,
        "cherry_prob":1/26,"suika_prob":1/43,"weak_chance_prob":1/120,
        "strong_cherry_prob":1/340,"strong_chance_prob":1/440,
        "cherry_bonus_rate":0.026,"strong_cherry_bonus_rate":0.13,
        "suika_bonus_rate":0.04,"weak_chance_bonus_rate":0.07,
        "strong_chance_bonus_rate":0.22,"bell_bonus_rate":0.006,
        "replay_bonus_rate":0.0028},
    4: {"payout":1.05,"bonus_prob":1/93,"replay_prob":1/2.3,"bell_prob":1/6.8,
        "cherry_prob":1/25,"suika_prob":1/42,"weak_chance_prob":1/115,
        "strong_cherry_prob":1/320,"strong_chance_prob":1/410,
        "cherry_bonus_rate":0.03,"strong_cherry_bonus_rate":0.14,
        "suika_bonus_rate":0.045,"weak_chance_bonus_rate":0.075,
        "strong_chance_bonus_rate":0.23,"bell_bonus_rate":0.007,
        "replay_bonus_rate":0.0035},
    5: {"payout":1.10,"bonus_prob":1/88,"replay_prob":1/2.2,"bell_prob":1/6.5,
        "cherry_prob":1/24,"suika_prob":1/41,"weak_chance_prob":1/110,
        "strong_cherry_prob":1/300,"strong_chance_prob":1/380,
        "cherry_bonus_rate":0.033,"strong_cherry_bonus_rate":0.15,
        "suika_bonus_rate":0.05,"weak_chance_bonus_rate":0.08,
        "strong_chance_bonus_rate":0.245,"bell_bonus_rate":0.008,
        "replay_bonus_rate":0.0038},
    6: {"payout":1.16,"bonus_prob":1/82,"replay_prob":1/2.1,"bell_prob":1/6.5,
        "cherry_prob":1/23,"suika_prob":1/40,"weak_chance_prob":1/105,
        "strong_cherry_prob":1/280,"strong_chance_prob":1/350,
        "cherry_bonus_rate":0.036,"strong_cherry_bonus_rate":0.16,
        "suika_bonus_rate":0.055,"weak_chance_bonus_rate":0.085,
        "strong_chance_bonus_rate":0.26,"bell_bonus_rate":0.009,
        "replay_bonus_rate":0.0045},
}

BONUS_RATIO = {
    "cherry":       {"regular":0.48,"big":0.45,"super":0.07},
    "strong_cherry":{"regular":0.44,"big":0.44,"super":0.12},
    "suika":        {"regular":0.46,"big":0.46,"super":0.08},
    "weak_chance":  {"regular":0.46,"big":0.44,"super":0.10},
    "strong_chance":{"regular":0.38,"big":0.42,"super":0.20},
    "bell":         {"regular":0.50,"big":0.50,"super":0.00},
    "replay":       {"regular":0.50,"big":0.50,"super":0.00},
}

LEGEND_PROB = 1/1500
GOD_PROB    = 1/8000

FREESPIN_GAMES = 10
FREESPIN_BASE_PAYOUT = 115

FREESPIN_TYPES = {
    "REGULAR":{"continue_rate":0.40,"label":"R E G U L A R","color":0x3498db},
    "BIG":    {"continue_rate":0.60,"label":"B I G",        "color":0xe67e22},
    "SUPER":  {"continue_rate":0.75,"label":"S U P E R B I G","color":0x9b59b6},
    "LEGEND": {"continue_rate":0.80,"label":"L E G E N D",  "color":0xf1c40f},
    "GOD":    {"continue_rate":0.90,"label":"G O D",        "color":0xff0000},
}

FREESPIN_YAKUS = {
    # 継続率: REGULAR40% / BIG60% / SUPER70% / LEGEND80% / GOD90%
    "REGULAR":{"replay":1/3,"bell":1/4,"cherry":0.020681,"suika":0.012925,"weak_chance":0.006463,"strong_cherry":1/200,"strong_chance":1/300},
    "BIG":    {"replay":1/3,"bell":1/4,"cherry":0.082906,"suika":0.051816,"weak_chance":0.025908,"strong_cherry":1/200,"strong_chance":1/300},
    "SUPER":  {"replay":1/3,"bell":1/4,"cherry":0.126504,"suika":0.079065,"weak_chance":0.039533,"strong_cherry":1/200,"strong_chance":1/300},
    "LEGEND": {"replay":1/3,"bell":1/4,"cherry":0.187186,"suika":0.116991,"weak_chance":0.058496,"strong_cherry":1/200,"strong_chance":1/300},
    "GOD":    {"replay":1/3,"bell":1/4,"cherry":0.288872,"suika":0.180545,"weak_chance":0.090273,"strong_cherry":1/200,"strong_chance":1/300},
}

FREESPIN_BONUS_RATES = {
    "replay":0.05,"bell":0.05,"cherry":0.30,"suika":0.30,
    "weak_chance":0.50,"strong_cherry":1.00,"strong_chance":1.00,
}

FREESPIN_PAYOUTS = {
    "replay":60,"bell":150,"cherry":60,"suika":180,
    "weak_chance":60,"strong_cherry":60,"strong_chance":60,
}

NORMAL_PAYOUTS = {
    "bell":90,"cherry":60,"suika":120,"strong_cherry":60,
    "replay":60,"weak_chance":60,"strong_chance":60,
}

REELS = {
    "blank":         ["🍋","🍊","🍇"],
    "cherry":        ["🍒","🍋","🍊"],
    "strong_cherry": ["🍒","🍒","🍒"],
    "suika":         ["🍉","🍉","🍉"],
    "bell":          ["🔔","🔔","🔔"],
    "replay":        ["🔄","🔄","🔄"],
    "weak_chance":   ["7️⃣","🍋","🍒"],
    "strong_chance": ["7️⃣","7️⃣","🍊"],
    "regular_bonus": ["⭐","⭐","⭐"],
    "big_bonus":     ["7️⃣","7️⃣","7️⃣"],
    "super_bonus":   ["💎","💎","💎"],
    "legend_bonus":  ["🌐","🌐","🌐"],
    "god_bonus":     ["☯️","☯️","☯️"],
}

# 演出パターン
SLOT_EFFECTS = {
    "miss": [
        "💨 何も起きなかった...",
        "😑 静かな回転...",
        "🌀 リールが虚しく回る...",
        "💤 今日は厳しいな...",
        "😶 何も来ない...",
        "🍃 風だけが通り過ぎた...",
        "👻 気配すら感じない...",
        "🌑 暗い回転...",
        "😮‍💨 はずれ...",
        "🫥 また外れか...",
    ],
    "weak": [
        "💫 なんか来そうな予感...",
        "🌊 水面がさざ波立った...",
        "👀 リールに視線が吸い寄せられる...",
        "💤 うとうとしてたら急に...",
        "🎵 BGMのテンポが少し上がった気がした...",
        "🍒 チェリーの気配...？",
        "🍉 スイカの気配...？",
        "💥 チャンス目の気配...？",
        "🍒 左リールに何か見えた気がした...",
        "🍉 緑色の何かが滑ってくる...？",
    ],
    "medium": [
        "⚡ リールが少し震えた...！",
        "🌀 第三リールがゆっくり止まる...",
        "🔮 何かが起きそうな気がする...！",
        "💥 ドンッ...！",
        "🎯 狙いを定めた...",
        "🌟 リールが一瞬光った...！",
        "😤 力が入る...",
    ],
    "strong": [
        "🔥 熱い...！何かが来る...！",
        "💎 第三リールが輝いている...！！",
        "😱 これは...！！",
        "🌪️ リールが激しく揺れている...！！",
        "👊 来い...！！",
        "⚡⚡ 電流が走った...！！",
        "🏆 何かが変わった...！！",
    ],
    "super": [
        "👁️ リールが止まらない...！！！",
        "💀 これは...見たことない...！！！",
        "🌟🌟🌟 全てが輝いている...！！！",
        "🤯 な、なんだ...！！！",
        "🔥🔥 限界を超えた...！！！",
        "⚡ 神が降りてくる...！！！",
    ],
    "contradiction": {
        "cherry":["🍒 チェリーの気配...？","🍒 左リールにチェリーが見えた...！"],
        "suika": ["🍉 スイカが滑ってきた...？","🍉 緑色の何かが...！"],
        "bell":  ["🔔 ベルの音が聞こえた気がした...","🔔 鐘の音...？"],
    },
    "legend":["🌟 リールが黄金に染まった...！！","👑 伝説が動き出す...！！","✨ 全てが止まった...！！"],
    "god":   ["👁️ .......","💀 何かがおかしい...","🌑 暗転した...！","⚡ 世界が震えた...！！！"],
}

EFFECT_CHANCE = 1.0  # 毎回演出表示
MISS_BONUS_CHANCE = 0.01  # ハズレ演出でも1%でボーナス

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣り設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FISHING_AREAS = {
    "lake":  {"cost":10,  "name":"🏞️ 湖"},
    "river": {"cost":50,  "name":"🏔️ 川"},
    "sea":   {"cost":100, "name":"🌊 海"},
}

ZUKAN_COMPLETE_BONUS = 30000
ZUKAN_ALL_BONUS      = 90000

GOLDEN_CROWN_CHANCE  = 0.05
SHADOW_CHANCE        = 0.01   # 全竿共通1%

# 竿別・影挑戦成功率
SHADOW_SUCCESS_RATES = {
    "bamboo":   0.01,   # 1%
    "glass":    0.02,   # 2%
    "carbon":   0.03,   # 3%
    "titanium": 0.07,   # 7%
    "legend":   0.10,   # 10%
}
BOSS_REWARD          = 100000

# 演出待機時間（秒）
FISHING_WAIT_NORMAL = 3.0   # ゴミ〜レア（通常の溜め）
FISHING_WAIT_SUPER  = 5.0   # スーパーレア以上（長めの溜めで違和感＝期待感）
SLOT_WAIT           = 1.5

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 演出テキスト（全て3行構成）
# レア度には影響しない（見せ方だけ）。結果のレアリティを先に抽選し、
# 下の FISHING_EFFECT_POOL から「そのレアリティ時に出る演出」を％で選ぶ。
# テキストはここを書き換えるだけで変更できる。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FISHING_EFFECTS = {
    # ゴミ系
    "trash_certain": "😅 なんか軽いな…ん？\n　全然手応えがない…\n　　これは…ゴミかも…",
    "trash_lean":    "🎣 糸を投げて待つ…\n　お、何か引っかかった？\n　　引き上げてみよう…",
    # コモン系
    "common_1": "🐟 小さな魚影が見えた\n　そっと近づいてくる…\n　　食いつくか…？",
    "common_2": "💤 静かな水面…\n　あれ？なんか来た？\n　　ちょっと揺れてる…",
    "common_3": "🌊 水面がちょっと揺れた\n　何かいる…？\n　　集中しよう…",
    "common_4": "🎣 いい感じに糸が沈む\n　ゆっくり待つ…\n　　そろそろかな…",
    # ランダム（不意の当たり）
    "random_1": "😴 うとうとしてたら…\n　急に竿が揺れた！\n　　よし、合わせろ！",
    "random_2": "🎵 鼻歌を歌ってたら…\n　突然ガツンと来た！\n　　逃すな…！",
    # アンコモン系
    "uncommon_1": "✨ 水中でキラリと\n　光るものが見えた…！\n　　なんだ…？",
    "uncommon_2": "👀 何かがつついている\n　来るか…来るか…？\n　　今だ…！",
    "uncommon_3": "⚡ 急に強い引きが来た！\n　おっ、悪くない手応え\n　　上げてみよう…！",
    # レア系
    "rare_1": "🌀 じわじわと\n　引っ張られてる…！\n　　これは結構デカいぞ…！",
    "rare_2": "💦 ずっしり重い…！\n　竿がしなってる…\n　　慎重に上げろ…！",
    "rare_3": "🌊 大きな波紋が\n　広がっていく…！\n　　大物の予感だ…！",
    # スーパーレア系
    "sr_1": "🔥 ものすごい引きだ…\n　竿が大きく曲がってる！\n　　逃がすな…！！",
    "sr_2": "😱 水面から何かが\n　飛び出してきた…！\n　　でかい…！！",
    "sr_3": "💎 水底で何かが光って\n　見えた…！\n　　引き上げろ…！！",
    "sr_4": "🦈 巨大な影が\n　近づいてくる…！！\n　　やばい…！！",
    "sr_5": "🌑 深いところから何かが\n　浮き上がってくる…！\n　　正体は…！！",
    # レジェンド系
    "legend_1": "💀 竿が折れそうなくらい\n　引っ張られてる…！！\n　　これは…何かがいる…！！！",
    "legend_2": "🌀 糸がものすごい勢いで\n　出ていく…止まらない！！\n　　引き止めろ…！！！",
    "legend_3": "🤯 こんなの見たことない…\n　化け物か…！！\n　　来い…！！！",
    # 確定演出（プレミア）
    "premium_rare": "💠 水面がきれいに輝いている…\n　何かが応えている…！\n　　これは当たりだ…！",   # レア以上確定
    "golden":       "🌟 水面が黄金に光った…！！\n　これは間違いない…！！\n　　来た…！！！",          # SR以上確定
    "rainbow":      "🌈 水面が虹色に光った…！！\n　これは…！！\n　　伝説だ…！！！",                # レジェンド確定
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# レアリティ別 演出プール（％・各レアリティで合計100）
# 「フェイント許容型」：ゴミ/コモンでもまれに熱い演出、上位でもまれに地味演出。
# 確定演出は対応レアリティで5%だけ出現（出たら○○以上が確定）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FISHING_EFFECT_POOL = {
    "trash": [
        ("trash_certain", 35), ("trash_lean", 35),
        ("common_1", 7), ("common_2", 6), ("common_3", 6), ("common_4", 6),
        ("rare_1", 2), ("rare_2", 2), ("rare_3", 1),                       # フェイント
    ],
    "common": [
        ("common_1", 14), ("common_2", 14), ("common_3", 14), ("common_4", 13),
        ("trash_certain", 8), ("trash_lean", 7),
        ("random_1", 13), ("random_2", 12),
        ("rare_1", 2), ("rare_2", 2), ("rare_3", 1),                       # フェイント
    ],
    "uncommon": [
        ("uncommon_1", 15), ("uncommon_2", 15), ("uncommon_3", 14),
        ("random_1", 8), ("random_2", 8),
        ("common_1", 5), ("common_2", 5), ("common_3", 5), ("common_4", 5),
        ("rare_1", 5), ("rare_2", 5), ("rare_3", 5),                       # フェイント
        ("trash_certain", 3), ("trash_lean", 2),                          # 不意打ち
    ],
    "rare": [
        ("rare_1", 17), ("rare_2", 17), ("rare_3", 16),
        ("uncommon_1", 9), ("uncommon_2", 8), ("uncommon_3", 8),
        ("common_1", 8), ("common_2", 7), ("trash_certain", 5),           # 不意打ち
        ("premium_rare", 5),                                              # 確定（レア以上）
    ],
    "super_rare": [
        ("sr_1", 12), ("sr_2", 12), ("sr_3", 12), ("sr_4", 12), ("sr_5", 12),
        ("rare_1", 9), ("rare_2", 8), ("rare_3", 8),
        ("uncommon_1", 6), ("common_1", 4),                              # 不意打ち
        ("golden", 5),                                                   # 確定（SR以上）
    ],
    "legend": [
        ("legend_1", 15), ("legend_2", 15), ("legend_3", 15),
        ("sr_1", 7), ("sr_2", 7), ("sr_3", 7), ("sr_4", 7), ("sr_5", 7),
        ("rare_1", 10), ("common_1", 5),                                # 不意打ち
        ("rainbow", 5),                                                 # 確定（レジェンド）
    ],
}

RARITY_COLORS = {
    "trash":      0x95a5a6,
    "common":     0xbdc3c7,
    "uncommon":   0x2ecc71,
    "rare":       0x3498db,
    "super_rare": 0x9b59b6,
    "legend":     0xf1c40f,
    "boss":       0xff0000,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 竿別レアリティ出率テーブル（1キャストあたり・合計1.0）
# レア度は「竿」だけで決まる（エリアで変わるのは釣れる魚種と売値のみ）。
# このテーブルの数値を書き換えるだけでバランス調整できる。
#   レア以上計: 竹4.3% / グラス7.5% / カーボン11.5% / チタン16% / 伝説22%
#   レジェンドは竹・グラスでは出ない（0%）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FISHING_RARITY = {
    "bamboo":   {"trash":0.330, "common":0.407, "uncommon":0.220, "rare":0.040, "super_rare":0.003, "legend":0.000},
    "glass":    {"trash":0.290, "common":0.385, "uncommon":0.250, "rare":0.070, "super_rare":0.005, "legend":0.000},
    "carbon":   {"trash":0.260, "common":0.365, "uncommon":0.260, "rare":0.100, "super_rare":0.010, "legend":0.005},
    "titanium": {"trash":0.230, "common":0.340, "uncommon":0.270, "rare":0.130, "super_rare":0.020, "legend":0.010},
    "legend":   {"trash":0.200, "common":0.310, "uncommon":0.270, "rare":0.170, "super_rare":0.030, "legend":0.020},
}

AREA_BOSS = {
    "lake":  {"name":"ネッシー",      "emoji":"🦕","value":BOSS_REWARD},
    "river": {"name":"クラーケン幼体","emoji":"🦑","value":BOSS_REWARD},
    "sea":   {"name":"メガロドン",    "emoji":"🦷","value":BOSS_REWARD},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣り装備設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FISHING_RODS = {
    # "uses" = 竿の耐久性（耐久ポイント）。消費はエリアで変わる（ROD_DURABILITY_COST）。
    "bamboo":   {"name":"竹竿",          "price":0,       "uses":999999, "emoji":"🎋",
                 "sea_ban":True, "river_ban":True},
    "glass":    {"name":"グラスロッド",   "price":2000,    "uses":400,    "emoji":"🎣",
                 "sea_ban":True},
    "carbon":   {"name":"カーボンロッド", "price":8000,    "uses":200,    "emoji":"🎣",
                 "sea_ban":False},
    "titanium": {"name":"チタンロッド",   "price":30000,   "uses":400,    "emoji":"🎣",
                 "sea_ban":False},
    "legend":   {"name":"伝説の釣り竿",   "price":100000,  "uses":500,    "emoji":"🎣",
                 "sea_ban":False},
}

# 竿の耐久消費量（エリア別）：海ほど早く消耗する
ROD_DURABILITY_COST = {"lake": 1, "river": 2, "sea": 3}

FISHING_REELS = {
    # 案A: リールは「主の出現率UP」と「金冠UP」を担当（シンプル）
    # ※実際の数値はゲーム内では非表示（バランス用の内部値）
    "spinning": {"name":"スピニングリール", "price":0,     "uses":999999, "emoji":"🎡",
                 "boss_appear_bonus":0.000, "crown_bonus":0.000},
    "bait":     {"name":"ベイトリール",     "price":500,   "uses":200,    "emoji":"🎡",
                 "boss_appear_bonus":0.001, "crown_bonus":0.005},
    "drag":     {"name":"ドラグ付きリール", "price":1500,  "uses":200,    "emoji":"🎡",
                 "boss_appear_bonus":0.002, "crown_bonus":0.010},
    "electric": {"name":"電動リール",       "price":4000,  "uses":200,    "emoji":"🎡",
                 "boss_appear_bonus":0.003, "crown_bonus":0.015},
    "magnet":   {"name":"マグネットリール", "price":8000,  "uses":200,    "emoji":"🎡",
                 "boss_appear_bonus":0.005, "crown_bonus":0.020},
}

FISHING_LINES = {
    # 金冠は最大+2%（0.5刻み）。主成功はライン据え置き。※数値はゲーム内非表示
    "nylon":    {"name":"ナイロンライン",      "price":0,     "uses":999999, "emoji":"🧵",
                 "crown_bonus":0.000, "boss_success_bonus":0.0},
    "fluoro":   {"name":"フロロカーボンライン","price":400,   "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.005, "boss_success_bonus":0.0},
    "pe":       {"name":"PEライン",            "price":1000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.010, "boss_success_bonus":0.0},
    "super_pe": {"name":"スーパーPEライン",    "price":3000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.015, "boss_success_bonus":0.0},
    "clear":    {"name":"透明ライン",          "price":6000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.020, "boss_success_bonus":0.10},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 魚リスト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LAKE_FISH = [
    {"name":"長靴",           "rarity":"trash",      "value":0,     "emoji":"👟"},
    {"name":"空き缶",         "rarity":"trash",      "value":0,     "emoji":"🥫"},
    {"name":"ペットボトル",   "rarity":"trash",      "value":0,     "emoji":"🍶"},
    {"name":"タイヤ",         "rarity":"trash",      "value":0,     "emoji":"⭕"},
    {"name":"傘",             "rarity":"trash",      "value":0,     "emoji":"☂️"},
    {"name":"ビニール袋",     "rarity":"trash",      "value":0,     "emoji":"🛍️"},
    {"name":"割れた瓶",       "rarity":"trash",      "value":0,     "emoji":"🍾"},
    {"name":"古い帽子",       "rarity":"trash",      "value":0,     "emoji":"🎩"},
    {"name":"メダカ",         "rarity":"common",     "value":2,     "emoji":"🐟"},
    {"name":"カワニナ",       "rarity":"common",     "value":3,     "emoji":"🐚"},
    {"name":"ヌカエビ",       "rarity":"common",     "value":3,     "emoji":"🦐"},
    {"name":"スジエビ",       "rarity":"common",     "value":3,     "emoji":"🦐"},
    {"name":"ヒメダカ",       "rarity":"common",     "value":4,     "emoji":"🐟"},
    {"name":"モロコ",         "rarity":"common",     "value":4,     "emoji":"🐟"},
    {"name":"ウキゴリ",       "rarity":"common",     "value":5,     "emoji":"🐟"},
    {"name":"クチボソ",       "rarity":"common",     "value":5,     "emoji":"🐟"},
    {"name":"タモロコ",       "rarity":"common",     "value":5,     "emoji":"🐟"},
    {"name":"ゲンゴロウ",     "rarity":"common",     "value":5,     "emoji":"🪲"},
    {"name":"タナゴ",         "rarity":"common",     "value":6,     "emoji":"🐟"},
    {"name":"ヨシノボリ",     "rarity":"common",     "value":6,     "emoji":"🐟"},
    {"name":"ドジョウ",       "rarity":"common",     "value":7,     "emoji":"🐍"},
    {"name":"ウグイ",         "rarity":"common",     "value":7,     "emoji":"🐟"},
    {"name":"カワムツ",       "rarity":"common",     "value":8,     "emoji":"🐟"},
    {"name":"オイカワ",       "rarity":"common",     "value":8,     "emoji":"🐟"},
    {"name":"ブルーギル",     "rarity":"common",     "value":8,     "emoji":"🐟"},
    {"name":"フナ",           "rarity":"common",     "value":9,     "emoji":"🐟"},
    {"name":"カジカ",         "rarity":"common",     "value":10,    "emoji":"🐟"},
    {"name":"コイ",           "rarity":"common",     "value":12,    "emoji":"🐠"},
    {"name":"ザリガニ",       "rarity":"common",     "value":15,    "emoji":"🦞"},
    {"name":"アメリカザリガニ","rarity":"uncommon",   "value":5,     "emoji":"🦞"},
    {"name":"ゲンゴロウブナ", "rarity":"uncommon",   "value":7,     "emoji":"🐟"},
    {"name":"ニゴイ",         "rarity":"uncommon",   "value":8,     "emoji":"🐟"},
    {"name":"ヘラブナ",       "rarity":"uncommon",   "value":9,     "emoji":"🐟"},
    {"name":"コクチバス",     "rarity":"uncommon",   "value":10,    "emoji":"🐟"},
    {"name":"ワカサギ",       "rarity":"uncommon",   "value":12,    "emoji":"🐟"},
    {"name":"バス",           "rarity":"uncommon",   "value":13,    "emoji":"🐟"},
    {"name":"テナガエビ",     "rarity":"uncommon",   "value":14,    "emoji":"🦐"},
    {"name":"ハス",           "rarity":"uncommon",   "value":15,    "emoji":"🐟"},
    {"name":"ライギョ",       "rarity":"uncommon",   "value":16,    "emoji":"🐍"},
    {"name":"ヤマメ",         "rarity":"uncommon",   "value":18,    "emoji":"🐟"},
    {"name":"アユ",           "rarity":"uncommon",   "value":20,    "emoji":"🐟"},
    {"name":"ナマズ",         "rarity":"uncommon",   "value":22,    "emoji":"🐡"},
    {"name":"イワナ",         "rarity":"uncommon",   "value":24,    "emoji":"🐟"},
    {"name":"アメマス",       "rarity":"uncommon",   "value":25,    "emoji":"🐟"},
    {"name":"ニジマス",       "rarity":"uncommon",   "value":27,    "emoji":"🐟"},
    {"name":"ビワマス",       "rarity":"uncommon",   "value":30,    "emoji":"🐟"},
    {"name":"スッポン",       "rarity":"uncommon",   "value":33,    "emoji":"🐢"},
    {"name":"ウナギ",         "rarity":"uncommon",   "value":38,    "emoji":"🐍"},
    {"name":"マゴイ",         "rarity":"uncommon",   "value":45,    "emoji":"🐠"},
    {"name":"タイワンドジョウ","rarity":"rare",       "value":20,    "emoji":"🐍"},
    {"name":"ソウギョ",       "rarity":"rare",       "value":25,    "emoji":"🐟"},
    {"name":"ハクレン",       "rarity":"rare",       "value":28,    "emoji":"🐟"},
    {"name":"アオウオ",       "rarity":"rare",       "value":30,    "emoji":"🐟"},
    {"name":"コウライケツギョ","rarity":"rare",       "value":35,    "emoji":"🐟"},
    {"name":"チョウザメ",     "rarity":"rare",       "value":45,    "emoji":"🐟"},
    {"name":"スッポンモドキ", "rarity":"rare",       "value":55,    "emoji":"🐢"},
    {"name":"イトウ",         "rarity":"rare",       "value":70,    "emoji":"🐟"},
    {"name":"オオサンショウウオ","rarity":"rare",     "value":90,    "emoji":"🦎"},
    {"name":"ピラルク",       "rarity":"rare",       "value":120,   "emoji":"🐟"},
    {"name":"ダントウボウ",   "rarity":"super_rare", "value":200,   "emoji":"🐟"},
    {"name":"アリゲーターガー","rarity":"super_rare","value":300,   "emoji":"🐊"},
    {"name":"ビワコオオナマズ","rarity":"super_rare","value":450,   "emoji":"🐡"},
    {"name":"オオウナギ",     "rarity":"super_rare", "value":600,   "emoji":"🐍"},
    {"name":"アカメ",         "rarity":"super_rare", "value":950,   "emoji":"🐟"},
    {"name":"幻のイトウ",     "rarity":"legend",     "value":3000,  "emoji":"👑"},
    {"name":"ガーパイク",     "rarity":"legend",     "value":5000,  "emoji":"🐉"},
    {"name":"黄金のコイ",     "rarity":"legend",     "value":8000,  "emoji":"✨"},
]

RIVER_FISH = [
    {"name":"長靴",              "rarity":"trash",      "value":0,     "emoji":"👟"},
    {"name":"空き缶",            "rarity":"trash",      "value":0,     "emoji":"🥫"},
    {"name":"流木",              "rarity":"trash",      "value":0,     "emoji":"🪵"},
    {"name":"古い釣り竿",        "rarity":"trash",      "value":0,     "emoji":"🎣"},
    {"name":"錆びたナイフ",      "rarity":"trash",      "value":0,     "emoji":"🔪"},
    {"name":"ペットボトル",      "rarity":"trash",      "value":0,     "emoji":"🍶"},
    {"name":"タイヤ",            "rarity":"trash",      "value":0,     "emoji":"⭕"},
    {"name":"ビニール袋",        "rarity":"trash",      "value":0,     "emoji":"🛍️"},
    {"name":"カワバタモロコ",    "rarity":"common",     "value":10,    "emoji":"🐟"},
    {"name":"ヌマチチブ",        "rarity":"common",     "value":12,    "emoji":"🐟"},
    {"name":"ヨシノボリ",        "rarity":"common",     "value":14,    "emoji":"🐟"},
    {"name":"アカザ",            "rarity":"common",     "value":16,    "emoji":"🐟"},
    {"name":"スナヤツメ",        "rarity":"common",     "value":18,    "emoji":"🐟"},
    {"name":"シマドジョウ",      "rarity":"common",     "value":20,    "emoji":"🐟"},
    {"name":"ムギツク",          "rarity":"common",     "value":22,    "emoji":"🐟"},
    {"name":"ズナガニゴイ",      "rarity":"common",     "value":24,    "emoji":"🐟"},
    {"name":"ウグイ",            "rarity":"common",     "value":25,    "emoji":"🐟"},
    {"name":"タカハヤ",          "rarity":"common",     "value":26,    "emoji":"🐟"},
    {"name":"アブラハヤ",        "rarity":"common",     "value":27,    "emoji":"🐟"},
    {"name":"カワヤツメ",        "rarity":"common",     "value":28,    "emoji":"🐟"},
    {"name":"ニゴイ",            "rarity":"common",     "value":29,    "emoji":"🐟"},
    {"name":"アカヒレタビラ",    "rarity":"common",     "value":30,    "emoji":"🐟"},
    {"name":"オイカワ",          "rarity":"common",     "value":32,    "emoji":"🐟"},
    {"name":"イチモンジタナゴ",  "rarity":"common",     "value":34,    "emoji":"🐟"},
    {"name":"ヤリタナゴ",        "rarity":"common",     "value":35,    "emoji":"🐟"},
    {"name":"カネヒラ",          "rarity":"common",     "value":37,    "emoji":"🐟"},
    {"name":"カワムツ",          "rarity":"common",     "value":40,    "emoji":"🐟"},
    {"name":"カジカ",            "rarity":"common",     "value":45,    "emoji":"🐟"},
    {"name":"オヤニラミ",        "rarity":"uncommon",   "value":30,    "emoji":"🐟"},
    {"name":"マルタウグイ",      "rarity":"uncommon",   "value":35,    "emoji":"🐟"},
    {"name":"ギギ",              "rarity":"uncommon",   "value":40,    "emoji":"🐟"},
    {"name":"ゴギ",              "rarity":"uncommon",   "value":50,    "emoji":"🐟"},
    {"name":"ライギョ",          "rarity":"uncommon",   "value":55,    "emoji":"🐍"},
    {"name":"ナマズ",            "rarity":"uncommon",   "value":60,    "emoji":"🐡"},
    {"name":"チョウザメ幼魚",    "rarity":"uncommon",   "value":65,    "emoji":"🐟"},
    {"name":"アマゴ",            "rarity":"uncommon",   "value":70,    "emoji":"🐟"},
    {"name":"ニジマス",          "rarity":"uncommon",   "value":75,    "emoji":"🐟"},
    {"name":"イワナ",            "rarity":"uncommon",   "value":80,    "emoji":"🐟"},
    {"name":"アメマス",          "rarity":"uncommon",   "value":85,    "emoji":"🐟"},
    {"name":"ヤマメ",            "rarity":"uncommon",   "value":88,    "emoji":"🐟"},
    {"name":"スッポン",          "rarity":"uncommon",   "value":90,    "emoji":"🐢"},
    {"name":"アユ",              "rarity":"uncommon",   "value":92,    "emoji":"🐟"},
    {"name":"ビワマス",          "rarity":"uncommon",   "value":95,    "emoji":"🐟"},
    {"name":"サクラマス",        "rarity":"uncommon",   "value":100,   "emoji":"🐟"},
    {"name":"ヒラメ",            "rarity":"uncommon",   "value":105,   "emoji":"🐟"},
    {"name":"スズキ",            "rarity":"uncommon",   "value":110,   "emoji":"🐟"},
    {"name":"ウナギ",            "rarity":"uncommon",   "value":120,   "emoji":"🐍"},
    {"name":"サクラマス",        "rarity":"uncommon",   "value":130,   "emoji":"🐟"},
    {"name":"アリゲーターガー幼魚","rarity":"rare",     "value":80,    "emoji":"🐊"},
    {"name":"ブラウントラウト",  "rarity":"rare",       "value":100,   "emoji":"🐟"},
    {"name":"カラフトマス",      "rarity":"rare",       "value":120,   "emoji":"🐟"},
    {"name":"サツキマス",        "rarity":"rare",       "value":150,   "emoji":"🐟"},
    {"name":"シロザケ",          "rarity":"rare",       "value":180,   "emoji":"🐟"},
    {"name":"オオウナギ",        "rarity":"rare",       "value":200,   "emoji":"🐍"},
    {"name":"タイメン幼魚",      "rarity":"rare",       "value":250,   "emoji":"🐟"},
    {"name":"イトウ",            "rarity":"rare",       "value":300,   "emoji":"🐟"},
    {"name":"コロンビアチョウザメ","rarity":"rare",     "value":350,   "emoji":"🐟"},
    {"name":"ゴールデントラウト","rarity":"rare",       "value":470,   "emoji":"✨"},
    {"name":"ビワコオオナマズ",  "rarity":"super_rare", "value":700,   "emoji":"🐡"},
    {"name":"ベルーガ幼魚",      "rarity":"super_rare", "value":900,   "emoji":"🐟"},
    {"name":"タイメン",          "rarity":"super_rare", "value":1200,  "emoji":"🐟"},
    {"name":"アカメ",            "rarity":"super_rare", "value":1800,  "emoji":"🐟"},
    {"name":"オオカワウソ",      "rarity":"super_rare", "value":2400,  "emoji":"🦦"},
    {"name":"ゴライアスタイガーフィッシュ","rarity":"legend","value":7500,"emoji":"😱"},
    {"name":"ベルーガ",          "rarity":"legend",     "value":11000, "emoji":"👑"},
    {"name":"ブルシャーク",      "rarity":"legend",     "value":15000, "emoji":"🦈"},
]

SEA_FISH = [
    {"name":"長靴",          "rarity":"trash",      "value":0,     "emoji":"👟"},
    {"name":"空き缶",        "rarity":"trash",      "value":0,     "emoji":"🥫"},
    {"name":"古い錨",        "rarity":"trash",      "value":0,     "emoji":"⚓"},
    {"name":"謎の瓶",        "rarity":"trash",      "value":30,    "emoji":"🍾"},
    {"name":"海賊の地図",    "rarity":"trash",      "value":30,    "emoji":"🗺️"},
    {"name":"錆びた缶詰",    "rarity":"trash",      "value":0,     "emoji":"🥫"},
    {"name":"ともせの眼鏡",  "rarity":"trash",      "value":0,     "emoji":"👓"},
    {"name":"ビニール袋",    "rarity":"trash",      "value":0,     "emoji":"🛍️"},
    {"name":"カタクチイワシ","rarity":"common",     "value":30,    "emoji":"🐟"},
    {"name":"マイワシ",      "rarity":"common",     "value":35,    "emoji":"🐟"},
    {"name":"イワシ",        "rarity":"common",     "value":40,    "emoji":"🐟"},
    {"name":"スズメダイ",    "rarity":"common",     "value":42,    "emoji":"🐟"},
    {"name":"ニシン",        "rarity":"common",     "value":45,    "emoji":"🐟"},
    {"name":"ハゼ",          "rarity":"common",     "value":48,    "emoji":"🐟"},
    {"name":"キス",          "rarity":"common",     "value":50,    "emoji":"🐟"},
    {"name":"ウミタナゴ",    "rarity":"common",     "value":52,    "emoji":"🐟"},
    {"name":"アジ",          "rarity":"common",     "value":55,    "emoji":"🐟"},
    {"name":"ベラ",          "rarity":"common",     "value":58,    "emoji":"🐟"},
    {"name":"サバ",          "rarity":"common",     "value":62,    "emoji":"🐟"},
    {"name":"ムラソイ",      "rarity":"common",     "value":65,    "emoji":"🐟"},
    {"name":"サンマ",        "rarity":"common",     "value":68,    "emoji":"🐟"},
    {"name":"イサキ",        "rarity":"common",     "value":72,    "emoji":"🐟"},
    {"name":"タケノコメバル","rarity":"common",     "value":75,    "emoji":"🐟"},
    {"name":"コチ",          "rarity":"common",     "value":78,    "emoji":"🐟"},
    {"name":"メバル",        "rarity":"common",     "value":82,    "emoji":"🐟"},
    {"name":"ホウボウ",      "rarity":"common",     "value":85,    "emoji":"🐟"},
    {"name":"カサゴ",        "rarity":"common",     "value":88,    "emoji":"🐡"},
    {"name":"クロダイ",      "rarity":"common",     "value":95,    "emoji":"🐟"},
    {"name":"イカ",          "rarity":"uncommon",   "value":80,    "emoji":"🦑"},
    {"name":"カワハギ",      "rarity":"uncommon",   "value":90,    "emoji":"🐡"},
    {"name":"タコ",          "rarity":"uncommon",   "value":100,   "emoji":"🐙"},
    {"name":"カツオ",        "rarity":"uncommon",   "value":110,   "emoji":"🐟"},
    {"name":"アイナメ",      "rarity":"uncommon",   "value":120,   "emoji":"🐟"},
    {"name":"タチウオ",      "rarity":"uncommon",   "value":130,   "emoji":"🐟"},
    {"name":"サワラ",        "rarity":"uncommon",   "value":140,   "emoji":"🐟"},
    {"name":"スズキ",        "rarity":"uncommon",   "value":150,   "emoji":"🐟"},
    {"name":"マゴチ",        "rarity":"uncommon",   "value":160,   "emoji":"🐟"},
    {"name":"ヒラマサ",      "rarity":"uncommon",   "value":170,   "emoji":"🐟"},
    {"name":"ヒラメ",        "rarity":"uncommon",   "value":180,   "emoji":"🐟"},
    {"name":"カンパチ",      "rarity":"uncommon",   "value":190,   "emoji":"🐟"},
    {"name":"マダイ",        "rarity":"uncommon",   "value":200,   "emoji":"🐟"},
    {"name":"ハタ",          "rarity":"uncommon",   "value":210,   "emoji":"🐟"},
    {"name":"オニオコゼ",    "rarity":"uncommon",   "value":220,   "emoji":"🐡"},
    {"name":"シマアジ",      "rarity":"uncommon",   "value":230,   "emoji":"🐟"},
    {"name":"イシダイ",      "rarity":"uncommon",   "value":240,   "emoji":"🐟"},
    {"name":"マハタ",        "rarity":"uncommon",   "value":260,   "emoji":"🐟"},
    {"name":"クエ",          "rarity":"uncommon",   "value":280,   "emoji":"🐟"},
    {"name":"ブリ",          "rarity":"uncommon",   "value":300,   "emoji":"🐟"},
    {"name":"クロシビカマス","rarity":"rare",       "value":200,   "emoji":"🐟"},
    {"name":"アブラソコムツ","rarity":"rare",       "value":240,   "emoji":"🐟"},
    {"name":"オオニベ",      "rarity":"rare",       "value":280,   "emoji":"🐟"},
    {"name":"バラムツ",      "rarity":"rare",       "value":300,   "emoji":"🐟"},
    {"name":"アカムツ",      "rarity":"rare",       "value":350,   "emoji":"🐟"},
    {"name":"キンメダイ",    "rarity":"rare",       "value":380,   "emoji":"🐟"},
    {"name":"イシナギ",      "rarity":"rare",       "value":420,   "emoji":"🐟"},
    {"name":"ヨシキリザメ",  "rarity":"rare",       "value":480,   "emoji":"🦈"},
    {"name":"クロマグロ",    "rarity":"rare",       "value":550,   "emoji":"🐟"},
    {"name":"カジキ",        "rarity":"rare",       "value":750,   "emoji":"🐟"},
    {"name":"チョウチンアンコウ","rarity":"super_rare","value":1500,"emoji":"🎣"},
    {"name":"タカアシガニ",  "rarity":"super_rare", "value":2000,  "emoji":"🦀"},
    {"name":"リュウグウノツカイ","rarity":"super_rare","value":2500,"emoji":"🐉"},
    {"name":"ダイオウイカ",  "rarity":"super_rare", "value":4000,  "emoji":"🦑"},
    {"name":"メガマウスザメ","rarity":"super_rare", "value":5000,  "emoji":"🦈"},
    {"name":"ホホジロザメ",  "rarity":"legend",     "value":15000, "emoji":"🦈"},
    {"name":"シーラカンス",  "rarity":"legend",     "value":22500, "emoji":"👑"},
    {"name":"ラブカ",        "rarity":"legend",     "value":30000, "emoji":"😱"},
]

CHINCHIRO_AI_PAYOUT = 0.90


# 釣り演出（当たり待ち）の共通色。
# レアリティ別の色だと結果が出る前にレア度が分かってしまうため、
# 当たり待ち中は必ずこの中立色を使う（結果表示はレアリティ色のまま）。
SUSPENSE_COLOR = 0x2B2D31
