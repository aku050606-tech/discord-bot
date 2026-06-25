# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# デイリークエスト — 進捗トラッキング（純粋ロジック層・discord 非依存）
#   ・固定クエスト（毎日必ず出る／各500）: チャット・VC
#   ・ランダムクエスト（プールから毎日3個／各1000）: 日付シードで全員共通・0時JSTで再抽選
#   ・進捗は record() を各ゲーム側から呼んで加算。受取はクエスト画面のボタンで一括。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import random
from datetime import date
from database import Database

db = Database()

# ── 固定クエスト（毎日必ず出る・各500ナトコイン）──
FIXED_QUESTS = [
    {"key": "chat", "emoji": "💬", "name": "おしゃべり", "desc": "どこかにチャットを打つ",
     "event": "chat", "target": 1, "reward": 500},
    {"key": "vc",   "emoji": "🎙️", "name": "ボイス参加", "desc": "VCに5分参加する",
     "event": "vc",   "target": 1, "reward": 500},
]

# ── ランダムプール（毎日3個抽選・各1000ナトコイン）──
POOL_QUESTS = [
    {"key": "fish",      "emoji": "🎣", "name": "釣り師",     "desc": "釣りを30回する",
     "event": "fish",      "target": 30, "reward": 1000},
    {"key": "slot",      "emoji": "🎰", "name": "スロッター", "desc": "スロットを30回回す",
     "event": "slot",      "target": 30, "reward": 1000},
    {"key": "casino",    "emoji": "🃏", "name": "カジノ通い", "desc": "カジノを10回プレイする",
     "event": "casino",    "target": 10, "reward": 1000},
    {"key": "chinchiro", "emoji": "🎲", "name": "チンチロ師", "desc": "チンチロを5回遊ぶ",
     "event": "chinchiro", "target": 5,  "reward": 1000},
    {"key": "shop",      "emoji": "🛒", "name": "買い出し",   "desc": "釣具屋で何か1回買う",
     "event": "shop",      "target": 1,  "reward": 1000},
    {"key": "send",      "emoji": "💸", "name": "気前よく",   "desc": "誰かにコインを送る",
     "event": "send",      "target": 1,  "reward": 1000},
]

DAILY_RANDOM_COUNT = 3   # ランダムプールから毎日選ぶ数


def _today() -> str:
    return str(date.today())


def get_daily_pool_keys(today: str = None):
    """その日のランダムクエスト3個を日付シードで固定（全員共通・0時JSTで再抽選）。"""
    if today is None:
        today = _today()
    # 他の日替わり（台/ジャグラー）とシードが被らないようずらす
    rng = random.Random(int(today.replace("-", "")) + 4649)
    keys = [q["key"] for q in POOL_QUESTS]
    rng.shuffle(keys)
    return keys[:DAILY_RANDOM_COUNT]


def get_today_quests(today: str = None):
    """今日のクエスト定義一覧（固定2 + ランダム3）を返す。"""
    if today is None:
        today = _today()
    pool_keys = set(get_daily_pool_keys(today))
    randoms = [q for q in POOL_QUESTS if q["key"] in pool_keys]
    return FIXED_QUESTS + randoms


def _active_quests_for_event(event: str, today: str = None):
    return [q for q in get_today_quests(today) if q["event"] == event]


def record(user_id, guild_id, event: str, n: int = 1):
    """各ゲーム側から呼ぶ進捗加算フック。今日アクティブなクエストにだけ加算する。
    クエスト記録の失敗がゲーム本体を止めないよう、例外は握り潰す。"""
    try:
        today = _today()
        for q in _active_quests_for_event(event, today):
            db.add_quest_progress(str(user_id), str(guild_id), today, q["key"], n, q["target"])
    except Exception:
        pass


def get_status(user_id, guild_id, today: str = None):
    """画面表示用：今日の各クエストの状態リストを返す。
    各要素 = {q, progress, claimed, completed}"""
    if today is None:
        today = _today()
    prog = db.get_quest_progress(str(user_id), str(guild_id), today)  # {key: (progress, claimed)}
    out = []
    for q in get_today_quests(today):
        p, claimed = prog.get(q["key"], (0, 0))
        p = min(p, q["target"])
        out.append({
            "q": q,
            "progress": p,
            "claimed": bool(claimed),
            "completed": p >= q["target"],
        })
    return out


def claim_all(user_id, guild_id, today: str = None):
    """達成済み・未受取のクエストを一括受取。(付与合計, 受取クエスト表示名リスト) を返す。"""
    if today is None:
        today = _today()
    total = 0
    claimed_names = []
    for s in get_status(user_id, guild_id, today):
        if s["completed"] and not s["claimed"]:
            db.set_quest_claimed(str(user_id), str(guild_id), today, s["q"]["key"])
            db.update_balance(str(user_id), str(guild_id), s["q"]["reward"])
            total += s["q"]["reward"]
            claimed_names.append(f"{s['q']['emoji']} {s['q']['name']}（+{s['q']['reward']:,}）")
    return total, claimed_names
