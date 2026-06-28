"""
🛤️ 街道（陸の冒険）の設定
─────────────────────────────────────────────
海の白兵戦エンジン・装備・技をそのまま流用する「陸」コンテンツ。
・平原＝素手でも確実に倒せる激弱バランス（ただし装備が無いと時間がかかり、ちまちま削られる）。
・森＝海のE2くらいの“手応え”。ちゃんと装備すればあまり食らわないが、生身だと痛手。
・山＝海のE3くらいの“手応え”。
・全体方針：敵の攻撃力は低め（＝あまりダメージを食らわない）。きついのは「装備が足りない」とき。
・HPは毎戦は回復しない（持ち越し）。タウンに戻れば全快。道中は食料で回復。
・XPは渋め＝雑魚およそ200匹で1レベルの体感。大きく稼ぐのはレアキャラ（激レア）。
・船・燃料・カケラは無い。

敵スペックは make_board_enemy(spec, scale) がそのまま食える形。
  敵HP  = crew_power × combat_scale(scale) × BOARD_E_HP_MULT(5.0) × hp_mult
  敵ATK = crew_power × scale^0.65 × BOARD_E_ATK_MULT(1.0) × atk_mult
  敵DEF = crew_power × scale^0.65 × BOARD_E_DEF_MULT(0.5)
"""
import random

# ── エリア定義 ──
#   req_lv：解放レベル（想定レベル）。base：crew_power の底上げ。scale：戦闘スケール。
#   xp/coin：撃破報酬の範囲（雑魚）。XPは渋め＝約200匹で1レベル。
LAND_AREAS = {
    1: {"name": "平原", "emoji": "🌿", "req_lv": 1,  "base": 8,  "scale": 1.0,
        "xp": [4, 6],     "coin": [200, 600],
        "intro": ("見渡すかぎりの草原。風が膝丈の草を撫でていく。\n"
                  "弱い魔物がぽつぽつと現れる――腕慣らしには、ちょうどいい。\n"
                  "……ふと、草の向こうで何かが動いた気がした。気のせいか。")},
    2: {"name": "森", "emoji": "🌲", "req_lv": 8,  "base": 18, "scale": 1.6,
        "xp": [6, 10],   "coin": [450, 1100],
        "intro": ("木々が空を覆い、足元は薄暗い。獣の気配が、あちこちに。\n"
                  "平原より、ずっと手強い――ちゃんと武器と防具を整えてこい。\n"
                  "奥には、人の手が入った痕跡。誰かが、この森を“管理”している。")},
    3: {"name": "山", "emoji": "⛰️", "req_lv": 15, "base": 20, "scale": 2.6,
        "xp": [10, 14],  "coin": [900, 2000],
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
    ],
    2: [  # 🌲 森 ☆2：海E2くらいの手応え。HP/DEFは厚いが攻撃は低め。装備で“倒す速さ”が効く。
        {"name": "森オオカミ",       "emoji": "🐺",  "ratio": 0.95, "hp_mult": 1.10, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "コボルト",         "emoji": "🦎",  "ratio": 1.00, "hp_mult": 1.12, "atk_mult": 0.46, "tier": 2, "stars": 2},
        {"name": "大グモ",           "emoji": "🕷️",  "ratio": 1.05, "hp_mult": 1.08, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "毒キノコ人間",     "emoji": "🍄",  "ratio": 1.05, "hp_mult": 1.18, "atk_mult": 0.44, "tier": 2, "stars": 2},
        {"name": "山賊の物見",       "emoji": "🗡️",  "ratio": 1.10, "hp_mult": 1.08, "atk_mult": 0.50, "tier": 2, "stars": 2},
        {"name": "大ムカデ",         "emoji": "🐛",  "ratio": 1.10, "hp_mult": 1.12, "atk_mult": 0.46, "tier": 2, "stars": 2},
        {"name": "塔の番犬",         "emoji": "🐕‍🦺", "ratio": 1.15, "hp_mult": 1.18, "atk_mult": 0.48, "tier": 2, "stars": 2},
        {"name": "森の熊",           "emoji": "🐻",  "ratio": 1.20, "hp_mult": 1.28, "atk_mult": 0.50, "tier": 2, "stars": 2},
    ],
    3: [  # ⛰️ 山 ☆3：海E3くらいの手応え。さらに厚く、tier3で技も使う。攻撃は中の下。
        {"name": "岩トカゲ",         "emoji": "🦎",  "ratio": 0.90, "hp_mult": 1.10, "atk_mult": 0.40, "tier": 3, "stars": 3},
        {"name": "山賊",             "emoji": "🪓",  "ratio": 1.00, "hp_mult": 1.00, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "ハーピー",         "emoji": "🦅",  "ratio": 1.00, "hp_mult": 0.95, "atk_mult": 0.46, "tier": 3, "stars": 3},
        {"name": "塔の衛兵",         "emoji": "💂",  "ratio": 1.05, "hp_mult": 1.10, "atk_mult": 0.42, "tier": 3, "stars": 3},
        {"name": "岩ゴーレム",       "emoji": "🗿",  "ratio": 1.10, "hp_mult": 1.25, "atk_mult": 0.38, "tier": 3, "stars": 3},
        {"name": "霜の魔狼",         "emoji": "🐺",  "ratio": 1.10, "hp_mult": 1.00, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "オーガ",           "emoji": "👹",  "ratio": 1.20, "hp_mult": 1.20, "atk_mult": 0.44, "tier": 3, "stars": 3},
        {"name": "ワイバーン",       "emoji": "🐉",  "ratio": 1.20, "hp_mult": 1.05, "atk_mult": 0.46, "tier": 3, "stars": 3},
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
         "xp": [900, 1500], "coin": [9000, 16000],
         "rare_intro": ("森のざわめきが、ふっと止んだ。\n"
                        "フードを目深にかぶった男が、音もなく行く手を塞ぐ。\n"
                        "……こいつは、これまでの獣とは“格”が違う。"),
         "story": "倒れた男の懐から、塔の紋章入りの書付が落ちた。\n「海の者を、陸に上げるな」――そう走り書きされていた。"},
    ],
    3: [
        {"name": "塔の伝令騎士",      "emoji": "🛡️", "ratio": 1.7, "hp_mult": 1.7, "atk_mult": 0.60, "tier": 4, "stars": 4,
         "xp": [3000, 5000], "coin": [18000, 35000],
         "rare_intro": ("空気が、軋んだ。\n"
                        "塔の紋章を掲げた騎士が、ゆっくりと剣を抜く。\n"
                        "ひと目でわかる――まともにやり合えば、ただでは済まない。"),
         "story": "騎士は崩れ落ちながら、低く笑った。\n「塔は海を抑えているのではない。……抑えられているのは、こちらの方だ」"},
    ],
}
RARE_SPAWN_RATE = 0.01   # 戦闘のうちレア（激レア）に化ける確率（1%）

# ── レアは全エリア共通で“☆3ボス級”の強さ（基本倒せない・逃げる前提）──
#   make_land_enemy がレアの戦闘力をこの固定値で上書きする（エリアのbase/scaleに依存しない）。
#   実測：Lv30・☆3フル装備でようやく勝率≈25%（ワンチャン）／それ未満はほぼ0%。
RARE_BOSS = {"crew_power": 60, "scale": 2.2, "hp_mult": 1.6, "atk_mult": 0.58, "tier": 4, "stars": 4,
             "drop": [(3, 0.20)]}   # 激レア撃破＝☆3装備20%

# ── 🔸 中レア（各エリア3種・遭遇5%）──
#   雑魚と激レアの中間。倒せるが歯ごたえあり＝固有名・XP/コイン多め・装備ドロップ高め。
#   強さはエリアのbase×ratioで雑魚と同じ計算（激レアのような固定ボスではない）。
#   midrare_drop：撃破時の装備ドロップ（☆, 確率）。
LAND_MIDRARES = {
    1: [  # 🌿 平原 ☆2
        {"name": "草原の大猪",     "emoji": "🐗", "ratio": 4.8, "hp_mult": 2.8, "atk_mult": 0.70, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [(1, 0.03)]},
        {"name": "古老ゴブリン",   "emoji": "👹", "ratio": 4.6, "hp_mult": 3.0, "atk_mult": 0.70, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [(1, 0.03)]},
        {"name": "群れの長狼",     "emoji": "🐺", "ratio": 5.0, "hp_mult": 2.6, "atk_mult": 0.76, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [(1, 0.03)]},
    ],
    2: [  # 🌲 森 ☆3
        {"name": "森の主・大熊",   "emoji": "🐻", "ratio": 1.7, "hp_mult": 1.7, "atk_mult": 0.40, "tier": 2, "stars": 3,
         "xp": [45, 85], "coin": [2200, 4800], "drop": [(2, 0.03)]},
        {"name": "毒蜘蛛の女王",   "emoji": "🕷️", "ratio": 1.6, "hp_mult": 1.6, "atk_mult": 0.42, "tier": 2, "stars": 3,
         "xp": [45, 85], "coin": [2200, 4800], "drop": [(2, 0.03)]},
        {"name": "山賊の頭目",     "emoji": "🗡️", "ratio": 1.7, "hp_mult": 1.5, "atk_mult": 0.44, "tier": 2, "stars": 3,
         "xp": [45, 85], "coin": [2200, 4800], "drop": [(2, 0.03)]},
    ],
    3: [  # ⛰️ 山 ☆3
        {"name": "古竜のなりそこない", "emoji": "🐲", "ratio": 1.6, "hp_mult": 1.6, "atk_mult": 0.46, "tier": 3, "stars": 3,
         "xp": [90, 160], "coin": [4500, 9000], "drop": [(3, 0.03)]},
        {"name": "石の巨人",       "emoji": "🗿", "ratio": 1.5, "hp_mult": 1.8, "atk_mult": 0.42, "tier": 3, "stars": 3,
         "xp": [90, 160], "coin": [4500, 9000], "drop": [(3, 0.03)]},
        {"name": "山の魔女",       "emoji": "🧙", "ratio": 1.6, "hp_mult": 1.5, "atk_mult": 0.48, "tier": 3, "stars": 3,
         "xp": [90, 160], "coin": [4500, 9000], "drop": [(3, 0.03)]},
    ],
}
MIDRARE_SPAWN_RATE = 0.05   # 戦闘のうち中レアに化ける確率（5%）

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
LAND_EQUIP_DROP = {1: [(1, 0.001)], 2: [(2, 0.001)], 3: [(3, 0.001)]}


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
    "bandage": {"emoji":"🩹", "name":"包帯", "rarity":"common", "price":4000, "shop":"always", "desc":"HPを20%回復"},
    "smoke_bomb": {"emoji":"💨", "name":"煙玉", "rarity":"rare", "price":15000, "shop":"random", "desc":"次の雑魚戦を回避"},
    "lucky_charm": {"emoji":"🍀", "name":"幸運のお守り", "rarity":"rare", "price":25000, "shop":"random", "desc":"次の探索だけ中ボス/大ボス率UP"},
    "old_map": {"emoji":"🗺️", "name":"古びた地図", "rarity":"rare", "price":30000, "shop":"random", "desc":"次の探索をイベント寄りにする"},
    "lantern": {"emoji":"🔦", "name":"探索ランタン", "rarity":"rare", "price":40000, "shop":"drop", "desc":"次の探索で何もなしを避けやすくする"},
    "gold_compass": {"emoji":"🧭", "name":"黄金の羅針盤", "rarity":"epic", "price":80000, "shop":"drop", "desc":"次の探索のコイン収穫+50%"},
    "decoy_doll": {"emoji":"🪆", "name":"身代わり人形", "rarity":"epic", "price":0, "shop":"drop", "desc":"死亡時の収穫ロストを自動で無効化"},
    "guardian_feather": {"emoji":"👼", "name":"守護の羽", "rarity":"legend", "price":0, "shop":"drop", "desc":"死亡時に使う/使わないを選べる。使うと収穫ロスト無効"},
}

# 戦闘合計50%固定：雑魚44 / 中ボス5 / 大ボス1。非戦闘側だけエリアで味付け。
LAND_EVENT_TABLE = {
    1: {"combat":44, "midrare":5, "rare":1, "story":14, "event":14, "item":6, "coin":8, "gather":6, "calm":2},
    2: {"combat":44, "midrare":5, "rare":1, "story":15, "event":15, "item":5, "coin":7, "gather":6, "calm":2},
    3: {"combat":44, "midrare":5, "rare":1, "story":16, "event":16, "item":5, "coin":6, "gather":5, "calm":2},
}

# アイテムイベント時の抽選。エピックは幻レベル寄り。
LAND_ITEM_EVENT_DROPS = [
    ("bandage", 45), ("smoke_bomb", 12), ("lucky_charm", 8), ("old_map", 8),
    ("lantern", 5), ("gold_compass", 1.2), ("decoy_doll", 0.15), ("guardian_feather", 0.04),
]

# 戦闘ドロップ：雑魚でも落ちるがかなり低確率。
LAND_ITEM_DROP_RATES = {
    # 雑魚からも「たまに」落ちる。使える消耗品は少し出やすく、エピック/レジェンドは幻枠。
    "zako": [("bandage",0.030), ("smoke_bomb",0.006), ("lucky_charm",0.004), ("old_map",0.004), ("lantern",0.002), ("decoy_doll",0.00010), ("guardian_feather",0.00003)],
    "mid":  [("bandage",0.100), ("smoke_bomb",0.030), ("lucky_charm",0.025), ("old_map",0.025), ("lantern",0.012), ("gold_compass",0.006), ("decoy_doll",0.00080), ("guardian_feather",0.00020)],
    "rare": [("bandage",0.250), ("smoke_bomb",0.080), ("lucky_charm",0.070), ("old_map",0.070), ("lantern",0.035), ("gold_compass",0.018), ("decoy_doll",0.00300), ("guardian_feather",0.00100)],
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
    force: rare / midrare / combat を指定できる。lucky_charm時はレア系が少し出やすい。"""
    a = LAND_AREAS[area]
    buffs = buffs or {}
    rare_rate = RARE_SPAWN_RATE * (2.0 if buffs.get("lucky_charm") else 1.0)
    mid_rate = MIDRARE_SPAWN_RATE * (1.5 if buffs.get("lucky_charm") else 1.0)
    roll = random.random()
    # ✨ 激レア（全エリア共通ボス）
    if (force == "rare" or (force is None and roll < rare_rate)) and LAND_RARES.get(area):
        e = random.choice(LAND_RARES[area])
        return {
            "name": e["name"], "emoji": e["emoji"], "key": f"land{area}_{e['name']}",
            "crew_power": RARE_BOSS["crew_power"],
            "hp_mult": RARE_BOSS["hp_mult"], "atk_mult": RARE_BOSS["atk_mult"],
            "tier": RARE_BOSS["tier"], "stars": RARE_BOSS["stars"],
            "scale_override": RARE_BOSS["scale"],
            "is_boss": False, "is_rare": True,
            "drop_table": RARE_BOSS["drop"],
            "rare_xp": e.get("xp"), "rare_coin": e.get("coin"),
            "rare_story": e.get("story", ""), "rare_intro": e.get("rare_intro", ""),
        }
    # 🔸 中レア
    if (force == "midrare" or (force is None and roll < rare_rate + mid_rate)) and LAND_MIDRARES.get(area):
        e = random.choice(LAND_MIDRARES[area])
        return {
            "name": e["name"], "emoji": e["emoji"], "key": f"landmid{area}_{e['name']}",
            "crew_power": max(1, round(a["base"] * e["ratio"])),
            "hp_mult": e.get("hp_mult", 1.0), "atk_mult": e.get("atk_mult", 1.0),
            "tier": e.get("tier", 1), "stars": e.get("stars", 2),
            "is_boss": False, "is_rare": False, "is_midrare": True,
            "mid_xp": e.get("xp"), "mid_coin": e.get("coin"),
            "drop_table": e.get("drop"),
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
    }


def land_encounter_pick(area, buffs=None):
    table = dict(LAND_EVENT_TABLE.get(area, LAND_EVENT_TABLE[1]))
    buffs = buffs or {}
    if buffs.get("old_map"):
        table["event"] += 18; table["item"] += 7; table["calm"] = max(0, table.get("calm", 0) - 2)
    if buffs.get("lantern"):
        table["calm"] = 0; table["gather"] += 2
    keys = list(table.keys()); wts = list(table.values())
    return random.choices(keys, weights=wts)[0]

def pick_land_item(area=None):
    keys = [x[0] for x in LAND_ITEM_EVENT_DROPS]; wts = [x[1] for x in LAND_ITEM_EVENT_DROPS]
    return random.choices(keys, weights=wts)[0]

def pick_random_event(area):
    pool = LAND_RANDOM_EVENTS.get(area, []) or LAND_EVENTS.get(area, [])
    return random.choice(pool) if pool else None


def pick_story(area):
    pool = LAND_STORY.get(area, [])
    return random.choice(pool) if pool else None


def pick_event(area):
    pool = LAND_EVENTS.get(area, [])
    return random.choice(pool) if pool else None
