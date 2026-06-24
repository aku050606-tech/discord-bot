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

def ai_action(strength: int, to_call: int) -> str:
    """AIの行動を決める。
    to_call: AIがコールするために必要な追加額（0以下ならタダでチェックできる）。
    タダでチェックできる場面では絶対に降りない（即フォールド対策）。"""
    if to_call <= 0:
        # チェック可能 → フォールドしない。強ければたまにレイズ
        if strength >= 4:
            return "raise" if random.random() < 0.6 else "call"
        if strength >= 2:
            return "raise" if random.random() < 0.25 else "call"
        return "call"  # ここでの "call" は実質チェック（差額0）
    # ベットに直面している場合のみ降りる可能性あり（降り過ぎないよう緩めに）
    if strength >= 4:      # ストレート以上
        return "raise" if random.random() < 0.5 else "call"
    if strength >= 2:      # ツーペア以上
        return "call" if random.random() < 0.85 else "fold"
    if strength == 1:      # ワンペア／好スタート
        return "call" if random.random() < 0.6 else "fold"
    return "call" if random.random() < 0.35 else "fold"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 対人戦ポーカー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

poker_rooms: dict[str, dict] = {}

class PokerView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=300)
        self.room_id = room_id

    @discord.ui.button(label="参加する", style=discord.ButtonStyle.success, emoji="✋")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = poker_rooms.get(self.room_id)
        if not room or room["phase"] != "waiting":
            await interaction.response.send_message("参加できません", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid in [p["id"] for p in room["players"]]:
            await interaction.response.send_message("すでに参加中です", ephemeral=True)
            return
        if len(room["players"]) >= 6:
            await interaction.response.send_message("満員です", ephemeral=True)
            return
        bal = db.get_balance(uid, room["guild_id"])
        if bal < room["ante"]:
            await interaction.response.send_message(f"ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, room["guild_id"], -room["ante"])
        room["players"].append({"id": uid, "name": interaction.user.display_name, "hand": []})
        room["pot"] += room["ante"]
        names = "\n".join(f"{i+1}. {p['name']}" for i, p in enumerate(room["players"]))
        embed = discord.Embed(
            title="⚔️ ポーカー 対人戦 — 参加者募集中",
            description=f"参加費: **{room['ante']:,} ナトコイン** | ポット: **{room['pot']:,} ナトコイン**\n\n{names}",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="ゲーム開始", style=discord.ButtonStyle.primary, emoji="▶️")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = poker_rooms.get(self.room_id)
        if not room:
            return
        if str(interaction.user.id) != room["host"]:
            await interaction.response.send_message("ホストだけが開始できます", ephemeral=True)
            return
        if len(room["players"]) < 2:
            await interaction.response.send_message("2人以上必要です", ephemeral=True)
            return

        deck = make_deck()
        random.shuffle(deck)
        community = [deck.pop() for _ in range(5)]
        for p in room["players"]:
            p["hand"] = [deck.pop(), deck.pop()]
        room["community"] = community
        room["phase"] = "showdown"

        results = []
        for p in room["players"]:
            score = best_hand(p["hand"] + community)
            results.append((score, p, HAND_NAMES[score[0]]))
        results.sort(key=lambda x: x[0], reverse=True)
        winner = results[0][1]

        db.update_balance(winner["id"], room["guild_id"], room["pot"])

        embed = discord.Embed(title="🃏 ポーカー 対人戦 — 結果発表", color=discord.Color.gold())
        embed.add_field(name="コミュニティカード", value=hand_str(community), inline=False)
        for score, p, hname in results:
            crown = "👑 " if p["id"] == winner["id"] else ""
            embed.add_field(
                name=f"{crown}{p['name']}",
                value=f"{hand_str(p['hand'])} → **{hname}**",
                inline=False
            )
        embed.add_field(
            name="🏆 勝者",
            value=f"**{winner['name']}** が {room['pot']:,} ナトコイン獲得！",
            inline=False
        )
        poker_rooms.pop(self.room_id, None)
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI戦ポーカー（フロップ→ターン→リバー形式）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ai_games: dict[str, dict] = {}

STAGES = ["preflop", "flop", "turn", "river", "showdown"]

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
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id

    def get_game(self):
        return ai_games.get(self.user_id)

    def advance_stage(self, game: dict):
        stage = game["stage"]
        deck = game["deck"]
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

    async def do_ai_action(self, game: dict) -> str:
        strength = ai_hand_strength(game["ai_hand"], game["community_shown"])
        to_call = game["player_bet"] - game["ai_bet"]  # AIが追いつくのに必要な額
        action = ai_action(strength, to_call)
        ante = game["ante"]

        if action == "fold":
            return "fold"
        elif action == "raise":
            raise_amount = ante * 2
            game["ai_bet"] += raise_amount
            game["pot"] += raise_amount
            return f"🔺 レイズ！ +{raise_amount:,} ナトコイン"
        else:
            diff = game["player_bet"] - game["ai_bet"]
            if diff > 0:
                game["ai_bet"] += diff
                game["pot"] += diff
            return "✅ コール"

    async def handle_player_action(self, interaction: discord.Interaction, action: str, raise_amount: int = 0):
        game = self.get_game()
        if not game:
            await interaction.response.send_message("ゲームが見つかりません", ephemeral=True)
            return

        player_log = ""
        if action == "fold":
            new_bal = db.get_balance(self.user_id, self.guild_id)
            embed = discord.Embed(title="🤖 ポーカー vs AI — 結果", color=discord.Color.red())
            embed.add_field(name="結果", value=f"🏳️ フォールド。AIの勝ち！\nポット {game['pot']:,} ナトコイン没収", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            ai_games.pop(self.user_id, None)
            self.clear_items()
            self.add_item(PokerAgainButton(game["ante"], self.user_id))
            self.add_item(PokerBackButton(self.user_id))
            await interaction.response.edit_message(embed=embed, view=self)
            return

        elif action == "call":
            diff = game["ai_bet"] - game["player_bet"]
            if diff > 0:
                bal = db.get_balance(self.user_id, self.guild_id)
                if bal < diff:
                    diff = bal
                db.update_balance(self.user_id, self.guild_id, -diff)
                game["player_bet"] += diff
                game["pot"] += diff
            player_log = "✅ コール"

        elif action == "raise":
            total = raise_amount
            bal = db.get_balance(self.user_id, self.guild_id)
            if bal < total:
                await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
                return
            db.update_balance(self.user_id, self.guild_id, -total)
            game["player_bet"] += total
            game["pot"] += total
            player_log = f"🔺 レイズ +{total:,} ナトコイン"

        elif action == "check":
            player_log = "⏭️ チェック"

        # AIアクション
        ai_log = await self.do_ai_action(game)
        if ai_log == "fold":
            # AIフォールド → プレイヤー勝ち
            db.update_balance(self.user_id, self.guild_id, game["pot"])
            new_bal = db.get_balance(self.user_id, self.guild_id)
            embed = discord.Embed(title="🤖 ポーカー vs AI — 結果", color=discord.Color.gold())
            embed.add_field(name="あなたの手札", value=hand_str(game["player_hand"]), inline=True)
            embed.add_field(name="AIの手札", value=hand_str(game["ai_hand"]), inline=True)
            embed.add_field(name="結果", value=f"🏳️ AIがフォールド！あなたの勝ち！\n+{game['pot']:,} ナトコイン獲得！", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            ai_games.pop(self.user_id, None)
            self.clear_items()
            self.add_item(PokerAgainButton(game["ante"], self.user_id))
            self.add_item(PokerBackButton(self.user_id))
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # ステージ進行
        if game["stage"] == "river":
            await self.showdown(interaction, game, player_log, ai_log)
            return

        self.advance_stage(game)
        combined_log = f"あなた: {player_log}\nAI: {ai_log}"
        embed = build_ai_embed(game, combined_log)
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
        elif ai_score > p_score:
            result_text = f"AIの勝ち！ -{game['player_bet']:,} ナトコイン損失"
            embed.color = discord.Color.red()
        else:
            half = game["pot"] // 2
            db.update_balance(self.user_id, self.guild_id, half)
            result_text = f"引き分け！ {half:,} ナトコイン返還"
            embed.color = discord.Color.blue()

        new_bal = db.get_balance(self.user_id, self.guild_id)
        embed.add_field(name="🏆 結果", value=result_text, inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)

        ai_games.pop(self.user_id, None)
        self.clear_items()
        self.add_item(PokerAgainButton(game["ante"], self.user_id))
        self.add_item(PokerBackButton(self.user_id))
        await interaction.response.edit_message(embed=embed, view=self)

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

    @discord.ui.button(label="レイズ（2倍）", style=discord.ButtonStyle.danger, emoji="🔺", row=0)
    async def raise_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = self.get_game()
        if not game:
            return
        await self.handle_player_action(interaction, "raise", raise_amount=game["ante"] * 2)

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
        ai_games[uid] = {
            "guild_id": guild_id, "ante": self.ante, "deck": deck,
            "player_hand": player_hand, "ai_hand": ai_hand, "community": community,
            "community_shown": [], "stage": "preflop",
            "pot": self.ante * 2, "player_bet": self.ante, "ai_bet": self.ante,
        }
        embed = build_ai_embed(ai_games[uid], "ゲーム開始！コール・チェック・レイズ・フォールドで行動してね")
        await interaction.response.edit_message(embed=embed, view=PokerAIView(uid, guild_id))

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
        super().__init__(timeout=30)
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

        ai_games[uid] = {
            "guild_id": guild_id,
            "ante": ante,
            "deck": deck,
            "player_hand": player_hand,
            "ai_hand": ai_hand,
            "community": community,
            "community_shown": [],
            "stage": "preflop",
            "pot": ante * 2,  # アンティ両者分
            "player_bet": ante,
            "ai_bet": ante,
        }

        embed = build_ai_embed(ai_games[uid], "ゲーム開始！コール・チェック・レイズ・フォールドで行動してね")
        view = PokerAIView(uid, guild_id)
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
            title="⚔️ ポーカー 対人戦 — 参加者募集中",
            description=(
                f"参加費（アンティ）: **{ante:,} ナトコイン**\n"
                f"最大6人まで参加可能\n\n"
                f"「参加する」を押して参加してね！全員揃ったらホストが開始！"
            ),
            color=discord.Color.dark_green()
        )
        embed.add_field(name="参加者", value=f"1. {interaction.user.display_name}（ホスト）", inline=False)
        view = PokerView(room_id)
        await interaction.response.edit_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
