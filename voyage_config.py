# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚓ 航海システム（さびれた港 再興後コンテンツ）設定ダイヤル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import random

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
    "ocean":   {"name":"🌊 大海原",   "val_mult":1.25, "danger":1.15, "unlock_hull":1, "fuel":3300,
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🗺️ エリア進行システム ── 探索を重ねて奥へ進む（4エリア）。奥ほど高リスク高リターン。
#   🔍探索 を同じエリアで10回 → ⛵進む が解禁 → 次エリアへ（探索カウント0に戻る）。
#   ⚓引き返す で1エリア手前へ（エリア1で引き返す＝港へ入金）。
#   エリア4(最深部)だけは、エリア3で「光る羅針盤のカケラ」3個が追加条件。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AREA_MAX = 4
EXPLORE_TO_ADVANCE = 10               # 同エリアで探索N回 → 進む解禁
AREA_NAMES  = {1: "浅瀬", 2: "大洋", 3: "暗い海", 4: "虚海"}   # E4 虚海（うつろうみ）＝最深部の固有名
AREA_EMOJI  = {1: "🏖️", 2: "🌊", 3: "🌑", 4: "🌟"}
AREA_MULT   = {1: 1.0, 2: 1.6, 3: 2.6, 4: 4.0}   # 敵強さ・報酬に掛けるエリア倍率

# エリアごとの遭遇テーブル（探索時）。奥ほど海賊・固有遭遇が増える。
#   ※「何もなし(平穏)」は EVENT_DEFS の "nothing"(凪いだ海) に一本化（組込calmは廃止）。
#     fish=魚影 は出すぎ→減量、減らした分は island(宝) に寄せて脅威%は据え置き。
AREA_ENCOUNTERS = {
    1: {"fish": 20, "island": 36, "maelstrom": 6, "pirate": 10},  # ☆1雑魚が少し（全部倒せる・装備の練習）
    2: {"fish": 22, "island": 34, "pirate": 40},                 # 脅威~2割（イベントと合算後）
    3: {"fish": 16, "island": 24, "pirate": 55, "boss": 13, "maelstrom": 20},  # 脅威~3割強
    4: {"fish": 14, "island": 18, "pirate": 53, "boss": 26, "abyss": 22},      # 脅威~4割・最深部
}

# 🧭 光る羅針盤のカケラ（エリア3でのみ拾える）。3個でエリア4が開く。
SHARD_NAME   = "🧭 光る羅針盤のカケラ"
SHARD_NEEDED = 3

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚖️ カルマ（Phase2・基盤）
#   中立=0スタート・3段階(善/中立/悪)・数値は見せる。
#   善＝その場は我慢/トータル得、悪＝その場は甘い/トータル損。
#   海賊だけは別ロジック（善でも友好にならない・悪でも共犯止まり）＝イベント側で処理。
#   ※しきい値・増減量は仮。後でイベントと合わせてモンテカルロ調整。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KARMA_START = 20
KARMA_GOOD_THRESHOLD = 30      # これ以上＝善
KARMA_EVIL_THRESHOLD = -30     # これ以下＝悪
KARMA_MIN, KARMA_MAX = -100, 100   # 振り切れる上下限
KARMA_DELTA = {"small": 5, "medium": 15, "large": 30}   # イベントのカルマ増減の基準量

# 🏕️ 停泊（釣り/宴会/休息）の燃料コスト。仮。停泊しすぎると燃料が尽きる＝緊張感。
STOPOVER_FEAST_FUEL = 500    # 🍖 宴会＝個人HP回復
STOPOVER_REST_FUEL  = 800    # 😴 休息＝個人HP全回復
FUEL_PRICE_PER = 0.6         # ⛽ ドック給油の単価（燃料1あたりのコイン）。満タンfrigate≈19,800
# 🎣 釣りは探索と同じ燃料（explore_fuel_cost）を消費

def karma_tier(karma):
    """善/中立/悪の3段階判定。"""
    if karma >= KARMA_GOOD_THRESHOLD: return "good"
    if karma <= KARMA_EVIL_THRESHOLD: return "evil"
    return "neutral"

KARMA_TIER_META = {
    "good":    {"emoji": "😇", "label": "善",   "note": "海に呑まれにくい／NPCは味方に"},
    "neutral": {"emoji": "⚖️", "label": "中立", "note": "どちらにも転べる"},
    "evil":    {"emoji": "😈", "label": "悪",   "note": "海が歓迎する／NPCは離れる"},
}
SHARD_DROP = {            # エリア3の各結果での "薄い" ドロップ確率
    "fish": 0.04, "island": 0.07, "pirate_win": 0.12,
    "explore": 0.16, "boss": 1.0, "maelstrom": 0.5,
}

# エリア3/4で出る固有ボス（海戦→白兵の2層。エリア倍率が掛かる）
AREA_BOSS = {
    3: {"name": "深海の主", "emoji": "🐙", "sea_power": 120, "crew_power": 95,  "reward_mult": 2.0},
    4: {"name": "海淵の古龍", "emoji": "🐲", "sea_power": 240, "crew_power": 190, "reward_mult": 3.0},
}

# 🔍探索の小宝・固有報酬
EXPLORE_TREASURE = {"base_min": 4500, "base_max": 15000}
ABYSS_TREASURE   = {"base_min": 8000, "base_max": 22000}   # エリア4の海淵
MAELSTROM_REWARD = {"base_min": 2000, "base_max": 7000}    # エリア3の渦潮

# ── 釣果（旧プレースホルダ：コイン額のティア抽選）。
#   VOYAGE_FISH_BY_AREA に移行済み。フォールバック用に残置。
FISH_HAUL = {
    "common":  {"weight":62, "base_min":1200,  "base_max":2600},
    "good":    {"weight":28, "base_min":3000,  "base_max":6500},
    "rare":    {"weight":8,  "base_min":9000,  "base_max":18000},
    "legend":  {"weight":2,  "base_min":28000, "base_max":60000},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎣 海の魚カタログ（4エリア専用）── 陸の釣り(FISH_BY_AREA)と同じ構造を航海に
#   レア度は「竿」(config.FISHING_RARITY) が決め、エリアが「どの魚が／いくらで」。
#   売値は陸の海(SEA_FISH legend上限3万)を大きく超える高設定。船倉(hold)に貯まる。
#   奥に行くほど「魚らしさ」が壊れていく＝世界観（観測者/カケラ/古代の伏線）。
#   ※数値・名前はバランス用ダイヤル。ここを書き換えるだけで調整できる。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOYAGE_FISH_BY_AREA = {
    # ── 🏖️ E1 浅瀬（入口の海・実在の大物）──
    1: [
        {"name":"流れ着いた木箱",     "rarity":"trash", "value":0,   "emoji":"📦"},
        {"name":"ちぎれた漁網",       "rarity":"trash", "value":0,   "emoji":"🕸️"},
        {"name":"空のラム酒瓶",       "rarity":"trash", "value":0,   "emoji":"🍾"},
        {"name":"漂着した宝箱の欠片", "rarity":"trash", "value":350, "emoji":"🪙"},
        {"name":"トビウオ",       "rarity":"common", "value":250, "emoji":"🐟"},
        {"name":"カツオ",         "rarity":"common", "value":360, "emoji":"🐟"},
        {"name":"カンパチ",       "rarity":"common", "value":460, "emoji":"🐟"},
        {"name":"アオリイカ",     "rarity":"common", "value":650, "emoji":"🦑"},
        {"name":"キハダマグロ",   "rarity":"uncommon", "value":850,  "emoji":"🐟"},
        {"name":"大マダイ",       "rarity":"uncommon", "value":1200, "emoji":"🐟"},
        {"name":"座布団ヒラメ",   "rarity":"uncommon", "value":1450, "emoji":"🐟"},
        {"name":"ランカーシーバス","rarity":"uncommon","value":1600, "emoji":"🐟"},
        {"name":"クエ",           "rarity":"rare", "value":2600, "emoji":"🐟"},
        {"name":"イシナギ",       "rarity":"rare", "value":3400, "emoji":"🐟"},
        {"name":"バショウカジキ", "rarity":"rare", "value":4000, "emoji":"🐟"},
        {"name":"若クロマグロ",   "rarity":"rare", "value":4800, "emoji":"🐟"},
        {"name":"本マグロ",       "rarity":"super_rare", "value":8000,  "emoji":"🐟"},
        {"name":"ロウニンアジ",   "rarity":"super_rare", "value":11000, "emoji":"🐟"},
        {"name":"大ウミガメ",     "rarity":"super_rare", "value":13000, "emoji":"🐢"},
        {"name":"黄金の本マグロ", "rarity":"legend", "value":35000, "emoji":"👑"},
        {"name":"浅瀬の主・大鯨", "rarity":"legend", "value":52000, "emoji":"🐋"},
    ],
    # ── 🌊 E2 大洋（外洋の巨獣）──
    2: [
        {"name":"難破船の船板",   "rarity":"trash", "value":0,   "emoji":"🪵"},
        {"name":"錆びた錨",       "rarity":"trash", "value":0,   "emoji":"⚓"},
        {"name":"破れた海賊旗",   "rarity":"trash", "value":0,   "emoji":"🏴‍☠️"},
        {"name":"ガラスの浮き玉", "rarity":"trash", "value":600, "emoji":"🔮"},
        {"name":"マンボウ",       "rarity":"common", "value":600,  "emoji":"🐡"},
        {"name":"オナガザメ",     "rarity":"common", "value":800,  "emoji":"🦈"},
        {"name":"ヨゴレ",         "rarity":"common", "value":1000, "emoji":"🦈"},
        {"name":"寒サワラ",       "rarity":"common", "value":1250, "emoji":"🐟"},
        {"name":"メカジキ",       "rarity":"uncommon", "value":1800, "emoji":"🐟"},
        {"name":"シュモクザメ",   "rarity":"uncommon", "value":2300, "emoji":"🦈"},
        {"name":"イトマキエイ",   "rarity":"uncommon", "value":2800, "emoji":"🐟"},
        {"name":"ミナミマグロ",   "rarity":"uncommon", "value":3300, "emoji":"🐟"},
        {"name":"クロカワカジキ", "rarity":"rare", "value":5200, "emoji":"🐟"},
        {"name":"イタチザメ",     "rarity":"rare", "value":6500, "emoji":"🦈"},
        {"name":"オキゴンドウ",   "rarity":"rare", "value":7800, "emoji":"🐬"},
        {"name":"銀のマカジキ",   "rarity":"rare", "value":9300, "emoji":"✨"},
        {"name":"ホホジロザメ",   "rarity":"super_rare", "value":15000, "emoji":"🦈"},
        {"name":"ダイオウイカ",   "rarity":"super_rare", "value":20000, "emoji":"🦑"},
        {"name":"シャチ",         "rarity":"super_rare", "value":24000, "emoji":"🐳"},
        {"name":"白鯨",           "rarity":"legend", "value":62000, "emoji":"🐋"},
        {"name":"海を統べる古き鯱","rarity":"legend", "value":92000, "emoji":"🐳"},
    ],
    # ── 🌑 E3 暗い海（深海の異形）──
    3: [
        {"name":"黒ずんだ骨",       "rarity":"trash", "value":0,   "emoji":"🦴"},
        {"name":"沈没船の錆びた鎖", "rarity":"trash", "value":0,   "emoji":"⛓️"},
        {"name":"濡れた古びた人形", "rarity":"trash", "value":0,   "emoji":"🎎"},
        {"name":"光らない深海の石", "rarity":"trash", "value":900, "emoji":"🪨"},
        {"name":"チョウチンアンコウ","rarity":"common", "value":1400, "emoji":"🎣"},
        {"name":"ミツクリザメ",     "rarity":"common", "value":1800, "emoji":"🦈"},
        {"name":"オニキンメ",       "rarity":"common", "value":2200, "emoji":"🐟"},
        {"name":"ホウライエソ",     "rarity":"common", "value":2700, "emoji":"🐟"},
        {"name":"ラブカ",           "rarity":"uncommon", "value":3800, "emoji":"🦈"},
        {"name":"ダイオウグソクムシ","rarity":"uncommon", "value":4600, "emoji":"🦐"},
        {"name":"メンダコ",         "rarity":"uncommon", "value":5400, "emoji":"🐙"},
        {"name":"リュウグウノツカイ","rarity":"uncommon", "value":6500, "emoji":"🐉"},
        {"name":"シーラカンス",         "rarity":"rare", "value":9800,  "emoji":"🐟"},
        {"name":"ダイオウホウズキイカ", "rarity":"rare", "value":12000, "emoji":"🦑"},
        {"name":"巨大ミズウオ",         "rarity":"rare", "value":14500, "emoji":"🐟"},
        {"name":"燐光を放つ深海魚",     "rarity":"rare", "value":18000, "emoji":"✨"},
        {"name":"深海の主の眷属",   "rarity":"super_rare", "value":28000, "emoji":"🐙"},
        {"name":"光を喰らう鮟鱇",   "rarity":"super_rare", "value":36000, "emoji":"🕯️"},
        {"name":"メガロドンの末裔", "rarity":"super_rare", "value":45000, "emoji":"🦈"},
        {"name":"古き海龍の落とし子",   "rarity":"legend", "value":110000, "emoji":"🐉"},
        {"name":"深海の王・盲いた巨鯨", "rarity":"legend", "value":165000, "emoji":"🐋"},
    ],
    # ── 🕳️ E4 虚海（うつろうみ）── 魚ですらない・観測者/古代の気配 ──
    4: [
        {"name":"沈黙の海の砂",     "rarity":"trash", "value":0,    "emoji":"⏳"},
        {"name":"何も映さない鏡",   "rarity":"trash", "value":0,    "emoji":"🪞"},
        {"name":"古代文字の石板",   "rarity":"trash", "value":0,    "emoji":"🪨"},
        {"name":"視線を感じる貝殻", "rarity":"trash", "value":1500, "emoji":"🐚"},
        {"name":"透き通った魚",     "rarity":"common", "value":3000, "emoji":"🫧"},
        {"name":"目のない魚",       "rarity":"common", "value":3600, "emoji":"🐟"},
        {"name":"影だけの魚",       "rarity":"common", "value":4300, "emoji":"🌑"},
        {"name":"静寂を纏う魚",     "rarity":"common", "value":5500, "emoji":"🤍"},
        {"name":"骨だけで泳ぐ魚",   "rarity":"uncommon", "value":8000,  "emoji":"🦴"},
        {"name":"二つの顔を持つ魚", "rarity":"uncommon", "value":10500, "emoji":"🎭"},
        {"name":"囁く貝の群れ",     "rarity":"uncommon", "value":12500, "emoji":"🐚"},
        {"name":"海の記憶を喰う魚", "rarity":"uncommon", "value":14500, "emoji":"🌀"},
        {"name":"原初の魚",         "rarity":"rare", "value":21000, "emoji":"🐟"},
        {"name":"光るカケラを宿す魚","rarity":"rare", "value":26000, "emoji":"🧭"},
        {"name":"漆黒を泳ぐ巨影",   "rarity":"rare", "value":33000, "emoji":"🌑"},
        {"name":"観る者の落とし物", "rarity":"rare", "value":38000, "emoji":"👁️"},
        {"name":"世界の裂け目から来た魚", "rarity":"super_rare", "value":70000, "emoji":"🌀"},
        {"name":"観測者の欠片を呑んだ魚", "rarity":"super_rare", "value":85000, "emoji":"👁️"},
        {"name":"深淵の女王",             "rarity":"super_rare", "value":98000, "emoji":"👑"},
        {"name":"古き海龍ヨルムンの仔",     "rarity":"legend", "value":200000, "emoji":"🐲"},
        {"name":"世界を視ていた一つ目の魚", "rarity":"legend", "value":300000, "emoji":"👁️"},
    ],
}

def voyage_fish_pool(area, rarity):
    """そのエリア・そのレア度の魚プール（無ければcommonにフォールバック）。"""
    lst = VOYAGE_FISH_BY_AREA.get(area, VOYAGE_FISH_BY_AREA[1])
    pool = [f for f in lst if f["rarity"] == rarity]
    if not pool:
        pool = [f for f in lst if f["rarity"] == "common"]
    return pool

# ━━━ 🎣 海の釣り：レア度（全エリア一律）━━━
#   伝説の竿でしか釣れない仕様＋値段がエリアで段違いなので、レア度は全エリア共通の一律に。
#   legend 0.1% / super_rare 1% / rare 5% を固定。残りを trash/common/uncommon に配分。合計＝1.0。
VOYAGE_FISH_RARITY_FLAT = {
    "trash":0.24, "common":0.42, "uncommon":0.279, "rare":0.05, "super_rare":0.01, "legend":0.001,
}
# 🌈 伝説の魚の噂モード：レジェンドが格段に出やすい特別な釣り（L率5%）。合計=1.0。
VOYAGE_FISH_RARITY_RUMOR = {
    "trash":0.08, "common":0.27, "uncommon":0.30, "rare":0.25, "super_rare":0.05, "legend":0.05,
}
# 🐟 大物の魚影モード：通常からSR+1%・レジェンド+1%だけ上げた1回限りの釣り。合計=1.0。
VOYAGE_FISH_RARITY_SHADOW = {
    "trash":0.23, "common":0.41, "uncommon":0.279, "rare":0.05, "super_rare":0.02, "legend":0.011,
}
# 互換：エリア別に引く呼び出しに対応（全エリア同じテーブルを返す）
VOYAGE_FISH_RARITY = {a: VOYAGE_FISH_RARITY_FLAT for a in (1, 2, 3, 4)}

def voyage_fish_rarity_pick(area=None, mode="normal"):
    """レア度を1つ抽選。mode='rumor'で伝説出やすい／'shadow'でSR・L+1%。"""
    table = {"rumor": VOYAGE_FISH_RARITY_RUMOR,
             "shadow": VOYAGE_FISH_RARITY_SHADOW}.get(mode, VOYAGE_FISH_RARITY_FLAT)
    r = random.random(); acc = 0.0
    for rar, p in table.items():
        acc += p
        if r < acc:
            return rar
    return "common"

# 🎣 魚を釣れる演出（魚影）1回ごとに釣れる回数（演出ごとの回数制限）。エリアで調整可。
FISH_SCHOOL_CASTS = {1: 3, 2: 3, 3: 3, 4: 3}

def fish_school_casts(area):
    return FISH_SCHOOL_CASTS.get(area, 3)

# 🎣 海の釣りに必要な竿（これ以外では釣れない）
VOYAGE_FISH_ROD = "legend"   # 伝説の釣り竿

# 🎣 航海専用の釣り竿（ドックで購入・永久・船に付ける）。これが無いと海では釣れない。
#   リール/ラインは航海の釣りでは無効（金冠なし）＝陸の釣りと切り離す。
VOYAGE_ROD_NAME  = "🎣 航海の釣り竿"
VOYAGE_ROD_PRICE = 100000

# 🏆 海の幸図鑑コンプリート報酬（エリアの非ごみ魚を全種そろえると一度だけ貰える）
VOYAGE_FISH_COMPLETE_REWARD = {1: 100000, 2: 200000, 3: 300000, 4: 400000}

# ⚔️ 魚影演出で「実は怪物だった」＝戦闘になる確率（エリア依存・奥ほど危険／E1は安全）
FISH_CUE_COMBAT_RATE = {1: 0.00, 2: 0.10, 3: 0.18, 4: 0.28}
# 魚影から襲ってくる海獣（エリア別。keyはENEMY_TYPES。エリア基準値で自動スケール）
FISH_CUE_BEASTS = {
    1: ["shark", "piranha"],
    2: ["shark", "serpent"],
    3: ["serpent", "venom_serpent"],
    4: ["serpent", "venom_serpent"],
}

def fish_cue_combat_roll(area):
    """魚影が実は怪物だった＝戦闘になるか判定。"""
    return random.random() < FISH_CUE_COMBAT_RATE.get(area, 0.0)

def pick_fish_cue_beast(area):
    """魚影から襲う海獣specを返す。"""
    keys = FISH_CUE_BEASTS.get(area, ["shark"])
    return make_enemy_spec(random.choice(keys), area)

def voyage_fish_total(area):
    """そのエリアの非ごみ魚の総数（コンプ判定用）。"""
    return len([f for f in VOYAGE_FISH_BY_AREA.get(area, []) if f["rarity"] != "trash"])

def voyage_fish_names(area):
    """そのエリアの非ごみ魚の名前集合（コンプ判定用）。"""
    return {f["name"] for f in VOYAGE_FISH_BY_AREA.get(area, []) if f["rarity"] != "trash"}

# ── 上陸（無人島）：宝 or ハズレ ──
ISLAND_TREASURE_RATE = 0.62      # 上陸して宝が見つかる確率
ISLAND_TREASURE = {"base_min":5500, "base_max":19000}

# ━━━ 🎒 アイテム（食料・燃料樽・素材）━━━
# 🍖 食料：HPを割合回復。ドロップ＋ドックで購入。
# 回復量はゲーム全体の最大値を50%に統一（全回復は家/休息など専用手段のみ）。
FOODS = {
    "hardtack": {"name": "乾パン",     "emoji": "🥖", "heal_pct": 0.15, "price": 2000, "stars": 1},
    "jerky":    {"name": "干し肉",     "emoji": "🍖", "heal_pct": 0.35, "price": 4000, "stars": 1},
    "feast":    {"name": "船員の宴",   "emoji": "🍲", "heal_pct": 0.50, "price": 7000, "stars": 2},
}
# ⛽ 燃料樽：拾うとその場で燃料補給（即時消費）
FUEL_BARREL = {"name": "燃料樽", "emoji": "🛢️", "fuel": 3000}
# 💎 素材：インベントリに溜まる（今は使い道なし・将来クラフト用）。敵カテゴリ×☆でドロップ。
MATERIALS = {
    "rusty_coin":     {"name": "さびた金貨",     "emoji": "🪙", "cat": "pirate",   "stars": 1},
    "torn_flag":      {"name": "千切れた海賊旗", "emoji": "🏴‍☠️","cat": "pirate",  "stars": 1},
    "looted_silver":  {"name": "略奪品の銀食器", "emoji": "🍴", "cat": "pirate",   "stars": 2},
    "sharp_fang":     {"name": "鋭い牙",         "emoji": "🦷", "cat": "beast",    "stars": 1},
    "hard_scale":     {"name": "硬い鱗",         "emoji": "🐊", "cat": "beast",    "stars": 1},
    "slimy_tentacle": {"name": "ぬめる触手",     "emoji": "🦑", "cat": "beast",    "stars": 2},
    "rotten_bone":    {"name": "朽ちた骨",       "emoji": "🦴", "cat": "undead",   "stars": 1},
    "wet_logbook":    {"name": "濡れた船員手帳", "emoji": "📓", "cat": "undead",   "stars": 1},
    "wraith_ring":    {"name": "亡者の指輪",     "emoji": "💍", "cat": "undead",   "stars": 2},
    "brass_button":   {"name": "真鍮のボタン",   "emoji": "🔘", "cat": "military", "stars": 1},
    "fleet_emblem":   {"name": "艦隊の徽章",     "emoji": "🎖️","cat": "military", "stars": 2},
    "trade_seal":     {"name": "交易印",         "emoji": "📜", "cat": "merchant", "stars": 1},
    "spice_pouch":    {"name": "香辛料の小袋",   "emoji": "🧂", "cat": "merchant", "stars": 2},
    "wet_journal":    {"name": "濡れた手記",     "emoji": "📔", "cat": "castaway", "stars": 1},
    "rusty_compass":  {"name": "錆びたコンパス", "emoji": "🧭", "cat": "castaway", "stars": 1},
}
MATERIAL_DROP_RATE = 0.65   # 敵撃破時に素材が落ちる確率
FOOD_DROP_RATE     = 0.35   # 島/戦闘勝利で食料が落ちる確率
BARREL_DROP_RATE   = 0.40   # 漂流物/渦で燃料樽が出る確率

# 🗡️ 装備ドロップ（人型の敵のみ・敵の☆に対応）。武器か防具をランダムで1個。
HUMANOID_CATS = ("pirate", "military", "castaway", "merchant", "undead")  # 装備を落とす＝人型
EQUIP_DROP_RATES = {
    # 敵☆: [(装備☆, 確率), ...]
    1: [(2, 0.003)],            # ☆1敵 → ☆2装備を超低確率
    2: [(2, 0.01)],             # ☆2敵 → ☆2装備を低確率
    3: [(2, 0.01), (3, 0.005)], # ☆3敵 → ☆2低確率＋☆3超低確率
    4: [(2, 0.01), (3, 0.005)], # ☆4敵も同様（ボスは別途除外）
    5: [(2, 0.01), (3, 0.005)],
}

def materials_for(cat, stars):
    """カテゴリ＋☆以下の素材キー一覧（その敵から落ちうる素材）。"""
    return [k for k, m in MATERIALS.items() if m["cat"] == cat and m["stars"] <= stars]

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
# ── エリア依存の海賊tier分布（海×エリア）──
#   HPレース戦闘だとtierの段差が「崖」になるため、浅いエリアは格下のみ・
#   奥ほど格上が出る形に（報酬スケールと噛み合う＝身の丈以上に潜ると全損リスク）。
#   未定義の (sea, area) は上の PIRATE_TABLE にフォールバック。
PIRATE_TABLE_BY_AREA = {
    "ocean": {
        1: [100,  0,  0,  0,  0],   # エリア1は戦闘なし（未使用）
        2: [ 20, 38, 32, 10,  0],   # 全損≈25%/航海（逃げ＆防衛で凌げる）
        3: [  0, 12, 48, 35,  5],   # 初期装備ではほぼ死ぬ（全損≈83%/航海）
        4: [  0,  0, 30, 45, 25],   # 最深部・即死級
    },
    "ice": {
        1: [40, 50, 10,  0,  0],
        2: [20, 45, 30,  5,  0],
        3: [ 5, 30, 45, 18,  2],
        4: [ 0, 15, 40, 38,  7],
    },
    "fire": {
        1: [ 0, 45, 45, 10,  0],
        2: [ 0, 25, 45, 28,  2],
        3: [ 0, 10, 40, 42,  8],
        4: [ 0,  0, 30, 45, 25],
    },
    "ancient": {
        1: [ 0,  0, 55, 40,  5],
        2: [ 0,  0, 35, 50, 15],
        3: [ 0,  0, 20, 50, 30],
        4: [ 0,  0, 10, 45, 45],
    },
}
def pirate_weights(sea, area):
    return PIRATE_TABLE_BY_AREA.get(sea, {}).get(area, PIRATE_TABLE[sea])
# 海賊撃破の基礎報酬（reward_mult × val_mult が掛かる前のベース）
PIRATE_BASE_REWARD = {"base_min":6500, "base_max":16000}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 敵カタログ（白兵戦・16種）。combatキーで一意に引ける。
#   crew_power = AREA_ENEMY_BASE[area] × ratio（エリアで底上げ）
#   敵HP = crew_power × combat_scale × BOARD_E_HP_MULT × hp_mult
#   reward = reward_mult（撃破報酬）, tier_add（スキル/AIの格・area基準に加算）
#   特性: boss / legendary（激レア・出現率側で薄く）/ first_strike（先制）/ undead / karma_react
#   ※数値は仮。後でモンテカルロ調整。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AREA_ENEMY_BASE = {1: 105, 2: 50, 3: 32, 4: 130}   # エリア別の標準crew_power（E1/E2は実測調整済・E3/E4は★3実装後に再調整）

ENEMY_TYPES = {
    # ── 🏴‍☠️ 海賊系 ──
    "pirate_old":    {"name":"老いぼれ海賊",     "emoji":"🚣", "ratio":0.55,"hp_mult":0.85,"atk_mult":0.85,"reward":0.7, "tier_add":-1, "stars":1},
    "pirate_drifter":{"name":"流れ者の海賊",     "emoji":"🏴‍☠️","ratio":0.75,"hp_mult":0.9, "atk_mult":0.95,"reward":0.85,"tier_add":0,  "stars":1},
    "pirate_washout":{"name":"海賊くずれ",       "emoji":"🏴‍☠️","ratio":0.9, "hp_mult":1.0, "atk_mult":1.0, "reward":0.95,"tier_add":0,  "stars":2},
    "pirate_rogue":  {"name":"ならず者の海賊",   "emoji":"🏴‍☠️","ratio":1.0, "hp_mult":1.0, "atk_mult":1.0, "reward":1.0, "tier_add":0,  "stars":2},
    "pirate_bounty": {"name":"賞金首の海賊",     "emoji":"🏴", "ratio":1.25,"hp_mult":1.15,"atk_mult":1.0, "reward":1.7, "tier_add":1,  "stars":3},
    "leviathan":     {"name":"血錨のレヴィアタン","emoji":"🩸","ratio":2.8, "hp_mult":1.8, "atk_mult":1.3, "reward":3.2, "tier_add":2,  "stars":5, "legendary":True},
    # ── 🪖 軍 ──
    "navy":          {"name":"大洋艦隊の軍人",   "emoji":"🪖", "ratio":1.2, "hp_mult":1.3, "atk_mult":0.85,"reward":0.8, "tier_add":1,  "stars":4, "karma_react":True},
    # ── 🧟 アンデッド系 ──
    "wight":         {"name":"彷徨う亡者",       "emoji":"🧟", "ratio":0.7, "hp_mult":1.3, "atk_mult":0.8, "reward":0.5, "tier_add":0,  "stars":1, "undead":True},
    "drowned":       {"name":"水死人の群れ",     "emoji":"🧟", "ratio":0.9, "hp_mult":1.5, "atk_mult":0.8, "reward":0.5, "tier_add":0,  "stars":2, "undead":True},
    "hands":         {"name":"無数の手",         "emoji":"🖐️","ratio":0.6, "hp_mult":2.2, "atk_mult":0.7, "reward":0.4, "tier_add":0,  "stars":2, "undead":True},
    "ghost":         {"name":"幽霊船の亡霊船員", "emoji":"👻", "ratio":1.1, "hp_mult":1.3, "atk_mult":0.9, "reward":1.4, "tier_add":1,  "stars":3, "undead":True, "shard_hint":True},
    "admiral":       {"name":"呑まれた提督",     "emoji":"☠️", "ratio":2.6, "hp_mult":1.8, "atk_mult":1.3, "reward":2.8, "tier_add":2,  "stars":5, "undead":True, "legendary":True},
    # ── 🦈 海獣系 ──
    "piranha":       {"name":"人食い魚の群れ",   "emoji":"🐟", "ratio":0.45,"hp_mult":0.65,"atk_mult":1.35,"reward":0.6, "tier_add":-1, "stars":1},  # 群れ・紙・速攻
    "shark":         {"name":"群れ喰らいのサメ", "emoji":"🦈", "ratio":0.55,"hp_mult":0.7, "atk_mult":1.4, "reward":0.8, "tier_add":-1, "stars":1},
    "venom_serpent": {"name":"毒の海蛇",         "emoji":"🐍", "ratio":1.1, "hp_mult":1.1, "atk_mult":0.9, "reward":1.2, "tier_add":0,  "stars":3},  # 出血特化
    "serpent":       {"name":"大海蛇",           "emoji":"🐍", "ratio":1.15,"hp_mult":1.15,"atk_mult":1.0, "reward":1.3, "tier_add":0,  "stars":3},
    # ── 🐙🐲 ボス級 ──
    "kraken":        {"name":"深淵のクラーケン", "emoji":"🐙", "ratio":1.6, "hp_mult":1.7, "atk_mult":1.0, "reward":2.2, "tier_add":1,  "stars":4, "boss":True},
    "yormun":        {"name":"古き海龍ヨルムン", "emoji":"🐲", "ratio":3.4, "hp_mult":2.2, "atk_mult":1.3, "reward":3.6, "tier_add":2,  "stars":5, "boss":True, "legendary":True},
    # ── 🪦 難破者 ──
    "castaway_foe":  {"name":"難破船の生存者",   "emoji":"🪦", "ratio":0.5, "hp_mult":0.9, "atk_mult":0.85,"reward":0.6, "tier_add":-1, "stars":1},  # 哀れ・弱い・襲うとカルマ↓
    # ── ⚔️ イベント専用 ──
    "ambush":        {"name":"伏兵の海賊",       "emoji":"⚔️", "ratio":1.0, "hp_mult":0.95,"atk_mult":1.05,"reward":1.0, "tier_add":0,  "stars":2, "first_strike":True},
    "merchant_raid": {"name":"商船の護衛",       "emoji":"⛵", "ratio":1.4, "hp_mult":1.4, "atk_mult":1.25,"reward":1.8, "tier_add":1,  "stars":3},   # 護衛が固い・襲撃は基本失敗(<10%)
    "merchant_big":  {"name":"大型商船の護衛団", "emoji":"🛡️","ratio":1.25,"hp_mult":1.35,"atk_mult":0.85,"reward":2.6, "tier_add":1,  "stars":4},
    # 🖤 クラーケンの影（特殊戦闘・手順④で専用実装）
    "kraken_shadow": {"name":"巨大な影",         "emoji":"🌑", "ratio":1.6, "hp_mult":2.0, "atk_mult":1.0, "reward":0.0, "tier_add":1,  "stars":5, "special":"kraken_shadow"},
}

# ── 敵タイプ別スキル（白兵戦・AIに個性を持たせる）──
#   rengeki=連撃(手数) kyougeki=強撃(一撃) konshin=渾身(溜め大) shukketsu=出血(dot) teppeki=鉄壁(守り)
ENEMY_SKILLS_BY_TYPE = {
    "pirate_old":    ["rengeki"],
    "pirate_drifter":["kyougeki"],
    "pirate_washout":["kyougeki"],
    "pirate_rogue":  ["kyougeki"],
    "pirate_bounty": ["kyougeki", "shukketsu"],
    "leviathan":     ["kyougeki", "konshin", "shukketsu"],
    "navy":          ["kyougeki", "teppeki"],          # 硬い・守って反撃
    "wight":         ["shukketsu"],
    "drowned":       ["shukketsu"],                    # 出血・粘る
    "ghost":         ["shukketsu", "kyougeki"],
    "hands":         ["shukketsu"],                    # じわじわ
    "admiral":       ["kyougeki", "konshin", "shukketsu"],
    "piranha":       ["rengeki"],                      # 群れ・連撃
    "shark":         ["rengeki"],                      # 連撃・手数
    "venom_serpent": ["shukketsu"],                    # 毒・出血特化
    "serpent":       ["rengeki", "shukketsu"],
    "kraken":        ["kyougeki", "konshin"],
    "yormun":        ["kyougeki", "konshin", "shukketsu"],
    "castaway_foe":  [],                               # 弱い・技なし
    "ambush":        ["rengeki"],                      # 先制・手数
    "merchant_raid": ["teppeki", "kyougeki"],          # 護衛が守って反撃
    "merchant_big":  ["teppeki", "kyougeki", "shukketsu"],
    "kraken_shadow": ["konshin"],                      # 影＝溜めの一撃（専用戦闘で上書き）
}

def make_enemy_spec(combat_key, area):
    """combatキー＋エリアから白兵戦の敵スペックを生成。未知キーはNone（呼び出し側で海賊フォールバック）。"""
    t = ENEMY_TYPES.get(combat_key)
    if not t:
        return None
    base = AREA_ENEMY_BASE.get(area, AREA_ENEMY_BASE[4])
    tier = max(1, min(5, area + t.get("tier_add", 0)))
    return {
        "name": t["name"], "emoji": t["emoji"],
        "key": combat_key,
        "area": area,
        "crew_power": max(1, round(base * t["ratio"])),
        "reward_mult": t["reward"],
        "hp_mult": t.get("hp_mult", 1.0),
        "atk_mult": t.get("atk_mult", 1.0),
        "tier": tier,
        "is_boss": t.get("boss", False),
        "legendary": t.get("legendary", False),
        "first_strike": t.get("first_strike", False),
        "undead": t.get("undead", False),
        "shard_hint": t.get("shard_hint", False),
        "karma_react": t.get("karma_react", False),
        "special": t.get("special"),
        "stars": t.get("stars", 1),
        "skills": ENEMY_SKILLS_BY_TYPE.get(combat_key, []),
    }

# ── エリア別の敵プール（出現率テーブルの "pirate" 枠がこれを引く）──
#   激レア(leviathan/admiral)は重み1-5で本当に薄く。E3/E4は★3実装後に重み再調整。
ENEMY_POOL_BY_AREA = {
    1: [("pirate_old",30),("shark",25),("piranha",25),("castaway_foe",20)],   # E1=☆1雑魚のみ（全部倒せる）
    2: [("pirate_old",15),("pirate_drifter",15),("pirate_washout",13),("pirate_rogue",15),("shark",11),("piranha",7),("drowned",10),("wight",9)],
    3: [("pirate_washout",10),("pirate_rogue",16),("pirate_bounty",18),("drowned",11),("wight",7),("ghost",12),("serpent",9),("venom_serpent",10),("navy",7),("merchant_big",9),("leviathan",1)],
    4: [("pirate_bounty",24),("ghost",20),("hands",15),("navy",15),("merchant_big",10),("venom_serpent",7),("leviathan",6),("admiral",3)],
}
# ── エリアボス（"boss" 枠）──
ENEMY_BOSS_BY_AREA = {
    3: [("kraken",100)],
    4: [("yormun",100)],
}

def pick_enemy(area):
    """エリアの敵プールから1体抽選してspecを返す（pirate枠用）。"""
    pool = ENEMY_POOL_BY_AREA.get(area)
    if not pool:
        return None
    key = random.choices([k for k,_ in pool], weights=[w for _,w in pool])[0]
    return make_enemy_spec(key, area)

def pick_boss(area):
    """エリアボスを抽選してspecを返す（boss枠用）。"""
    pool = ENEMY_BOSS_BY_AREA.get(area)
    if not pool:
        return None
    key = random.choices([k for k,_ in pool], weights=[w for _,w in pool])[0]
    return make_enemy_spec(key, area)

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

# ━━━ ⛽ 燃料タンク制（Phase1）━━━
# 燃料は「船のタンク」から消費する。ナトコイン都度払いは廃止。
# 出航で満タン(船のmax_fuel)。探索1回ごと＋エリア移動ごとに消費。深いエリアほど大きく消費。
# frigate(33000)は E1-E2 をクリアできるが、E3でカケラ集めの燃料が尽きる＝詰み。E4到達は上位船(大タンク)必須。
# ※数値は仮。後でまとめて当てはめ・モンテカルロで整合を取る。
VOYAGE_EXPLORE_FUEL = {1: 900, 2: 1300, 3: 1700, 4: 2200}   # 探索1回の燃料消費（エリア別）
VOYAGE_MOVE_FUEL    = {2: 1500, 3: 2500, 4: 3500}            # 「進む」＝エリアNへ移動する燃料消費

def explore_fuel_cost(area):
    return VOYAGE_EXPLORE_FUEL.get(area, VOYAGE_EXPLORE_FUEL[4])

def move_fuel_cost(to_area):
    return VOYAGE_MOVE_FUEL.get(to_area, VOYAGE_MOVE_FUEL[4])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚢 船システム（船本体＋部位スロット）── 個人装備と同じ思想
#   船本体：☆レア度・基礎HP・基礎防御・部位スロット・技スロット・海の解放グレード。
#   部位（砲/装甲/艤装）に船装備を1個ずつ挿す。各船装備も☆レア度＆技スロット持ち。
#   装着制限：船のrank+2 までの装備しか挿せない（☆2船→☆4装備までOK）。
#   艤装は今は枠だけ（ソナー等の探索装備を後で）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RARITY_ENGRAVE_GAP = 2        # 船rank+2 まで の装備を挿せる

SHIP_PART_ORDER = ["cannon", "armor", "rigging"]
SHIP_PART_META = {
    "cannon":  {"name": "砲",   "emoji": "🔫", "role": "海戦の攻撃力"},
    "armor":   {"name": "装甲", "emoji": "🛡️", "role": "海戦の防御力"},
    "rigging": {"name": "艤装", "emoji": "🧭", "role": "探索装備（ソナー等・今後）"},
}

# 船本体カタログ（☆1は存在しない。最初の船は☆2）
SHIPS = {
    "frigate": {
        "name": "帆船", "emoji": "🚢", "rank": 2,
        "base_hp": 300, "base_def": 15,
        "parts": ["cannon", "armor", "rigging"],   # 使える部位スロット
        "skill_slots": 1,                          # 船本体に刻める技数
        "sea_unlock": 1,                           # 解放できる海グレード（1=大海原）
        "price": 200_000,
        "max_fuel": 33_000,                        # ⛽ 燃料タンク容量（満タン）。上位船ほど大きい＝航続距離↑
        "desc": "外洋に出られる最初の一隻（☆2）。砲・装甲・艤装を積んで戦う。",
    },
}

# 船装備カタログ（部位別・☆レア度・技スロット・耐久）
SHIP_PARTS = {
    "cannon": {"name": "砲", "emoji": "🔫", "items": {
        "iron_cannon": {"name": "鉄製砲", "power": 45, "rank": 1, "slots": 1,
                        "dura": 90, "price": 90_000,
                        "desc": "標準的な鉄の艦砲。海戦の主力。"},
    }},
    "armor": {"name": "装甲", "emoji": "🛡️", "items": {
        "iron_plate": {"name": "鉄装甲", "power": 22, "rank": 1, "slots": 1,
                       "dura": 110, "price": 80_000,
                       "desc": "船体を覆う鉄板。被ダメを抑える。"},
    }},
    "rigging": {"name": "艤装", "emoji": "🧭", "items": {}},   # 枠だけ（ソナー等は今後）
}

# ── 個人の装備（白兵）＆レベル ──
#   武器は「種別(剣/双剣/杖…)」を持つカタログ。技は武器種別で装着制限される。
#   防具は部位制（胴/脚。今後 足/腕 を追加予定）。装備に技スロット(slots)を持つ。
#   ★レアリティ(rank)で表示。今は全部 rank1=★1。上位は金星・黒星で青天井。

# 武器種別（6枠。今は剣/双剣/杖だけ実物あり。弓/刀/銃は枠のみ）
WEAPON_TYPES = {
    "bow":        {"name": "弓",   "emoji": "🏹"},
    "sword":      {"name": "剣",   "emoji": "⚔️"},
    "katana":     {"name": "刀",   "emoji": "🗡️"},
    "staff":      {"name": "杖",   "emoji": "🪄"},
    "twin":       {"name": "双剣", "emoji": "⚔️"},
    "gun":        {"name": "銃",   "emoji": "🔫"},
    "greatsword": {"name": "大剣", "emoji": "🗡️"},
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
    # ⚔️ 剣（バランス・一撃中）
    "cutlass":         {"name": "カトラス",   "wtype": "sword", "power": 35, "hits": 1, "slots": 1, "rank": 1, "req_lv": 1,  "price": 34000,  "desc": "扱いやすい片手剣。一撃の重さが持ち味。"},
    "corsair_blade":   {"name": "海賊刀",     "wtype": "sword", "power": 49, "hits": 1, "slots": 1, "rank": 2, "req_lv": 8,  "price": 85000, "desc": "歴戦の海賊が振るう片手剣。"},
    "admiral_sword":   {"name": "提督の長剣", "wtype": "sword", "power": 68, "hits": 1, "slots": 2, "rank": 3, "req_lv": 15, "price": 200000, "desc": "艦隊提督の佩刀。技を2つ刻める。"},
    # 🗡️ 双剣（手数・1発軽い／後半暴れないようpower低め）
    "twinblade":       {"name": "双剣",       "wtype": "twin",  "power": 12, "hits": 3, "slots": 1, "rank": 1, "req_lv": 1,  "price": 26000, "desc": "二刀の手数型。1発は軽いが三連で押す。"},
    "twin_fang":       {"name": "双牙",       "wtype": "twin",  "power": 17, "hits": 3, "slots": 1, "rank": 2, "req_lv": 8,  "price": 65000, "desc": "鋭く噛みつく二刀。"},
    "storm_twin":      {"name": "嵐の双刃",   "wtype": "twin",  "power": 24, "hits": 3, "slots": 2, "rank": 3, "req_lv": 15, "price": 152000, "desc": "嵐のように斬り刻む双刃。技を2つ刻める。"},
    # 🪄 杖（補助・回復）
    "staff":           {"name": "司祭の錫杖", "wtype": "staff", "power": 28, "hits": 1, "slots": 1, "rank": 1, "req_lv": 1,  "price": 29000, "desc": "回復技を扱えるヒーラー兼アタッカー。"},
    "sea_staff":       {"name": "海神の杖",   "wtype": "staff", "power": 40, "hits": 1, "slots": 1, "rank": 2, "req_lv": 8,  "price": 72000, "desc": "海神の加護を宿す杖。"},
    "abyss_staff":     {"name": "深海の宝杖", "wtype": "staff", "power": 55, "hits": 1, "slots": 2, "rank": 3, "req_lv": 15, "price": 170000, "desc": "深海の秘宝。技を2つ刻める。"},
    # 🏹 弓（中手数・安定）
    "pirate_bow":      {"name": "海賊の弓",   "wtype": "bow",   "power": 18, "hits": 2, "slots": 1, "rank": 1, "req_lv": 1,  "price": 30000, "desc": "二の矢で押す手数の弓。"},
    "strong_bow":      {"name": "強弓",       "wtype": "bow",   "power": 26, "hits": 2, "slots": 1, "rank": 2, "req_lv": 8,  "price": 75000, "desc": "張りの強い弓。"},
    "storm_bow":       {"name": "嵐弓",       "wtype": "bow",   "power": 35, "hits": 2, "slots": 2, "rank": 3, "req_lv": 15, "price": 176000, "desc": "矢継ぎ早に射る嵐の弓。技を2つ刻める。"},
    # 🔫 銃（一撃・貫通技と好相性）
    "matchlock":       {"name": "火縄銃",     "wtype": "gun",   "power": 35, "hits": 1, "slots": 1, "rank": 1, "req_lv": 1,  "price": 33000, "desc": "一撃は重いが、扱いに癖がある。"},
    "repeater":        {"name": "連発銃",     "wtype": "gun",   "power": 50, "hits": 1, "slots": 1, "rank": 2, "req_lv": 8,  "price": 82000, "desc": "連射の効く実弾銃。"},
    "admiral_gun":     {"name": "提督の銃",   "wtype": "gun",   "power": 68, "hits": 1, "slots": 2, "rank": 3, "req_lv": 15, "price": 194000, "desc": "提督の象徴たる銃。技を2つ刻める。"},
    # 🗡️ 大剣（重い一撃・硬い敵を断つ）
    "greatsword":      {"name": "大剣",       "wtype": "greatsword", "power": 42, "hits": 1, "slots": 1, "rank": 1, "req_lv": 1,  "price": 28000, "desc": "重い一撃で硬い敵を断つ。"},
    "iron_greatsword": {"name": "鉄塊の大剣", "wtype": "greatsword", "power": 59, "hits": 1, "slots": 1, "rank": 2, "req_lv": 8,  "price": 70000, "desc": "鉄塊のごとき大剣。"},
    "sea_cleaver":     {"name": "海割の大剣", "wtype": "greatsword", "power": 82, "hits": 1, "slots": 2, "rank": 3, "req_lv": 15, "price": 164000, "desc": "海をも断つ大剣。技を2つ刻める。"},
}

# 防具カタログ（部位制：胴/脚。今後 足/腕 を追加予定）。全部 rank1=★1・Lv1。
ARMOR_PARTS = {
    "torso": {"name": "胴", "emoji": "🦺", "items": {
        "leather_vest": {"name": "革の胴鎧",     "power": 12, "slots": 1, "rank": 1, "req_lv": 1,  "price": 19_000, "desc": "胴を守る革鎧。防御の要。"},
        "chainmail":    {"name": "鎖帷子",       "power": 20, "slots": 1, "rank": 2, "req_lv": 8,  "price": 47_000, "desc": "鎖を編んだ胴鎧。斬撃に強い。"},
        "plate_armor":  {"name": "鋼鉄の胸当て", "power": 30, "slots": 1, "rank": 3, "req_lv": 15, "price": 110_000,"desc": "鋼鉄の重鎧。最高の守り。"},
    }},
    "legs": {"name": "脚", "emoji": "🦵", "items": {
        "leather_greaves": {"name": "革のすね当て",   "power": 8,  "slots": 1, "rank": 1, "req_lv": 1,  "price": 15_000, "desc": "脚を守るすね当て。軽い守り。"},
        "chain_greaves":   {"name": "鎖の脚甲",       "power": 14, "slots": 1, "rank": 2, "req_lv": 8,  "price": 38_000, "desc": "鎖で編んだ脚甲。"},
        "plate_greaves":   {"name": "鋼鉄のグリーブ", "power": 22, "slots": 1, "rank": 3, "req_lv": 15, "price": 90_000, "desc": "鋼鉄の脚甲。重いが頑強。"},
    }},
}
ARMOR_PART_ORDER = ["torso", "legs"]

# ── 個人レベル ──
LEVEL_BASE_POWER = 2          # Lvごとの個人攻撃力ベース加算（控えめ＝装備が主役）
OFFHAND_HIT_MULT = 0.6        # 通常攻撃の2発目以降（手数武器の追撃）＝武器power×この倍率（レベル分は乗らない＝後半の手数爆発を抑制）
# A案：技の基礎値は武器の☆で決まる（武器の種類によらず横並び）。＝その☆の武器power平均値あたり。
SKILL_BASE_BY_RANK = {1: 30, 2: 42, 3: 56}
LEVEL_BASE_DEF   = 2          # Lvごとの個人防御力ベース加算（攻撃と同じ伸び）
LEVEL_MAX = 50
# XP獲得源（薄く配分）
XP_PER_FISH = 3
XP_PER_ISLAND = 5
XP_PER_PIRATE_WIN = 25
XP_PER_PIRATE_LOSE = 8        # 負けても少し経験は得る
# 必要XP（Lv→次Lvまで）。
# Lv5以降から必要XPを強めに上げ、Lv10以降はさらに重くする。
# 平原など低エリアで「XPが急に下がった」と見えないよう、報酬側ではなく必要XP側で詰まらせる。
def xp_to_next(level):
    level = int(level)
    if level <= 4:
        return int(60 * (level ** 1.45))
    # Lv5〜9：平原1000探索前後でLv10を狙う帯
    if level == 5:
        return 900
    if level == 6:
        return 1100
    if level == 7:
        return 1300
    if level == 8:
        return 1500
    if level == 9:
        return 1800
    # Lv10以降：次のステージへ行かないと現実的に伸びにくい重さ
    if level == 10:
        return 6000
    if level == 11:
        return 7500
    if level == 12:
        return 9000
    if level == 13:
        return 11000
    if level == 14:
        return 13500
    return int(13500 * ((level / 14) ** 2.0))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# マーケット適正価格ガード（Phase3で使用・少しきつめ）
#   出品可能レンジ = 基準価格 × [1-band, 1+band]。基準は (レア度=price) と戦闘力から自動算出。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MARKET_PRICE_BAND = 0.20      # ±20%（きつめ。金銭授受の抜け道を絞る）
MARKET_FEE = 0.05            # 売買手数料（コインシンク）

# ── 技ガチャ ──
GACHA_PRICE = 10_000
GACHA_TEN_PRICE = 90_000
GACHA_SKILL3_RATE = 0.002   # 0.2%
GACHA_PET_RATE = 0.001      # 0.1%
# ガチャv2：技/ペット以外にも街道消耗品を混ぜ、ハズレ感を減らす。
# 判定は上から順。残りは宝くじ。
GACHA_EPIC_ITEM_RATE = 0.0010       # 0.10%（身代わり人形/守護の羽）
GACHA_RARE_ITEM_RATE = 0.0220       # 2.20%（煙玉/お守り/地図）
GACHA_UNCOMMON_ITEM_RATE = 0.0400   # 4.00%（ランタン/羅針盤）
GACHA_FOOD_RATE = 0.4500            # 45.00%（乾パン/干し肉/船員の宴/包帯）
GACHA_MEDAL_PER_PULL = 1
GACHA_SKILL3_EXCHANGE_MEDALS = 200
GACHA_PET_EXCHANGE_MEDALS = 400
LOTTERY_ITEM_ID = "lottery_ticket"
LOTTERY_ITEM = {"name": "宝くじ", "emoji": "🎟️"}
PETS = {
    "pet_dog": {"name": "犬", "emoji": "🐶", "desc": "人懐っこい相棒。今は図鑑登録のみ。"},
    "pet_cat": {"name": "猫", "emoji": "🐱", "desc": "気まぐれな相棒。今は図鑑登録のみ。"},
}



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 海戦コマンドバトル接続（確率式 _pirate_fight → 実コマンド戦に置換）
#   海戦フェーズ（自船HP vs 敵船HP・船技発動）→ 4分岐 → 白兵フェーズ。
#     敵船HP0 → 乗り込み白兵(攻) ：勝=撃破/報酬・負=撤退/船倉無事
#     自船HP0 → 防衛白兵(守)      ：勝=撃退/船倉無事(船大破)・負=💀全損(船倉ロスト)
#   敵「船」ステは sea_power、敵「白兵」ステは crew_power から導出。
#   combat_scale は報酬スケールより緩い（高エリアでHP/ATKが爆発→詰みスロッグ化を防ぐ）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAVAL_SCALE_EXP   = 0.65       # 戦闘スケール圧縮: reward=scale / combat=scale**exp
def combat_scale(scale):
    return scale ** NAVAL_SCALE_EXP

# 敵「船」ステ導出（S = sea_power × combat_scale）
NAVAL_E_HP_MULT   = 5.0
NAVAL_E_ATK_MULT  = 0.9
NAVAL_E_DEF_MULT  = 0.4
# 敵「白兵」ステ導出（C = crew_power × combat_scale）
BOARD_E_HP_MULT   = 5.0
BOARD_E_ATK_MULT  = 1.0
BOARD_E_DEF_MULT  = 0.5

# 全損（自船HP0→防衛白兵敗北）の船倉ロスト率（1.0=全ロスト。特殊アイテムは生還）
WRECK_HOLD_LOSS   = 1.0

# 海戦からの撤退を許可（白兵フェーズ＝乗込/防衛は撤退不可で最後までやる）
NAVAL_ALLOW_FLEE  = True
# 撤退の成功率＝船の戦闘力依存（船が強い/敵が弱いほど振り切りやすい）。失敗すると敵の一撃を食らって戦闘続行。
FLEE_SHIP_W = 1.0      # 敵海戦力の重み（大きいほど強敵から逃げにくい）
FLEE_MIN    = 0.12     # 下限（どんな格上でも最低これだけは成功）
FLEE_MAX    = 0.90     # 上限
def flee_success_chance(ship_power, enemy_sea_eff):
    return max(FLEE_MIN, min(FLEE_MAX, ship_power / (ship_power + FLEE_SHIP_W * max(1.0, enemy_sea_eff))))

# 白兵の非対称：乗り込む側(攻)は敵"全員"＝強い／乗り込まれる側(防衛)は敵"一部"＝弱い
BOARD_DEFENSE_CREW_MULT = 0.45   # 防衛白兵での敵crew倍率（防衛で粘れる余地）

# 敵が海戦で使う船技（tierで増える）。値は voyage_skills の技ID。
NAVAL_ENEMY_SKILLS = {1: [], 2: [], 3: ["seisha"], 4: ["seisha", "tekkoudan"], 5: ["seisha", "tekkoudan", "enmaku"]}
# ボスのtier割当（AREA_BOSS は tier を持たないので外から付与）
BOSS_TIER = {3: 4, 4: 5}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚒️ 鍛冶屋クラフト v20 ── 重周回素材・採取イベント・職人装備
# ・素材図鑑に反映。入手場所は明記せず、名前と説明から推理する方針。
# ・☆2は平原素材 約1000周＋浅瀬素材 約300周が目安。
# ・☆3は森＋大洋素材を要求。現状は未来目標として表示。
# ・☆4ボス素材はクラフト素材に使わない。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRAFT_MATERIALS = {
    # 共通：どの装備にも絡みやすい基礎素材
    "plain_wood":       {"name":"乾いた木材",       "emoji":"🪵", "group":"common", "hint":"踏み固められた道のそばで見つかる、扱いやすい木材。"},
    "rough_stone":      {"name":"粗い石材",         "emoji":"🪨", "group":"common", "hint":"道端や岩陰で拾える、武具の芯材に向く石。"},
    "beast_hide":       {"name":"丈夫な獣革",       "emoji":"🥾", "group":"common", "hint":"草地を駆ける獣から取れる、しなやかで破れにくい革。"},
    "beast_bone":       {"name":"獣骨",             "emoji":"🦴", "group":"common", "hint":"小型の魔物や獣から残る、加工しやすい骨材。"},
    "plant_fiber":      {"name":"草編み繊維",       "emoji":"🧵", "group":"common", "hint":"草葉をより合わせた丈夫な繊維。弓や防具の補強に使える。"},
    "charcoal":         {"name":"鍛冶炭",           "emoji":"⚫", "group":"common", "hint":"火持ちのよい黒い炭。鍛冶場ではいくらあっても足りない。"},
    "small_magic_stone": {"name":"魔石の欠片",       "emoji":"💠", "group":"rare",   "hint":"魔物の気配が濃い場所でまれに見つかる、小さな光る欠片。"},
    "old_cloth":        {"name":"古布",             "emoji":"🧶", "group":"common", "hint":"風雨にさらされても破れにくい布。柄や杖の巻き材になる。"},

    # 平原（街道1）
    "green_ore":        {"name":"緑鉱石",           "emoji":"🟢", "group":"plain",  "hint":"草の根に抱かれるように眠る、淡く緑に光る鉱石。"},
    "sun_grass":        {"name":"陽だまり草",       "emoji":"🌿", "group":"plain",  "hint":"日当たりのよい草地で育つ、しなやかな薬草。"},
    "meadow_sinew":     {"name":"草原獣の腱",       "emoji":"〰️", "group":"plain",  "hint":"素早い獣から取れる強靭な腱。弓や双剣の素材に合う。"},
    "wind_shell":       {"name":"風鳴り殻",         "emoji":"🐚", "group":"plain",  "hint":"風の強い草地に転がる軽い殻。耳を当てると風の音がする。"},
    "plain_relic":      {"name":"草原の古片",       "emoji":"🏺", "group":"plain",  "hint":"草むらの下から出てくる古い欠片。なぜか鍛冶師が欲しがる。"},

    # 浅瀬（海洋1）
    "tide_iron":        {"name":"潮鉄",             "emoji":"⚙️", "group":"shallow","hint":"潮の香りが染みついた青白い鉄。水辺の漂着物に混じることがある。"},
    "shallow_coral":    {"name":"浅瀬サンゴ",       "emoji":"🪸", "group":"shallow","hint":"陽の届く海で育つ硬いサンゴ。磨くと防具の補強材になる。"},
    "driftwood_core":   {"name":"流木の芯材",       "emoji":"🪵", "group":"shallow","hint":"ただの流木ではない。塩に鍛えられた芯だけが武器に使える。"},
    "blue_glass_sand":  {"name":"青玻璃砂",         "emoji":"🔹", "group":"shallow","hint":"浅い海で光る青い砂。熱すると硬く透き通る。"},
    "foam_pearl":       {"name":"泡真珠",           "emoji":"⚪", "group":"shallow","hint":"泡のように軽い小粒の真珠。魔力を少しだけ通す。"},

    # 森（街道2 / ☆3）
    "ancient_wood":     {"name":"古木材",           "emoji":"🌳", "group":"forest", "hint":"深い森で長い年月を生きた木から取れる、粘りのある木材。"},
    "sap_crystal":      {"name":"樹液結晶",         "emoji":"🟡", "group":"forest", "hint":"森の奥で固まった樹液。魔力を通しやすい。"},
    "forest_fang":      {"name":"森狼の牙",         "emoji":"🦷", "group":"forest", "hint":"暗い木々の間で獲物を追う獣の牙。刃物に混ぜるとよく食い込む。"},
    "moss_stone":       {"name":"苔むした石",       "emoji":"🟩", "group":"forest", "hint":"湿った森で苔に覆われた石。衝撃を吸う性質がある。"},
    "spirit_leaf":      {"name":"精霊葉",           "emoji":"🍃", "group":"forest", "hint":"風もないのに揺れる葉。杖や弓に使うとよく馴染む。"},

    # 大洋（海洋2 / ☆3）
    "ocean_steel":      {"name":"大洋鋼",           "emoji":"🔩", "group":"ocean",  "hint":"外洋の荒波に揉まれた、重く粘る鋼材。"},
    "blue_pearl":       {"name":"蒼真珠",           "emoji":"🔵", "group":"ocean",  "hint":"澄んだ大洋でまれに見つかる、青く澄んだ真珠。"},
    "seaweed_fiber":    {"name":"海藻繊維",         "emoji":"🌊", "group":"ocean",  "hint":"強い潮にも千切れない海藻から取れる繊維。"},
    "white_coral":      {"name":"白珊瑚",           "emoji":"🤍", "group":"ocean",  "hint":"白く硬い珊瑚。磨くと金属のような光沢を持つ。"},
    "storm_shell":      {"name":"嵐貝の殻",         "emoji":"🐚", "group":"ocean",  "hint":"荒れた海で育つ貝の殻。薄いのに割れにくい。"},

    # 山（街道3 / 将来用）
    "granite":          {"name":"花崗岩",           "emoji":"🪨", "group":"mountain","hint":"硬い山肌から削れる重い岩材。守りの装備に向く。"},
    "mountain_silver":  {"name":"山銀",             "emoji":"⬜", "group":"mountain","hint":"高い場所の岩脈に眠る、鈍く輝く銀。"},
    "flint":            {"name":"火打石",           "emoji":"🔥", "group":"mountain","hint":"打つと火花を散らす石。鍛冶火の調整にも使われる。"},
    "giant_bone":       {"name":"巨獣の骨",         "emoji":"🦴", "group":"mountain","hint":"山に棲む大きな獣の骨。普通の刃では削れない。"},
    "hawk_feather":     {"name":"山鷹の羽",         "emoji":"🪶", "group":"mountain","hint":"高所を舞う鳥の羽。軽い装備に向く。"},

    # 沖合（海洋3 / 将来用）
    "obsidian":         {"name":"黒曜石",           "emoji":"⚫", "group":"offshore","hint":"黒く鋭い石。刃にするとよく切れるが扱いが難しい。"},
    "deep_iron":        {"name":"深海鉄",           "emoji":"🔧", "group":"offshore","hint":"深い海底で冷やされ続けた鉄。重く、非常に硬い。"},
    "giant_shell":      {"name":"巨大貝殻",         "emoji":"🐚", "group":"offshore","hint":"人の盾ほどもある貝殻。防具職人が目を輝かせる。"},
    "sea_king_crystal": {"name":"海王結晶",         "emoji":"💎", "group":"offshore","hint":"海の圧で生まれた結晶。まだ使い道は謎が多い。"},
    "black_salt":       {"name":"黒塩",             "emoji":"🧂", "group":"offshore","hint":"黒くざらついた塩。金属の焼き入れに使うという。"},
}
MATERIALS.update({mid: {"name": m["name"], "emoji": m["emoji"], "cat":"craft", "stars":1, "hint":m["hint"], "group":m.get("group","craft")}
                  for mid, m in CRAFT_MATERIALS.items()})

# エリア別クラフト素材ドロップ。land=街道、voyage=海洋探索。
# 1周目安：landは戦闘/採取/発見で複数機会があるため、レシピ側の要求数を重くして約1000周に寄せる。
# voyageは戦闘/発見で落ちるため、浅瀬素材は約300周に寄せる。
CRAFT_MATERIAL_DROPS = {
    "land": {
        1: [
            ("plain_wood",0.46),("rough_stone",0.40),("beast_hide",0.32),("beast_bone",0.30),
            ("plant_fiber",0.28),("charcoal",0.24),("old_cloth",0.18),
            ("green_ore",0.085),("sun_grass",0.075),("meadow_sinew",0.050),("wind_shell",0.040),
            ("plain_relic",0.018),("small_magic_stone",0.026),
        ],
        2: [
            ("ancient_wood",0.34),("sap_crystal",0.070),("forest_fang",0.055),("moss_stone",0.090),
            ("spirit_leaf",0.035),("beast_hide",0.20),("plant_fiber",0.20),("charcoal",0.18),
            ("small_magic_stone",0.030),
        ],
        3: [
            ("granite",0.26),("mountain_silver",0.060),("flint",0.11),("giant_bone",0.040),
            ("hawk_feather",0.035),("rough_stone",0.20),("charcoal",0.16),("small_magic_stone",0.035),
        ],
    },
    "voyage": {
        1: [
            ("driftwood_core",0.34),("tide_iron",0.24),("shallow_coral",0.20),
            ("blue_glass_sand",0.15),("foam_pearl",0.065),("small_magic_stone",0.035),
        ],
        2: [
            ("ocean_steel",0.18),("blue_pearl",0.075),("seaweed_fiber",0.20),("white_coral",0.11),
            ("storm_shell",0.055),("small_magic_stone",0.035),
        ],
        3: [
            ("obsidian",0.13),("deep_iron",0.11),("giant_shell",0.060),("sea_king_crystal",0.030),
            ("black_salt",0.10),("small_magic_stone",0.040),
        ],
        4: [("small_magic_stone",0.050)],
    }
}

def roll_craft_material(source, area, bonus=1.0, amount_bonus=False):
    """source='land'/'voyage'。当たれば素材ID、外れはNone。
    amount_bonus は将来用。今はIDだけ返し、個数は呼び出し側で決める。
    """
    pool = CRAFT_MATERIAL_DROPS.get(source, {}).get(int(area), [])
    hits = []
    for mid, rate in pool:
        if random.random() < rate * bonus:
            hits.append(mid)
    return random.choice(hits) if hits else None

# 鍛冶専用装備：既存☆2/☆3より約5〜10%弱い。ステータス詳細はUIで原則隠す。
WEAPONS.update({
    # ☆2 crafted（平原＋浅瀬）
    "forge_tide_sword": {"name":"鍛造・潮鉄の剣", "wtype":"sword", "power":45, "hits":1, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"潮鉄を打って作る鍛冶屋製の剣。ガチャ産☆2より少し控えめ。"},
    "forge_tide_twin":  {"name":"鍛造・潮牙の双剣", "wtype":"twin", "power":16, "hits":3, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"浅瀬素材で作る双剣。軽く、数で押す。"},
    "forge_coral_staff":{"name":"鍛造・珊瑚の杖", "wtype":"staff", "power":37, "hits":1, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"浅瀬サンゴを芯にした杖。"},
    "forge_green_bow":  {"name":"鍛造・緑鉱の弓", "wtype":"bow", "power":24, "hits":2, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"緑鉱石で補強した弓。"},
    "forge_tide_gun":   {"name":"鍛造・潮鳴り銃", "wtype":"gun", "power":46, "hits":1, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"潮鉄の銃身を持つ銃。"},
    "forge_core_greatsword":{"name":"鍛造・芯材の大剣", "wtype":"greatsword", "power":54, "hits":1, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"流木の芯材と潮鉄を束ねた大剣。"},
    # ☆3 crafted（森＋大洋。現状は素材不足で100%作れない未来目標）
    "forge_forest_sword": {"name":"鍛造・森潮の剣", "wtype":"sword", "power":62, "hits":1, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"森と大洋の素材を合わせた未踏の設計図。"},
    "forge_forest_twin":  {"name":"鍛造・森牙の双刃", "wtype":"twin", "power":22, "hits":3, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"森素材が必要な双刃。"},
    "forge_sap_staff":    {"name":"鍛造・樹液結晶の杖", "wtype":"staff", "power":51, "hits":1, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"樹液結晶を魔力の導線にした杖。"},
    "forge_ocean_bow":    {"name":"鍛造・大洋の強弓", "wtype":"bow", "power":32, "hits":2, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"大洋鋼で張力を高めた弓。"},
    "forge_ocean_gun":    {"name":"鍛造・蒼真珠の銃", "wtype":"gun", "power":62, "hits":1, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"蒼真珠を照準器に使う銃。"},
    "forge_ocean_greatsword":{"name":"鍛造・大洋鋼の大剣", "wtype":"greatsword", "power":75, "hits":1, "slots":2, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"大洋鋼を惜しみなく使った大剣。"},
})
ARMOR_PARTS["torso"]["items"].update({
    "forge_coral_mail": {"name":"鍛造・浅瀬の胴鎧", "power":18, "slots":1, "rank":2, "req_lv":8, "price":0, "crafted":True, "desc":"浅瀬サンゴと丈夫な獣革で作る鍛冶屋製の胴鎧。"},
    "forge_forest_mail":{"name":"鍛造・森潮の胴鎧", "power":27, "slots":1, "rank":3, "req_lv":15, "price":0, "crafted":True, "desc":"森素材と大洋素材を重ねた胴鎧。"},
})

CRAFT_RECIPES = {
    # ☆2武器：平原1000周＋浅瀬300周くらいの重め目標。武器種で素材傾向を分ける。
    "forge_tide_sword": {"kind":"weapon", "item":"forge_tide_sword", "rank":2, "cost":{"plain_wood":360,"beast_hide":260,"green_ore":70,"tide_iron":70,"driftwood_core":80,"small_magic_stone":24}},
    "forge_tide_twin": {"kind":"weapon", "item":"forge_tide_twin", "rank":2, "cost":{"beast_hide":320,"meadow_sinew":46,"green_ore":55,"tide_iron":65,"shallow_coral":60,"blue_glass_sand":42,"small_magic_stone":24}},
    "forge_coral_staff": {"kind":"weapon", "item":"forge_coral_staff", "rank":2, "cost":{"plain_wood":420,"old_cloth":140,"sun_grass":70,"driftwood_core":95,"shallow_coral":85,"foam_pearl":18,"small_magic_stone":28}},
    "forge_green_bow": {"kind":"weapon", "item":"forge_green_bow", "rank":2, "cost":{"plain_wood":460,"plant_fiber":260,"meadow_sinew":52,"wind_shell":38,"driftwood_core":90,"blue_glass_sand":38,"small_magic_stone":24}},
    "forge_tide_gun": {"kind":"weapon", "item":"forge_tide_gun", "rank":2, "cost":{"rough_stone":360,"charcoal":220,"green_ore":78,"plain_relic":16,"tide_iron":95,"foam_pearl":16,"small_magic_stone":30}},
    "forge_core_greatsword": {"kind":"weapon", "item":"forge_core_greatsword", "rank":2, "cost":{"rough_stone":430,"beast_bone":280,"green_ore":85,"plain_relic":18,"driftwood_core":115,"tide_iron":105,"small_magic_stone":32}},
    # ☆2防具：1種類作れれば満足できる重さ。防御の価値を上げる導線。
    "forge_coral_mail": {"kind":"armor", "part":"torso", "item":"forge_coral_mail", "rank":2, "cost":{"beast_hide":420,"beast_bone":260,"rough_stone":380,"shallow_coral":105,"tide_iron":80,"blue_glass_sand":46,"foam_pearl":18,"small_magic_stone":30}},

    # ☆3：森＋大洋素材。現状は作れない未来目標として鍛冶屋に表示。
    "forge_forest_sword": {"kind":"weapon", "item":"forge_forest_sword", "rank":3, "cost":{"ancient_wood":520,"sap_crystal":90,"forest_fang":65,"ocean_steel":140,"blue_pearl":55,"seaweed_fiber":160,"small_magic_stone":70}},
    "forge_forest_twin": {"kind":"weapon", "item":"forge_forest_twin", "rank":3, "cost":{"ancient_wood":440,"sap_crystal":105,"forest_fang":90,"ocean_steel":120,"blue_pearl":65,"storm_shell":42,"small_magic_stone":70}},
    "forge_sap_staff": {"kind":"weapon", "item":"forge_sap_staff", "rank":3, "cost":{"ancient_wood":620,"sap_crystal":145,"spirit_leaf":58,"blue_pearl":80,"white_coral":90,"small_magic_stone":84}},
    "forge_ocean_bow": {"kind":"weapon", "item":"forge_ocean_bow", "rank":3, "cost":{"ancient_wood":700,"moss_stone":110,"spirit_leaf":50,"ocean_steel":120,"seaweed_fiber":220,"storm_shell":45,"small_magic_stone":72}},
    "forge_ocean_gun": {"kind":"weapon", "item":"forge_ocean_gun", "rank":3, "cost":{"charcoal":500,"sap_crystal":95,"ocean_steel":210,"blue_pearl":92,"white_coral":110,"small_magic_stone":88}},
    "forge_ocean_greatsword": {"kind":"weapon", "item":"forge_ocean_greatsword", "rank":3, "cost":{"ancient_wood":520,"forest_fang":75,"ocean_steel":260,"blue_pearl":75,"white_coral":120,"small_magic_stone":96}},
    "forge_forest_mail": {"kind":"armor", "part":"torso", "item":"forge_forest_mail", "rank":3, "cost":{"ancient_wood":620,"moss_stone":180,"sap_crystal":120,"ocean_steel":190,"white_coral":150,"storm_shell":70,"small_magic_stone":90}},
}
