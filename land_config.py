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
    1: {"name": "平原", "emoji": "🌿", "req_lv": 1,  "base": 5,  "scale": 1.0,
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

# ── 敵カタログ（エリア別）──
#   ratio：base への倍率（強さ）。hp_mult/atk_mult：味付け。tier：AI・技の強さ。stars：表示用の☆（強さ＝1〜3）。
LAND_ENEMIES = {
    1: [  # 🌿 平原 ☆1：素手でも確実に倒せる。攻撃は微々たるもの。
        {"name": "スライム",         "emoji": "🟢",  "ratio": 0.7, "hp_mult": 1.0, "atk_mult": 0.35, "tier": 1, "stars": 1},
        {"name": "野ねずみの群れ",   "emoji": "🐀",  "ratio": 0.8, "hp_mult": 0.8, "atk_mult": 0.40, "tier": 1, "stars": 1},
        {"name": "青大将",           "emoji": "🐍",  "ratio": 0.9, "hp_mult": 0.9, "atk_mult": 0.40, "tier": 1, "stars": 1},
        {"name": "野犬",             "emoji": "🐕",  "ratio": 1.0, "hp_mult": 0.9, "atk_mult": 0.45, "tier": 1, "stars": 1},
        {"name": "ゴブリンの子",     "emoji": "👶",  "ratio": 1.0, "hp_mult": 0.9, "atk_mult": 0.40, "tier": 1, "stars": 1},
        {"name": "大バッタ",         "emoji": "🦗",  "ratio": 1.1, "hp_mult": 0.8, "atk_mult": 0.45, "tier": 1, "stars": 1},
        {"name": "はぐれゴブリン",   "emoji": "👺",  "ratio": 1.2, "hp_mult": 1.0, "atk_mult": 0.45, "tier": 1, "stars": 1},
        {"name": "イノシシ",         "emoji": "🐗",  "ratio": 1.3, "hp_mult": 1.1, "atk_mult": 0.50, "tier": 1, "stars": 1},
    ],
    2: [  # 🌲 森 ☆2：海E2くらいの手応え。HP/DEFは厚いが攻撃は低め。装備で“倒す速さ”が効く。
        {"name": "森オオカミ",       "emoji": "🐺",  "ratio": 0.90, "hp_mult": 0.95, "atk_mult": 0.36, "tier": 2, "stars": 2},
        {"name": "コボルト",         "emoji": "🦎",  "ratio": 0.95, "hp_mult": 1.00, "atk_mult": 0.34, "tier": 2, "stars": 2},
        {"name": "大グモ",           "emoji": "🕷️",  "ratio": 1.00, "hp_mult": 0.95, "atk_mult": 0.36, "tier": 2, "stars": 2},
        {"name": "毒キノコ人間",     "emoji": "🍄",  "ratio": 1.00, "hp_mult": 1.05, "atk_mult": 0.32, "tier": 2, "stars": 2},
        {"name": "山賊の物見",       "emoji": "🗡️",  "ratio": 1.05, "hp_mult": 0.95, "atk_mult": 0.38, "tier": 2, "stars": 2},
        {"name": "大ムカデ",         "emoji": "🐛",  "ratio": 1.05, "hp_mult": 1.00, "atk_mult": 0.34, "tier": 2, "stars": 2},
        {"name": "塔の番犬",         "emoji": "🐕‍🦺", "ratio": 1.10, "hp_mult": 1.05, "atk_mult": 0.36, "tier": 2, "stars": 2},
        {"name": "森の熊",           "emoji": "🐻",  "ratio": 1.15, "hp_mult": 1.15, "atk_mult": 0.36, "tier": 2, "stars": 2},
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
        {"name": "草原の大猪",     "emoji": "🐗", "ratio": 4.2, "hp_mult": 2.2, "atk_mult": 0.50, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [(1, 0.03)]},
        {"name": "古老ゴブリン",   "emoji": "👹", "ratio": 4.0, "hp_mult": 2.4, "atk_mult": 0.50, "tier": 1, "stars": 2,
         "xp": [20, 40], "coin": [1000, 2500], "drop": [(1, 0.03)]},
        {"name": "群れの長狼",     "emoji": "🐺", "ratio": 4.4, "hp_mult": 2.0, "atk_mult": 0.54, "tier": 1, "stars": 2,
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


def make_land_enemy(area):
    """make_board_enemy(spec, scale) が食える敵スペックを返す。
    抽選：激レア1%（ボス級）→ 中レア5% → 雑魚94%。"""
    a = LAND_AREAS[area]
    roll = random.random()
    # ✨ 激レア（全エリア共通ボス）
    if roll < RARE_SPAWN_RATE and LAND_RARES.get(area):
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
    if roll < RARE_SPAWN_RATE + MIDRARE_SPAWN_RATE and LAND_MIDRARES.get(area):
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


def land_encounter_pick(area):
    table = LAND_ENCOUNTERS.get(area, LAND_ENCOUNTERS[1])
    keys = list(table.keys()); wts = list(table.values())
    return random.choices(keys, weights=wts)[0]


def pick_story(area):
    pool = LAND_STORY.get(area, [])
    return random.choice(pool) if pool else None


def pick_event(area):
    pool = LAND_EVENTS.get(area, [])
    return random.choice(pool) if pool else None
