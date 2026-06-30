"""
🛤️ 街道（陸の冒険）の設定
─────────────────────────────────────────────
海の白兵戦エンジン・装備・技をそのまま流用する「陸」コンテンツ。
・平原＝素手でも確実に倒せる激弱バランス（ただし装備が無いと時間がかかり、ちまちま削られる）。
・森＝海のE2くらいの“手応え”。ちゃんと装備すればあまり食らわないが、生身だと痛手。
・山＝海のE3くらいの“手応え”。
・全体方針：敵の攻撃力は低め（＝あまりダメージを食らわない）。きついのは「装備が足りない」とき。
・HPは毎戦は回復しない（持ち越し）。タウンに戻っても全快しない。回復は家/食料で行う。
・XPはエリアごとの想定周回数で調整。森はLv10〜20を約1500探索、山はLv20〜30を約2000探索の体感。
・船・燃料・カケラは無い。

敵スペックは make_board_enemy(spec, scale) がそのまま食える形。
  敵HP  = crew_power × combat_scale(scale) × BOARD_E_HP_MULT(5.0) × hp_mult
  敵ATK = crew_power × scale^0.65 × BOARD_E_ATK_MULT(1.0) × atk_mult
  敵DEF = crew_power × scale^0.65 × BOARD_E_DEF_MULT(0.5)
"""
import random

# ── エリア定義 ──
#   req_lv：解放レベル（想定レベル）。base：crew_power の底上げ。scale：戦闘スケール。
#   xp/coin：撃破報酬の範囲（雑魚）。森/山は想定探索回数から逆算。
LAND_AREAS = {
    1: {"name": "平原", "emoji": "🌿", "req_lv": 1,  "base": 8,  "scale": 1.0,
        "xp": [4, 6],     "coin": [200, 600],
        "intro": ("見渡すかぎりの草原。風が膝丈の草を撫でていく。\n"
                  "弱い魔物がぽつぽつと現れる――腕慣らしには、ちょうどいい。\n"
                  "……ふと、草の向こうで何かが動いた気がした。気のせいか。")},
    2: {"name": "森", "emoji": "🌲", "req_lv": 8,  "base": 30, "scale": 1.8,
        "xp": [120, 180], "coin": [450, 1100],
        "intro": ("木々が空を覆い、足元は薄暗い。獣の気配が、あちこちに。\n"
                  "平原より、ずっと手強い――ちゃんと武器と防具を整えてこい。\n"
                  "奥には、人の手が入った痕跡。誰かが、この森を“管理”している。")},
    3: {"name": "山", "emoji": "⛰️", "req_lv": 15, "base": 36, "scale": 2.8,
        "xp": [220, 300], "coin": [900, 2000],
        "intro": ("切り立った岩肌と、薄い空気。棲むものは、どれも一筋縄ではいかない。\n"
                  "尾根の向こうに、ぽつんと立つ塔の影。\n"
                  "あれが――海と戦い続けているという、“陸のやつら”の根城か。")},
}


# ── 街道XP補正 ──
# XPは報酬を急に下げず、必要XP（voyage_config.xp_to_next）側で詰まらせる。
# そのためエリア補正は原則1.0。
LAND_XP_AREA_SCALE = {
    1: [(1, 1.00)],
    2: [(1, 1.00)],
    3: [(1, 1.00)],
}

def land_xp_scale(area:int, level:int) -> float:
    scale = 1.0
    for min_lv, mult in LAND_XP_AREA_SCALE.get(area, [(1,1.0)]):
        if level >= min_lv:
            scale = mult
    return scale

# ── 敵カタログ（エリア別）──
#   ratio：base への倍率（強さ）。hp_mult/atk_mult：味付け。tier：AI・技の強さ。stars：表示用の☆（強さ＝1〜3）。
LAND_ENEMIES = {
    1: [  # 🌿 平原 ☆1：素手でも確実に倒せる。攻撃は微々たるもの。
        {"name": "スライム",         "emoji": "🟢",  "ratio": 0.95, "hp_mult": 1.85, "atk_mult": 1.12, "tier": 1, "stars": 1},
        {"name": "野ねずみの群れ",   "emoji": "🐀",  "ratio": 1.05, "hp_mult": 1.65, "atk_mult": 1.18, "tier": 1, "stars": 1},
        {"name": "青大将",           "emoji": "🐍",  "ratio": 1.15, "hp_mult": 1.75, "atk_mult": 1.18, "tier": 1, "stars": 1},
        {"name": "野犬",             "emoji": "🐕",  "ratio": 1.25, "hp_mult": 1.75, "atk_mult": 1.28, "tier": 1, "stars": 1},
        {"name": "ゴブリンの子",     "emoji": "👶",  "ratio": 1.25, "hp_mult": 1.85, "atk_mult": 1.22, "tier": 1, "stars": 1},
        {"name": "大バッタ",         "emoji": "🦗",  "ratio": 1.35, "hp_mult": 1.65, "atk_mult": 1.28, "tier": 1, "stars": 1},
        {"name": "はぐれゴブリン",   "emoji": "👺",  "ratio": 1.45, "hp_mult": 1.90, "atk_mult": 1.32, "tier": 1, "stars": 1},
        {"name": "イノシシ",         "emoji": "🐗",  "ratio": 1.55, "hp_mult": 2.05, "atk_mult": 1.42, "tier": 1, "stars": 1},
        # v18追加：表示は全て☆1。既存☆1の中で弱め2体・強め3体にばらけさせる。
        {"name": "草むらネズミ",     "emoji": "🐭",  "ratio": 0.82, "hp_mult": 1.45, "atk_mult": 1.05, "tier": 1, "stars": 1},
        {"name": "泥はねガエル",     "emoji": "🐸",  "ratio": 0.90, "hp_mult": 1.70, "atk_mult": 1.04, "tier": 1, "stars": 1},
        {"name": "錆び短剣の盗人",   "emoji": "🗡️",  "ratio": 1.18, "hp_mult": 1.65, "atk_mult": 1.30, "tier": 1, "stars": 1},
        {"name": "棍棒ゴブリン",     "emoji": "👺",  "ratio": 1.34, "hp_mult": 1.85, "atk_mult": 1.32, "tier": 1, "stars": 1},
        {"name": "飢えた狼",         "emoji": "🐺",  "ratio": 1.50, "hp_mult": 1.70, "atk_mult": 1.48, "tier": 1, "stars": 1},
    ],
    2: [  # 🌲 森：Lv15＋☆1フル装備を基準。雑魚は勝てるが、強い個体はしっかり削る。
        {"name": "森オオカミ",       "emoji": "🐺",  "ratio": 0.95, "hp_mult": 1.10, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "コボルト",         "emoji": "🦎",  "ratio": 1.00, "hp_mult": 1.12, "atk_mult": 0.46, "tier": 2, "stars": 2},
        {"name": "大グモ",           "emoji": "🕷️",  "ratio": 1.05, "hp_mult": 1.08, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "毒キノコ人間",     "emoji": "🍄",  "ratio": 1.05, "hp_mult": 1.18, "atk_mult": 0.44, "tier": 2, "stars": 2},
        {"name": "山賊の物見",       "emoji": "🗡️",  "ratio": 1.10, "hp_mult": 1.08, "atk_mult": 0.50, "tier": 2, "stars": 2},
        {"name": "大ムカデ",         "emoji": "🐛",  "ratio": 1.10, "hp_mult": 1.12, "atk_mult": 0.46, "tier": 2, "stars": 2},
        {"name": "塔の番犬",         "emoji": "🐕‍🦺", "ratio": 1.15, "hp_mult": 1.18, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "森の熊",           "emoji": "🐻",  "ratio": 1.20, "hp_mult": 1.28, "atk_mult": 0.50, "tier": 2, "stars": 2},
        # v18追加：表示は全て☆2。既存☆2の中で弱め2体・強め3体にばらけさせる。
        {"name": "枝角ウサギ",       "emoji": "🐇",  "ratio": 0.84, "hp_mult": 1.02, "atk_mult": 0.43, "tier": 2, "stars": 2},
        {"name": "苔むした小鬼",     "emoji": "🧌",  "ratio": 0.90, "hp_mult": 1.15, "atk_mult": 0.43, "tier": 2, "stars": 2},
        {"name": "毒牙イタチ",       "emoji": "🦡",  "ratio": 1.08, "hp_mult": 1.00, "atk_mult": 0.52, "tier": 2, "stars": 2},
        {"name": "森賊の斧使い",     "emoji": "🪓",  "ratio": 1.16, "hp_mult": 1.12, "atk_mult": 0.54, "tier": 2, "stars": 2},
        {"name": "黒毛の大狼",       "emoji": "🐺",  "ratio": 1.24, "hp_mult": 1.20, "atk_mult": 0.54, "tier": 2, "stars": 2},
    ],
    3: [  # ⛰️ 山：Lv25＋☆2フル装備を基準。雑魚でも手応え、中ボスは明確な危険枠。
        {"name": "岩トカゲ",         "emoji": "🦎",  "ratio": 0.90, "hp_mult": 1.10, "atk_mult": 0.40, "tier": 3, "stars": 3},
        {"name": "山賊",             "emoji": "🪓",  "ratio": 1.00, "hp_mult": 1.00, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "ハーピー",         "emoji": "🦅",  "ratio": 1.00, "hp_mult": 0.95, "atk_mult": 0.46, "tier": 3, "stars": 3},
        {"name": "塔の衛兵",         "emoji": "💂",  "ratio": 1.05, "hp_mult": 1.10, "atk_mult": 0.42, "tier": 3, "stars": 3},
        {"name": "岩ゴーレム",       "emoji": "🗿",  "ratio": 1.10, "hp_mult": 1.25, "atk_mult": 0.38, "tier": 3, "stars": 3},
        {"name": "霜の魔狼",         "emoji": "🐺",  "ratio": 1.10, "hp_mult": 1.00, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "オーガ",           "emoji": "👹",  "ratio": 1.20, "hp_mult": 1.20, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "ワイバーン",       "emoji": "🐉",  "ratio": 1.20, "hp_mult": 1.05, "atk_mult": 0.46, "tier": 3, "stars": 3},
        # v18追加：表示は全て☆3。既存☆3の中で弱め2体・強め3体にばらけさせる。
        {"name": "岩影コウモリ",     "emoji": "🦇",  "ratio": 0.82, "hp_mult": 0.92, "atk_mult": 0.38, "tier": 3, "stars": 3},
        {"name": "痩せ山狼",         "emoji": "🐺",  "ratio": 0.90, "hp_mult": 0.98, "atk_mult": 0.40, "tier": 3, "stars": 3},
        {"name": "落石まとう山賊",   "emoji": "🪨",  "ratio": 1.08, "hp_mult": 1.12, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "塔の槍兵",         "emoji": "💂",  "ratio": 1.14, "hp_mult": 1.08, "atk_mult": 0.48, "tier": 3, "stars": 3},
        {"name": "若いワイバーン",   "emoji": "🐲",  "ratio": 1.22, "hp_mult": 1.10, "atk_mult": 0.50, "tier": 3, "stars": 3},
    ],
}

# ── ✨ レアキャラ（激レア＝遭遇1%・固有名・☆4・XP/コイン大盛り）──
#   戦闘前に「挑む／見送る」を選べる（＝確実に逃げられる）。rare_intro＝やばさを煽る前口上。
LAND_RARES = {
    1: [
        {"name": "迷い込んだ白鹿",   "emoji": "🦌", "ratio": 1.6, "hp_mult": 1.6, "atk_mult": 0.42, "tier": 2, "stars": 4,
         "xp": [200, 350], "coin": [4000, 8000],
         "rare_intro": ("草原の空気が、ぴたりと凍りついた。\n"
                        "見たこともない白い獣が、こちらをじっと見据えている。\n"
                        "なぜか――背筋が、ぞくりと粟立つ。"),
         "story": "白鹿は息絶える間際、こちらをじっと見た。\nその瞳の奥には、深い森と、もっと深い“なにか”が映っていた。"},
    ],
    2: [
        {"name": "森番のフードの男",  "emoji": "🧥", "ratio": 2.2, "hp_mult": 1.8, "atk_mult": 0.50, "tier": 3, "stars": 4,
         "xp": [900, 1400], "coin": [9000, 16000],
         "rare_intro": ("森のざわめきが、ふっと止んだ。\n"
                        "フードを目深にかぶった男が、音もなく行く手を塞ぐ。\n"
                        "……こいつは、これまでの獣とは“格”が違う。"),
         "story": "倒れた男の懐から、塔の紋章入りの書付が落ちた。\n「海の者を、陸に上げるな」――そう走り書きされていた。"},
    ],
    3: [
        {"name": "塔の伝令騎士",      "emoji": "🛡️", "ratio": 1.7, "hp_mult": 1.7, "atk_mult": 0.60, "tier": 4, "stars": 4,
         "xp": [2200, 3400], "coin": [18000, 35000],
         "rare_intro": ("空気が、軋んだ。\n"
                        "塔の紋章を掲げた騎士が、ゆっくりと剣を抜く。\n"
                        "ひと目でわかる――まともにやり合えば、ただでは済まない。"),
         "story": "騎士は崩れ落ちながら、低く笑った。\n「塔は海を抑えているのではない。……抑えられているのは、こちらの方だ」"},
    ],
}
RARE_SPAWN_RATE = 0.01   # 戦闘のうちレア（激レア）に化ける確率（1%）

# ── 激レア☆4の強さ（平原の白鹿を基準に、森・山は段階的に格上げ）──
#   旧仕様は全エリア共通 crew_power=60 だったため、白鹿・森番・塔騎士がほぼ同じ強さになっていた。
#   今回は白鹿だけ旧値を維持し、森=1.5倍、山=2.0倍を目安に危険度と報酬を釣り合わせる。
RARE_BOSS_BY_AREA = {
    1: {"crew_power": 60,  "scale": 2.20, "hp_mult": 1.60, "atk_mult": 0.58, "tier": 4, "stars": 4},  # 迷い込んだ白鹿：旧強さ維持
    2: {"crew_power": 90,  "scale": 2.35, "hp_mult": 1.75, "atk_mult": 0.62, "tier": 4, "stars": 4},  # 森番：白鹿より明確に強い
    3: {"crew_power": 120, "scale": 2.50, "hp_mult": 1.90, "atk_mult": 0.68, "tier": 5, "stars": 4},  # 塔騎士：山の危険枠
}
RARE_BOSS = {**RARE_BOSS_BY_AREA[1],
             "drop": [("dist", 0.20, [(2, 0.95), (3, 0.05)])]}   # 互換用。白鹿の旧値と同じ。

# ── 🔸 中レア（各エリア3種・遭遇5%）──
#   雑魚と激レアの中間。倒せるが歯ごたえあり＝固有名・XP/コイン多め・装備ドロップ高め。
#   強さはエリアのbase×ratioで雑魚と同じ計算（激レアのような固定ボスではない）。
#   midrare_drop：撃破時の装備ドロップ（☆, 確率）。
LAND_MIDRARES = {
    1: [  # 🌿 平原 ☆2
        {"name": "草原の大猪",     "emoji": "🐗", "ratio": 3.6, "hp_mult": 2.2, "atk_mult": 0.58, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "古老ゴブリン",   "emoji": "👹", "ratio": 3.4, "hp_mult": 2.3, "atk_mult": 0.58, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "群れの長狼",     "emoji": "🐺", "ratio": 3.8, "hp_mult": 2.1, "atk_mult": 0.62, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
    ],
    2: [  # 🌲 森 ☆3
        {"name": "森の主・大熊",   "emoji": "🐻", "ratio": 2.2, "hp_mult": 1.7, "atk_mult": 0.40, "tier": 2, "stars": 3,
         "xp": [300, 480], "coin": [2200, 4800], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "毒蜘蛛の女王",   "emoji": "🕷️", "ratio": 2.0, "hp_mult": 1.6, "atk_mult": 0.42, "tier": 2, "stars": 3,
         "xp": [300, 480], "coin": [2200, 4800], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "山賊の頭目",     "emoji": "🗡️", "ratio": 2.1, "hp_mult": 1.5, "atk_mult": 0.44, "tier": 2, "stars": 3,
         "xp": [300, 480], "coin": [2200, 4800], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
    ],
    3: [  # ⛰️ 山 ☆3
        {"name": "古竜のなりそこない", "emoji": "🐲", "ratio": 2.5, "hp_mult": 1.6, "atk_mult": 0.46, "tier": 3, "stars": 3,
         "xp": [750, 1050], "coin": [4500, 9000], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "石の巨人",       "emoji": "🗿", "ratio": 2.2, "hp_mult": 1.8, "atk_mult": 0.42, "tier": 3, "stars": 3,
         "xp": [750, 1050], "coin": [4500, 9000], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
        {"name": "山の魔女",       "emoji": "🧙", "ratio": 2.4, "hp_mult": 1.5, "atk_mult": 0.48, "tier": 3, "stars": 3,
         "xp": [750, 1050], "coin": [4500, 9000], "drop": [("dist", 0.03, [(1, 0.70), (2, 0.29), (3, 0.01)])]},
    ],
}
MIDRARE_SPAWN_RATE = 0.05   # 戦闘のうち中レアに化ける確率（5%）

# 🔥 熱いイベント経由の強敵用ドロップ。
# ☆3装備はバランス崩壊を避けるため出さない。
# 通常の中ボスと同じく「3%で装備抽選」だが、当たった場合は☆1/☆2のみ。
HOT_EVENT_EQUIP_DROP = [("dist", 0.03, [(1, 0.70), (2, 0.30)])]



# ── 💎 経験値逃走モンスター v17 ──
# 戦闘枠の中で低確率。装備/アイテムの平均ドロップ率を変えないため、ドロップは無し。
# 通常版：約2% / キング版：約0.1%。毎ターン50%で逃げる。
XP_RUNNER_RATE = 0.02
XP_RUNNER_KING_RATE = 0.001
XP_RUNNERS = {
    1: {
        "normal": {"name":"黄金スライム", "emoji":"💎", "ratio":2.8, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.35, "def_mult":12.0, "tier":1, "stars":2, "xp_mult":20, "coin_mult":0.25},
        "king":   {"name":"黄金キングスライム", "emoji":"👑", "ratio":4.2, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.45, "def_mult":14.0, "tier":2, "stars":4, "xp_mult":100, "coin_mult":0.50},
    },
    2: {
        "normal": {"name":"翡翠の妖精虫", "emoji":"💎", "ratio":1.8, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.34, "def_mult":13.0, "tier":2, "stars":3, "xp_mult":20, "coin_mult":0.25},
        "king":   {"name":"翡翠の女王虫", "emoji":"👑", "ratio":2.8, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.44, "def_mult":15.0, "tier":3, "stars":4, "xp_mult":100, "coin_mult":0.50},
    },
    3: {
        "normal": {"name":"結晶岩ゴーレム", "emoji":"💎", "ratio":1.6, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.34, "def_mult":14.0, "tier":3, "stars":3, "xp_mult":20, "coin_mult":0.25},
        "king":   {"name":"水晶巨人", "emoji":"👑", "ratio":2.5, "fixed_hp":6, "hp_mult":1.0, "atk_mult":0.46, "def_mult":16.0, "tier":4, "stars":4, "xp_mult":100, "coin_mult":0.50},
    },
}

# ── 採取（戦闘なし・小コイン＋雰囲気）──
LAND_GATHER = {
    1: ["道端で薬草をひと摑み摘んだ。", "茂みで木の実を見つけた。", "湧き水のほとりで、こぼれた小銭を拾った。"],
    2: ["倒木の陰で、立派なきのこを採った。", "うろの中に、野生の蜂蜜を見つけた。",
        "落ち葉の下から、塔の紋章が刻まれた古い硬貨が出てきた。"],
    3: ["岩肌から、きらりと光る鉱石を削り出した。", "斜面で、薬になりそうな薬石を拾った。",
        "崩れた見張り小屋の跡から、忘れられた銭袋を見つけた。"],
}
LAND_GATHER_COIN = {1: [80, 300], 2: [200, 600], 3: [400, 1100]}

# ── 何も無し（平穏）──
LAND_CALM = [
    "🌾 風が草を渡っていく。今は、何も現れなかった。",
    "🐦 小鳥のさえずりだけが響いている。静かなものだ。",
    "☀️ 雲が流れ、影が地面を撫でていった。特に、何も。",
    "🍃 道は、どこまでも続いている。ひとまず、ひと息ついた。",
    "🌫️ 遠くに、塔の影がぼんやり見える。今日は、それ以上は何も。",
]

# ── 遭遇の重み（探索1回・エリア別に調整可）──
#   combat＝戦闘（基本これが半分）。story＝陸ストーリー。event＝海っぽい寄り道イベント。
#   gather＝採取。calm＝なにもなし。各エリア合計100。
LAND_ENCOUNTERS = {
    1: {"combat": 50, "story": 14, "event": 16, "gather": 14, "calm": 6},
    2: {"combat": 50, "story": 16, "event": 16, "gather": 12, "calm": 6},
    3: {"combat": 50, "story": 18, "event": 18, "gather": 8,  "calm": 6},
}

# ── 装備ドロップ（陸でも“たまに”落ちる。エリア＝☆対応・一律0.5%）──
# 通常雑魚の装備ドロップ。
# まず 0.1% の「装備が落ちるか」判定 → 当たった場合だけ星抽選。
# ☆1雑魚：☆1 99% / ☆2 1% / ☆3以上 0%。
# ※エリア制限は入れない。平原でも森でも山でも、通常雑魚からの☆3装備は出ない。
LAND_EQUIP_DROP = {1: [("dist", 0.001, [(1, 0.99), (2, 0.01)])],
                   2: [("dist", 0.001, [(1, 0.99), (2, 0.01)])],
                   3: [("dist", 0.001, [(1, 0.99), (2, 0.01)])]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📖 陸ストーリー（塔＝“陸のやつら”＝第2層）
#   暗いトーン。陸勢力（塔）は海と戦う別存在だが、正義ではない。
#   ※ 最深層（観測者）の核心はまだ伏せる＝ここでは塔・陸・海の話に留める。
#   type: "text"  … 一話完結フレーバー（選択肢なし）
#         "choice"… 選択肢つき（coin / xp で分岐）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAND_STORY = {
    1: [  # 🌿 平原：塔の“噂”。海から来た余所者という視点。
        {"id": "p_traveler", "type": "choice",
         "emoji": "🧳", "title": "草原の旅人",
         "flavor": ("荷を背負った旅人が、警戒した目でこちらを見た。\n"
                    "「あんた……海の匂いがするな。陸じゃ珍しい。\n"
                    "　北の塔の連中に見つかる前に、深入りはやめときな」"),
         "choices": [
             {"label": "💰 路銀を分ける", "result": ("旅人は驚き、礼に古地図の切れ端をくれた。\n"
                                                 "「塔は、海を“抑えてる”んだと。……何から、かは知らんがね」"),
              "coin": [300, 800], "xp": [3, 6]},
             {"label": "❓ 塔のことを訊く", "result": ("「昔から山にあるのさ。海と戦ってる、とも、海を飼ってる、とも言う。\n"
                                                    "　どっちにしろ、まともじゃない」――旅人は足早に去っていった。"),
              "xp": [2, 5]},
             {"label": "⚓ 関わらない", "result": "旅人は小さく頷いて、草原の向こうへ消えた。", "xp": [1, 3]},
         ]},
        {"id": "p_stone", "type": "text",
         "emoji": "🪨", "title": "古い境界石",
         "body": ("草の中に、苔むした境界石。\n"
                  "「ここより先、海の理は通用せず」と、かすれた字で彫られている。\n"
                  "陸は陸の掟で回っている。お前は、その外から来た客だ。")},
        {"id": "p_scout", "type": "text",
         "emoji": "🏹", "title": "草の向こうの影",
         "body": ("遠くの茂みが、不自然に揺れた。\n"
                  "塔の斥候だろうか。海から上がった者を、陸はずっと警戒している。\n"
                  "見られていることに、いい気はしない。")},
    ],
    2: [  # 🌲 森：塔の“支配”が見えてくる。陸勢力は正義ではない。
        {"id": "f_post", "type": "text",
         "emoji": "📌", "title": "立て札",
         "body": ("木に打ち付けられた、塔の名の立て札。\n"
                  "「海より上がりし者の通行を禁ず。見つけ次第、これを討つ」\n"
                  "歓迎されていないのは、とうにわかっていた。")},
        {"id": "f_hunter", "type": "choice",
         "emoji": "🏹", "title": "森番の狩人",
         "flavor": ("弓を構えた狩人が、木陰から現れた。\n"
                    "「塔の命令だ。海の者は通せん。……が、俺は命令が好きじゃない。\n"
                    "　見逃してやる代わりに、ひとつ運んでくれ。山の上の“あれ”に届けてくれ」"),
         "choices": [
             {"label": "📦 荷を引き受ける", "result": ("狩人は黒い封蝋の包みを押し付けてきた。\n"
                                                   "「中身は見るな。塔の連中も、本当は何を抑えてるか知らんのさ」"),
              "xp": [8, 14], "coin": [400, 1000]},
             {"label": "⚔️ 信用しない", "result": ("「賢明だ」と狩人は笑い、矢を下ろした。\n"
                                                "「だが覚えとけ。この森で“管理”してるのは、獣じゃない。塔だ」"),
              "xp": [6, 11]},
         ]},
        {"id": "f_cage", "type": "text",
         "emoji": "⛓️", "title": "空っぽの檻",
         "body": ("森の奥に、人ひとり入る大きさの鉄の檻。\n"
                  "錆びた鉄格子は内側から押し曲げられている。\n"
                  "塔は、何かを“ここに留めて”おこうとして――失敗したらしい。")},
    ],
    3: [  # ⛰️ 山：塔へ近づく。陸勢力の本性。
        {"id": "m_gate", "type": "text",
         "emoji": "🏯", "title": "塔の門前",
         "body": ("尾根を越えると、巨大な石の塔がそびえていた。\n"
                  "壁面には無数の鎖。すべて、海の方角へ向かって張られている。\n"
                  "彼らは本当に、海“そのもの”を縛り上げようとしているのか。")},
        {"id": "m_warden", "type": "choice",
         "emoji": "🗝️", "title": "塔の管理者",
         "flavor": ("灰色のローブの男が、塔の影から声をかけてきた。\n"
                    "「海の客人か。よく来た。……だが、勘違いするな。\n"
                    "　我々は英雄ではない。海を“抑える”ためなら、何でもする。お前ごとでもな」"),
         "choices": [
             {"label": "🤝 協力を申し出る", "result": ("「ふん。海の者が陸に与するか。面白い」\n"
                                                   "男は鍵束を鳴らした。「だが忘れるな。海は、縛るほどに静かに牙を研ぐ。\n"
                                                   "　いつか、この鎖ごと飲み込まれる日が来る」"),
              "xp": [12, 20], "coin": [1500, 3500]},
             {"label": "🚪 立ち去る", "result": ("「賢明だ。深入りした客は、たいてい帰らん」\n"
                                              "背を向けると、塔の鎖が、ぎぃ、と低く鳴いた。"),
              "xp": [9, 16]},
         ]},
        {"id": "m_quiet", "type": "text",
         "emoji": "🪨", "title": "鎖の根元",
         "body": ("塔の真下、海へ伸びる鎖の根元に立った。\n"
                  "鎖は、ぴんと張りつめ、かすかに脈打っている。\n"
                  "縛られているのは海か、それとも――塔の方なのか。")},
    ],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎁 寄り道イベント（海っぽい：発見・選択・小事件）
#   schema は story と互換＋効果キー：coin / xp / heal(割合) / dmg(固定HP) / food(食料id付与)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAND_EVENTS = {
    1: [
        {"id": "e_purse", "type": "choice",
         "emoji": "👛", "title": "落とし物の財布",
         "flavor": "道端に、ぽつんと革の財布が落ちている。中には、そこそこの銭。",
         "choices": [
             {"label": "💰 拾って懐に入れる", "result": "ありがたく頂戴した。", "coin": [400, 900]},
             {"label": "🏘️ 番屋に届ける",   "result": "落とし主が現れ、礼金をくれた。気分がいい。", "coin": [200, 500], "xp": [2, 4]},
             {"label": "🚶 見なかったことに", "result": "関わらず、先を急いだ。", "xp": [1, 2]},
         ]},
        {"id": "e_teahouse", "type": "choice",
         "emoji": "🍵", "title": "街道の茶屋",
         "flavor": "草原のはずれに、ぽつんと茶屋。婆さんが手招きしている。",
         "choices": [
             {"label": "🍙 握り飯をもらう", "result": "婆さんは握り飯を持たせてくれた。道中の足しに。", "food": "hardtack"},
             {"label": "☕ 一服する",       "result": "熱い茶で、少し体が癒えた。", "heal": 0.25},
             {"label": "🚶 通り過ぎる",     "result": "会釈だけして、先へ進んだ。", "xp": [1, 2]},
         ]},
        {"id": "e_pitfall", "type": "choice",
         "emoji": "🕳️", "title": "道の落とし穴",
         "flavor": "前方の地面が、妙に不自然だ。獣道に仕掛けられた穴かもしれない。",
         "choices": [
             {"label": "🐾 慎重に避ける", "result": "用心して回り込んだ。何事もなし。", "xp": [2, 4]},
             {"label": "🏃 走って渡る",   "result": "勢いで踏み抜き、軽く足を痛めた。が、穴の底に小銭が。", "dmg": 8, "coin": [300, 700]},
         ]},
    ],
    2: [
        {"id": "e_chest", "type": "choice",
         "emoji": "🎁", "title": "朽ちた宝箱",
         "flavor": "倒木の陰に、苔むした木箱。鍵は壊れている。",
         "choices": [
             {"label": "📦 一気に開ける",   "result": "中には小金。だが埃が舞い、少しむせた。", "coin": [800, 1800], "dmg": 6},
             {"label": "🔍 用心して開ける", "result": "罠を確かめてから開けた。安全に中身を頂いた。", "coin": [500, 1200], "xp": [4, 7]},
             {"label": "🚶 放っておく",     "result": "嫌な予感がして、触らずに離れた。", "xp": [2, 4]},
         ]},
        {"id": "e_honey", "type": "choice",
         "emoji": "🍯", "title": "野生の蜂蜜",
         "flavor": "うろの中に、たっぷりの蜂蜜。だが蜂の羽音がうるさい。",
         "choices": [
             {"label": "🍯 採って舐める", "result": "甘い。少し元気が出た。残りは持ち帰る。", "heal": 0.30, "food": "jerky"},
             {"label": "🚶 諦める",       "result": "刺されるのは御免だ。先へ進んだ。", "xp": [2, 4]},
         ]},
        {"id": "e_beast", "type": "choice",
         "emoji": "🩸", "title": "手負いの獣",
         "flavor": "茂みの中、傷を負った大鹿がうずくまっている。息が荒い。",
         "choices": [
             {"label": "🗡️ 楽にしてやる", "result": "ひと突きで仕留めた。立派な角は、いい値になる。", "coin": [600, 1400], "xp": [5, 9]},
             {"label": "🌿 手当てする",   "result": "傷を縛ってやると、鹿は森へ消えた。なぜか、心が軽い。", "xp": [6, 11]},
         ]},
    ],
    3: [
        {"id": "e_vein", "type": "choice",
         "emoji": "💎", "title": "鉱脈の煌めき",
         "flavor": "岩肌に、きらりと光る鉱脈。掘ればそれなりに出そうだ。",
         "choices": [
             {"label": "⛏️ 思いきり掘る", "result": "大きな鉱石を掘り当てた！ が、岩が崩れ少し怪我を。", "coin": [1500, 3500], "dmg": 14},
             {"label": "⛏️ ほどほどに",   "result": "無理せず、削れる分だけ持ち帰った。", "coin": [700, 1600], "xp": [4, 7]},
             {"label": "🚶 やめておく",   "result": "落石が怖い。手を出さなかった。", "xp": [3, 5]},
         ]},
        {"id": "e_hut", "type": "choice",
         "emoji": "🏚️", "title": "崩れた山小屋",
         "flavor": "尾根に、崩れかけた山小屋。誰かが残した物が、まだ眠っていそうだ。",
         "choices": [
             {"label": "🔦 物色する", "result": "残された保存食と、隠してあった銭を見つけた。", "coin": [900, 2200], "food": "feast"},
             {"label": "🛌 ひと休み", "result": "壁の陰で、しばし体を休めた。", "heal": 0.35},
             {"label": "🚶 立ち去る", "result": "長居は無用。すぐに小屋を後にした。", "xp": [3, 6]},
         ]},
        {"id": "e_rockfall", "type": "choice",
         "emoji": "⚡", "title": "落石",
         "flavor": "頭上で、ごろりと嫌な音。斜面の岩が、ぐらりと動いた。",
         "choices": [
             {"label": "🤸 伏せてやり過ごす", "result": "間一髪、岩は頭上を越えていった。", "xp": [4, 8]},
             {"label": "🛡️ 盾で受ける",       "result": "受け止めたが、衝撃で腕が痺れた。砕けた岩から、光る石が。", "dmg": 18, "coin": [800, 1800]},
         ]},
    ],
}



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎒 街道 消耗品・テーブル設定 v2
#   価格は高め。常設/ランダム入荷/ドロップ限定を分離。
#   回復系は最大50%まで。全回復は通常アイテムでは行わない。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAND_ITEMS = {
    "bandage": {"emoji":"🩹", "name":"包帯", "rarity":"common", "price":4000, "shop":"always", "desc":"HPを25%回復"},
    "smoke_bomb": {"emoji":"💨", "name":"煙玉", "rarity":"rare", "price":15000, "shop":"random", "desc":"次の雑魚戦を確定回避"},
    "lucky_charm": {"emoji":"🍀", "name":"幸運のお守り", "rarity":"rare", "price":25000, "shop":"random", "desc":"10探索：中ボス/大ボス/アイテム率UP"},
    "old_map": {"emoji":"🗺️", "name":"古びた地図", "rarity":"rare", "price":30000, "shop":"random", "desc":"10探索：イベント/発見率大幅UP"},
    "lantern": {"emoji":"🔦", "name":"探索ランタン", "rarity":"rare", "price":40000, "shop":"drop", "desc":"20探索：何もなし無効/イベント率UP"},
    "gold_compass": {"emoji":"🧭", "name":"黄金の羅針盤", "rarity":"epic", "price":80000, "shop":"drop", "desc":"20探索：コイン収穫+60%"},
    "decoy_doll": {"emoji":"🪆", "name":"身代わり人形", "rarity":"epic", "price":0, "shop":"drop", "desc":"死亡時の収穫ロストを自動で無効化"},
    "guardian_feather": {"emoji":"👼", "name":"守護の羽", "rarity":"legend", "price":0, "shop":"drop", "desc":"死亡時に使う/使わないを選べる。使うと収穫ロスト無効"},
}

# 戦闘合計50%固定：雑魚44 / 中ボス5 / 大ボス1。非戦闘側だけエリアで味付け。
LAND_EVENT_TABLE = {
    1: {"combat":44, "midrare":5, "rare":1, "story":15, "event":15, "item":4, "coin":8, "gather":6, "calm":2},
    2: {"combat":44, "midrare":5, "rare":1, "story":16, "event":16, "item":4, "coin":7, "gather":6, "calm":1},
    3: {"combat":44, "midrare":5, "rare":1, "story":17, "event":17, "item":4, "coin":6, "gather":5, "calm":1},
}

# アイテムイベント時の抽選。エピックは幻レベル寄り。
LAND_ITEM_EVENT_DROPS = [
    # アイテム発見イベント用。出すぎ防止のため、便利系はやや渋め。
    ("bandage", 38), ("smoke_bomb", 9), ("lucky_charm", 6), ("old_map", 6),
    ("lantern", 4), ("gold_compass", 0.9), ("decoy_doll", 0.10), ("guardian_feather", 0.025),
]

# 戦闘ドロップ：雑魚でも落ちるがかなり低確率。
LAND_ITEM_DROP_RATES = {
    # 戦闘ドロップ。アイテムが溢れすぎないよう v14 で全体的に約35〜45%ナーフ。
    "zako": [("bandage",0.018), ("smoke_bomb",0.0035), ("lucky_charm",0.0025), ("old_map",0.0025), ("lantern",0.0012), ("decoy_doll",0.00006), ("guardian_feather",0.000015)],
    "mid":  [("bandage",0.065), ("smoke_bomb",0.020), ("lucky_charm",0.016), ("old_map",0.016), ("lantern",0.008), ("gold_compass",0.004), ("decoy_doll",0.00050), ("guardian_feather",0.00012)],
    "rare": [("bandage",0.180), ("smoke_bomb",0.055), ("lucky_charm",0.045), ("old_map",0.045), ("lantern",0.025), ("gold_compass",0.013), ("decoy_doll",0.00200), ("guardian_feather",0.00070)],
}

LAND_COIN_EVENT = {1:[250,900], 2:[700,1800], 3:[1400,3600]}

# 世界観イベント：イベントは「きっかけ」。選択肢の中で outcome を再抽選する。
# 重要：ここは「確定報酬」ではなく、選んだ後にも coin/item/combat/damage/heal/xp/story/nothing が揺れる。
LAND_RANDOM_EVENTS = {
    1: [
        {"id":"rv_cart", "type":"choice", "emoji":"🛞", "title":"壊れた荷車", "flavor":"車輪の外れた荷車が、道端に打ち捨てられている。布の下で、何かがかすかに鳴った。",
         "choices":[
          {"label":"🔍 布をめくる", "result":"埃っぽい布をそっとめくった。", "outcomes":[("coin",30), ("item",22), ("combat",28), ("damage",12), ("nothing",8)]},
          {"label":"🛠️ 車輪を直す", "result":"軋む木材を押さえ、車輪をはめ直す。", "outcomes":[("coin",25), ("xp",25), ("item",15), ("combat",15), ("nothing",20)]},
          {"label":"🚶 触らず離れる", "result":"嫌な予感がして、荷車には触れなかった。", "outcomes":[("nothing",60), ("xp",20), ("combat",20)]},
         ]},
        {"id":"rv_well", "type":"choice", "emoji":"🕳️", "title":"古井戸", "flavor":"草に埋もれた井戸。底は見えない。石壁には、塔の紋章が薄く刻まれている。",
         "choices":[
          {"label":"👀 底を覗く", "result":"暗い底から、冷たい風が吹き上がる。", "outcomes":[("item",16), ("coin",20), ("damage",18), ("story",22), ("nothing",24)]},
          {"label":"🪙 コインを投げる", "result":"コインは、いつまでも底に届かなかった。", "cost":[100,500], "outcomes":[("item",24), ("xp",22), ("nothing",34), ("combat",20)]},
         ]},
        {"id":"rv_roadside_fire", "type":"choice", "emoji":"🔥", "title":"消えかけの焚き火", "flavor":"まだ温かい焚き火跡。誰かが、ついさっきまでここにいた。",
         "choices":[
          {"label":"🧺 周囲を探す", "result":"灰の周りを慎重に探った。", "outcomes":[("item",24), ("coin",24), ("combat",28), ("nothing",24)]},
          {"label":"🍵 少し休む", "result":"火の残り香に、ほんの少し緊張が解ける。", "outcomes":[("heal",40), ("combat",25), ("xp",20), ("nothing",15)]},
         ]},
        {"id":"rv_child", "type":"choice", "emoji":"🧒", "title":"泣いている子供", "flavor":"道端に小さな子供が座り込んでいる。近くに大人の姿はない。",
         "choices":[
          {"label":"🤝 声をかける", "result":"子供は涙を拭い、震える指で草むらを指した。", "outcomes":[("item",20), ("coin",20), ("combat",35), ("story",15), ("nothing",10)]},
          {"label":"🍖 食料を分ける", "result":"食料を渡すと、子供は小さく頭を下げた。", "outcomes":[("xp",35), ("item",25), ("story",20), ("nothing",20)]},
          {"label":"🚶 距離を取る", "result":"不自然に静かだ。深追いはしなかった。", "outcomes":[("nothing",55), ("combat",35), ("damage",10)]},
         ]},
        {"id":"rv_milestone", "type":"choice", "emoji":"🪨", "title":"古い道標", "flavor":"半ば土に埋もれた道標。『塔へ至る道』の文字だけが、妙にはっきり読める。",
         "choices":[
          {"label":"📖 文字を読む", "result":"読み進めるほど、背筋が冷えていく。", "outcomes":[("xp",35), ("story",30), ("combat",15), ("nothing",20)]},
          {"label":"⛏️ 掘り起こす", "result":"石の下から、古い袋が出てきた。", "outcomes":[("item",25), ("coin",25), ("damage",15), ("combat",20), ("nothing",15)]},
         ]},
        {"id":"rv_flowerfield", "type":"choice", "emoji":"🌼", "title":"風のない花畑", "flavor":"草原の一角だけ、花が輪を描くように咲いている。そこだけ風がない。",
         "choices":[
          {"label":"🌼 花を摘む", "result":"指先に、かすかな温もりが残った。", "outcomes":[("heal",30), ("item",25), ("damage",10), ("nothing",35)]},
          {"label":"👣 輪の中心へ入る", "result":"一歩踏み込んだ瞬間、耳鳴りがした。", "outcomes":[("story",30), ("combat",30), ("xp",20), ("nothing",20)]},
         ]},
        {"id":"rv_broken_sword", "type":"choice", "emoji":"🗡️", "title":"折れた剣", "flavor":"土に刺さった折れた剣。柄には、まだ新しい血が乾いている。",
         "choices":[
          {"label":"🗡️ 引き抜く", "result":"剣は驚くほど軽かった。だが、その瞬間、草むらが揺れた。", "outcomes":[("combat",45), ("item",20), ("xp",20), ("damage",10), ("nothing",5)]},
          {"label":"🙏 手を合わせる", "result":"誰のものかもわからない剣に、短く祈った。", "outcomes":[("heal",25), ("story",25), ("xp",25), ("nothing",25)]},
         ]},
        {"id":"rv_peddler", "type":"choice", "emoji":"🎒", "title":"怪しい行商人", "flavor":"大きな荷物を背負った男が、にやりと笑って手招きしている。",
         "choices":[
          {"label":"🛒 品を見る", "result":"箱の中身は、妙に古びた道具ばかりだった。", "outcomes":[("item",30), ("coin",10), ("damage",10), ("nothing",30), ("combat",20)]},
          {"label":"❓ 塔のことを聞く", "result":"行商人の笑みが、ほんの少しだけ消えた。", "outcomes":[("story",40), ("xp",20), ("combat",20), ("nothing",20)]},
          {"label":"🚶 無視する", "result":"背後で、男の笑い声だけがしばらく残った。", "outcomes":[("nothing",60), ("damage",10), ("combat",30)]},
         ]},
    ],
    2: [
        {"id":"rv_shrine", "type":"choice", "emoji":"⛩️", "title":"朽ちた祠", "flavor":"苔むした小さな祠。供え物は古く、だが誰かが手入れしている形跡がある。",
         "choices":[
          {"label":"🙏 祈る", "result":"手を合わせると、森のざわめきが一瞬だけ遠のいた。", "outcomes":[("heal",25), ("item",25), ("xp",20), ("damage",10), ("nothing",20)]},
          {"label":"🎁 供え物を探す", "result":"祠の裏側に手を伸ばす。", "outcomes":[("item",25), ("coin",15), ("combat",35), ("damage",15), ("nothing",10)]},
         ]},
        {"id":"rv_camp", "type":"choice", "emoji":"🏕️", "title":"荒らされた野営地", "flavor":"テントは裂かれ、焚き火は踏み消されている。逃げたのか、連れ去られたのか。",
         "choices":[
          {"label":"🧭 足跡を追う", "result":"湿った土に残る足跡を追った。", "outcomes":[("combat",42), ("mid_hint",10), ("item",18), ("xp",20), ("nothing",10)]},
          {"label":"🎒 残り物を調べる", "result":"破れた袋と、折れた矢をどかす。", "outcomes":[("item",26), ("coin",18), ("damage",14), ("combat",25), ("nothing",17)]},
         ]},
        {"id":"rv_sign", "type":"choice", "emoji":"📌", "title":"塔の立て札", "flavor":"『海より上がりし者、森を乱すべからず』。文字は新しい。誰かが見回っている。",
         "choices":[
          {"label":"📖 読み込む", "result":"警告文の下に、小さな追記を見つけた。", "outcomes":[("xp",32), ("story",28), ("combat",25), ("nothing",15)]},
          {"label":"🗡️ 叩き斬る", "result":"刃を入れた瞬間、森の奥で何かが動いた。", "outcomes":[("combat",60), ("item",12), ("damage",13), ("nothing",15)]},
         ]},
        {"id":"rv_hunter_trap", "type":"choice", "emoji":"🪤", "title":"狩人の罠", "flavor":"落ち葉の下に、巧妙な罠が仕掛けられている。まだ新しい。",
         "choices":[
          {"label":"🛠️ 外してみる", "result":"金具がぎしりと鳴った。", "outcomes":[("item",28), ("damage",28), ("xp",20), ("nothing",24)]},
          {"label":"👣 罠の先を見る", "result":"罠は森の奥へ誘導するように並んでいた。", "outcomes":[("combat",45), ("story",25), ("mid_hint",15), ("nothing",15)]},
         ]},
        {"id":"rv_mushroom_ring", "type":"choice", "emoji":"🍄", "title":"茸の輪", "flavor":"巨大な茸が円を描いて生えている。胞子が、淡く光っている。",
         "choices":[
          {"label":"🍄 少し採る", "result":"胞子が手袋にまとわりついた。", "outcomes":[("item",28), ("heal",18), ("damage",24), ("nothing",30)]},
          {"label":"🌀 輪の中心に立つ", "result":"森の音が、ぐにゃりと歪んだ。", "outcomes":[("story",30), ("combat",35), ("xp",20), ("nothing",15)]},
         ]},
        {"id":"rv_blood_arrow", "type":"choice", "emoji":"🏹", "title":"血の付いた矢", "flavor":"木の幹に、血で濡れた矢が深く刺さっている。矢羽根には塔の印。",
         "choices":[
          {"label":"🏹 抜き取る", "result":"矢を抜いた穴から、黒い樹液が滲んだ。", "outcomes":[("combat",45), ("item",20), ("damage",15), ("story",10), ("nothing",10)]},
          {"label":"📖 印を見る", "result":"塔の印は、森の管理を示すものらしい。", "outcomes":[("story",38), ("xp",24), ("combat",20), ("nothing",18)]},
         ]},
        {"id":"rv_old_bridge", "type":"choice", "emoji":"🌉", "title":"軋む吊り橋", "flavor":"谷にかかった古い吊り橋。向こう岸で、何かがこちらを見ている。",
         "choices":[
          {"label":"🌉 渡る", "result":"板が大きくしなった。", "outcomes":[("coin",25), ("item",20), ("combat",35), ("damage",15), ("nothing",5)]},
          {"label":"🪵 橋を調べる", "result":"縄に、刃物で切られかけた跡がある。", "outcomes":[("xp",30), ("story",25), ("item",15), ("nothing",30)]},
         ]},
        {"id":"rv_white_moth", "type":"choice", "emoji":"🦋", "title":"白い蛾の群れ", "flavor":"白い蛾が、まるで道案内のように森の奥へ飛んでいく。",
         "choices":[
          {"label":"🦋 追う", "result":"蛾は大樹の根元で消えた。", "outcomes":[("item",24), ("story",24), ("combat",32), ("nothing",20)]},
          {"label":"🔥 追い払う", "result":"蛾は一斉に散り、森がざわついた。", "outcomes":[("combat",45), ("damage",15), ("xp",20), ("nothing",20)]},
         ]},
    ],
    3: [
        {"id":"rv_chain", "type":"choice", "emoji":"⛓️", "title":"地中の鎖", "flavor":"岩の隙間から、太い鎖が覗いている。鎖は山の上――塔の方角へ続いている。",
         "choices":[
          {"label":"✋ 触れる", "result":"冷たい。だが、ただの鉄ではない。", "outcomes":[("story",28), ("damage",24), ("item",18), ("combat",22), ("nothing",8)]},
          {"label":"⛏️ 掘り返す", "result":"鎖の根元を掘る。石が崩れ、何かが露出した。", "outcomes":[("coin",22), ("item",20), ("combat",32), ("damage",22), ("nothing",4)]},
         ]},
        {"id":"rv_broken_banner", "type":"choice", "emoji":"🏴", "title":"折れた軍旗", "flavor":"塔の紋章が入った軍旗。旗竿は折れ、布には黒い焦げ跡が残っている。",
         "choices":[
          {"label":"🎒 旗の下を探る", "result":"積もった灰を払う。", "outcomes":[("item",25), ("coin",22), ("combat",28), ("nothing",25)]},
          {"label":"📖 紋章を調べる", "result":"紋章の裏に、小さな傷文字が刻まれていた。", "outcomes":[("story",34), ("xp",28), ("combat",24), ("nothing",14)]},
         ]},
        {"id":"rv_black_box", "type":"choice", "emoji":"⬛", "title":"黒い箱", "flavor":"岩陰に、黒い箱が置かれている。鍵穴はない。箱の周囲だけ、雪が溶けている。",
         "choices":[
          {"label":"📦 開ける", "result":"箱に手をかけた瞬間、指先が痺れた。", "outcomes":[("item",32), ("damage",28), ("combat",28), ("nothing",12)]},
          {"label":"🚶 離れる", "result":"関わるべきではない。そう判断した。", "outcomes":[("nothing",55), ("xp",20), ("combat",25)]},
         ]},
        {"id":"rv_stone_statue", "type":"choice", "emoji":"🗿", "title":"山腹の石像", "flavor":"顔の削られた石像が、山道を見下ろしている。足元には古い供物。",
         "choices":[
          {"label":"🙏 供物を置く", "result":"石像の影が、ほんの少しだけ動いた。", "outcomes":[("heal",24), ("story",28), ("item",20), ("nothing",28)]},
          {"label":"⛏️ 足元を掘る", "result":"硬い土の下に、何かが埋まっている。", "outcomes":[("item",28), ("coin",24), ("combat",28), ("damage",16), ("nothing",4)]},
         ]},
        {"id":"rv_thunder", "type":"choice", "emoji":"🌩️", "title":"遠雷", "flavor":"晴れているのに、山の向こうで雷が鳴った。空気が金属の味を帯びる。",
         "choices":[
          {"label":"⛰️ 先へ進む", "result":"雷鳴が、足音に重なった。", "outcomes":[("combat",45), ("xp",20), ("damage",18), ("nothing",17)]},
          {"label":"🪨 岩陰で待つ", "result":"岩陰で息を潜める。風が長く尾を引いた。", "outcomes":[("heal",22), ("story",22), ("item",18), ("nothing",38)]},
         ]},
        {"id":"rv_abandoned_lift", "type":"choice", "emoji":"🛗", "title":"廃れた昇降機", "flavor":"塔へ資材を運んでいたらしい木製の昇降機。鎖はまだ生きている。",
         "choices":[
          {"label":"⚙️ 動かす", "result":"歯車が悲鳴を上げ、山肌が震えた。", "outcomes":[("coin",25), ("item",22), ("combat",35), ("damage",18)]},
          {"label":"📖 操作盤を見る", "result":"操作盤には、海図に似た線が刻まれていた。", "outcomes":[("story",40), ("xp",25), ("combat",20), ("nothing",15)]},
         ]},
        {"id":"rv_frozen_corpse", "type":"choice", "emoji":"🧊", "title":"凍った兵士", "flavor":"岩陰に、塔の兵士が凍りついている。手には開封済みの封書。",
         "choices":[
          {"label":"✉️ 封書を取る", "result":"封書は指に貼りつくほど冷たかった。", "outcomes":[("story",35), ("item",20), ("combat",25), ("damage",15), ("nothing",5)]},
          {"label":"🧤 装備を探る", "result":"凍った革袋から、何かがこぼれた。", "outcomes":[("item",30), ("coin",25), ("damage",20), ("nothing",25)]},
         ]},
        {"id":"rv_sky_door", "type":"choice", "emoji":"🚪", "title":"空へ続く扉", "flavor":"山壁に、扉だけが埋まっている。開けても向こうは岩のはずだ。なのに、隙間から風が吹く。",
         "choices":[
          {"label":"🚪 開ける", "result":"扉の向こうは、真っ暗だった。", "outcomes":[("story",35), ("combat",35), ("item",20), ("damage",10)]},
          {"label":"🔒 鍵穴を見る", "result":"鍵穴は古代の鍵と同じ形をしている。", "outcomes":[("xp",30), ("item",20), ("nothing",30), ("combat",20)]},
         ]},
    ],
}


def make_land_enemy(area, force=None, buffs=None):
    """make_board_enemy(spec, scale) が食える敵スペックを返す。
    force: rare / midrare / hot_midrare / combat を指定できる。lucky_charm時はレア系が少し出やすい。"""
    a = LAND_AREAS[area]
    buffs = buffs or {}
    rare_rate = RARE_SPAWN_RATE * (2.0 if buffs.get("lucky_charm") else 1.0)
    mid_rate = MIDRARE_SPAWN_RATE * (1.5 if buffs.get("lucky_charm") else 1.0)
    runner_roll = random.random()
    # 💎 経験値逃走モンスター（ドロップ無し・XP専用）
    runner_pack = XP_RUNNERS.get(area, {})
    if force in ("xprunner", "kingrunner") or (force in (None, "combat") and runner_pack and runner_roll < (XP_RUNNER_RATE + XP_RUNNER_KING_RATE)):
        kind = "king" if force == "kingrunner" or (force in (None, "combat") and runner_roll < XP_RUNNER_KING_RATE) else "normal"
        e = runner_pack.get(kind) or runner_pack.get("normal")
        return {
            "name": e["name"], "emoji": e["emoji"], "key": f"landrunner{area}_{e['name']}",
            "crew_power": max(1, round(a["base"] * e["ratio"])),
            "hp_mult": e.get("hp_mult", 1.0), "atk_mult": e.get("atk_mult", 1.0), "def_mult": e.get("def_mult", 1.0),
            "fixed_hp": e.get("fixed_hp"),
            "tier": e.get("tier", 1), "stars": e.get("stars", 2),
            "is_boss": False, "is_rare": False, "is_midrare": False,
            "is_xp_runner": True, "is_king_runner": kind == "king",
            "escape_chance": 0.50, "no_item_drop": True, "drop_table": [],
            "xp_mult": e.get("xp_mult", 20), "coin_mult": e.get("coin_mult", 0.25),
        }
    roll = random.random()
    # ✨ 激レア（白鹿を基準に、森・山はエリア別に格上げ）
    if (force == "rare" or (force is None and roll < rare_rate)) and LAND_RARES.get(area):
        e = random.choice(LAND_RARES[area])
        boss = RARE_BOSS_BY_AREA.get(area, RARE_BOSS_BY_AREA[1])
        return {
            "name": e["name"], "emoji": e["emoji"], "key": f"land{area}_{e['name']}",
            "crew_power": boss["crew_power"],
            "hp_mult": boss["hp_mult"], "atk_mult": boss["atk_mult"],
            "tier": boss["tier"], "stars": boss["stars"],
            "scale_override": boss["scale"],
            "is_boss": False, "is_rare": True,
            "drop_table": RARE_BOSS["drop"],
            "rare_xp": e.get("xp"), "rare_coin": e.get("coin"),
            "rare_story": e.get("story", ""), "rare_intro": e.get("rare_intro", ""),
            "reward_ratio": e.get("ratio", 1.0),
        }
    # 🔸 中レア
    if (force in ("midrare", "hot_midrare") or (force is None and roll < rare_rate + mid_rate)) and LAND_MIDRARES.get(area):
        e = random.choice(LAND_MIDRARES[area])
        return {
            "name": e["name"], "emoji": e["emoji"], "key": f"landmid{area}_{e['name']}",
            "crew_power": max(1, round(a["base"] * e["ratio"])),
            "hp_mult": e.get("hp_mult", 1.0), "atk_mult": e.get("atk_mult", 1.0),
            "tier": e.get("tier", 1), "stars": e.get("stars", 2),
            "is_boss": False, "is_rare": False, "is_midrare": True,
            "mid_xp": e.get("xp"), "mid_coin": e.get("coin"),
            "drop_table": HOT_EVENT_EQUIP_DROP if force == "hot_midrare" else e.get("drop"),
            "hot_event_enemy": force == "hot_midrare",
            "reward_ratio": e.get("ratio", 1.0),
        }
    # 通常の雑魚
    e = random.choice(LAND_ENEMIES[area])
    return {
        "name": e["name"], "emoji": e["emoji"], "key": f"land{area}_{e['name']}",
        "crew_power": max(1, round(a["base"] * e["ratio"])),
        "hp_mult": e.get("hp_mult", 1.0),
        "atk_mult": e.get("atk_mult", 1.0),
        "tier": e.get("tier", 1),
        "stars": e.get("stars", 1),
        "is_boss": False,
        "is_rare": False,
        "reward_ratio": e.get("ratio", 1.0),
    }


def land_encounter_pick(area, buffs=None):
    table = dict(LAND_EVENT_TABLE.get(area, LAND_EVENT_TABLE[1]))
    buffs = buffs or {}
    if buffs.get("lucky_charm"):
        # 使った感が出るように、10探索のあいだ強敵・アイテム寄りへ。
        table["midrare"] += 3; table["rare"] += 1; table["item"] += 4; table["calm"] = max(0, table.get("calm", 0) - 2)
    if buffs.get("old_map"):
        # 「地図」らしく、ただの確率UPではなくイベント/発見の道へ寄せる。
        table["event"] += 22; table["story"] += 6; table["item"] += 10; table["coin"] += 4; table["calm"] = 0
    if buffs.get("lantern"):
        # 20探索のあいだ空振りを消し、探索イベントを増やす。
        table["calm"] = 0; table["event"] += 8; table["gather"] += 4
    keys = list(table.keys()); wts = list(table.values())
    return random.choices(keys, weights=wts)[0]

def pick_land_item(area=None):
    keys = [x[0] for x in LAND_ITEM_EVENT_DROPS]; wts = [x[1] for x in LAND_ITEM_EVENT_DROPS]
    return random.choices(keys, weights=wts)[0]

def pick_hot_land_item(area=None):
    # 熱いイベント専用：出現率は変えず、当たった時の中身だけ少し夢寄りにする。
    # 平均ドロップ率そのものは変更しない。
    table = [("bandage", 20), ("smoke_bomb", 20), ("lucky_charm", 18), ("old_map", 18),
             ("lantern", 14), ("gold_compass", 7), ("decoy_doll", 2.5), ("guardian_feather", 0.5)]
    keys = [x[0] for x in table]; wts = [x[1] for x in table]
    return random.choices(keys, weights=wts)[0]

def pick_random_event(area):
    pool = LAND_RANDOM_EVENTS.get(area, []) or LAND_EVENTS.get(area, [])
    if not pool:
        return None
    # v15: イベントにもweightを持たせる。通常は1.0、熱いイベントは0.15〜0.35で薄く出す。
    weights = [max(0.01, float(e.get("weight", 1.0))) for e in pool]
    return random.choices(pool, weights=weights)[0]


def pick_story(area):
    # 🟣 観測者シリーズ：メインのstory出現率は変えず、story枠の中で低確率差し込み。
    # 敵遭遇率・ホットイベント率・ドロップ率には触れない。
    obs = OBSERVER_STORY_EVENTS.get(area, []) if "OBSERVER_STORY_EVENTS" in globals() else []
    if obs and random.random() < OBSERVER_STORY_RATE:
        return random.choice(obs)
    pool = LAND_STORY.get(area, [])
    return random.choice(pool) if pool else None


def pick_event(area):
    pool = LAND_EVENTS.get(area, [])
    return random.choice(pool) if pool else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌏 街道イベント土台 v9 追加パック
#   既存LAND_RANDOM_EVENTSへ追加するだけで、コード本体を触らずイベントを増やせる。
#   形式：きっかけイベント → 選択肢 → サブ抽選(outcomes)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAND_RANDOM_EVENT_PACK_V9 = {
    1: [
        {"id":"v9_plain_wounded_soldier", "type":"choice", "emoji":"🩸", "title":"倒れた兵士", "flavor":"草むらの陰に、塔の紋章をつけた兵士が倒れている。まだ息はある。だが、手は剣から離れていない。",
         "choices":[
          {"label":"🩹 手当てする", "result":"傷口を縛ると、兵士はうわ言のように塔の名を呟いた。", "outcomes":[("xp",32),("item",22),("story",22),("combat",14),("nothing",10)]},
          {"label":"🎒 荷物を見る", "result":"革袋に手を伸ばす。兵士の目が、かすかに開いた。", "outcomes":[("coin",28),("item",24),("combat",28),("damage",12),("nothing",8)]},
          {"label":"🚶 立ち去る", "result":"関わらない。そう決めて、足早に離れた。", "outcomes":[("nothing",56),("xp",18),("combat",18),("story",8)]},
         ]},
        {"id":"v9_plain_traveling_merchant", "type":"choice", "emoji":"🧺", "title":"行商人", "flavor":"荷車を引く行商人が、妙に安い道具を並べている。笑顔が少しだけ作り物めいている。",
         "choices":[
          {"label":"🛒 品物を見る", "result":"埃っぽい布の上に、見慣れない道具が並ぶ。", "outcomes":[("item",34),("coin",10),("damage",8),("nothing",28),("combat",20)]},
          {"label":"❓ 塔の噂を聞く", "result":"行商人は声を潜めた。『塔に近づくなら、空を見すぎるな』。", "outcomes":[("story",36),("xp",24),("item",12),("nothing",28)]},
          {"label":"🚶 無視する", "result":"安すぎるものには裏がある。", "outcomes":[("nothing",62),("combat",20),("xp",18)]},
         ]},
        {"id":"v9_plain_old_windmill", "type":"choice", "emoji":"🌬️", "title":"止まった風車", "flavor":"丘の上に、羽根の折れた風車が立っている。風はあるのに、まったく動かない。",
         "choices":[
          {"label":"⚙️ 内部を調べる", "result":"軋む扉を押し開ける。中は思ったより暗い。", "outcomes":[("item",24),("coin",22),("combat",28),("story",14),("nothing",12)]},
          {"label":"🪜 上に登る", "result":"古い梯子が、体重を受けて悲鳴を上げた。", "outcomes":[("xp",26),("damage",20),("coin",20),("combat",22),("nothing",12)]},
         ]},
        {"id":"v9_plain_blue_butterfly", "type":"choice", "emoji":"🦋", "title":"青い蝶", "flavor":"青い蝶が一匹、目の前を横切った。羽根には、地図のような模様が浮かんでいる。",
         "choices":[
          {"label":"🦋 追いかける", "result":"蝶は草原の奥へ、振り返るように飛んでいく。", "outcomes":[("item",28),("story",24),("combat",24),("xp",14),("nothing",10)]},
          {"label":"✋ 手を伸ばす", "result":"指先に止まった瞬間、蝶は光の粒になった。", "outcomes":[("heal",24),("item",22),("xp",22),("nothing",32)]},
         ]},
        {"id":"v9_plain_broken_sword", "type":"choice", "emoji":"🗡️", "title":"折れた剣", "flavor":"道端に、刃の折れた剣が突き立っている。周囲の草だけが黒く焦げていた。",
         "choices":[
          {"label":"🗡️ 引き抜く", "result":"柄を握ると、手のひらがじんと痺れた。", "outcomes":[("combat",36),("item",20),("damage",16),("story",18),("nothing",10)]},
          {"label":"📖 刻印を見る", "result":"剣には塔の文字で『帰還不能』と刻まれている。", "outcomes":[("story",38),("xp",24),("combat",18),("nothing",20)]},
         ]},
        {"id":"v9_plain_dry_river", "type":"choice", "emoji":"🏞️", "title":"干上がった川", "flavor":"川底が剥き出しになっている。水はないのに、濡れた足跡だけが続いている。",
         "choices":[
          {"label":"👣 足跡を追う", "result":"足跡は途中で、急に四つ足のものへ変わった。", "outcomes":[("combat",42),("item",16),("coin",16),("story",14),("nothing",12)]},
          {"label":"💎 川底を探る", "result":"乾いた泥を掘り返す。", "outcomes":[("coin",30),("item",22),("damage",10),("nothing",28),("combat",10)]},
         ]},
        {"id":"v9_plain_singing_traveler", "type":"choice", "emoji":"🎻", "title":"吟遊詩人", "flavor":"遠くから、古い歌が聞こえる。歌詞には海と塔、そして帰らぬ者の名が混じっていた。",
         "choices":[
          {"label":"🎵 歌を聞く", "result":"歌は妙に耳に残る。知らないはずの風景が、頭に浮かんだ。", "outcomes":[("story",40),("xp",30),("heal",12),("nothing",18)]},
          {"label":"💰 チップを渡す", "result":"詩人は一礼し、古い噂をひとつ置いていった。", "cost":[100,800], "outcomes":[("item",24),("story",34),("xp",22),("nothing",20)]},
         ]},
        {"id":"v9_plain_abandoned_shrine", "type":"choice", "emoji":"🕯️", "title":"草原の祠", "flavor":"小さな祠に、消えかけた蝋燭が残っている。火はないのに、芯だけが赤い。",
         "choices":[
          {"label":"🙏 祈る", "result":"祠の奥で、何かが小さく鳴った。", "outcomes":[("heal",26),("item",20),("story",22),("damage",10),("nothing",22)]},
          {"label":"🕯️ 蝋燭を持つ", "result":"蝋燭は冷たい。けれど、影だけが揺れている。", "outcomes":[("item",28),("combat",26),("story",20),("nothing",26)]},
         ]},
        {"id":"v9_plain_hidden_cache", "type":"choice", "emoji":"📦", "title":"隠された木箱", "flavor":"石の裏に、小さな木箱が隠されている。誰かの非常用の備えだろうか。",
         "choices":[
          {"label":"📦 開ける", "result":"蓋は簡単に外れた。中身はまだ使えそうだ。", "outcomes":[("item",40),("coin",20),("combat",15),("nothing",25)]},
          {"label":"🪤 罠を確認する", "result":"底に細い糸が張ってあった。危なかった。", "outcomes":[("xp",26),("item",26),("nothing",38),("combat",10)]},
         ]},
        {"id":"v9_plain_black_cat", "type":"choice", "emoji":"🐈‍⬛", "title":"黒猫", "flavor":"黒猫が道の真ん中に座り、こちらを見上げている。首輪には小さな鍵が下がっていた。",
         "choices":[
          {"label":"🐈‍⬛ 近づく", "result":"猫は逃げず、こちらを試すように尾を揺らした。", "outcomes":[("item",30),("story",24),("combat",20),("nothing",26)]},
          {"label":"🍖 食べ物を見せる", "result":"猫は満足げに鳴き、草むらの奥へ案内する。", "outcomes":[("item",36),("coin",20),("xp",20),("nothing",24)]},
         ]},
    ],
    2: [
        {"id":"v9_forest_old_altar", "type":"choice", "emoji":"🪦", "title":"古い祭壇", "flavor":"倒木に囲まれた石の祭壇。表面には、削り取られた古い紋様が残っている。",
         "choices":[
          {"label":"🙏 手を置く", "result":"冷たい石が、ほんの一瞬だけ脈打った。", "outcomes":[("story",34),("damage",18),("item",22),("combat",16),("nothing",10)]},
          {"label":"🔍 周囲を探す", "result":"落ち葉の下に、誰かが残した供物がある。", "outcomes":[("item",32),("coin",18),("combat",28),("nothing",22)]},
         ]},
        {"id":"v9_forest_giant_claw", "type":"choice", "emoji":"🐾", "title":"巨大な爪痕", "flavor":"大樹の幹に、深い爪痕が刻まれている。爪痕は人の背丈より大きい。",
         "choices":[
          {"label":"🐾 痕跡を追う", "result":"折れた枝が、森の奥へ続いている。", "outcomes":[("combat",45),("mid_hint",12),("item",16),("xp",17),("nothing",10)]},
          {"label":"📖 爪痕を見る", "result":"爪痕の下に、塔の警告印が刻まれていた。", "outcomes":[("story",36),("xp",24),("combat",24),("nothing",16)]},
         ]},
        {"id":"v9_forest_lost_scout", "type":"choice", "emoji":"🧭", "title":"迷った斥候", "flavor":"塔の斥候らしき若者が、木の根元で震えている。敵か、ただの迷子か。",
         "choices":[
          {"label":"🤝 助ける", "result":"斥候は怯えながらも、森の抜け道を教えてくれた。", "outcomes":[("story",30),("xp",28),("item",18),("combat",14),("nothing",10)]},
          {"label":"🎒 持ち物を調べる", "result":"彼の袋には、塔の配給品が入っていた。", "outcomes":[("item",34),("coin",20),("combat",26),("nothing",20)]},
         ]},
        {"id":"v9_forest_hollow_tree", "type":"choice", "emoji":"🌳", "title":"空洞の大樹", "flavor":"幹に大きな空洞のある大樹。中から、かすかな光が漏れている。",
         "choices":[
          {"label":"🔦 中を覗く", "result":"空洞の奥は、思ったより広い。", "outcomes":[("item",32),("combat",28),("story",22),("damage",8),("nothing",10)]},
          {"label":"🪵 木肌を叩く", "result":"返ってきた音は、木のものではなかった。", "outcomes":[("combat",42),("xp",22),("item",16),("nothing",20)]},
         ]},
        {"id":"v9_forest_silent_brook", "type":"choice", "emoji":"💧", "title":"音のない小川", "flavor":"水は流れているのに、水音がしない。川面には空ではなく、塔の影が映っている。",
         "choices":[
          {"label":"💧 水を飲む", "result":"冷たい水が喉を通る。けれど、後味が鉄っぽい。", "outcomes":[("heal",25),("damage",16),("story",24),("nothing",35)]},
          {"label":"🪙 川底を探る", "result":"小石に混じって、古い硬貨が沈んでいる。", "outcomes":[("coin",34),("item",22),("combat",22),("nothing",22)]},
         ]},
        {"id":"v9_forest_old_hut", "type":"choice", "emoji":"🏚️", "title":"森番の小屋", "flavor":"人の気配のない小屋。壁には弓、床には新しい泥の跡。無人のはずなのに、誰かが使っている。",
         "choices":[
          {"label":"🚪 入る", "result":"床板が軋む。奥の部屋で、何かが倒れた。", "outcomes":[("item",30),("combat",34),("coin",14),("story",12),("nothing",10)]},
          {"label":"👣 泥の跡を追う", "result":"足跡は小屋の裏で途切れている。", "outcomes":[("combat",38),("story",26),("xp",20),("nothing",16)]},
         ]},
        {"id":"v9_forest_bell", "type":"choice", "emoji":"🔔", "title":"木に吊るされた鈴", "flavor":"枝から小さな鈴が吊るされている。風もないのに、ちりん、と鳴った。",
         "choices":[
          {"label":"🔔 鳴らす", "result":"森の奥から、同じ音が返ってきた。", "outcomes":[("combat",40),("story",24),("item",18),("nothing",18)]},
          {"label":"✋ 外す", "result":"鈴を外すと、周囲の虫の声が戻った。", "outcomes":[("item",30),("xp",22),("damage",12),("nothing",36)]},
         ]},
        {"id":"v9_forest_buried_bag", "type":"choice", "emoji":"🎒", "title":"埋められた背嚢", "flavor":"木の根元に、不自然に盛り上がった土。布の端が少し見えている。",
         "choices":[
          {"label":"⛏️ 掘り出す", "result":"湿った土の中から、古い背嚢が出てきた。", "outcomes":[("item",38),("coin",24),("combat",18),("damage",8),("nothing",12)]},
          {"label":"👂 耳を澄ます", "result":"土の下から、かすかに音がする。", "outcomes":[("combat",40),("story",20),("xp",20),("nothing",20)]},
         ]},
    ],
    3: [
        {"id":"v9_mountain_bell_tower", "type":"choice", "emoji":"🛕", "title":"鐘のない鐘楼", "flavor":"山道の脇に、鐘のない鐘楼が立っている。なのに、遠くで鐘の音が鳴った。",
         "choices":[
          {"label":"🛕 登る", "result":"階段は途中から崩れている。上には、山の全景が見えた。", "outcomes":[("story",34),("xp",24),("combat",24),("damage",10),("nothing",8)]},
          {"label":"🔍 床を調べる", "result":"床板の下に、小さな箱が隠されている。", "outcomes":[("item",32),("coin",22),("combat",28),("nothing",18)]},
         ]},
        {"id":"v9_mountain_chain_marker", "type":"choice", "emoji":"📍", "title":"鎖の標石", "flavor":"道標の代わりに、鉄鎖が地面に打ち込まれている。鎖は低く唸っていた。",
         "choices":[
          {"label":"✋ 鎖に触れる", "result":"掌に、冷たさではない痛みが走る。", "outcomes":[("damage",26),("story",30),("item",18),("combat",18),("nothing",8)]},
          {"label":"📖 標石を読む", "result":"『海圧安定。異常なし』――何の記録だろうか。", "outcomes":[("story",42),("xp",26),("combat",18),("nothing",14)]},
         ]},
        {"id":"v9_mountain_goat_path", "type":"choice", "emoji":"🐐", "title":"山羊の細道", "flavor":"崖沿いに、細い道が続いている。山羊の足跡に混じって、人の足跡もある。",
         "choices":[
          {"label":"🐐 進む", "result":"足元の石が、ぱらぱらと崖下へ落ちていく。", "outcomes":[("coin",24),("item",22),("combat",30),("damage",18),("nothing",6)]},
          {"label":"👣 足跡を調べる", "result":"人の足跡は途中で消え、代わりに鎧の擦れた跡が残っている。", "outcomes":[("story",30),("combat",34),("xp",22),("nothing",14)]},
         ]},
        {"id":"v9_mountain_cave_mouth", "type":"choice", "emoji":"🕳️", "title":"洞穴の入口", "flavor":"山肌にぽっかりと穴が開いている。奥から、風ではない息のような音がする。",
         "choices":[
          {"label":"🔦 入る", "result":"一歩踏み入れると、背後の光が急に遠くなった。", "outcomes":[("combat",42),("item",24),("coin",16),("damage",10),("nothing",8)]},
          {"label":"🪨 石を投げる", "result":"石は、落ちる音を返さなかった。", "outcomes":[("story",32),("combat",32),("xp",18),("nothing",18)]},
         ]},
        {"id":"v9_mountain_snowless_patch", "type":"choice", "emoji":"♨️", "title":"雪のない地面", "flavor":"周囲には薄雪があるのに、その一角だけ地面がむき出しだ。土から熱が立ちのぼっている。",
         "choices":[
          {"label":"✋ 土に触れる", "result":"温かい。いや、熱い。", "outcomes":[("damage",24),("item",22),("story",20),("nothing",34)]},
          {"label":"⛏️ 掘る", "result":"少し掘ると、黒い石片が出てきた。", "outcomes":[("coin",28),("item",28),("combat",28),("nothing",16)]},
         ]},
        {"id":"v9_mountain_echo", "type":"choice", "emoji":"📣", "title":"返らないこだま", "flavor":"声を出せば反響しそうな谷。だが、ここでは音が戻ってこない。",
         "choices":[
          {"label":"📣 声を出す", "result":"声は谷に吸われた。数秒後、別の声が返ってきた。", "outcomes":[("combat",42),("story",28),("damage",10),("nothing",20)]},
          {"label":"🤫 黙って進む", "result":"息を殺して、岩陰を抜ける。", "outcomes":[("item",20),("xp",24),("nothing",40),("combat",16)]},
         ]},
        {"id":"v9_mountain_supply_crate", "type":"choice", "emoji":"📦", "title":"塔の補給箱", "flavor":"塔の印が焼き付けられた補給箱。封は切られていない。近くに見張りはいないようだ。",
         "choices":[
          {"label":"📦 開ける", "result":"封を切ると、油と鉄の匂いがした。", "outcomes":[("item",36),("coin",22),("combat",28),("nothing",14)]},
          {"label":"🪤 罠を探す", "result":"底に、細い警報線が仕込まれていた。", "outcomes":[("xp",26),("item",24),("nothing",34),("combat",16)]},
         ]},
        {"id":"v9_mountain_red_sky", "type":"choice", "emoji":"🌆", "title":"赤い空", "flavor":"一瞬だけ、空が赤く染まった。夕焼けではない。塔の方角から、低い振動が伝わる。",
         "choices":[
          {"label":"⛰️ 塔の方を見る", "result":"塔の影が、実際よりも大きく見えた。", "outcomes":[("story",44),("combat",24),("xp",20),("nothing",12)]},
          {"label":"🏃 早足で進む", "result":"振動から逃げるように、山道を急いだ。", "outcomes":[("combat",36),("damage",16),("item",18),("nothing",30)]},
         ]},
    ],
}


# ── 🔥 熱い低確率イベント v15 ──
# 出現率はイベント枠の中でさらに薄め。出たらアイテム/コイン/強敵など良い意味で荒れる。
LAND_HOT_EVENT_PACK_V15 = {
    1: [
        {"id":"v15_plain_sealed_chest", "weight":0.25, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["風が止んだ。","草の奥で、封印布だけが不自然に揺れている。","開ければ、何かが変わる気がする。"], "type":"choice", "emoji":"📦", "title":"封印された木箱", "flavor":"草原の石陰に、古い封印布で縛られた木箱がある。普通の落とし物ではない。",
         "choices":[
          {"label":"🗝️ 封印を解く", "result":"布をほどくと、箱の中から淡い光が漏れた。", "outcomes":[("item",48),("coin",18),("combat",22),("damage",8),("nothing",4)]},
          {"label":"🪤 罠を調べる", "result":"底板に細い針金が仕込まれていた。危ないところだった。", "outcomes":[("item",36),("xp",20),("coin",16),("nothing",20),("combat",8)]},
         ]},
        {"id":"v15_plain_tower_patrol", "weight":0.22, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["遠くで鎧の音がした。","塔の旗が、風もないのに震えている。","見つかれば、ただでは済まない。"], "type":"choice", "emoji":"🚩", "title":"塔の巡回旗", "flavor":"丘の向こうに、塔の旗を掲げた小隊が見える。こちらにはまだ気付いていない。",
         "choices":[
          {"label":"👀 様子を見る", "result":"兵たちは何かを探している。足跡は森の方へ続いていた。", "outcomes":[("story",38),("xp",22),("item",16),("combat",18),("nothing",6)]},
          {"label":"🎒 補給袋を狙う", "result":"一瞬の隙をついて、置かれた袋に手を伸ばす。", "outcomes":[("item",42),("coin",18),("combat",32),("damage",6),("nothing",2)]},
         ]},
    ],
    2: [
        {"id":"v15_forest_silver_cache", "weight":0.24, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["森が静まり返る。","根の下で、銀色の箱が脈打つように光った。","触れれば、森の主に気づかれる。"], "type":"choice", "emoji":"✨", "title":"銀色の隠し箱", "flavor":"根の絡まった大樹の下に、銀色の小箱が埋まっている。森番の印が刻まれていた。",
         "choices":[
          {"label":"📦 開ける", "result":"蓋が開いた瞬間、森の奥で獣が吠えた。", "outcomes":[("item",50),("combat",28),("coin",14),("damage",6),("nothing",2)]},
          {"label":"🌲 印を読む", "result":"印は道順のようにも、警告のようにも見える。", "outcomes":[("story",34),("item",30),("xp",20),("combat",12),("nothing",4)]},
         ]},
        {"id":"v15_forest_hunter_whistle", "weight":0.18, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["笛が、勝手に鳴った。","音は森の奥へ沈み、足音だけが返ってくる。","呼んではいけないものを呼んだのかもしれない。"], "type":"choice", "emoji":"🪈", "title":"狩人の笛", "flavor":"枝に吊られた小さな笛。触れる前から、低い音が鳴っている。",
         "choices":[
          {"label":"🪈 吹く", "result":"森のあちこちから、足音が返ってきた。", "outcomes":[("combat",48),("item",26),("xp",16),("damage",8),("nothing",2)]},
          {"label":"🎒 持ち去る", "result":"笛は指先に吸い付くように冷たい。", "outcomes":[("item",46),("story",20),("combat",24),("nothing",10)]},
         ]},
    ],
    3: [
        {"id":"v15_mountain_black_reliquary", "weight":0.20, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["山の空気が急に重くなる。","黒い箱の周りだけ、雪が消えている。","鎖を外すなら、覚悟がいる。"], "type":"choice", "emoji":"🖤", "title":"黒い聖遺箱", "flavor":"崩れた石段の奥に、黒い箱が鎖で固定されている。箱の周囲だけ、雪が積もらない。",
         "choices":[
          {"label":"⛓️ 鎖を外す", "result":"鎖が外れると同時に、山道の空気が重くなった。", "outcomes":[("item",54),("combat",30),("damage",10),("story",4),("nothing",2)]},
          {"label":"📖 刻印を読む", "result":"刻印には『塔へ返せ』とだけ記されている。", "outcomes":[("story",42),("xp",22),("item",22),("combat",12),("nothing",2)]},
         ]},
        {"id":"v15_mountain_fallen_banner", "weight":0.22, "hot":True, "risk_mult":5, "reward_mult":5, "prelude":["崖の向こうで、獣が吠えた。","折れた軍旗は、まだ誰かを待っている。","ここは敗走の跡だ。勝利の跡ではない。"], "type":"choice", "emoji":"🏴", "title":"折れた軍旗", "flavor":"崖の縁に、塔の軍旗が折れて刺さっている。旗布には大きな爪痕が残っていた。",
         "choices":[
          {"label":"🏴 引き抜く", "result":"旗を抜いた瞬間、遠くで何かが吠えた。", "outcomes":[("combat",46),("item",26),("coin",14),("damage",10),("nothing",4)]},
          {"label":"🔍 周囲を探す", "result":"岩陰に、撤退時に捨てられた補給品が残っている。", "outcomes":[("item",44),("coin",22),("combat",20),("nothing",14)]},
         ]},
    ],
}

for _area, _events in LAND_HOT_EVENT_PACK_V15.items():
    LAND_RANDOM_EVENTS.setdefault(_area, [])
    _seen = {e.get("id") for e in LAND_RANDOM_EVENTS[_area]}
    for _ev in _events:
        if _ev.get("id") not in _seen:
            LAND_RANDOM_EVENTS[_area].append(_ev)
            _seen.add(_ev.get("id"))

for _area, _events in LAND_RANDOM_EVENT_PACK_V9.items():
    LAND_RANDOM_EVENTS.setdefault(_area, [])
    # zipを何度作り直しても二重追加にならないようidで重複排除
    _seen = {e.get("id") for e in LAND_RANDOM_EVENTS[_area]}
    for _ev in _events:
        if _ev.get("id") not in _seen:
            LAND_RANDOM_EVENTS[_area].append(_ev)
            _seen.add(_ev.get("id"))

# v9の目安：既存8件前後＋追加 平原10/森8/山8。ここからJSON化/外部化しやすい形に寄せていく。

# ── v23 森・山 難易度微調整 ──
# 戦闘中に包帯/煙玉を使えるようになったぶん、森山は少しだけ危険寄りへ。
# 食料は戦闘中に使わせない（CombatItemSelect側は LAND_ITEMS の bandage/smoke_bomb のみ）。
def _apply_v23_forest_mountain_difficulty():
    tables = [LAND_ENEMIES, LAND_RARES, LAND_MIDRARES]
    # 森：HP+15% / 攻撃+20%、山：HP+20% / 攻撃+25%
    mults = {2: (1.15, 1.20), 3: (1.20, 1.25)}
    for area, (hp_mul, atk_mul) in mults.items():
        for table in tables:
            for spec in table.get(area, []) or []:
                spec["hp_mult"] = round(float(spec.get("hp_mult", 1.0)) * hp_mul, 3)
                spec["atk_mult"] = round(float(spec.get("atk_mult", 1.0)) * atk_mul, 3)

_apply_v23_forest_mountain_difficulty()
