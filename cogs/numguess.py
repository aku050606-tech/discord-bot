import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random

db = Database()

MAX_TRIES = 5

# 配当表：1回目は夢の×50！ 5回・ヒントありで出率≒105%（最適プレイ時）。
# 5回だと二分探索でも全部は当てられない（31/100が当たり圏）＝ギャンブル性あり。
MULTIPLIERS = {1: 50, 2: 8, 3: 3, 4: 1.4, 5: 1.0}

# 進行中ゲーム
active_games: dict[str, dict] = {}


def build_game_embed(game: dict, message: str = "") -> discord.Embed:
    tries = game["tries"]
    remaining = MAX_TRIES - tries
    next_mult = MULTIPLIERS.get(tries + 1, 1)
    bet = game["bet"]

    embed = discord.Embed(
        title="🎯 数字当てゲーム",
        color=discord.Color.blurple()
    )
    if message:
        embed.description = message

    table = "\n".join(
        f"{'→ ' if t == tries + 1 else '　'}{t}回目: ×{m}"
        for t, m in MULTIPLIERS.items()
    )
    embed.add_field(name="💰 配当表", value=table, inline=True)
    embed.add_field(
        name="📊 状況",
        value=f"残り回数: **{remaining}回**\n次の配当: **×{next_mult}**\n賭け: **{bet:,} ナトコイン**",
        inline=True
    )
    hist = game.get("history", [])
    if hist:
        lines = "\n".join(f"{i+1}. **{n}** … {m}" for i, (n, m) in enumerate(hist))
        embed.add_field(name="📝 これまでの入力", value=lines, inline=False)
    return embed


class GuessModal(discord.ui.Modal, title="数字を入力してください"):
    number = discord.ui.TextInput(
        label="1〜100の数字",
        placeholder="例: 42",
        min_length=1,
        max_length=3,
    )

    def __init__(self, user_id: str, guild_id: str):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        # 数字チェック
        try:
            num = int(self.number.value)
        except ValueError:
            await interaction.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return

        if num < 1 or num > 100:
            await interaction.response.send_message("❌ 1〜100の数字を入力してください", ephemeral=True)
            return

        game = active_games.get(self.user_id)
        if not game:
            await interaction.response.send_message(
                "❌ ゲームの有効期限が切れたか、見つかりませんでした。メニューから新しく始めてください。",
                ephemeral=True)
            return

        game["tries"] += 1
        tries = game["tries"]
        answer = game["answer"]
        bet = game["bet"]
        # 入力履歴を記録
        if num == answer:
            mark = "🎯 正解！"
        elif num < answer:
            mark = "📈 もっと大きい"
        else:
            mark = "📉 もっと小さい"
        game.setdefault("history", []).append((num, mark))

        if num == answer:
            # 正解
            mult = MULTIPLIERS.get(tries, 1)
            winnings = int(bet * mult)
            db.update_balance(self.user_id, self.guild_id, winnings)
            new_bal = db.get_balance(self.user_id, self.guild_id)
            active_games.pop(self.user_id, None)

            embed = discord.Embed(
                title="🎯 正解！！",
                description=f"答えは **{answer}** でした！\n{tries}回目で正解 → **×{mult}倍** 配当！",
                color=discord.Color.gold()
            )
            embed.add_field(name="獲得ナトコイン", value=f"+{winnings:,} ナトコイン", inline=True)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
            net = winnings - bet
            if net > 0:
                from cogs.doubleup import build_entry_view
                view = build_entry_view(self.user_id, self.guild_id, net, "数字当て",
                                        lambda: NumguessResultView(bet, self.user_id))
            else:
                view = NumguessResultView(bet, self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)

        elif tries >= MAX_TRIES:
            # ゲームオーバー
            active_games.pop(self.user_id, None)
            new_bal = db.get_balance(self.user_id, self.guild_id)
            embed = discord.Embed(
                title="💀 ゲームオーバー",
                description=f"正解は **{answer}** でした！\n{MAX_TRIES}回全て外れ... -{bet:,} ナトコイン",
                color=discord.Color.red()
            )
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
            await interaction.response.edit_message(embed=embed, view=NumguessResultView(bet, self.user_id))

        else:
            # ヒント
            hint = "📈 もっと大きい！" if num < answer else "📉 もっと小さい！"
            embed = build_game_embed(game, f"**{num}** は違います。{hint}")
            await interaction.response.edit_message(embed=embed, view=NumguessPlayView(self.user_id, self.guild_id))


class NumguessPlayView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="数字を入力する", style=discord.ButtonStyle.primary, emoji="🎯")
    async def guess(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        modal = GuessModal(self.user_id, self.guild_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="やめる（賭け金没収）", style=discord.ButtonStyle.secondary, emoji="🏳️")
    async def quit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_games.pop(self.user_id, None)
        if game:
            new_bal = db.get_balance(self.user_id, self.guild_id)
            embed = discord.Embed(
                title="🏳️ ゲーム終了",
                description=f"答えは **{game['answer']}** でした\n賭け金 {game['bet']:,} ナトコイン没収",
                color=discord.Color.dark_gray()
            )
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
            await interaction.response.edit_message(embed=embed, view=NumguessResultView(game["bet"], self.user_id))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_games.pop(self.user_id, None)
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(self.user_id))

    async def on_timeout(self):
        active_games.pop(self.user_id, None)


class NumguessResultView(discord.ui.View):
    def __init__(self, bet: int, user_id: str):
        super().__init__(timeout=900)
        self.bet = bet
        self.user_id = user_id

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎯")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -self.bet)
        answer = random.randint(1, 100)
        active_games[uid] = {"answer": answer, "tries": 0, "bet": self.bet, "guild_id": guild_id, "history": []}
        game = active_games[uid]
        embed = build_game_embed(game, "1〜100の数字を当ててください！")
        await interaction.response.edit_message(embed=embed, view=NumguessPlayView(uid, guild_id))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(self.user_id))


class NumberGuess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="numguess", description="1〜100の数字を当てよう！当てるほど高配当")
    @app_commands.describe(bet="賭けるナトコイン数（最低10）")
    async def numguess(self, interaction: discord.Interaction, bet: int):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if uid in active_games:
            await interaction.response.send_message(
                "❌ すでにゲーム中です。ボタンから続けてください", ephemeral=True
            )
            return
        if bet < 10:
            await interaction.response.send_message("❌ 最低10ナトコインから", ephemeral=True)
            return

        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, guild_id, -bet)
        answer = random.randint(1, 100)
        active_games[uid] = {"answer": answer, "tries": 0, "bet": bet, "guild_id": guild_id, "history": []}
        game = active_games[uid]

        embed = build_game_embed(game, "1〜100の数字を当ててください！")
        await interaction.response.send_message(embed=embed, view=NumguessPlayView(uid, guild_id))


async def setup(bot):
    await bot.add_cog(NumberGuess(bot))
