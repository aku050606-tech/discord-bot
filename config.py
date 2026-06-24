# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全体設定ファイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VC_REWARD_COINS = 100
VC_REWARD_INTERVAL = 300
CHAT_REWARD_COINS = 1
PVP_FEE_RATE = 0.10

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スロット設定  ── EVENT HORIZON 仕様（完全版）──
#   構造: 通常時(小役で土台) → GOD抽選 → EVENT HORIZON(継続ランクループ)
#   ランク: NOVA25% → FLARE50% → SUPERNOVA65% → PULSAR75% → SINGULARITY85%(聖域)
#
#   ・聖域(SINGULARITY)は単独フラグでのみ当選。当選時は必ず専用7秒演出でバラす
#   ・その他GODはレア役からの当選。強役ほど当選力＆入口ランクが高い
#   ・GOD中は子役連動でランクアップ（強役=ほぼ確定昇格、1段ずつ・PULSAR上限）
#   ・上限なしループ / 結果先抽選→演出は見せ方だけ / 確率はゲーム内非表示
#
#   ※ モンテカルロ検算済み:
#       総戻り率 設定1:100.8% 〜 設定6:137.0%
#       通常時コイン持ち 1000枚で33〜39回転（20スロ感）
#       GOD平均一撃 ≈ 3,450枚 / 中央 2,300枚
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SLOT_BET = 60

# 日付ベースでシード固定。1日1回、各台の設定(1〜6)を割り当て
def get_daily_machines():
    from datetime import date
    seed = int(str(date.today()).replace("-", ""))
    rng = __import__('random').Random(seed)
    return [rng.randint(1, 6) for _ in range(10)]

# ── 設定別パラメータ ──
#   koyaku_mult : 小役払い出し倍率（高設定ほど持つ）
#   god_mult    : レア役からのGOD当選率の設定倍率（高設定ほど当たる）
#   premium_per : 聖域(SINGULARITY)単独抽選 1/n（高設定ほど引きやすい）
SLOT_SETTINGS = {
    1: {"koyaku_mult": 1.10, "god_mult": 0.80, "premium_per": 6000},
    2: {"koyaku_mult": 1.13, "god_mult": 0.89, "premium_per": 5500},
    3: {"koyaku_mult": 1.16, "god_mult": 0.98, "premium_per": 5000},
    4: {"koyaku_mult": 1.19, "god_mult": 1.06, "premium_per": 4600},
    5: {"koyaku_mult": 1.22, "god_mult": 1.14, "premium_per": 4200},
    6: {"koyaku_mult": 1.25, "god_mult": 1.23, "premium_per": 3900},
}

# ── 通常時 小役 (キー, 基本払い出し, 出現率) ──
# 上から順に判定し、最初に当たった1役を採用（順送り）
SLOT_KOYAKU = [
    ("replay", 60,  1/7.3),   # 実質ベット返却（リプレイは絞り目で20スロ感）
    ("bell",   120, 1/9),     # 主力子役
    ("cherry", 70,  1/26),
    ("suika",  260, 1/40),    # 引けたら嬉しいドン
    ("weak",   60,  1/120),   # チャンス目（GOD契機・中）
    ("schk",   60,  1/220),   # 強チャンス目（GOD契機・強／出現2倍）
    ("schy",   60,  1/170),   # 強チェリー  （GOD契機・強／出現2倍）
]

# ── レア役ごとの GOD当選率（× 設定 god_mult）──
# 強役は「ほぼ確定」ではなく確率制：設定で36〜57%に変動＝設定推測の手がかり
GOD_TRIGGER_RATE = {
    "replay": 0.0,
    "bell":   0.002,
    "cherry": 0.10,
    "suika":  0.13,
    "weak":   0.35,
    "schk":   0.50,
    "schy":   0.425,
}

# ── GOD入口ランク（契機役の強さで決まる）──
# 重み NOVA / FLARE / SUPERNOVA / PULSAR
GOD_ENTRY_WEIGHTS = {
    "soft":   [0.62, 0.28, 0.08, 0.02],   # bell / cherry / suika
    "mid":    [0.45, 0.32, 0.18, 0.05],   # weak（チャンス目）
    "strong": [0.18, 0.30, 0.32, 0.20],   # schk / schy（強役は良いとこスタート）
}
GOD_TRIGGER_GROUP = {
    "bell": "soft", "cherry": "soft", "suika": "soft",
    "weak": "mid", "schk": "strong", "schy": "strong",
}

# ── GODランク定義 ──
GOD_ZONE_NAME = "EVENT HORIZON"
GOD_RANKS = [   # 子役で到達できるランク（上限PULSAR）
    {"key": "nova",      "name": "NOVA",      "rate": 0.25, "emoji": "💫"},
    {"key": "flare",     "name": "FLARE",     "rate": 0.50, "emoji": "🔥"},
    {"key": "supernova", "name": "SUPERNOVA", "rate": 0.65, "emoji": "🌠"},
    {"key": "pulsar",    "name": "PULSAR",    "rate": 0.75, "emoji": "🌀"},
]
GOD_SINGULARITY = {"key": "singularity", "name": "SINGULARITY", "rate": 0.85, "emoji": "🌌"}  # 聖域

# ── GOD中 子役連動ランクアップ ──
# 各セットで子役抽選（順送り・最強1役のみ反映）→ 出た子役で昇格抽選（1段ずつ）
# 実効昇格期待値 ≈ 0.15/セット（balance据え置き）
GOD_SET_KOYAKU = [   # (キー, セット内出現率, 昇格率, 表示名, emoji)
    ("strong", 0.045, 0.95, "強チェリー",   "🌠"),  # 出たらほぼ確定昇格
    ("mid",    0.130, 0.55, "スイカ",       "🍉"),
    ("weak",   0.260, 0.18, "チェリー",     "🍒"),
]

GOD_SET_BASE = 850   # 1セット基本獲得
# ルート別 上乗せ分布 (額, 確率) ── 期待値は全ルート=650でEV中立、波だけ違う ──
GOD_UP_BALANCED = [(300, 0.70), (800, 0.20), (2000, 0.08), (6000, 0.02)]   # オート時(中庸)
GOD_UP_ORBIT    = [(450, 0.45), (700, 0.42), (1200, 0.13)]                 # 🛰️ 軌道: 低分散
GOD_UP_BIGBANG  = [(0,   0.70), (400, 0.18), (3500, 0.10), (11500, 0.02)]  # 💥 爆発: 高分散

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 演出ウェイト（秒）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLOT_WAIT = {
    "calm":     1.5,   # 🌑凪（ハズレ）はサクッと
    "weak":     2.3,   # ✨微
    "hot":      3.0,   # ⚡熱
    "superhot": 3.8,   # 💥激
    "god":      4.5,   # ☯️GOD確定（通常）
    # 聖域は3ビート（暗転→検知→顕現＝計7秒）
    "holy_1":   2.5,
    "holy_2":   2.0,
    "holy_3":   2.5,
    # GOD中「狙え」開示タメ（ランクで延長）
    "aim":             0.6,
    "aim_pulsar":      1.0,
    "aim_singularity": 1.5,
    "rankup":   1.2,   # 昇格演出
    "feint":    1.4,   # フェイントのタメ
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# リール表示
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REELS = {
    "blank":       ["🌑", "⭐", "🌠"],
    "replay":      ["🔄", "🔄", "🔄"],
    "bell":        ["🔔", "🔔", "🔔"],
    "cherry":      ["🍒", "🌑", "⭐"],
    "suika":       ["🍉", "🍉", "🍉"],
    "weak":        ["⭐", "🌠", "🍒"],
    "schk":        ["⭐", "⭐", "🌠"],
    "schy":        ["🍒", "🍒", "🍒"],
    "nova":        ["💫", "💫", "💫"],
    "flare":       ["🔥", "🔥", "🔥"],
    "supernova":   ["🌠", "🌠", "🌠"],
    "pulsar":      ["🌀", "🌀", "🌀"],
    "singularity": ["🌌", "🌌", "🌌"],
    "entry":       ["☯️", "☯️", "☯️"],
    "dark":        ["🌑", "🌑", "🌑"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ① 通常時 演出（結果先抽選→信頼度プールで見せ方を選ぶ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLOT_EFFECTS = {
    "calm": [
        "🌑 静かな宙（そら）…", "💤 計器は沈黙したまま…", "🍃 暗い真空を漂う…",
        "😶 星ひとつ瞬かない…", "🛰️ 信号は途絶えたまま…", "🌀 虚空が回る…",
    ],
    "weak": [
        "✨ 遠くで何かが瞬いた…？", "📡 微かな信号を捉えた…", "💫 宇宙塵がざわめく…",
        "👀 計器がわずかに反応した…", "🌌 重力がゆらいだ気がする…",
    ],
    "hot": [
        "⚡ 計器の針が跳ねた…！", "🔥 エネルギーが急上昇していく…！",
        "🌠 何かが生まれようとしている…！", "💥 空間がねじれ始めた…！",
    ],
    "superhot": [
        "⚡⚡ 計器が振り切れた…！！", "🔥 臨界点を突破…！！",
        "🌪️ 時空が軋んでいる…！！", "😱 巨大な“何か”が近づく…！！！",
    ],
    "god_confirm": [   # ☯️＝GOD確定（ランクは不明）
        "──　☯️　──", "視界の端を、黒い円がよぎった。", "重力波、検知。",
    ],
}

# 通常時 信頼度テーブル：結果ごとに各溜めの出現率（合計1.0）
# キー: calm / weak / hot / superhot / god_confirm
SLOT_EFFECT_WEIGHTS = {
    "blank":  {"calm": 0.740, "weak": 0.220, "hot": 0.035, "superhot": 0.005},
    "replay": {"calm": 0.500, "weak": 0.420, "hot": 0.070, "superhot": 0.010},
    "bell":   {"calm": 0.500, "weak": 0.420, "hot": 0.070, "superhot": 0.010},
    "cherry": {"calm": 0.080, "weak": 0.520, "hot": 0.340, "superhot": 0.060},
    "suika":  {"calm": 0.080, "weak": 0.520, "hot": 0.340, "superhot": 0.060},
    "weak":   {"calm": 0.030, "weak": 0.150, "hot": 0.520, "superhot": 0.300},
    "schk":   {"calm": 0.030, "weak": 0.150, "hot": 0.520, "superhot": 0.300},
    "schy":   {"calm": 0.030, "weak": 0.150, "hot": 0.520, "superhot": 0.300},
    # GOD当選時：激寄り＋☯️確定が12%
    "god":    {"calm": 0.05, "weak": 0.08, "hot": 0.30, "superhot": 0.45, "god_confirm": 0.12},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ②-A 通常GOD突入演出（5種バリエーション・ランダム）
#     (絵文字, 1行目, 2行目)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOD_ENTRY_EFFECTS = [
    ("☯️", "EVENT HORIZON", "── 事象の地平線を、超えた。"),
    ("🌀", "空間が、歪む──", "重力に呑まれていく…！"),
    ("🌑", "……と、思いきや。", "引き返せない領域へ。"),
    ("💥", "臨界、突破ァ！！", "新しい星が、生まれる──"),
    ("☯️", "──　確定。", "GOD、来た。"),   # ☯️確定演出から繋ぐ版
]

# ②-B 聖域突入演出（専用・7秒3ビート）
GOD_HOLY_BEATS = [
    ("🌑", "", "　……"),                                       # ビート1：暗転
    ("☯️", "重力波、検知。", "光が、一点へ堕ちていく──"),        # ビート2：異変
    ("🌌🌌🌌", "S I N G U L A R I T Y", "特異点、開く。"),       # ビート3：顕現
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ④ 継続「狙え」演出
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 「狙え」ボタンの文言（ランク連動）
GOD_AIM_LABELS = {
    "nova": "☯️ 狙え", "flare": "☯️ 狙え",
    "supernova": "☄️ 狙い撃て…！", "pulsar": "☄️ 狙い撃て…！",
    "singularity": "🌌 視ろ──",
}

# 継続カットイン（信頼度4段）。weightは継続時の出やすさ
GOD_CONTINUE_EFFECTS = [
    ("normal",  0.78, "🔥 継続！！", "ループは続く──"),
    ("strong",  0.15, "⚡⚡ まだだ、まだ終わらない…！！", ""),
    ("super",   0.05, "💥 ねじ伏せた──！！！", ""),
    ("rainbow", 0.02, "🌈 ―― 約束された継続。", ""),   # 虹＝継続確定（押す前でも出うる）
]

# フェイント（共通入り→タメ後に分岐）。継続・終了それぞれ20%で発生
GOD_FEINT_RATE = 0.20
GOD_FEINT_INTRO = ("💨", "引力が、緩んでいく……")     # 継続・終了で完全同一
GOD_FEINT_CONTINUE = ("🔥", "……否。掴んだ。継続！！")
GOD_FEINT_END      = ("🌑", "……そのまま、抜けた。")

# 通常の終了余韻（フェイントでない80%）
GOD_END_EFFECTS = [
    ("🌑", "……ふっと、軽くなった。"),
    ("🌑", "引力が、消えた。"),
    ("🌌", "静寂が、戻ってくる。"),
]

# 昇格（ランクアップ）進化演出： to_key -> (emoji, text)
GOD_RANKUP_EFFECTS = {
    "flare":     ("🔥", "燃え上がる── FLARE 到達"),
    "supernova": ("🌠", "爆発的に膨張── SUPERNOVA"),
    "pulsar":    ("🌀", "規則的な脈動── PULSAR"),
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⑥ 終了総括の締め文言（一撃額で格付け・案①詩的）
#     (しきい値, 文言)  ※上から判定、最初に超えたもの
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOD_FINISH_LINES = [
    (30000, "🌠 銀河が、ひれ伏した。"),
    (10000, "💫 重力すら、味方につけた。"),
    (3000,  "🔥 軌道に、爪痕を残した。"),
    (0,     "星は、また沈んだ。"),
]
GOD_FINISH_HOLY = "🌌 ―― 特異点の中心で、それを見た。"   # 聖域制覇 専用

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
