# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全体設定ファイル
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── 日替わりの基準日（JST固定オフセット）──
#   Railway(Nixpacks)のコンテナには tzdata が無いことがあり、TZ=Asia/Tokyo を
#   指定しても解決できず黙ってUTCにフォールバックする。すると date.today() が
#   UTCになり、日替わりが JST 9時(=UTC 0時)にズレる。
#   日本はサマータイム無し＝+9固定で常に正しいので、tzdataに依存しないこの方式を
#   全ての日替わり判定の単一ソースにする（釣り/weather/rewardsと同じ作法に統一）。
from datetime import datetime as _dt, timezone as _tz, timedelta as _td
JST = _tz(_td(hours=9))

def jst_today():
    """JST(日本時間)基準の今日の日付(date)。日替わり判定はすべてこれを使う。"""
    return _dt.now(JST).date()

def jst_today_str() -> str:
    """JST基準の今日の日付を 'YYYY-MM-DD' 文字列で返す。"""
    return jst_today().isoformat()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 管理者設定（このIDのユーザーだけ /admin を操作できる）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN_USER_IDS = ["418739767966957579"]

# 1回の管理操作で動かせる上限（誤操作でとんでもない額にならないための安全弁）
ADMIN_MAX_AMOUNT = 1_000_000_000

VC_REWARD_COINS = 100
VC_REWARD_INTERVAL = 300
CHAT_REWARD_COINS = 1

# ── デイリーボーナス・送金（menu.py / economy.py 共通の単一ソース）──
DAILY_AMOUNT = 2000        # デイリーボーナス額（ナトコイン）
DAILY_SEND_LIMIT = 3000    # 1日の送金上限（ナトコイン）

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スロット設定  ── EVENT HORIZON 仕様（完全版）──
#   構造: 通常時(小役で土台) → GOD抽選 → EVENT HORIZON(継続ランクループ)
#   ランク: NOVA45% → FLARE58% → SUPERNOVA70% → PULSAR80% → SINGULARITY90%(聖域)
#
#   ・聖域(SINGULARITY)は単独フラグでのみ当選。当選時は必ず専用7秒演出でバラす
#   ・その他GODはレア役からの当選。強役ほど当選力＆入口ランクが高い
#   ・GOD中は子役連動でランクアップ（強役=ほぼ確定昇格、1段ずつ・PULSAR上限）
#   ・上限なしループ / 結果先抽選→演出は見せ方だけ / 確率はゲーム内非表示
#
#   ※ モンテカルロ検算済み:
#       総戻り率 設定1:100.2% 〜 設定6:124.3%
#       通常時コイン持ち 1000枚で33〜39回転（20スロ感）
#       GOD平均一撃 ≈ 3,450枚 / 中央 2,300枚
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SLOT_BET = 60

# 日付ベースでシード固定。1日1回、各台の設定(1〜6)を割り当て
# 末尾が 1 / 3 / 7 の日は「設定6を1台・設定1なし」のイベント日にする
HIGH_SETTING_DAY_DIGITS = (1, 3, 7)

def is_high_setting_day(today=None):
    """その日が『設定6が1台入る熱い日（末尾1/3/7）』かどうか（JST基準）"""
    if today is None:
        today = jst_today()
    return (today.day % 10) in HIGH_SETTING_DAY_DIGITS

def get_daily_machines(today=None):
    """その日の各台(5台)の設定を返す。位置は日付シードで固定シャッフル。
    ・末尾 1/3/7 の日 : 設定6を1台 + 設定2〜5（=設定1なし）
    ・それ以外の日     : 設定1〜5を1台ずつ
    """
    import random as _r
    if today is None:
        today = jst_today()
    rng = _r.Random(int(str(today).replace("-", "")))
    if is_high_setting_day(today):
        settings = [6, 2, 3, 4, 5]   # 設定6を1台、設定1は無し
    else:
        settings = [1, 2, 3, 4, 5]   # 設定1〜5を1台ずつ
    rng.shuffle(settings)
    return settings

# ── 設定別パラメータ ──
#   koyaku_mult : 小役払い出し倍率（高設定ほど持つ）
#   god_mult    : レア役からのGOD当選率の設定倍率（高設定ほど当たる）
#   premium_per : 聖域(SINGULARITY)単独抽選 1/n（高設定ほど引きやすい）
# 設定差は「GOD突入率(god_mult)」＋「入口ランク(entry)」だけに隠す。
# 小役払い出しは全設定common(koyaku_mult=1.0)＝引いても額でバレない。
#   奇数(1,3,5): 突入渋い／入口良い(伸びる)  = 一撃ロマン型
#   偶数(2,4,6): 突入軽い／入口控えめ(伸びにくい) = ライト回転型
#   設定6     : 当たるのに伸びる(奇偶セオリー破壊の特別台)
SLOT_SETTINGS = {
    1: {"koyaku_mult": 1.0, "god_mult": 0.90, "premium_per": 5200, "entry": "good"},
    2: {"koyaku_mult": 1.0, "god_mult": 1.12, "premium_per": 5200, "entry": "weak"},
    3: {"koyaku_mult": 1.0, "god_mult": 0.98, "premium_per": 5200, "entry": "good"},
    4: {"koyaku_mult": 1.0, "god_mult": 1.18, "premium_per": 5200, "entry": "weak"},
    5: {"koyaku_mult": 1.0, "god_mult": 1.02, "premium_per": 5000, "entry": "vgood"},
    6: {"koyaku_mult": 1.0, "god_mult": 1.16, "premium_per": 4500, "entry": "super6"},
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
# ── 設定別 入口ランク重み（プロファイル→[NOVA,FLARE,SUPERNOVA,PULSAR]）──
# soft(弱レア)を基準に、mid/strong役ほど良い入口へ補正。設定はこのプロファイルで決まる。
#   ※初当たりの高ランクスタートを抑制（全体的にNOVA寄りへ）。
#     代わりにGOD中の子役昇格を増やして「自力で上げる」設計へ移行（GOD_GAME_KOYAKU参照）。
_ENTRY_SOFT_PROFILE = {
    "weak":   [0.80, 0.16, 0.035, 0.005],  # 偶数:伸びにくい（浮き補正でさらに低く）
    "good":   [0.62, 0.27, 0.090, 0.020],  # 奇数:伸びる
    "vgood":  [0.49, 0.30, 0.160, 0.050],  # 設定5:かなり伸びる
    "super6": [0.42, 0.33, 0.180, 0.070],  # 設定6:超伸びる
}
def _build_entry_table(soft):
    # 入口補正を弱め、mid/strong契機でも上ランクへの寄せを控えめに（高ランク即スタートを抑制）
    mid    = [max(0.0, soft[0]-0.10), soft[1]+0.04, soft[2]+0.05, soft[3]+0.01]
    strong = [max(0.0, soft[0]-0.22), soft[1]+0.06, soft[2]+0.12, soft[3]+0.04]
    def norm(x):
        t=sum(x); return [v/t for v in x]
    return {"soft": norm(soft), "mid": norm(mid), "strong": norm(strong)}
# プロファイル名 → {soft/mid/strong: [4ランク重み]}
GOD_ENTRY_TABLE = {name: _build_entry_table(soft) for name, soft in _ENTRY_SOFT_PROFILE.items()}

GOD_TRIGGER_GROUP = {
    "bell": "soft", "cherry": "soft", "suika": "soft",
    "weak": "mid", "schk": "strong", "schy": "strong",
}

# ── GODランク定義 ──
GOD_ZONE_NAME = "GRAVITAS GAME"
GOD_RANKS = [   # 子役で到達できるランク（上限PULSAR）
    {"key": "nova",      "name": "NOVA",      "rate": 0.45, "emoji": "💫"},
    {"key": "flare",     "name": "FLARE",     "rate": 0.58, "emoji": "🔥"},
    {"key": "supernova", "name": "SUPERNOVA", "rate": 0.70, "emoji": "🌠"},
    {"key": "pulsar",    "name": "PULSAR",    "rate": 0.80, "emoji": "🌀"},
]
GOD_SINGULARITY = {"key": "singularity", "name": "SINGULARITY", "rate": 0.90, "emoji": "🌌"}  # 聖域

# ── GOD中 進行：1セット=10ゲーム、1ゲームずつ抽選（自力感）──
# 各ゲームで子役を1つ抽選 → 払い出し（基本＋ルート別上乗せ）＋（強い役なら）昇格抽選。
# 昇格は「1セット最大1回・1段ずつ・PULSAR上限」。10ゲーム消化後にセット継続抽選。
# モンテカルロ調整済み：入口を下げ・昇格を増やし・全体機械割を引き下げ。
#   昇格≈0.26/セット（旧0.11の約2.4倍＝自力で上げる感）。戻り率は
#   設定1≈100% / 設定6≈124%（全体的に渋く調整）。設定差はGOD内部には一切出さない。
GOD_SET_GAMES = 10            # 1セットのゲーム数
GOD_PAYOUT_SCALE = 0.688      # 戻り率の一括調整ダイヤル（継続率底上げに伴い1G払い出しを再配分）

# 1ゲーム子役（全設定・全ルート共通）: (キー, 出現率, 昇格率, 基本払い出し, 表示名, emoji)
#   昇格率は「そのゲームで昇格を試みる確率」。1セット最大1回まで反映。
#   昇格を素直に上げて「子役で自力昇格」を体感できるように（全設定共通）。
GOD_GAME_KOYAKU = [
    ("strong", 0.040, 0.55, 400, "強チェリー", "🌠"),  # 大コイン＋昇格本命（0.30→0.55）
    ("suika",  0.090, 0.18, 250, "スイカ",     "🍉"),  # 0.06→0.18
    ("cherry", 0.110, 0.08, 160, "チェリー",   "🍒"),  # 0.00→0.08（新規に昇格契機化）
    ("bell",   0.270, 0.00,  90, "ベル",       "🔔"),
    ("blank",  0.490, 0.00,   0, "──",         "　"),  # ハズレ
]

# ルート別 1ゲーム上乗せ (額, 確率) ── EVは全ルート≈69で中立、波の荒さだけ違う ──
GOD_GAME_UP_BALANCED = [(0, 0.60), (80, 0.27), (260, 0.10), (720, 0.03)]   # 中庸
GOD_GAME_UP_ORBIT    = [(45, 0.45), (70, 0.42), (150, 0.13)]              # 🛰️ 軌道: 低分散
GOD_GAME_UP_BIGBANG  = [(0, 0.80), (130, 0.12), (430, 0.06), (1380, 0.02)] # 💥 爆発: 高分散


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
# ハズレのリール目（複数バリエーション・揃い目なし＝ハズレ感）
#   効果は全て同一（ただのハズレ）。通常時/AT中の両方でランダムに選ぶ。
#   ※「揃い」は当たりに見えるので入れない。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MISS_REELS = [
    ["🌑", "⭐", "🌠"],
    ["⭐", "🌑", "🌠"],
    ["🌠", "🌑", "⭐"],
    ["🌑", "🌠", "⭐"],
    ["⭐", "🌠", "🌑"],
    ["🌠", "⭐", "🌑"],
]

# AT中の子役 → リール目（REELSのキー）。ハズレは MISS_REELS からランダムに出す。
GOD_KOYAKU_REEL = {
    "strong": "schy",    # 強チェリー → 🍒🍒🍒
    "suika":  "suika",   # スイカ     → 🍉🍉🍉
    "cherry": "cherry",  # チェリー   → 🍒🌑⭐
    "bell":   "bell",    # ベル       → 🔔🔔🔔
}

# 継続力を表す枠色（ランクが上がるほど熱く：青→橙→赤→マゼンタ→金）
GOD_RANK_COLOR = {
    "nova":        (90, 140, 230),
    "flare":       (255, 140, 30),
    "supernova":   (255, 90, 40),
    "pulsar":      (220, 40, 140),
    "singularity": (255, 205, 50),
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
    # ハズレ/リプレイからは hot/superhot をほぼ出さない＝「熱い煽り＝ほぼ当たり」に
    "blank":  {"calm": 0.880, "weak": 0.119, "hot": 0.001, "superhot": 0.000},
    "replay": {"calm": 0.620, "weak": 0.375, "hot": 0.005, "superhot": 0.000},
    "bell":   {"calm": 0.450, "weak": 0.460, "hot": 0.090, "superhot": 0.000},
    "cherry": {"calm": 0.060, "weak": 0.460, "hot": 0.400, "superhot": 0.080},
    "suika":  {"calm": 0.060, "weak": 0.460, "hot": 0.400, "superhot": 0.080},
    "weak":   {"calm": 0.000, "weak": 0.100, "hot": 0.550, "superhot": 0.350},
    "schk":   {"calm": 0.000, "weak": 0.050, "hot": 0.450, "superhot": 0.500},
    "schy":   {"calm": 0.000, "weak": 0.050, "hot": 0.450, "superhot": 0.500},
    # GOD当選時：激寄り＋☯️確定が12%
    "god":    {"calm": 0.05, "weak": 0.08, "hot": 0.30, "superhot": 0.45, "god_confirm": 0.12},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ②-A 通常GOD突入演出（5種バリエーション・ランダム）
#     (絵文字, 1行目, 2行目)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOD_ENTRY_EFFECTS = [
    ("☯️", "GRAVITAS GAME", "── 事象の地平線を、超えた。"),
    ("☯️", "──　確定。", "GRAVITAS GAME へ、ようこそ。"),
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
# 🃏 ジャグラー設定 ── ノーマル機（ボーナスのみ・GOGOランプ告知）──
#   構造: 通常時(子役で土台) → ボーナス抽選(BIG/REG) → GOGOランプ告知 → 純増付与
#   ・ATループなし。毎ゲーム独立抽選のノーマルタイプ。
#   ・設定差はボーナス確率のみ（子役は全設定共通＝ぶどうでは設定が割れない）。
#   ・告知は先告知/後告知ランダム。ペカってからBIG/REGを後出し。
#
#   ※ モンテカルロ検算済み（パッチ1.04：子役厚め＋ボーナス小型高頻度で低ボラ化）:
#       設定1:105.5% / 2:107.7% / 3:109.4% / 4:112.4% / 5:116.2% / 6:120.6%
#       子役のみ戻り 52.2%（全設定共通） / ハイパービッグ寄与 +1.6%（全設定共通）
#       → 全設定100%超え（マイナス機なし）。ボーナス頻度 1/97〜1/71 でコイン持ち改善。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JUGGLER_BET = SLOT_BET   # 60。GRAVITASと共通の経済圏

# ── 子役（全設定共通）: (キー, 出現率, 払い出し, 表示名, リール目) ──
#   ぶどうが主力。リプレイはベット返却。実機の枚数をナトコイン換算(1枚≒20)。
JUGGLER_KOYAKU = [
    ("replay",  1/7.3, 60,  "リプレイ", ("🔄", "🔄", "🔄")),
    ("budou",   1/5.2, 108, "ぶどう",   ("🍇", "🍇", "🍇")),
    ("cherry",  1/32,  40,  "チェリー", ("🍒", "　", "　")),
    ("pierrot", 1/400, 220, "ピエロ",   ("🃏", "🃏", "🃏")),
    ("bell",    1/400, 220, "ベル",     ("🔔", "🔔", "🔔")),
]

# ── ボーナス純増（ナトコイン）。BIG:REG ≒ 2.5:1（実機比準拠）──
JUGGLER_BIG_NET = 4000
JUGGLER_REG_NET = 1600
JUGGLER_HYPER_NET = 8000    # ★ハイパービッグ（プレミアフラグ）。通常BIGの約2倍

# ── ハイパービッグ出現率（全設定共通の固定プレミア。1/8192）──
#   設定差は付けない＝どの台でも夢として等しく降ってくるプレミアフラグ。
JUGGLER_HYPER_RATE = 1/8192

# ── 設定別ボーナス確率（1/n）。機械割の本体。設定6はほぼBIG=REG（実機の味）──
#   ハイパービッグは全設定共通(JUGGLER_HYPER_RATE)。設定差はBIG/REGのみで付ける。
JUGGLER_BONUS = {
    1: {"big": 1/164, "reg": 1/250, "hyper": JUGGLER_HYPER_RATE},
    2: {"big": 1/158, "reg": 1/240, "hyper": JUGGLER_HYPER_RATE},
    3: {"big": 1/152, "reg": 1/225, "hyper": JUGGLER_HYPER_RATE},
    4: {"big": 1/147, "reg": 1/206, "hyper": JUGGLER_HYPER_RATE},
    5: {"big": 1/140, "reg": 1/186, "hyper": JUGGLER_HYPER_RATE},
    6: {"big": 1/138, "reg": 1/150, "hyper": JUGGLER_HYPER_RATE},
}

# ── 先告知の割合（残りは後告知）──
JUGGLER_PREEMPTIVE_RATE = 0.5

# ── その日の各台(5台)の設定を割り当て（GRAVITASとは独立シード）──
def get_daily_jugglers(today=None):
    """ジャグラー5台の設定を日付シードで固定。GRAVITASと別シードで独立に割り当てる。
    ・末尾 1/3/7 の日 : 設定6を1台 + 設定2〜5（設定1なし）
    ・それ以外の日     : 設定1〜5を1台ずつ
    """
    import random as _r
    if today is None:
        today = jst_today()
    # GRAVITASと被らないようシードをずらす（+77）
    rng = _r.Random(int(str(today).replace("-", "")) + 77)
    if is_high_setting_day(today):
        settings = [6, 2, 3, 4, 5]
    else:
        settings = [1, 2, 3, 4, 5]
    rng.shuffle(settings)
    return settings

def get_juggler_setting(machine_no, today=None):
    return get_daily_jugglers(today)[machine_no - 1]

# ── 演出ウェイト（秒）──
JUGGLER_WAIT = {
    "spin":      1.0,   # 通常回転
    "peka":      1.6,   # GOGO!! ペカリ
    "reveal":    1.8,   # BIG/REG 開示までのタメ
    "bonus":     1.2,   # ボーナス純増の演出
}

# ── GOGOランプ告知演出（ペカリ。BIG/REGはまだ伏せる）──
JUGGLER_PEKA_PRE = [   # 先告知（回した瞬間）
    "💡　ピカッ……！？",
    "💡　ゴゴッ……来た！",
    "💡　いきなり点いた！！",
]
JUGGLER_PEKA_POST = [  # 後告知（子役のあとに点く）
    "……と思ったら　💡　ペカッ！！",
    "止めた瞬間　💡　ゴーゴー！！",
    "じわっと……　💡　点いたァ！！",
]
JUGGLER_BIG_REVEAL = [
    "🎉🎉 **BIG BONUS** 🎉🎉",
    "🔴 **BIG確定ッ！！** 🔴",
]
JUGGLER_REG_REVEAL = [
    "✨ **REGULAR BONUS** ✨",
    "🔵 **REG…！でも嬉しい** 🔵",
]
JUGGLER_HYPER_REVEAL = [  # ★ハイパービッグ（プレミア）専用の大開放
    "🌈🌈 **HYPER BIG BONUS** 🌈🌈",
    "👑 **ハイパービッグ降臨ッ！！** 👑",
    "🌌 **──プレミアフラグ、開花。** 🌌",
]
JUGGLER_MISS_LINES = [  # ハズレ時のフレーバー（点かない）
    "　── ランプは、静かなまま。",
    "　── 今回は、お預け。",
    "　── ゴーゴーならず。",
]


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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 宝の地図（ごみから稀にドロップ → 使うと運で宝発見）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TREASURE_MAP_DROP_RATE = 0.05   # ごみを釣った時、5%で「宝の地図」になる

# ── レアなゴミ（ごみの中に低確率で混ざる。売値はALL 1000コイン）──
#   宝の地図を引かなかったごみ抽選の中で、さらにこの確率でレアごみに昇格する。
#   エリア別に2種類ずつ（湖・川・海）。図鑑は各エリアの「ごみ」に並ぶ。
RARE_TRASH_RATE = 0.03   # ごみのうち約3%がレアごみに
RARE_TRASH_BY_AREA = {
    "lake":  [
        {"name": "古銭の束",            "value": 1000, "emoji": "🪙"},
        {"name": "アンティークのカギ",   "value": 1000, "emoji": "🗝️"},
    ],
    "river": [
        {"name": "油まみれの高級腕時計", "value": 1000, "emoji": "⌚"},
        {"name": "金歯",                "value": 1000, "emoji": "🦷"},
    ],
    "sea":   [
        {"name": "防水ケース入りスマホ", "value": 1000, "emoji": "📱"},
        {"name": "片方だけのダイヤピアス","value": 1000, "emoji": "💎"},
    ],
}

# 宝の地図を使った時の抽選（rank, 確率, (最小, 最大)報酬）
TREASURE_OUTCOMES = [
    ("miss",    0.509, (0, 0)),
    ("small",   0.400, (100, 300)),
    ("big",     0.090, (1000, 3000)),
    ("jackpot", 0.001, (10000, 10000)),
]

# エリア別・ランク別の宝（図鑑用の名前＆絵文字）。miss は宝なし。
# 宝は「最後に釣っていたエリア」の種類から出る。
TREASURE_BY_AREA = {
    "lake": {
        "small":   [{"name":"古い銅貨","emoji":"🪙"},{"name":"苔むした指輪","emoji":"💍"},{"name":"小さな鍵","emoji":"🗝️"}],
        "big":     [{"name":"銀の燭台","emoji":"🕯️"},{"name":"沈んだ宝石","emoji":"💎"},{"name":"古代の壺","emoji":"🏺"}],
        "jackpot": [{"name":"湖底の黄金像","emoji":"🗿"}],
    },
    "river": {
        "small":   [{"name":"砂金","emoji":"✨"},{"name":"川底の古銭","emoji":"🪙"},{"name":"真鍮の懐中時計","emoji":"⏱️"}],
        "big":     [{"name":"金塊","emoji":"🟡"},{"name":"ルビーの原石","emoji":"❤️"},{"name":"武将の刀","emoji":"⚔️"}],
        "jackpot": [{"name":"幻の砂金脈","emoji":"🌟"}],
    },
    "sea": {
        "small":   [{"name":"海賊の銀貨","emoji":"🪙"},{"name":"真珠","emoji":"⚪"},{"name":"古いコンパス","emoji":"🧭"}],
        "big":     [{"name":"金貨の詰まった袋","emoji":"💰"},{"name":"サンゴの宝冠","emoji":"👑"},{"name":"沈没船の財宝","emoji":"⚓"}],
        "jackpot": [{"name":"ポセイドンの黄金","emoji":"🔱"}],
    },
}

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
FISHING_SHADOW_WAIT = 3.0   # SR以上：プレミア影を見せてからカード開示までの溜め

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
#   レア以上計: 竹4.8% / グラス8.5% / カーボン11.5% / チタン16% / 伝説22%
#   竹SR0.5%・レジェ0.3%／グラスSR1%・レジェ0.5%（スターター竿でも夢あり。上位は据え置き）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FISHING_RARITY = {
    "bamboo":   {"trash":0.325, "common":0.407,  "uncommon":0.220, "rare":0.040, "super_rare":0.005, "legend":0.003},
    "glass":    {"trash":0.280, "common":0.385,  "uncommon":0.250, "rare":0.070, "super_rare":0.010, "legend":0.005},
    "carbon":   {"trash":0.260, "common":0.3675, "uncommon":0.260, "rare":0.100, "super_rare":0.010, "legend":0.0025},
    "titanium": {"trash":0.230, "common":0.345,  "uncommon":0.270, "rare":0.130, "super_rare":0.020, "legend":0.005},
    "legend":   {"trash":0.200, "common":0.320,  "uncommon":0.270, "rare":0.170, "super_rare":0.030, "legend":0.010},
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
    # "uses" = 竿の耐久性（耐久ポイント）。消費は竿×エリアで変わる（ROD_AREA_DURABILITY）。
    # "home"  = その竿が得意なエリア（消耗が軽く、しっかり稼げる）。それ以外は消耗が増えて収支トントン。
    "bamboo":   {"name":"竹竿",          "price":0,       "uses":999999, "emoji":"🎋",
                 "home":"lake",  "sea_ban":True, "river_ban":True},
    "glass":    {"name":"グラスロッド",   "price":2000,    "uses":550,    "emoji":"🎣",
                 "home":"river", "sea_ban":True},
    "carbon":   {"name":"カーボンロッド", "price":8000,    "uses":250,    "emoji":"🎣",
                 "home":"river", "sea_ban":False},
    "titanium": {"name":"チタンロッド",   "price":30000,   "uses":350,    "emoji":"🎣",
                 "home":"sea",   "sea_ban":False},
    "legend":   {"name":"伝説の釣り竿",   "price":100000,  "uses":380,    "emoji":"🎣",
                 "home":"sea",   "sea_ban":False},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 竿の耐久消費量（竿 × エリア）── 実質ROI（竿の消耗込み）の制御ダイヤル ──
#   得意エリア(home)は消耗が軽く稼げる／それ以外は消耗が増えて収支トントン(~100%)。
#   換金額もレア出率も触らず、消耗だけで実質ROIを作る。小数可（耐久プールから小数で引く）。
#   モンテカルロ検算済みの本領ROI: 竹湖206 / グラス川126 / カーボン川112 / チタン海115 / 伝説海110。
#   伝説は完全に海用。湖・川でもレジェンド魚は釣れるが収支はトントン(=得しない)。
ROD_AREA_DURABILITY = {
    "bamboo":   {"lake": 1.0},
    "glass":    {"lake": 0.8, "river": 0.1},
    "carbon":   {"lake": 0.94, "river": 1.38, "sea": 3.25},
    "titanium": {"lake": 0.59, "river": 1.24, "sea": 2.11},
    "legend":   {"lake": 0.32, "river": 0.69, "sea": 1.3},
}
# 旧キー互換（未定義の竿/エリアのフォールバック）
ROD_DURABILITY_COST = {"lake": 1, "river": 2, "sea": 3}

def get_rod_dura_cost(rod_id, area):
    """竿×エリアの耐久消費量を返す（未定義はエリア基準にフォールバック）。"""
    return ROD_AREA_DURABILITY.get(rod_id, {}).get(area, ROD_DURABILITY_COST.get(area, 1))

# 各竿が「しっかり稼げる」エリア（収支110%前後以上）。ここ以外は収支トントンで警告を出す。
# グラスは安くて丈夫なので湖・川どちらも得意。海3竿は本領エリアのみ。
ROD_GOOD_AREAS = {
    "bamboo":   {"lake"},
    "glass":    {"lake", "river"},
    "carbon":   {"river"},
    "titanium": {"sea"},
    "legend":   {"sea"},
}

def rod_warns_here(rod_id, area):
    """その竿でそのエリアに行くと『得しない（収支トントン）』なら True。"""
    good = ROD_GOOD_AREAS.get(rod_id)
    if good is None:
        return False
    return area not in good

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

# ====== 魚リスト（common/uncommon を半分に間引き済み。rare/SR/Lは不変）======
LAKE_FISH = [
    # --- trash ---
    {"name":"長靴", "rarity":"trash", "value":0, "emoji":"👟"},
    {"name":"空き缶", "rarity":"trash", "value":0, "emoji":"🥫"},
    {"name":"ペットボトル", "rarity":"trash", "value":0, "emoji":"🍶"},
    {"name":"タイヤ", "rarity":"trash", "value":0, "emoji":"⭕"},
    {"name":"傘", "rarity":"trash", "value":0, "emoji":"☂️"},
    {"name":"ビニール袋", "rarity":"trash", "value":0, "emoji":"🛍️"},
    {"name":"割れた瓶", "rarity":"trash", "value":0, "emoji":"🍾"},
    {"name":"古い帽子", "rarity":"trash", "value":0, "emoji":"🎩"},
    # --- common ---
    {"name":"メダカ", "rarity":"common", "value":2, "emoji":"🐟"},
    {"name":"ヌカエビ", "rarity":"common", "value":3, "emoji":"🦐"},
    {"name":"ヒメダカ", "rarity":"common", "value":4, "emoji":"🐟"},
    {"name":"ウキゴリ", "rarity":"common", "value":5, "emoji":"🐟"},
    {"name":"タモロコ", "rarity":"common", "value":5, "emoji":"🐟"},
    {"name":"タナゴ", "rarity":"common", "value":6, "emoji":"🐟"},
    {"name":"ドジョウ", "rarity":"common", "value":7, "emoji":"🐍"},
    {"name":"カワムツ", "rarity":"common", "value":8, "emoji":"🐟"},
    {"name":"フナ", "rarity":"common", "value":9, "emoji":"🐟"},
    {"name":"コイ", "rarity":"common", "value":12, "emoji":"🐠"},
    {"name":"ザリガニ", "rarity":"common", "value":15, "emoji":"🦞"},
    # --- uncommon ---
    {"name":"アメリカザリガニ", "rarity":"uncommon", "value":5, "emoji":"🦞"},
    {"name":"ニゴイ", "rarity":"uncommon", "value":8, "emoji":"🐟"},
    {"name":"コクチバス", "rarity":"uncommon", "value":10, "emoji":"🐟"},
    {"name":"バス", "rarity":"uncommon", "value":13, "emoji":"🐟"},
    {"name":"ハス", "rarity":"uncommon", "value":15, "emoji":"🐟"},
    {"name":"ヤマメ", "rarity":"uncommon", "value":18, "emoji":"🐟"},
    {"name":"ナマズ", "rarity":"uncommon", "value":22, "emoji":"🐡"},
    {"name":"アメマス", "rarity":"uncommon", "value":25, "emoji":"🐟"},
    {"name":"ビワマス", "rarity":"uncommon", "value":30, "emoji":"🐟"},
    {"name":"ウナギ", "rarity":"uncommon", "value":38, "emoji":"🐍"},
    # --- rare ---
    {"name":"タイワンドジョウ", "rarity":"rare", "value":20, "emoji":"🐍"},
    {"name":"ソウギョ", "rarity":"rare", "value":25, "emoji":"🐟"},
    {"name":"ハクレン", "rarity":"rare", "value":28, "emoji":"🐟"},
    {"name":"アオウオ", "rarity":"rare", "value":30, "emoji":"🐟"},
    {"name":"コウライケツギョ", "rarity":"rare", "value":35, "emoji":"🐟"},
    {"name":"チョウザメ", "rarity":"rare", "value":45, "emoji":"🐟"},
    {"name":"スッポンモドキ", "rarity":"rare", "value":55, "emoji":"🐢"},
    {"name":"イトウ", "rarity":"rare", "value":70, "emoji":"🐟"},
    {"name":"オオサンショウウオ", "rarity":"rare", "value":90, "emoji":"🦎"},
    {"name":"ピラルク", "rarity":"rare", "value":120, "emoji":"🐟"},
    # --- super_rare ---
    {"name":"ダントウボウ", "rarity":"super_rare", "value":200, "emoji":"🐟"},
    {"name":"アロワナ", "rarity":"super_rare", "value":300, "emoji":"🐉"},
    {"name":"ビワコオオナマズ", "rarity":"super_rare", "value":450, "emoji":"🐡"},
    {"name":"オオウナギ", "rarity":"super_rare", "value":600, "emoji":"🐍"},
    {"name":"アカメ", "rarity":"super_rare", "value":950, "emoji":"🐟"},
    # --- legend ---
    {"name":"幻のイトウ", "rarity":"legend", "value":3000, "emoji":"👑"},
    {"name":"ガーパイク", "rarity":"legend", "value":5000, "emoji":"🐉"},
    {"name":"黄金のコイ", "rarity":"legend", "value":8000, "emoji":"✨"},
]

RIVER_FISH = [
    # --- trash ---
    {"name":"長靴", "rarity":"trash", "value":0, "emoji":"👟"},
    {"name":"空き缶", "rarity":"trash", "value":0, "emoji":"🥫"},
    {"name":"流木", "rarity":"trash", "value":0, "emoji":"🪵"},
    {"name":"古い釣り竿", "rarity":"trash", "value":0, "emoji":"🎣"},
    {"name":"錆びたナイフ", "rarity":"trash", "value":0, "emoji":"🔪"},
    {"name":"ペットボトル", "rarity":"trash", "value":0, "emoji":"🍶"},
    {"name":"タイヤ", "rarity":"trash", "value":0, "emoji":"⭕"},
    {"name":"ビニール袋", "rarity":"trash", "value":0, "emoji":"🛍️"},
    # --- common ---
    {"name":"カワバタモロコ", "rarity":"common", "value":10, "emoji":"🐟"},
    {"name":"アカザ", "rarity":"common", "value":16, "emoji":"🐟"},
    {"name":"シマドジョウ", "rarity":"common", "value":20, "emoji":"🐟"},
    {"name":"ズナガニゴイ", "rarity":"common", "value":24, "emoji":"🐟"},
    {"name":"タカハヤ", "rarity":"common", "value":26, "emoji":"🐟"},
    {"name":"カワヤツメ", "rarity":"common", "value":28, "emoji":"🐟"},
    {"name":"アカヒレタビラ", "rarity":"common", "value":30, "emoji":"🐟"},
    {"name":"イチモンジタナゴ", "rarity":"common", "value":34, "emoji":"🐟"},
    {"name":"カネヒラ", "rarity":"common", "value":37, "emoji":"🐟"},
    {"name":"カジカ", "rarity":"common", "value":45, "emoji":"🐟"},
    # --- uncommon ---
    {"name":"オヤニラミ", "rarity":"uncommon", "value":30, "emoji":"🐟"},
    {"name":"ギギ", "rarity":"uncommon", "value":40, "emoji":"🐟"},
    {"name":"ライギョ", "rarity":"uncommon", "value":55, "emoji":"🐍"},
    {"name":"チョウザメ幼魚", "rarity":"uncommon", "value":65, "emoji":"🐟"},
    {"name":"ニジマス", "rarity":"uncommon", "value":75, "emoji":"🐟"},
    {"name":"アメマス", "rarity":"uncommon", "value":85, "emoji":"🐟"},
    {"name":"ヤマメ", "rarity":"uncommon", "value":88, "emoji":"🐟"},
    {"name":"アユ", "rarity":"uncommon", "value":92, "emoji":"🐟"},
    {"name":"スズキ", "rarity":"uncommon", "value":110, "emoji":"🐟"},
    {"name":"サクラマス", "rarity":"uncommon", "value":130, "emoji":"🐟"},
    # --- rare ---
    {"name":"アリゲーターガー幼魚", "rarity":"rare", "value":80, "emoji":"🐊"},
    {"name":"ブラウントラウト", "rarity":"rare", "value":100, "emoji":"🐟"},
    {"name":"カラフトマス", "rarity":"rare", "value":120, "emoji":"🐟"},
    {"name":"サツキマス", "rarity":"rare", "value":150, "emoji":"🐟"},
    {"name":"シロザケ", "rarity":"rare", "value":180, "emoji":"🐟"},
    {"name":"オオウナギ", "rarity":"rare", "value":200, "emoji":"🐍"},
    {"name":"タイメン幼魚", "rarity":"rare", "value":250, "emoji":"🐟"},
    {"name":"イトウ", "rarity":"rare", "value":300, "emoji":"🐟"},
    {"name":"コロンビアチョウザメ", "rarity":"rare", "value":350, "emoji":"🐟"},
    {"name":"ゴールデントラウト", "rarity":"rare", "value":470, "emoji":"✨"},
    # --- super_rare ---
    {"name":"ビワコオオナマズ", "rarity":"super_rare", "value":700, "emoji":"🐡"},
    {"name":"ベルーガ幼魚", "rarity":"super_rare", "value":900, "emoji":"🐟"},
    {"name":"タイメン", "rarity":"super_rare", "value":1200, "emoji":"🐟"},
    {"name":"アカメ", "rarity":"super_rare", "value":1800, "emoji":"🐟"},
    {"name":"オオカワウソ", "rarity":"super_rare", "value":2400, "emoji":"🦦"},
    # --- legend ---
    {"name":"ゴライアスタイガーフィッシュ", "rarity":"legend", "value":7500, "emoji":"😱"},
    {"name":"ベルーガ", "rarity":"legend", "value":11000, "emoji":"👑"},
    {"name":"ブルシャーク", "rarity":"legend", "value":15000, "emoji":"🦈"},
]

SEA_FISH = [
    # --- trash ---
    {"name":"長靴", "rarity":"trash", "value":0, "emoji":"👟"},
    {"name":"空き缶", "rarity":"trash", "value":0, "emoji":"🥫"},
    {"name":"古い錨", "rarity":"trash", "value":0, "emoji":"⚓"},
    {"name":"謎の瓶", "rarity":"trash", "value":30, "emoji":"🍾"},
    {"name":"ボロボロの紙くず", "rarity":"trash", "value":30, "emoji":"📄"},
    {"name":"錆びた缶詰", "rarity":"trash", "value":0, "emoji":"🥫"},
    {"name":"ともせの眼鏡", "rarity":"trash", "value":0, "emoji":"👓"},
    {"name":"ビニール袋", "rarity":"trash", "value":0, "emoji":"🛍️"},
    # --- common ---
    {"name":"カタクチイワシ", "rarity":"common", "value":30, "emoji":"🐟"},
    {"name":"イワシ", "rarity":"common", "value":40, "emoji":"🐟"},
    {"name":"キス", "rarity":"common", "value":50, "emoji":"🐟"},
    {"name":"アジ", "rarity":"common", "value":55, "emoji":"🐟"},
    {"name":"サバ", "rarity":"common", "value":62, "emoji":"🐟"},
    {"name":"サンマ", "rarity":"common", "value":68, "emoji":"🐟"},
    {"name":"タケノコメバル", "rarity":"common", "value":75, "emoji":"🐟"},
    {"name":"メバル", "rarity":"common", "value":82, "emoji":"🐟"},
    {"name":"カサゴ", "rarity":"common", "value":88, "emoji":"🐡"},
    {"name":"クロダイ", "rarity":"common", "value":95, "emoji":"🐟"},
    # --- uncommon ---
    {"name":"イカ", "rarity":"uncommon", "value":80, "emoji":"🦑"},
    {"name":"タコ", "rarity":"uncommon", "value":100, "emoji":"🐙"},
    {"name":"アイナメ", "rarity":"uncommon", "value":120, "emoji":"🐟"},
    {"name":"サワラ", "rarity":"uncommon", "value":140, "emoji":"🐟"},
    {"name":"マゴチ", "rarity":"uncommon", "value":160, "emoji":"🐟"},
    {"name":"ヒラメ", "rarity":"uncommon", "value":180, "emoji":"🐟"},
    {"name":"マダイ", "rarity":"uncommon", "value":200, "emoji":"🐟"},
    {"name":"オニオコゼ", "rarity":"uncommon", "value":220, "emoji":"🐡"},
    {"name":"イシダイ", "rarity":"uncommon", "value":240, "emoji":"🐟"},
    {"name":"ブリ", "rarity":"uncommon", "value":300, "emoji":"🐟"},
    # --- rare ---
    {"name":"クロシビカマス", "rarity":"rare", "value":200, "emoji":"🐟"},
    {"name":"アブラソコムツ", "rarity":"rare", "value":240, "emoji":"🐟"},
    {"name":"オオニベ", "rarity":"rare", "value":280, "emoji":"🐟"},
    {"name":"バラムツ", "rarity":"rare", "value":300, "emoji":"🐟"},
    {"name":"アカムツ", "rarity":"rare", "value":350, "emoji":"🐟"},
    {"name":"キンメダイ", "rarity":"rare", "value":380, "emoji":"🐟"},
    {"name":"イシナギ", "rarity":"rare", "value":420, "emoji":"🐟"},
    {"name":"ヨシキリザメ", "rarity":"rare", "value":480, "emoji":"🦈"},
    {"name":"クロマグロ", "rarity":"rare", "value":550, "emoji":"🐟"},
    {"name":"カジキ", "rarity":"rare", "value":750, "emoji":"🐟"},
    # --- super_rare ---
    {"name":"チョウチンアンコウ", "rarity":"super_rare", "value":1500, "emoji":"🎣"},
    {"name":"タカアシガニ", "rarity":"super_rare", "value":2000, "emoji":"🦀"},
    {"name":"リュウグウノツカイ", "rarity":"super_rare", "value":2500, "emoji":"🐉"},
    {"name":"ダイオウイカ", "rarity":"super_rare", "value":4000, "emoji":"🦑"},
    {"name":"メガマウスザメ", "rarity":"super_rare", "value":5000, "emoji":"🦈"},
    # --- legend ---
    {"name":"ホホジロザメ", "rarity":"legend", "value":15000, "emoji":"🦈"},
    {"name":"シーラカンス", "rarity":"legend", "value":22500, "emoji":"👑"},
    {"name":"ラブカ", "rarity":"legend", "value":30000, "emoji":"😱"},
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎊 大勝利アナウンス（BOT告知）
#   1回の勝ち額がこの値以上になったら、プレイ中のチャンネルにBOTが告知する。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BIG_WIN_ANNOUNCE = 10000

# 大勝利アナウンスを出す固定チャンネルID。
#   0 にすると「ゲームを遊んだチャンネル」にそのまま出す（従来動作）。
BIG_WIN_ANNOUNCE_CHANNEL_ID = 1519413046039019712

# ── 賭け金の下限・上限（所持金以上は賭けられない）──
CHINCHIRO_MIN_BET = 10
CHINCHIRO_MAX_BET = 1000

# ── 役の倍率（チンチロ共通）。勝者の役で配当倍率が決まる ──
#   ヒフミは「負けた側が払う」ペナルティ役（出ても勝てず、敗者なら2倍払い）。
#   目なしは決着役にならない（振り直し対象）。
CHINCHIRO_MULT = {
    "pinzoro": 5,   # 👑 ピンゾロ（1・1・1）
    "zorome":  3,   # 🎲 ゾロ目（同じ目3つ）
    "shigoro": 2,   # 🔥 シゴロ（4・5・6）
    "me":      1,   # 🎯 目（ペア＋出目）
    "hifumi":  2,   # 💀 ヒフミ（1・2・3）= 負けたら2倍払い
    "menashi": 1,   # ❓ 目なし
}


# 釣り演出（当たり待ち）の共通色。
# レアリティ別の色だと結果が出る前にレア度が分かってしまうため、
# 当たり待ち中は必ずこの中立色を使う（結果表示はレアリティ色のまま）。
SUSPENSE_COLOR = 0x2B2D31


# ============================================================
# 天候・限定魚システム（weather.py エンジンと対で使う）
# 既存の釣り出率は不変。限定魚は通常プールにスワップ注入される。
# ============================================================
# 限定天候中、1キャストが「限定魚」になる確率。残りは通常魚（＝通常魚も出つつ限定魚も混ざる）。
# 0.0で限定魚なし／1.0で従来挙動(限定魚で上書き)。
LIMITED_FISH_RATE = 0.30

LIMITED_FISH = {
  "lake": {
    "rain": [{"name":"アメフラシモロコ","rarity":"common","value":18,"emoji":"🐠"}, {"name":"シズクナマズ","rarity":"uncommon","value":46,"emoji":"🐟"}, {"name":"レインボートラウト","rarity":"rare","value":144,"emoji":"🎣"}, {"name":"アマゴイウナギ","rarity":"super_rare","value":1140,"emoji":"🌟"}, {"name":"龍雨","rarity":"legend","value":9600,"emoji":"🐉"}],
    "fog": [{"name":"カスミウキゴリ","rarity":"common","value":16,"emoji":"🐠"}, {"name":"ミストパイク","rarity":"uncommon","value":42,"emoji":"🐟"}, {"name":"朧月魚","rarity":"rare","value":132,"emoji":"🎣"}, {"name":"キリノヌシゴイ","rarity":"super_rare","value":1045,"emoji":"🌟"}, {"name":"霧隠","rarity":"legend","value":8800,"emoji":"🐉"}],
    "glow": [{"name":"アサヤケタナゴ","rarity":"common","value":16,"emoji":"🐠"}, {"name":"ユウヤケブナ","rarity":"uncommon","value":42,"emoji":"🐟"}, {"name":"茜雲魚","rarity":"rare","value":132,"emoji":"🎣"}, {"name":"コハクマス","rarity":"super_rare","value":1045,"emoji":"🌟"}, {"name":"黄金黎明","rarity":"legend","value":8800,"emoji":"🐉"}],
    "storm": [{"name":"アラシゴリ","rarity":"common","value":22,"emoji":"🐠"}, {"name":"カミナリナマズ","rarity":"uncommon","value":57,"emoji":"🐟"}, {"name":"雷紋魚","rarity":"rare","value":180,"emoji":"🎣"}, {"name":"ストームパイク","rarity":"super_rare","value":1425,"emoji":"🌟"}, {"name":"嵐龍","rarity":"legend","value":12000,"emoji":"🐉"}],
    "blood_moon": [{"name":"アカツキメダカ","rarity":"common","value":22,"emoji":"🐠"}, {"name":"紅鱗魚","rarity":"uncommon","value":57,"emoji":"🐟"}, {"name":"月喰い","rarity":"rare","value":180,"emoji":"🎣"}, {"name":"ブラッドギル","rarity":"super_rare","value":1425,"emoji":"🌟"}, {"name":"緋月龍","rarity":"legend","value":12000,"emoji":"🐉"}],
  },
  "river": {
    "rain": [{"name":"アメウグイ","rarity":"common","value":54,"emoji":"🐠"}, {"name":"デッポウアマゴ","rarity":"uncommon","value":156,"emoji":"🐟"}, {"name":"レインサーモン","rarity":"rare","value":564,"emoji":"🎣"}, {"name":"雨乞鯰","rarity":"super_rare","value":2880,"emoji":"🌟"}, {"name":"水神","rarity":"legend","value":18000,"emoji":"🐉"}],
    "fog": [{"name":"キリハヤ","rarity":"common","value":50,"emoji":"🐠"}, {"name":"ガスマスキー","rarity":"uncommon","value":143,"emoji":"🐟"}, {"name":"霞鱒","rarity":"rare","value":517,"emoji":"🎣"}, {"name":"ファントムイトウ","rarity":"super_rare","value":2640,"emoji":"🌟"}, {"name":"川霧の主","rarity":"legend","value":16500,"emoji":"🐉"}],
    "glow": [{"name":"アサセタカハヤ","rarity":"common","value":50,"emoji":"🐠"}, {"name":"ユウバエヤマメ","rarity":"uncommon","value":143,"emoji":"🐟"}, {"name":"紅染岩魚","rarity":"rare","value":517,"emoji":"🎣"}, {"name":"サンセットサーモン","rarity":"super_rare","value":2640,"emoji":"🌟"}, {"name":"暁光鱒","rarity":"legend","value":16500,"emoji":"🐉"}],
    "storm": [{"name":"テッポウハヤ","rarity":"common","value":68,"emoji":"🐠"}, {"name":"ライデンギギ","rarity":"uncommon","value":195,"emoji":"🐟"}, {"name":"濁流岩魚","rarity":"rare","value":705,"emoji":"🎣"}, {"name":"サンダーマスキー","rarity":"super_rare","value":3600,"emoji":"🌟"}, {"name":"荒瀬龍","rarity":"legend","value":22500,"emoji":"🐉"}],
    "blood_moon": [{"name":"アカツキモロコ","rarity":"common","value":68,"emoji":"🐠"}, {"name":"血染山女","rarity":"uncommon","value":195,"emoji":"🐟"}, {"name":"紅淵魚","rarity":"rare","value":705,"emoji":"🎣"}, {"name":"クリムゾンイトウ","rarity":"super_rare","value":3600,"emoji":"🌟"}, {"name":"緋淵の主","rarity":"legend","value":22500,"emoji":"🐉"}],
  },
  "sea": {
    "rain": [{"name":"アメフリイワシ","rarity":"common","value":114,"emoji":"🐠"}, {"name":"シズクダコ","rarity":"uncommon","value":360,"emoji":"🐟"}, {"name":"レインボーシイラ","rarity":"rare","value":900,"emoji":"🎣"}, {"name":"アマグモエイ","rarity":"super_rare","value":6000,"emoji":"🌟"}, {"name":"海雨竜","rarity":"legend","value":36000,"emoji":"🐉"}],
    "fog": [{"name":"カスミアジ","rarity":"common","value":105,"emoji":"🐠"}, {"name":"ミストカサゴ","rarity":"uncommon","value":330,"emoji":"🐟"}, {"name":"朧鯛","rarity":"rare","value":825,"emoji":"🎣"}, {"name":"ファントムハタ","rarity":"super_rare","value":5500,"emoji":"🌟"}, {"name":"海霧の主","rarity":"legend","value":33000,"emoji":"🐉"}],
    "glow": [{"name":"アサヤケアジ","rarity":"common","value":105,"emoji":"🐠"}, {"name":"ユウヤケダイ","rarity":"uncommon","value":330,"emoji":"🐟"}, {"name":"茜縞鯛","rarity":"rare","value":825,"emoji":"🎣"}, {"name":"サンセットマグロ","rarity":"super_rare","value":5500,"emoji":"🌟"}, {"name":"黄昏鯨魚","rarity":"legend","value":33000,"emoji":"🐉"}],
    "storm": [{"name":"アラシアジ","rarity":"common","value":142,"emoji":"🐠"}, {"name":"カミナリイカ","rarity":"uncommon","value":450,"emoji":"🐟"}, {"name":"雷紋鯛","rarity":"rare","value":1125,"emoji":"🎣"}, {"name":"ストームシャーク","rarity":"super_rare","value":7500,"emoji":"🌟"}, {"name":"海嵐竜","rarity":"legend","value":45000,"emoji":"🐉"}],
    "blood_moon": [{"name":"アカツキイワシ","rarity":"common","value":142,"emoji":"🐠"}, {"name":"紅墨烏賊","rarity":"uncommon","value":450,"emoji":"🐟"}, {"name":"月喰鮟鱇","rarity":"rare","value":1125,"emoji":"🎣"}, {"name":"ブラッドレイ","rarity":"super_rare","value":7500,"emoji":"🌟"}, {"name":"緋海竜","rarity":"legend","value":45000,"emoji":"🐉"}],
  },
}

# 嵐の宝箱（中身はコイン化＋お宝図鑑 storm_treasure に登録）
STORM_CHEST_RATE = 0.05
STORM_TREASURES = [
    {"name":"濡れた小銭袋","rarity":"並","min":800,"max":1500,"weight":40,"emoji":"💰","desc":"波に流れ着いた小銭の入った革袋。湿っている"},
    {"name":"古い金貨","rarity":"並","min":1500,"max":2800,"weight":30,"emoji":"🪙","desc":"苔むした沈没船から零れた一枚。刻印は読めない"},
    {"name":"沈没船の宝石","rarity":"レア","min":2800,"max":5000,"weight":19,"emoji":"💎","desc":"嵐で砕けた船倉から流れ出た原石。鈍く光る"},
    {"name":"海賊の金塊","rarity":"レア","min":5000,"max":8000,"weight":8,"emoji":"🥇","desc":"どこぞの海賊が隠した延べ棒。ずっしり重い"},
    {"name":"伝説の財宝","rarity":"激レア","min":10000,"max":14000,"weight":3,"emoji":"🏆","desc":"嵐の夜にのみ浮上すると伝わる財宝箱。本物だ"},
]

# 赤月主（赤い月の夜のみ各エリアの主とスワップ）
BLOOD_MOON_BOSS = {
  "lake": {"name":"緋眼の主","emoji":"👁️","value":120000,"success_mult":1.0,"desc":"赤い月の夜、湖底から緋色の眼だけが浮かび上がる。古老が見るなと戒めた湖の主。"},
  "river": {"name":"紅鱗の蛇神","emoji":"🐍","value":180000,"success_mult":1.0,"desc":"赤月に照らされた渓流を遡る、血色の鱗を持つ大蛇のごとき魚。捕えた者は富を得ると伝わる。"},
  "sea": {"name":"緋海の古王","emoji":"👑","value":300000,"success_mult":0.6,"desc":"赤い月が満ちる夜、深海より浮上する太古の王。その姿を見た船乗りは二度と戻らぬという。"},
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 解放ファンド（コミュニティ募金で次コンテンツ解放）
#   みんなで貯めて目標額に到達するとサーバー全体で解放される。
#   将来このリストに項目を足せば段階解放できる（順序は dict 順）。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FUND_GOALS = {
    "danger_zone": {
        "name": "⚓ さびれた港 再興",
        "goal": 2_000_000,
        "emoji": "⚓",
        "desc": ("遥か先の二つの海への **遠征港** を取り戻す大計画。\n"
                 "船を仕立て、未知の海へ漕ぎ出そう。"),
        "unlock_title": "🌊⚓ さびれた港、再興ッ！！",
        "unlock_msg": ("サーバーの総力で **さびれた港** がよみがえった！\n"
                       "🧊 氷獄海・🔥 煉獄海への遠征が、ついに可能に…！"),
    },
}
