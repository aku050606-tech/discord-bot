# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全体設定ファイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VC_REWARD_COINS = 100
VC_REWARD_INTERVAL = 300
CHAT_REWARD_COINS = 1
PVP_FEE_RATE = 0.10

SLOT_BET = 60

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
    "REGULAR":{"replay":1/3,"bell":1/4,"cherry":1/25,"suika":1/40,"weak_chance":1/80,"strong_cherry":1/200,"strong_chance":1/300},
    "BIG":    {"replay":1/3,"bell":1/4,"cherry":1/18,"suika":1/28,"weak_chance":1/55,"strong_cherry":1/200,"strong_chance":1/300},
    "SUPER":  {"replay":1/3,"bell":1/4,"cherry":1/12,"suika":1/18,"weak_chance":1/35,"strong_cherry":1/200,"strong_chance":1/300},
    "LEGEND": {"replay":1/3,"bell":1/4,"cherry":1/10,"suika":1/14,"weak_chance":1/28,"strong_cherry":1/200,"strong_chance":1/300},
    "GOD":    {"replay":1/3,"bell":1/4,"cherry":1/7, "suika":1/9, "weak_chance":1/18,"strong_cherry":1/200,"strong_chance":1/300},
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
    "lake":  {"cost":10,  "name":"🏞️ 湖", "payout_rate":1.10},
    "river": {"cost":50,  "name":"🏔️ 川", "payout_rate":1.10},
    "sea":   {"cost":100, "name":"🌊 海", "payout_rate":1.10},
}

ZUKAN_COMPLETE_BONUS = 30000
ZUKAN_ALL_BONUS      = 90000

FISHING_EFFECT_CHANCE = 1.0   # 毎回演出表示
GOLDEN_CROWN_CHANCE   = 0.05
SHADOW_CHANCE         = 0.01
SHADOW_SUCCESS_RATE   = 0.10
BOSS_REWARD           = 200000

# 演出待機時間（秒）
FISHING_WAIT_NORMAL = 2.0   # コモン〜レア
FISHING_WAIT_SUPER  = 3.0   # スーパーレア以上
SLOT_WAIT           = 1.5   # スロット演出待機

FISHING_EFFECTS = [
    ("🎣 糸を投げると...何かが引っかかった",        "trash"),
    ("😴 うとうとしてたら急に竿が揺れた！",          "random"),
    ("💤 静かだ...あれ？なんか来た？",               "common"),
    ("🌊 水面がちょっと揺れた...何かいる？",         "common"),
    ("🎣 いい感じに糸が沈んでいく...",               "common"),
    ("👀 何かがつついている...来るか...？",           "uncommon"),
    ("⚡ 急に引きが来た！",                          "uncommon"),
    ("🌀 じわじわと引っ張られてる...！",             "rare"),
    ("💦 ずっしり重い...これはデカいぞ！",           "rare"),
    ("🔥 ものすごい引きだ...竿が曲がってる！",       "super_rare"),
    ("😱 水面から何かが飛び出してきた...！",         "super_rare"),
    ("💎 水底で何かが光って見えた...！",             "super_rare"),
    ("🦈 巨大な影が近づいてくる...！！",             "super_rare"),
    ("💀 竿が折れそうなくらい引っ張られてる...！！", "legend"),
    ("🌀 糸がものすごい勢いで出ていく...止まらない！！","legend"),
    ("🤯 こんなの見たことない...化け物か...！！",    "legend"),
    ("🏆 これは...伝説の...！！竿が限界だ！！",      "legend_certain"),
    ("👻 なんか変な感じがする...いやな予感？",       "both_extreme"),
    ("🎊 水面が虹色に光った...！！",                 "super_certain"),
    ("😅 なんか軽いな...ん？",                       "trash_certain"),
    ("🎵 鼻歌歌ってたら突然ガツン！と来た！",        "random"),
    ("🌊 大きな波紋が広がっていく...！",             "rare"),
    ("✨ 水中でキラリと光るものが...！",             "uncommon"),
    ("🐟 小さな魚影が見えた",                        "common"),
    ("🌑 深いところから何かが浮き上がってくる...！", "super_rare"),
]

RARITY_COLORS = {
    "trash":      0x95a5a6,
    "common":     0xbdc3c7,
    "uncommon":   0x2ecc71,
    "rare":       0x3498db,
    "super_rare": 0x9b59b6,
    "legend":     0xf1c40f,
    "boss":       0xff0000,
}

FISHING_PROBS = {
    "lake":  {"trash":0.25,"common":0.33,"uncommon":0.27,"rare":0.08,"super_rare":0.05,"legend":0.02},
    "river": {"trash":0.25,"common":0.33,"uncommon":0.27,"rare":0.08,"super_rare":0.05,"legend":0.02},
    "sea":   {"trash":0.25,"common":0.33,"uncommon":0.27,"rare":0.08,"super_rare":0.05,"legend":0.02},
}

FISHING_TIME_BONUS = {
    "morning":  {"hours":list(range(6,9)),   "boost":{"common":1.3,"uncommon":1.2}},
    "evening":  {"hours":list(range(17,19)), "boost":{"rare":1.3}},
    "night":    {"hours":list(range(19,24)), "boost":{"uncommon":1.2,"rare":1.2}},
    "midnight": {"hours":list(range(0,6)),   "boost":{"super_rare":1.5,"legend":1.3,"trash":1.3}},
}

FISHING_WEEKDAY_BONUS = {
    0: {"boost":{"common":1.2}},
    1: {"boost":{"rare":1.3}},
    2: {"boost":{"uncommon":1.3}},
    3: {"boost":{"trash":0.5}},
    4: {"boost":{"rare":1.3,"super_rare":1.2}},
    5: {"boost":{"legend":1.3}},
    6: {"boost":{"legend":1.5,"super_rare":1.3}},
}

FISHING_SPECIAL_DAYS = {
    (1,1):   {"boost":{"legend":2.0,"super_rare":1.5},"label":"🎍 お正月"},
    (1,2):   {"boost":{"legend":1.8,"super_rare":1.4},"label":"🎍 お正月"},
    (1,3):   {"boost":{"legend":1.5,"super_rare":1.3},"label":"🎍 お正月"},
    (2,14):  {"boost":{"super_rare":1.5},             "label":"💝 バレンタイン"},
    (4,1):   {"boost":{"trash":3.0},                  "label":"🤡 エイプリルフール"},
    (10,31): {"boost":{"super_rare":1.5,"legend":1.3},"label":"🎃 ハロウィン"},
    (12,25): {"boost":{"legend":1.5,"super_rare":1.5},"label":"🎄 クリスマス"},
    (12,29): {"boost":{"legend":1.3,"super_rare":1.3},"label":"🎍 年末"},
    (12,30): {"boost":{"legend":1.4,"super_rare":1.4},"label":"🎍 年末"},
    (12,31): {"boost":{"legend":1.8,"super_rare":1.5},"label":"🎍 大晦日"},
}

AREA_BOSS = {
    "lake":  {"name":"ネッシー",     "emoji":"🦕","value":BOSS_REWARD},
    "river": {"name":"クラーケン幼体","emoji":"🦑","value":BOSS_REWARD},
    "sea":   {"name":"メガロドン",   "emoji":"🦷","value":BOSS_REWARD},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣り装備設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FISHING_RODS = {
    "bamboo":   {"name":"竹竿",          "price":0,       "uses":999999, "emoji":"🎋",
                 "probs":{"trash":0.30,"common":0.46,"uncommon":0.22,"rare":0.02,"super_rare":0.0,"legend":0.0},
                 "sea_ban":True},
    "glass":    {"name":"グラスロッド",   "price":2000,    "uses":200,    "emoji":"🎣",
                 "probs":{"trash":0.25,"common":0.33,"uncommon":0.27,"rare":0.08,"super_rare":0.005,"legend":0.0},
                 "sea_ban":False},
    "carbon":   {"name":"カーボンロッド", "price":8000,    "uses":200,    "emoji":"🎣",
                 "probs":{"trash":0.15,"common":0.38,"uncommon":0.31,"rare":0.092,"super_rare":0.005,"legend":0.0},
                 "sea_ban":False},
    "titanium": {"name":"チタンロッド",   "price":30000,   "uses":200,    "emoji":"🎣",
                 "probs":{"trash":0.229,"common":0.302,"uncommon":0.249,"rare":0.13,"super_rare":0.005,"legend":0.02,"boss":0.005},
                 "sea_ban":False},
    "legend":   {"name":"伝説の釣り竿",   "price":100000,  "uses":200,    "emoji":"🎣",
                 "probs":{"trash":0.243,"common":0.32,"uncommon":0.262,"rare":0.08,"super_rare":0.006,"legend":0.02,"boss":0.01},
                 "sea_ban":False},
}

FISHING_REELS = {
    "spinning": {"name":"スピニングリール", "price":0,     "uses":999999, "emoji":"🎡",
                 "super_rare_bonus":0.0, "boss_bonus":0.0},
    "bait":     {"name":"ベイトリール",     "price":500,   "uses":200,    "emoji":"🎡",
                 "super_rare_bonus":0.001,"boss_bonus":0.0},
    "drag":     {"name":"ドラグ付きリール", "price":1500,  "uses":200,    "emoji":"🎡",
                 "super_rare_bonus":0.002,"boss_bonus":0.0},
    "electric": {"name":"電動リール",       "price":4000,  "uses":200,    "emoji":"🎡",
                 "super_rare_bonus":0.004,"boss_bonus":0.005},
    "magnet":   {"name":"マグネットリール", "price":8000,  "uses":200,    "emoji":"🎡",
                 "super_rare_bonus":0.006,"boss_bonus":0.01},
}

FISHING_LINES = {
    "nylon":    {"name":"ナイロンライン",      "price":0,     "uses":999999, "emoji":"🧵",
                 "crown_bonus":0.0, "boss_success_bonus":0.0},
    "fluoro":   {"name":"フロロカーボンライン","price":400,   "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.01,"boss_success_bonus":0.0},
    "pe":       {"name":"PEライン",            "price":1000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.02,"boss_success_bonus":0.0},
    "super_pe": {"name":"スーパーPEライン",    "price":3000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.03,"boss_success_bonus":0.0},
    "clear":    {"name":"透明ライン",          "price":6000,  "uses":200,    "emoji":"🧵",
                 "crown_bonus":0.04,"boss_success_bonus":0.10},
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
    {"name":"ゴライアスタイガーフィッシュ","rarity":"legend","value":15000,"emoji":"😱"},
    {"name":"ベルーガ",          "rarity":"legend",     "value":22000, "emoji":"👑"},
    {"name":"ブルシャーク",      "rarity":"legend",     "value":30000, "emoji":"🦈"},
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
    {"name":"ホホジロザメ",  "rarity":"legend",     "value":30000, "emoji":"🦈"},
    {"name":"シーラカンス",  "rarity":"legend",     "value":45000, "emoji":"👑"},
    {"name":"ラブカ",        "rarity":"legend",     "value":60000, "emoji":"😱"},
]

CHINCHIRO_AI_PAYOUT = 0.90
