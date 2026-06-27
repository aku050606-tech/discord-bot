# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚓ 航海システム（さびれた港 再興後コンテンツ）設定ダイヤル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  方針:
#   ・船は1隻20万・1種・装備式。装備で強くなる／奥の海へ行ける。
#   ・航海＝進む(advance)たびにランダムエンカウント。引き返す(return)で船倉を銀行入金。
#   ・敗北で失うのは「航海中の船倉」だけ（港に戻すまで未確定）。
#   ・海賊戦は2層：①海戦(船戦闘力) → ピンチ側が ②白兵戦(個人戦闘力)。
#   ・船戦は勝敗問わず船装備の耐久がガッツリ減る＝修理代が最大のシンク（105%の蛇口を裏で締める）。
#   ・全体ネット ≈ 105%（モンテカルロで詰める。下の数値は全部その制御ダイヤル）。
#  ※ Phase1: ガチャ/マーケット/協力航海は未実装。まず単独航海ループを完成させる。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 船本体（1種・装備式）──
SHIP_PRICE = 200_000
SHIP_BASE_POWER = 10          # 装備なしの素の船戦闘力
SHIP_HULL_DURA = 200          # 船本体の耐久（白兵で乗り込まれ防衛失敗等で削れる）
SHIP_REPAIR_PER_DURA = 18     # 船本体・装備の耐久1あたりの修理単価（コインシンク）

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 海（4種）。hull(船体)tier が解放鍵。奥ほど高リターン・高リスク。
#   val_mult  : 釣果・宝・海賊報酬の倍率
#   danger    : 海賊の強さ倍率 ＆ エンカウント頻度の重み
#   unlock_hull: この海に出るのに必要な「船体tier」
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEAS = {
    "ocean":   {"name":"🌊 大海原",   "val_mult":1.0, "danger":1.0, "unlock_hull":1, "fuel":3300,
                "flavor":"穏やかな外洋。だが油断は禁物――海賊は、どこにでもいる。"},
    "ice":     {"name":"🧊 氷の海",   "val_mult":1.9, "danger":1.6, "unlock_hull":2, "fuel":6200,
                "flavor":"凍てつく霧の海。流氷の陰に巨大な影が潜む。"},
    "fire":    {"name":"🔥 炎の海",   "val_mult":3.4, "danger":2.4, "unlock_hull":3, "fuel":9600,
                "flavor":"灼熱の火山海。海面が煮え立ち、灰が降り注ぐ。"},
    "ancient": {"name":"🏛️ 古代の海", "val_mult":6.5, "danger":3.4, "unlock_hull":4, "fuel":16000,
                "flavor":"地図にない太古の海。理を超えた財宝と、それを守る者たち。"},
}
SEA_ORDER = ["ocean", "ice", "fire", "ancient"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1回の「進む」で起きるエンカウント（重み％・合計100）
#   fish=釣果 / island=上陸(宝) / pirate=海賊戦 / calm=平穏(微回復) / merchant=漂流商人(後Phase)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ENCOUNTER_WEIGHTS = {
    "fish":    42,
    "island":  16,
    "pirate":  30,
    "calm":    12,
}

# ── 釣果（船倉に貯まる海産物。海のval_multで増える）──
#   base_value × val_mult をベースに ±振れ。rare枠は低確率で高額。
FISH_HAUL = {
    "common":  {"weight":62, "base_min":1200,  "base_max":2600},
    "good":    {"weight":28, "base_min":3000,  "base_max":6500},
    "rare":    {"weight":8,  "base_min":9000,  "base_max":18000},
    "legend":  {"weight":2,  "base_min":28000, "base_max":60000},
}

# ── 上陸（無人島）：宝 or ハズレ ──
ISLAND_TREASURE_RATE = 0.62      # 上陸して宝が見つかる確率
ISLAND_TREASURE = {"base_min":4000, "base_max":14000}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 海賊（NPC）。出るランクは海の danger で底上げされる。
#   sea_power  : 海戦の敵戦闘力（船 vs 船）
#   crew_power : 白兵の敵戦闘力（個人 vs 個人）
#   reward_mult: 撃破時の報酬倍率（海のval_multにさらに掛ける）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PIRATE_RANKS = [
    {"name":"こそ泥船",     "emoji":"🏴",  "tier":1, "sea_power":12,  "crew_power":10,  "reward_mult":0.9},
    {"name":"無頼の海賊団", "emoji":"🏴‍☠️","tier":2, "sea_power":35,  "crew_power":28,  "reward_mult":1.1},
    {"name":"赤旗の私掠船", "emoji":"⚔️",  "tier":3, "sea_power":80,  "crew_power":62,  "reward_mult":1.35},
    {"name":"深海の亡霊船", "emoji":"💀",  "tier":4, "sea_power":160, "crew_power":130, "reward_mult":1.7},
    {"name":"古王の旗艦",   "emoji":"👑",  "tier":5, "sea_power":320, "crew_power":260, "reward_mult":2.2},
]
# 海ごとに出やすい海賊tier（重み）。奥の海ほど格上が増える。
PIRATE_TABLE = {
    "ocean":   [55, 35, 10,  0,  0],
    "ice":     [20, 45, 30,  5,  0],
    "fire":    [ 0, 20, 45, 30,  5],
    "ancient": [ 0,  0, 20, 45, 35],
}
# 海賊撃破の基礎報酬（reward_mult × val_mult が掛かる前のベース）
PIRATE_BASE_REWARD = {"base_min":5000, "base_max":12000}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 戦闘計算（Bradley-Terry型：勝率 = 味方^k /(味方^k + 敵^k)）
#   k を上げるほど戦闘力差が勝敗に直結（番狂わせが減る）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMBAT_K = 1.6
COMBAT_WIN_CLAMP = (0.05, 0.95)   # 勝率の上下限（理不尽な確定を防ぐ）

# ── 敗北時の船倉ロスト率：抽選（負け＝即全ロストではない）──
#   完全ランダムではなく「戦闘力差」で重み付け：格上に負けるほど 100% 寄り、
#   格下に番狂わせで負けたら 25% で済む。armor(船の装甲)でさらに下振れ。
LOSS_TIERS = [1.00, 0.75, 0.50, 0.25]
# 装甲tierごとに「ロスト率を1段軽くする確率」（装甲が高いほど被害が軽い）
ARMOR_MITIGATE_CHANCE = {0:0.0, 1:0.15, 2:0.30, 3:0.45, 4:0.60, 5:0.75}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 船戦の耐久消費（勝敗問わず削れる＝修理代シンク）。海のdangerで増える。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAVAL_DURA_COST = 14          # 海戦1回で砲・装甲・船体それぞれから引く基礎耐久
BOARD_DURA_COST = 6           # 白兵に発展した場合、船本体(hull)から追加で引く
SAIL_DURA_COST  = 1           # 「進む」1回ごとの航海消耗（軽い）

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 船の装備（3スロット）。tierを上げるほど強い・高い・(一部)解放鍵。
#   power=戦闘力 / dura=耐久 / price=購入額（ガチャ/マーケットでも入手可・Phase2+）
#   cannon=砲(海戦攻撃) / armor=装甲(被害軽減＋海戦少々) / hull=船体(戦闘力＋海の解放鍵＋耐久)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SHIP_EQUIP = {
    "cannon": {
        "name":"砲", "emoji":"💥", "role":"海戦の攻撃力",
        "tiers":[
            {"t":1, "name":"木製砲",   "power":8,   "dura":50,  "price":15_000},
            {"t":2, "name":"鉄製砲",   "power":22,  "dura":70,  "price":55_000},
            {"t":3, "name":"鋼鉄砲",   "power":50,  "dura":95,  "price":180_000},
            {"t":4, "name":"重連装砲", "power":105, "dura":125, "price":480_000},
            {"t":5, "name":"竜骨砲",   "power":210, "dura":160, "price":1_200_000},
        ],
    },
    "armor": {
        "name":"装甲", "emoji":"🛡️", "role":"被害軽減＋海戦少々",
        "tiers":[
            {"t":1, "name":"木甲",     "power":3,  "dura":60,  "price":12_000},
            {"t":2, "name":"鉄甲",     "power":8,  "dura":85,  "price":45_000},
            {"t":3, "name":"鋼鉄装甲", "power":18, "dura":115, "price":150_000},
            {"t":4, "name":"重装甲",   "power":40, "dura":150, "price":420_000},
            {"t":5, "name":"竜鱗装甲", "power":80, "dura":200, "price":1_050_000},
        ],
    },
    "hull": {
        "name":"船体", "emoji":"⛵", "role":"戦闘力＋奥の海の解放鍵＋耐久",
        "tiers":[
            {"t":1, "name":"小型船体",   "power":5,   "dura":120, "price":0},         # 船購入時に標準装備
            {"t":2, "name":"補強船体",   "power":25,  "dura":180, "price":120_000},   # 🧊解放
            {"t":3, "name":"鋼鉄船体",   "power":65,  "dura":260, "price":400_000},   # 🔥解放
            {"t":4, "name":"古代船体",   "power":140, "dura":380, "price":1_100_000}, # 🏛️解放
        ],
    },
}

# ── 個人の装備（白兵）＆レベル ──
#   武器は「種別(剣/双剣/杖…)」を持つカタログ。技は武器種別で装着制限される。
#   防具は部位制（胴/脚。今後 足/腕 を追加予定）。装備に技スロット(slots)を持つ。
#   ★レアリティ(rank)で表示。今は全部 rank1=★1。上位は金星・黒星で青天井。

# 武器種別（6枠。今は剣/双剣/杖だけ実物あり。弓/刀/銃は枠のみ）
WEAPON_TYPES = {
    "bow":    {"name": "弓",   "emoji": "🏹"},
    "sword":  {"name": "剣",   "emoji": "⚔️"},
    "katana": {"name": "刀",   "emoji": "🗡️"},
    "staff":  {"name": "杖",   "emoji": "🪄"},
    "twin":   {"name": "双剣", "emoji": "⚔️"},
    "gun":    {"name": "銃",   "emoji": "🔫"},
}

# ★レアリティ表示：rank(1始まり) → 星。5刻みで星種が繰り上がる（青天井）。
RARITY_STAR_BANDS = ["★", "🌟", "⭐", "✦"]  # 1-5=★ / 6-10=🌟 / 11-15=⭐ / 16-20=✦ …
def rarity_stars(rank):
    band = (rank - 1) // 5
    pos = (rank - 1) % 5 + 1
    star = RARITY_STAR_BANDS[band] if band < len(RARITY_STAR_BANDS) else "✧"
    return star * pos

# 武器カタログ（全部 rank1=★1・Lv1）。slots=技スロット数。
WEAPONS = {
    "cutlass":   {"name": "カトラス",   "wtype": "sword", "power": 15, "slots": 2,
                  "rank": 1, "req_lv": 1, "price": 8_000,
                  "desc": "扱いやすい片手剣。技を2つ刻める拡張性が魅力。"},
    "twinblade": {"name": "双剣",       "wtype": "twin",  "power": 28, "slots": 1,
                  "rank": 1, "req_lv": 1, "price": 12_000,
                  "desc": "二刀の手数型。連撃と好相性。"},
    "staff":     {"name": "司祭の錫杖", "wtype": "staff", "power": 18, "slots": 1,
                  "rank": 1, "req_lv": 1, "price": 10_000,
                  "desc": "回復技を扱えるヒーラー兼アタッカー。攻撃も多少こなす。"},
}

# 防具カタログ（部位制：胴/脚。今後 足/腕 を追加予定）。全部 rank1=★1・Lv1。
ARMOR_PARTS = {
    "torso": {"name": "胴", "emoji": "🦺", "items": {
        "leather_vest": {"name": "革の胴鎧", "power": 12, "slots": 1,
                         "rank": 1, "req_lv": 1, "price": 7_000,
                         "desc": "胴を守る革鎧。防御の要。"},
    }},
    "legs": {"name": "脚", "emoji": "🦵", "items": {
        "leather_greaves": {"name": "革のすね当て", "power": 8, "slots": 1,
                            "rank": 1, "req_lv": 1, "price": 5_000,
                            "desc": "脚を守るすね当て。軽い守り。"},
    }},
}
ARMOR_PART_ORDER = ["torso", "legs"]

# ── 個人レベル ──
LEVEL_BASE_POWER = 2          # Lvごとの個人戦闘力ベース加算（控えめ＝装備が主役）
LEVEL_MAX = 50
# XP獲得源（薄く配分）
XP_PER_FISH = 3
XP_PER_ISLAND = 5
XP_PER_PIRATE_WIN = 25
XP_PER_PIRATE_LOSE = 8        # 負けても少し経験は得る
# 必要XP（Lv→次Lvまで）。緩やかな累乗。
def xp_to_next(level):
    return int(60 * (level ** 1.45))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# マーケット適正価格ガード（Phase3で使用・少しきつめ）
#   出品可能レンジ = 基準価格 × [1-band, 1+band]。基準は (レア度=price) と戦闘力から自動算出。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARKET_PRICE_BAND = 0.20      # ±20%（きつめ。金銭授受の抜け道を絞る）
MARKET_FEE = 0.05            # 売買手数料（コインシンク）

# ── ガチャ（Phase2で使用）──
GACHA_PRICE = 30_000
