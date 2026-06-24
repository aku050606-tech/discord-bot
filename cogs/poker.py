import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random
from collections import Counter
from itertools import combinations

db = Database()

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VAL = {r: i for i, r in enumerate(RANKS)}

def make_deck():
    return [{"suit": s, "rank": r} for s in SUITS for r in RANKS]

def card_str(card):
    return f"{card['suit']}{card['rank']}"

def hand_str(hand):
    return " ".join(card_str(c) for c in hand)

def best_hand(cards):
    best = None
    for combo in combinations(cards, 5):
        score = evaluate_5(list(combo))
        if best is None or score > best:
            best = score
    return best

def evaluate_5(hand):
    ranks = sorted([RANK_VAL[c["rank"]] for c in hand], reverse=True)
    suits = [c["suit"] for c in hand]
    flush = len(set(suits)) == 1
    straight = (max(ranks) - min(ranks) == 4 and len(set(ranks)) == 5)
    if set(ranks) == {12, 0, 1, 2, 3}:
        straight = True
        ranks = [3, 2, 1, 0, -1]
    count = Counter(ranks)
    freq = sorted(count.values(), reverse=True)
    groups = sorted(count.keys(), key=lambda r: (count[r], r), reverse=True)
    if straight and flush: return (8, ranks)
    if freq == [4, 1]: return (7, groups)
    if freq == [3, 2]: return (6, groups)
    if flush: return (5, ranks)
    if straight: return (4, ranks)
    if freq[0] == 3: return (3, groups)
    if freq[:2] == [2, 2]: return (2, groups)
    if freq[0] == 2: return (1, groups)
    return (0, ranks)

HAND_NAMES = ["ハイカード", "ワンペア", "ツーペア", "スリーカード",
              "ストレート", "フラッシュ", "フルハウス", "フォーカード", "ストレートフラッシュ"]

def ai_hand_strength(hand: list, community: list) -> int:
    """AIの手の強さを0〜8で返す（役レベル）"""
    all_cards = hand + community
    if len(all_cards) < 5:
        # フロップ前は手札だけで簡易評価
        vals = sorted([RANK_VAL[c["rank"]] for c in hand], reverse=True)
        if vals[0] == vals[1]: return 2          # ポケットペア
        if min(vals) >= 9: return 1              # 両方J以上
        if max(vals) >= 11: return 1             # A or K を持っている
        return 0
    return best_hand(all_cards)[0]

def ai_equity(hand, community_shown, iters=320):
    """モンテカルロで勝率(エクイティ)を推定。残りコミュニティと相手2枚をランダムに配って比較。"""
    known = hand + community_shown
    rem = [c for c in make_deck()
           if not any(c["suit"] == k["suit"] and c["rank"] == k["rank"] for k in known)]
    need = 5 - len(community_shown)
    wins = 0.0
    for _ in range(iters):
        sample = random.sample(rem, need + 2)
        comm = community_shown + sample[:need]
        my = best_hand(hand + comm)
        op = best_hand(sample[need:need + 2] + comm)
        if my > op:
            wins += 1.0
        elif my == op:
            wins += 0.5
    return wins / iters


def ai_decide(equity, to_call, pot, ante):
    """エクイティ＋ポットオッズで意思決定。強い手は積極レイズ、適度にブラフ。"""
    r = random.random()
    if to_call <= 0:
        # チェック可能：価値ベット中心＋たまにブラフ
        if equity >= 0.78:
            return "raise" if r < 0.85 else "call"
        if equity >= 0.62:
            return "raise" if r < 0.60 else "call"
        if equity >= 0.50:
            return "raise" if r < 0.30 else "call"
        return "raise" if r < 0.08 else "call"   # 8% ブラフベット
    # ベットに直面：ポットオッズで判断
    pot_odds = to_call / (pot + to_call)
    if equity >= 0.80 and r < 0.65:
        return "raise"                            # モンスター → バリューレイズ
    if equity >= 0.66 and r < 0.30:
        return "raise"
    if equity >= pot_odds - 0.03:
        return "call"                             # 適正価格ならコール
    if r < 0.05:
        return "raise"                            # 5% セミブラフ
    return "fold"


def ai_action(strength: int, to_call: int) -> str:
    """（旧・役カテゴリ判断：互換のため残置。現在は ai_decide を使用）"""
    if to_call <= 0:
        if strength >= 4:
            return "raise" if random.random() < 0.70 else "call"
        if strength >= 2:
            return "raise" if random.random() < 0.40 else "call"
        if strength == 1:
            return "raise" if random.random() < 0.15 else "call"
        return "call"
    if strength >= 4:
        return "raise" if random.random() < 0.55 else "call"
    if strength >= 2:
        return "raise" if random.random() < 0.25 else "call"
    if strength == 1:
        return "fold" if random.random() < 0.12 else "call"
    return "fold" if random.random() < 0.45 else "call"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 対人戦ポーカー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

poker_rooms: dict[str, dict] = {}

# vs-AIモードの進行中ゲーム（user_id -> game dict）
ai_games: dict[str, dict] = {}

# vs-AI 1ストリートあたりのレイズ上限
AI_MAX_RAISES = 3

def _new_ai_game(guild_id, ante, deck, player_hand, ai_hand, community):
    """vs-AI のゲーム状態を生成。street_* はストリートごとにリセットされるベット。"""
    return {
        "guild_id": guild_id, "ante": ante, "deck": deck,
        "player_hand": player_hand, "ai_hand": ai_hand, "community": community,
        "community_shown": [], "stage": "preflop",
        "pot": ante * 2, "player_bet": ante, "ai_bet": ante,
        "street_player": 0, "street_ai": 0, "street_bet": 0, "raises": 0,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 対人ポーカー：2人ヘッズアップ・テキサスホールデム（本格ベット制）
# 手札は伏せ、手番が来たらメンションで通知。ボタン一発でエフェメラルのアクション画面。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAX_RAISES_PER_ROUND = 3
STAGE_NAME = {"preflop": "プリフロップ", "flop": "フロップ", "turn": "ターン", "river": "リバー"}
STAGE_ORDER = ["preflop", "flop", "turn", "river"]
BOARD_SHOWN = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
_ping = discord.AllowedMentions(users=True)


def hu_start(room):
    deck = make_deck()
    random.shuffle(deck)
    room["deck"] = deck
    for p in room["players"]:
        p["hand"] = [deck.pop(), deck.pop()]
        p["rbet"] = 0
        p["folded"] = False
    room["community"] = [deck.pop() for _ in range(5)]
    room["stage"] = "preflop"
    room["current_bet"] = 0
    room["raises"] = 0
    room["acted"] = [False, False]
    room["to_act"] = 0
    room["phase"] = "betting"


def hu_to_call(room, i):
    return room["current_bet"] - room["players"][i]["rbet"]


def hu_legal(room, i):
    tc = hu_to_call(room, i)
    if tc <= 0:
        acts = ["check"]
        if room["raises"] < MAX_RAISES_PER_ROUND:
            acts.append("bet")
        acts.append("fold")
    else:
        acts = ["call"]
        if room["raises"] < MAX_RAISES_PER_ROUND:
            acts.append("raise")
        acts.append("fold")
    return acts


def hu_apply(room, i, action):
    """アクションを適用し、{type: continue|advance|fold|showdown, ...} を返す。"""
    g = room["guild_id"]
    ante = room["ante"]
    p = room["players"][i]
    opp = room["players"][1 - i]

    if action == "fold":
        p["folded"] = True
        db.update_balance(opp["id"], g, room["pot"])
        return {"type": "fold", "winner": 1 - i}

    if action == "check":
        pass
    elif action == "bet":
        amt = min(ante, db.get_balance(p["id"], g))
        db.update_balance(p["id"], g, -amt)
        p["rbet"] += amt
        room["pot"] += amt
        room["current_bet"] = p["rbet"]
        room["raises"] += 1
        room["acted"] = [False, False]
    elif action == "call":
        diff = hu_to_call(room, i)
        amt = min(diff, db.get_balance(p["id"], g))
        db.update_balance(p["id"], g, -amt)
        p["rbet"] += amt
        room["pot"] += amt
        if p["rbet"] < room["current_bet"]:  # ショートオールイン → 余剰を相手に返却
            uncalled = room["current_bet"] - p["rbet"]
            db.update_balance(opp["id"], g, uncalled)
            room["pot"] -= uncalled
            opp["rbet"] -= uncalled
            room["current_bet"] = p["rbet"]
    elif action == "raise":
        target = room["current_bet"] + ante
        amt = target - p["rbet"]
        bal = db.get_balance(p["id"], g)
        if bal < amt:
            amt = bal
        db.update_balance(p["id"], g, -amt)
        p["rbet"] += amt
        room["pot"] += amt
        room["current_bet"] = max(room["current_bet"], p["rbet"])
        room["raises"] += 1
        room["acted"] = [False, False]

    room["acted"][i] = True
    if all(room["acted"]) and room["players"][0]["rbet"] == room["players"][1]["rbet"]:
        return hu_end_round(room)
    room["to_act"] = 1 - i
    return {"type": "continue"}


def hu_end_round(room):
    if room["stage"] == "river":
        return hu_showdown(room)
    nxt = STAGE_ORDER[STAGE_ORDER.index(room["stage"]) + 1]
    room["stage"] = nxt
    for p in room["players"]:
        p["rbet"] = 0
    room["current_bet"] = 0
    room["raises"] = 0
    room["acted"] = [False, False]
    room["to_act"] = 0
    return {"type": "advance", "stage": nxt}


def hu_showdown(room):
    g = room["guild_id"]
    p0, p1 = room["players"]
    s0 = best_hand(p0["hand"] + room["community"])
    s1 = best_hand(p1["hand"] + room["community"])
    if s0 > s1:
        db.update_balance(p0["id"], g, room["pot"])
        win = 0
    elif s1 > s0:
        db.update_balance(p1["id"], g, room["pot"])
        win = 1
    else:
        half = room["pot"] // 2
        db.update_balance(p0["id"], g, half)
        db.update_balance(p1["id"], g, room["pot"] - half)
        win = None
    return {"type": "showdown", "winner": win, "s0": s0, "s1": s1}


def _board_str(room):
    shown = BOARD_SHOWN[room["stage"]]
    cards = [card_str(c) for c in room["community"][:shown]]
    cards += ["🂠"] * (5 - shown)
    return " ".join(cards)


def build_hu_public_embed(room):
    p0, p1 = room["players"]
    e = discord.Embed(title="🃏 ポーカー 対人戦（ヘッズアップ）", color=discord.Color.dark_green())
    e.add_field(name="ステージ", value=STAGE_NAME[room["stage"]], inline=True)
    e.add_field(name="ポット", value=f"{room['pot']:,} ナトコイン", inline=True)
    e.add_field(name="コミュニティ", value=_board_str(room), inline=False)
    for idx, p in enumerate(room["players"]):
        turn = "🎮 行動中" if (idx == room["to_act"]) else ""
        bet = f"ベット{p['rbet']:,}" if p["rbet"] else "—"
        e.add_field(name=f"{p['name']} {turn}", value=f"🂠🂠（非公開）／ {bet}", inline=True)
    cur = room["players"][room["to_act"]]
    e.set_footer(text=f"{cur['name']} の番｜「自分の番（アクション）」を押してね")
    return e


def build_hu_reveal_embed(room, ev):
    p0, p1 = room["players"]
    e = discord.Embed(title="🃏 ポーカー 対人戦 — 結果", color=discord.Color.gold())
    e.add_field(name="コミュニティ", value=" ".join(card_str(c) for c in room["community"]), inline=False)
    if ev["type"] == "fold":
        w = room["players"][ev["winner"]]
        e.add_field(name="結果", value=f"🏳️ {room['players'][1 - ev['winner']]['name']} がフォールド\n👑 **{w['name']}** が {room['pot']:,} ナトコイン獲得！", inline=False)
        return e
    n0 = HAND_NAMES[ev["s0"][0]]
    n1 = HAND_NAMES[ev["s1"][0]]
    e.add_field(name=f"{p0['name']} → {n0}", value=hand_str(p0["hand"]), inline=True)
    e.add_field(name=f"{p1['name']} → {n1}", value=hand_str(p1["hand"]), inline=True)
    if ev["winner"] is None:
        e.add_field(name="結果", value=f"🤝 引き分け！ ポット折半", inline=False)
    else:
        w = room["players"][ev["winner"]]
        e.add_field(name="結果", value=f"👑 **{w['name']}** の勝ち！ +{room['pot']:,} ナトコイン", inline=False)
    return e


class HUWaitView(discord.ui.View):
    def __init__(self, room_id):
        super().__init__(timeout=900)
        self.room_id = room_id

    @discord.ui.button(label="⚔️ 参加して対戦！", style=discord.ButtonStyle.success)
    async def join(self, interaction, button):
        room = poker_rooms.get(self.room_id)
        if not room or room["phase"] != "waiting":
            await interaction.response.send_message("参加できません", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid == room["players"][0]["id"]:
            await interaction.response.send_message("自分自身とは対戦できません", ephemeral=True)
            return
        g = room["guild_id"]
        if db.get_balance(uid, g) < room["ante"]:
            await interaction.response.send_message("❌ ナトコインが足りません", ephemeral=True)
            return
        db.update_balance(uid, g, -room["ante"])
        room["players"].append({"id": uid, "name": interaction.user.display_name, "hand": []})
        room["pot"] += room["ante"]
        hu_start(room)
        embed = build_hu_public_embed(room)
        mention = f"<@{room['players'][room['to_act']]['id']}>"
        await interaction.response.edit_message(content=f"{mention} の番です！", embed=embed,
                                                view=HUPublicView(self.room_id), allowed_mentions=_ping)
        room["message"] = interaction.message


class HUPublicView(discord.ui.View):
    def __init__(self, room_id):
        super().__init__(timeout=900)
        self.room_id = room_id

    @discord.ui.button(label="🎴 自分の番（アクション）", style=discord.ButtonStyle.primary)
    async def act(self, interaction, button):
        room = poker_rooms.get(self.room_id)
        if not room or room.get("phase") != "betting":
            await interaction.response.send_message("いまは行動できません", ephemeral=True)
            return
        uid = str(interaction.user.id)
        idx = next((k for k, p in enumerate(room["players"]) if p["id"] == uid), None)
        if idx is None:
            await interaction.response.send_message("あなたはこの対戦の参加者ではありません", ephemeral=True)
            return
        me = room["players"][idx]
        e = discord.Embed(title="🃏 あなたの手札",
                          description=f"{hand_str(me['hand'])}\nコミュニティ: {_board_str(room)}\nポット: {room['pot']:,}",
                          color=discord.Color.blurple())
        e.set_footer(text="この表示はあなたにだけ見えています")
        if idx != room["to_act"]:
            e.description += "\n\nいまは相手の番です。待っててね。"
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        tc = hu_to_call(room, idx)
        if tc > 0:
            e.description += f"\n\nコールに必要: **{tc:,} ナトコイン**"
        await interaction.response.send_message(embed=e, view=HUActionView(self.room_id, idx), ephemeral=True)


class HUActionButton(discord.ui.Button):
    LABELS = {"check": "✓ チェック", "fold": "🏳️ フォールド"}
    STYLES = {"fold": discord.ButtonStyle.secondary, "check": discord.ButtonStyle.secondary,
              "call": discord.ButtonStyle.success, "bet": discord.ButtonStyle.primary,
              "raise": discord.ButtonStyle.danger}

    def __init__(self, action, room, idx):
        ante = room["ante"]
        if action == "call":
            label = f"✅ コール({hu_to_call(room, idx):,})"
        elif action == "bet":
            label = f"💰 ベット({ante:,})"
        elif action == "raise":
            label = f"🔺 レイズ(+{ante:,})"
        else:
            label = self.LABELS[action]
        super().__init__(label=label, style=self.STYLES[action])
        self.action = action

    async def callback(self, interaction):
        await self.view.do_action(interaction, self.action)


class HUActionView(discord.ui.View):
    def __init__(self, room_id, idx):
        super().__init__(timeout=900)
        self.room_id = room_id
        self.idx = idx
        room = poker_rooms.get(room_id)
        if room:
            for a in hu_legal(room, idx):
                self.add_item(HUActionButton(a, room, idx))

    async def do_action(self, interaction, action):
        room = poker_rooms.get(self.room_id)
        if not room or room.get("phase") != "betting":
            await interaction.response.send_message("いまは行動できません", ephemeral=True)
            return
        if str(interaction.user.id) != room["players"][self.idx]["id"] or self.idx != room["to_act"]:
            await interaction.response.send_message("いまはあなたの番ではありません", ephemeral=True)
            return
        if action not in hu_legal(room, self.idx):
            await interaction.response.send_message("その行動は今できません", ephemeral=True)
            return

        ev = hu_apply(room, self.idx, action)

        # 自分のエフェメラルを「完了」に更新
        done = discord.Embed(title="🃏 行動しました",
                             description=f"あなたの行動：**{action}**", color=discord.Color.greyple())
        await interaction.response.edit_message(embed=done, view=None)

        msg = room.get("message")
        if ev["type"] in ("fold", "showdown"):
            room["phase"] = "ended"
            if msg:
                try:
                    await msg.edit(content="", embed=build_hu_reveal_embed(room, ev), view=None, allowed_mentions=_ping)
                except Exception:
                    pass
            poker_rooms.pop(self.room_id, None)
        else:
            if msg:
                mention = f"<@{room['players'][room['to_act']]['id']}>"
                try:
                    await msg.edit(content=f"{mention} の番です！", embed=build_hu_public_embed(room),
                                   view=HUPublicView(self.room_id), allowed_mentions=_ping)
                except Exception:
                    pass


def build_ai_embed(game: dict, action_log: str = "") -> discord.Embed:
    stage_label = {"preflop": "プリフロップ", "flop": "フロップ", "turn": "ターン", "river": "リバー", "showdown": "ショーダウン"}
    stage = game["stage"]
    embed = discord.Embed(
        title=f"🤖 ポーカー vs AI — {stage_label.get(stage, stage)}",
        color=discord.Color.dark_green()
    )
    embed.add_field(name="あなたの手札", value=hand_str(game["player_hand"]), inline=True)
    embed.add_field(name="AIの手札", value="🂠 🂠（非公開）", inline=True)

    community = game["community_shown"]
    if community:
        embed.add_field(name="コミュニティカード", value=hand_str(community), inline=False)

    embed.add_field(name="ポット", value=f"{game['pot']:,} ナトコイン", inline=True)
    embed.add_field(name="あなたの賭け", value=f"{game['player_bet']:,} ナトコイン", inline=True)
    embed.add_field(name="AIの賭け", value=f"{game['ai_bet']:,} ナトコイン", inline=True)

    if action_log:
        embed.add_field(name="💬 AIのアクション", value=action_log, inline=False)
    return embed


class PokerAIView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id

    def get_game(self):
        return ai_games.get(self.user_id)

    def advance_stage(self, game: dict):
        stage = game["stage"]
        if stage == "preflop":
            game["community_shown"] = game["community"][:3]
            game["stage"] = "flop"
        elif stage == "flop":
            game["community_shown"] = game["community"][:4]
            game["stage"] = "turn"
        elif stage == "turn":
            game["community_shown"] = game["community"][:5]
            game["stage"] = "river"
        elif stage == "river":
            game["stage"] = "showdown"
        # 新ストリート：ベットをリセット（プレイヤー先手）
        game["street_player"] = 0
        game["street_ai"] = 0
        game["street_bet"] = 0
        game["raises"] = 0

    def _sync_buttons(self, game: dict):
        """場況に応じてボタンの活殺を切り替える（コール額が無ければチェックのみ等）。"""
        tc = game["street_bet"] - game["street_player"]
        can_raise = game["raises"] < AI_MAX_RAISES
        for ch in self.children:
            if not isinstance(ch, discord.ui.Button):
                continue
            if ch.label == "コール":
                ch.disabled = tc <= 0
            elif ch.label == "チェック":
                ch.disabled = tc > 0
            elif ch.label == "レイズ":
                ch.disabled = not can_raise
            # フォールドは常時可能

    def _ai_respond(self, game: dict):
        """AIの応手。戻り値 (status, log)。status: fold|closed|need_player。
        AI側のチップはハウス資金（実残高は動かさず pot/ai_bet のみ加算）。"""
        tc_ai = game["street_bet"] - game["street_ai"]
        equity = ai_equity(game["ai_hand"], game["community_shown"])
        decision = ai_decide(equity, tc_ai, game["pot"], game["ante"])

        if decision == "fold":
            if tc_ai <= 0:
                decision = "call"          # タダなら降りずチェック
            else:
                return ("fold", "🏳️ AIフォールド")
        if decision == "raise" and game["raises"] >= AI_MAX_RAISES:
            decision = "call"              # 上限到達 → コール/チェック

        if decision == "raise":
            unit = min(game["ante"] * 2, 2000)
            new_level = game["street_bet"] + unit
            pay = new_level - game["street_ai"]
            game["street_ai"] += pay
            game["ai_bet"] += pay
            game["pot"] += pay
            game["street_bet"] = game["street_ai"]
            game["raises"] += 1
            return ("need_player", f"🔺 AIレイズ +{pay:,}")

        # call / check
        if tc_ai > 0:
            game["street_ai"] += tc_ai
            game["ai_bet"] += tc_ai
            game["pot"] += tc_ai
            return ("closed", f"✅ AIコール {tc_ai:,}")
        return ("closed", "⏭️ AIチェック")

    async def _finish(self, interaction, game, embed):
        """結果表示してゲーム終了（もう一回／戻るボタン）。"""
        ai_games.pop(self.user_id, None)
        self.clear_items()
        self.add_item(PokerAgainButton(game["ante"], self.user_id))
        self.add_item(PokerBackButton(self.user_id))
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_player_action(self, interaction: discord.Interaction, action: str, raise_amount: int = 0):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("ゲームが見つかりません", ephemeral=True)
            return

        uid, g = self.user_id, self.guild_id
        tc = game["street_bet"] - game["street_player"]

        # ── フォールド ──
        if action == "fold":
            new_bal = db.get_balance(uid, g)
            embed = discord.Embed(title="🤖 ポーカー vs AI — 結果", color=discord.Color.red())
            embed.add_field(name="あなたの手札", value=hand_str(game["player_hand"]), inline=True)
            embed.add_field(name="AIの手札", value=hand_str(game["ai_hand"]), inline=True)
            embed.add_field(name="結果", value=f"🏳️ フォールド。AIの勝ち\n-{game['player_bet']:,} ナトコイン", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            await self._finish(interaction, game, embed)
            return

        # ── プレイヤーの行動を適用 ──
        if action == "check":
            if tc > 0:
                await interaction.response.send_message("❌ チェックできません（コールかフォールドを）", ephemeral=True)
                return
            player_log = "⏭️ チェック"
        elif action == "call":
            if tc <= 0:
                await interaction.response.send_message("❌ コールする額がありません（チェックを）", ephemeral=True)
                return
            bal = db.get_balance(uid, g)
            pay = min(tc, bal)
            db.update_balance(uid, g, -pay)
            game["street_player"] += pay
            game["player_bet"] += pay
            game["pot"] += pay
            player_log = f"✅ コール {pay:,}"
        elif action == "raise":
            if game["raises"] >= AI_MAX_RAISES:
                await interaction.response.send_message("❌ これ以上レイズできません", ephemeral=True)
                return
            bal = db.get_balance(uid, g)
            if bal <= tc:
                await interaction.response.send_message(f"❌ レイズする残高が足りません（残高: {bal:,}）", ephemeral=True)
                return
            unit = min(game["ante"] * 2, 2000)
            new_level = game["street_bet"] + unit
            pay = min(new_level - game["street_player"], bal)
            db.update_balance(uid, g, -pay)
            game["street_player"] += pay
            game["player_bet"] += pay
            game["pot"] += pay
            game["street_bet"] = game["street_player"]
            game["raises"] += 1
            player_log = f"🔺 レイズ +{pay:,}"
        else:
            return

        # ── コールでベットが揃ったらストリート確定（AIは既に行動済み）──
        if action == "call":
            await self._after_street_closed(interaction, game, player_log, "")
            return

        # ── それ以外（チェック/ベット/レイズ）→ AIが応手 ──
        status, ai_log = self._ai_respond(game)
        if status == "fold":
            db.update_balance(uid, g, game["pot"])
            new_bal = db.get_balance(uid, g)
            fold_net = game["pot"] - game.get("player_bet", 0)
            embed = discord.Embed(title="🤖 ポーカー vs AI — 結果", color=discord.Color.gold())
            embed.add_field(name="あなたの手札", value=hand_str(game["player_hand"]), inline=True)
            embed.add_field(name="AIの手札", value=hand_str(game["ai_hand"]), inline=True)
            embed.add_field(name="結果", value=f"🏳️ AIがフォールド！あなたの勝ち\n+{game['pot']:,} ナトコイン", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            await self._finish(interaction, game, embed)
            from cogs.bigwin import announce_big_win
            await announce_big_win(interaction, interaction.user, "ポーカー",
                                   fold_net, balance=new_bal, detail="AIフォールド勝ち")
            return

        if status == "need_player":
            # AIがレイズ → プレイヤーが応じる番。進行せずアクション画面を再表示
            embed = build_ai_embed(game, f"あなた: {player_log}\nAI: {ai_log}\n→ あなたの番です")
            self._sync_buttons(game)
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # status == closed → ストリート確定
        await self._after_street_closed(interaction, game, player_log, ai_log)

    async def _after_street_closed(self, interaction, game, player_log, ai_log):
        if game["stage"] == "river":
            await self.showdown(interaction, game, player_log, ai_log)
            return
        self.advance_stage(game)
        log = f"あなた: {player_log}" + (f"\nAI: {ai_log}" if ai_log else "")
        embed = build_ai_embed(game, log)
        self._sync_buttons(game)
        await interaction.response.edit_message(embed=embed, view=self)

    async def showdown(self, interaction, game, player_log, ai_log):
        p_score = best_hand(game["player_hand"] + game["community"])
        ai_score = best_hand(game["ai_hand"] + game["community"])
        p_name = HAND_NAMES[p_score[0]]
        ai_name = HAND_NAMES[ai_score[0]]

        embed = discord.Embed(title="🤖 ポーカー vs AI — ショーダウン", color=discord.Color.gold())
        embed.add_field(name="コミュニティカード", value=hand_str(game["community"]), inline=False)
        embed.add_field(name=f"あなたの手札 → {p_name}", value=hand_str(game["player_hand"]), inline=True)
        embed.add_field(name=f"AIの手札 → {ai_name}", value=hand_str(game["ai_hand"]), inline=True)

        if p_score > ai_score:
            db.update_balance(self.user_id, self.guild_id, game["pot"])
            result_text = f"あなたの勝ち！ +{game['pot']:,} ナトコイン獲得！"
            embed.color = discord.Color.gold()
            won_net = game["pot"] - game.get("player_bet", 0)
        elif ai_score > p_score:
            result_text = f"AIの勝ち！ -{game['player_bet']:,} ナトコイン損失"
            embed.color = discord.Color.red()
            won_net = 0
        else:
            half = game["pot"] // 2
            db.update_balance(self.user_id, self.guild_id, half)
            result_text = f"引き分け！ {half:,} ナトコイン返還"
            embed.color = discord.Color.blue()
            won_net = 0

        new_bal = db.get_balance(self.user_id, self.guild_id)
        embed.add_field(name="🏆 結果", value=result_text, inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)

        ai_games.pop(self.user_id, None)
        self.clear_items()
        self.add_item(PokerAgainButton(game["ante"], self.user_id))
        self.add_item(PokerBackButton(self.user_id))
        await interaction.response.edit_message(embed=embed, view=self)

        # 勝ち額が大きければBOT告知
        if won_net >= 0:
            from cogs.bigwin import announce_big_win
            await announce_big_win(interaction, interaction.user, "ポーカー",
                                   won_net, balance=new_bal, detail=p_name)

    @discord.ui.button(label="コール", style=discord.ButtonStyle.primary, emoji="✅", row=0)
    async def call(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        await self.handle_player_action(interaction, "call")

    @discord.ui.button(label="チェック", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def check(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        await self.handle_player_action(interaction, "check")

    @discord.ui.button(label="レイズ", style=discord.ButtonStyle.danger, emoji="🔺", row=0)
    async def raise_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = self.get_game()
        if not game:
            return
        amount = min(game["ante"] * 2, 2000)   # レイズは最大2,000ナトコインまで
        await self.handle_player_action(interaction, "raise", raise_amount=amount)

    @discord.ui.button(label="フォールド", style=discord.ButtonStyle.secondary, emoji="🏳️", row=1)
    async def fold(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        await self.handle_player_action(interaction, "fold")

    async def on_timeout(self):
        ai_games.pop(self.user_id, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 結果後ボタン
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PokerAgainButton(discord.ui.Button):
    def __init__(self, ante: int, user_id: str):
        super().__init__(label="もう一回！", style=discord.ButtonStyle.primary, emoji="♠️")
        self.ante = ante
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.ante:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -self.ante)
        deck = make_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        ai_hand = [deck.pop(), deck.pop()]
        community = [deck.pop() for _ in range(5)]
        ai_games[uid] = _new_ai_game(guild_id, self.ante, deck, player_hand, ai_hand, community)
        embed = build_ai_embed(ai_games[uid], "ゲーム開始！チェック・ベット（レイズ）・フォールドで行動してね")
        view = PokerAIView(uid, guild_id)
        view._sync_buttons(ai_games[uid])
        await interaction.response.edit_message(embed=embed, view=view)

class PokerBackButton(discord.ui.Button):
    def __init__(self, user_id: str):
        super().__init__(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(self.user_id))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# モード選択
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PokerModeView(discord.ui.View):
    def __init__(self, ante: int):
        super().__init__(timeout=900)
        self.ante = ante

    @discord.ui.button(label="🤖 AIと対戦", style=discord.ButtonStyle.primary)
    async def vs_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        ante = self.ante
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if uid in ai_games:
            await interaction.response.send_message("❌ すでにゲーム中です", ephemeral=True)
            return

        bal = db.get_balance(uid, guild_id)
        if bal < ante:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, guild_id, -ante)

        deck = make_deck()
        random.shuffle(deck)
        player_hand = [deck.pop(), deck.pop()]
        ai_hand = [deck.pop(), deck.pop()]
        community = [deck.pop() for _ in range(5)]

        ai_games[uid] = _new_ai_game(guild_id, ante, deck, player_hand, ai_hand, community)

        embed = build_ai_embed(ai_games[uid], "ゲーム開始！チェック・ベット（レイズ）・フォールドで行動してね")
        view = PokerAIView(uid, guild_id)
        view._sync_buttons(ai_games[uid])
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚔️ 人と対戦", style=discord.ButtonStyle.success)
    async def vs_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        ante = self.ante
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        room_id = f"{guild_id}_{interaction.channel.id}"

        if room_id in poker_rooms:
            await interaction.response.send_message("❌ このチャンネルでゲームが進行中です", ephemeral=True)
            return

        bal = db.get_balance(uid, guild_id)
        if bal < ante:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, guild_id, -ante)
        poker_rooms[room_id] = {
            "host": uid,
            "guild_id": guild_id,
            "players": [{"id": uid, "name": interaction.user.display_name, "hand": []}],
            "pot": ante,
            "ante": ante,
            "phase": "waiting",
            "community": []
        }

        embed = discord.Embed(
            title="⚔️ ポーカー 対人戦（ヘッズアップ／1対1）",
            description=(
                f"参加費（アンティ）: **{ante:,} ナトコイン**\n"
                f"テキサスホールデム・固定刻みベット\n\n"
                f"**{interaction.user.display_name}** が対戦相手を募集中！\n"
                f"「⚔️ 参加して対戦！」を押すと開始！"
            ),
            color=discord.Color.dark_green()
        )
        view = HUWaitView(room_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @discord.ui.button(label="🔙 カジノへ戻る", style=discord.ButtonStyle.secondary, row=4)
    async def __back_casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction)

class Poker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="poker", description="テキサスホールデム！AIと対戦 or 人と対戦を選べる")
    @app_commands.describe(ante="参加費（アンティ）ナトコイン数")
    async def poker(self, interaction: discord.Interaction, ante: int = 100):
        if ante < 10:
            await interaction.response.send_message("❌ アンティは最低10ナトコイン", ephemeral=True)
            return

        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < ante:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        embed = discord.Embed(
            title="♠️ ポーカー",
            description=f"アンティ: **{ante:,} ナトコイン**\n\nモードを選んでください！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="🤖 AIと対戦", value="フロップ→ターン→リバーの本格形式。コール・レイズ・フォールドで読み合い！", inline=False)
        embed.add_field(name="⚔️ 人と対戦", value="サーバーメンバーと対決。最大6人まで参加OK！", inline=False)
        await interaction.response.send_message(embed=embed, view=PokerModeView(ante))


async def setup(bot):
    await bot.add_cog(Poker(bot))
