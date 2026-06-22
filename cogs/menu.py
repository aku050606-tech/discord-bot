import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random
from datetime import date

db = Database()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セレクトメニュー：ゲームカテゴリ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BetModal(discord.ui.Modal):
    def __init__(self, game: str):
        super().__init__(title=f"{game} — 賭け金を入力")
        self.game = game
        self.bet_input = discord.ui.TextInput(
            label="賭けるコイン数（最低10）",
            placeholder="例: 100",
            min_length=1,
            max_length=6
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value)
        except ValueError:
            await interaction.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return

        if bet < 10:
            await interaction.response.send_message("❌ 最低10コイン", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        if self.game == "slot":
            await run_slot(interaction, user_id, guild_id, bet)
        elif self.game == "coinflip":
            await interaction.response.send_message(
                "表・裏どちらに賭けますか？",
                view=CoinflipChoiceView(bet),
                ephemeral=True
            )
        elif self.game == "blackjack":
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                f"ブラックジャックを {bet:,} コインで開始します。`/blackjack {bet}` を使ってください！",
                ephemeral=True
            )
        elif self.game == "numguess":
            await interaction.response.defer(ephemeral=False)
            await interaction.followup.send(
                f"数字当てを {bet:,} コインで開始します。`/numguess {bet}` を使ってください！",
                ephemeral=True
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スロット処理
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]
SLOT_PAYOUTS = {
    "💎💎💎": 50, "7️⃣7️⃣7️⃣": 30, "⭐⭐⭐": 15,
    "🍇🍇🍇": 10, "🍊🍊🍊": 8, "🍋🍋🍋": 5, "🍒🍒🍒": 3,
}

async def run_slot(interaction, user_id, guild_id, bet):
    reels = [random.choice(SLOT_SYMBOLS) for _ in range(3)]
    combo = "".join(reels)
    won = 0
    for pattern, mult in SLOT_PAYOUTS.items():
        if combo == pattern:
            won = bet * mult
            break
    if won == 0 and (reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]):
        won = int(bet * 1.5)

    net = won - bet
    db.update_balance(user_id, guild_id, net)
    new_bal = db.get_balance(user_id, guild_id)

    if won > bet:
        color = discord.Color.gold()
        result = f"🎉 当たり！ +{won:,} コイン"
    elif won > 0:
        color = discord.Color.blue()
        result = f"😐 ペア！ ±{net:+,} コイン"
    else:
        color = discord.Color.red()
        result = f"😢 ハズレ... -{bet:,} コイン"

    embed = discord.Embed(title="🎰 スロット", color=color)
    embed.add_field(name="リール", value=f"[ {' | '.join(reels)} ]", inline=False)
    embed.add_field(name="結果", value=result, inline=False)
    embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)

    view = SlotAgainView(bet)
    await interaction.response.send_message(embed=embed, view=view)


class SlotAgainView(discord.ui.View):
    def __init__(self, bet: int):
        super().__init__(timeout=60)
        self.bet = bet

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎰")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        await run_slot(interaction, user_id, guild_id, self.bet)

    @discord.ui.button(label="メニューへ戻る", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_menu(interaction, edit=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# コインフリップ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CoinflipChoiceView(discord.ui.View):
    def __init__(self, bet: int):
        super().__init__(timeout=30)
        self.bet = bet

    async def do_flip(self, interaction: discord.Interaction, choice: str):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        result = random.choice(["heads", "tails"])
        won = choice == result
        net = self.bet if won else -self.bet
        db.update_balance(user_id, guild_id, net)
        new_bal = db.get_balance(user_id, guild_id)

        result_emoji = "🪙 表" if result == "heads" else "🪙 裏"
        embed = discord.Embed(
            title="🪙 コインフリップ",
            color=discord.Color.green() if won else discord.Color.red()
        )
        embed.add_field(name="結果", value=result_emoji, inline=True)
        embed.add_field(name="あなた", value="表" if choice == "heads" else "裏", inline=True)
        embed.add_field(name="判定", value=f"{'🎉 勝ち！' if won else '😢 負け...'} {net:+,} コイン", inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)

        view = CoinflipAgainView(self.bet, choice)
        await interaction.response.send_message(embed=embed, view=view)

    @discord.ui.button(label="表 (Heads)", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "heads")

    @discord.ui.button(label="裏 (Tails)", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "tails")


class CoinflipAgainView(discord.ui.View):
    def __init__(self, bet: int, last_choice: str):
        super().__init__(timeout=60)
        self.bet = bet
        self.last_choice = last_choice

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🪙")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "表・裏どちらに賭けますか？",
            view=CoinflipChoiceView(self.bet),
            ephemeral=True
        )

    @discord.ui.button(label="メニューへ戻る", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_menu(interaction, edit=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 占い
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORTUNES = [
    ("大吉", discord.Color.gold(), "最高の一日！何でも積極的に挑戦しよう！"),
    ("吉",   discord.Color.green(), "良いことが起きる予感。前向きに過ごそう！"),
    ("中吉", discord.Color.blue(), "コツコツ努力が報われる日。"),
    ("小吉", discord.Color.teal(), "小さな幸せを大切に。"),
    ("末吉", discord.Color.blurple(), "慎重に行動すると吉。"),
    ("凶",   discord.Color.orange(), "無理せず休息を取ろう。"),
    ("大凶", discord.Color.red(), "要注意！でも明日はきっと良くなる。"),
]
LUCKY_ITEMS = ["コーヒー", "青ペン", "ネコ", "古い本", "星形のもの", "音楽"]
LUCKY_COLORS = ["赤", "青", "緑", "金", "白", "紫"]

async def run_fortune(interaction: discord.Interaction):
    seed = int(str(interaction.user.id) + str(date.today()).replace("-", ""))
    rng = random.Random(seed)
    name, color, msg = rng.choice(FORTUNES)
    item = rng.choice(LUCKY_ITEMS)
    lucky_color = rng.choice(LUCKY_COLORS)
    lucky_num = rng.randint(1, 99)

    embed = discord.Embed(title=f"🔮 今日の運勢: {name}", description=msg, color=color)
    embed.add_field(name="🍀 ラッキーアイテム", value=item, inline=True)
    embed.add_field(name="🎨 ラッキーカラー", value=lucky_color, inline=True)
    embed.add_field(name="🔢 ラッキーナンバー", value=str(lucky_num), inline=True)
    embed.set_footer(text=f"{interaction.user.display_name} の運勢（{date.today()} 版）")

    view = BackToMenuView()
    await interaction.response.send_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# チーム分け
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_teamsplit(interaction: discord.Interaction):
    players = list(range(1, 11))
    random.shuffle(players)
    team1 = sorted(players[:5])
    team2 = sorted(players[5:])

    embed = discord.Embed(title="⚔️ チーム分け結果", color=discord.Color.blue())
    embed.add_field(name="🔵 チーム1", value=" / ".join(f"**{p}番**" for p in team1), inline=False)
    embed.add_field(name="🔴 チーム2", value=" / ".join(f"**{p}番**" for p in team2), inline=False)
    embed.set_footer(text="もう一度シャッフルするにはボタンを押してください")

    view = TeamsplitAgainView()
    await interaction.response.send_message(embed=embed, view=view)


class TeamsplitAgainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="もう一度シャッフル", style=discord.ButtonStyle.primary, emoji="🔀")
    async def resplit(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])
        embed = discord.Embed(title="⚔️ チーム分け結果", color=discord.Color.blue())
        embed.add_field(name="🔵 チーム1", value=" / ".join(f"**{p}番**" for p in team1), inline=False)
        embed.add_field(name="🔴 チーム2", value=" / ".join(f"**{p}番**" for p in team2), inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="メニューへ戻る", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_menu(interaction, edit=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 残高・デイリー・ランキング
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_balance(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    gid = str(interaction.guild.id)
    bal = db.get_balance(uid, gid)
    embed = discord.Embed(title="💰 残高確認", color=discord.Color.gold())
    embed.add_field(name=interaction.user.display_name, value=f"**{bal:,} コイン**")
    view = BackToMenuView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def run_daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    gid = str(interaction.guild.id)
    today = str(date.today())
    last = db.get_last_daily(uid)

    if last == today:
        await interaction.response.send_message(
            "⏰ 今日はすでにデイリーボーナスを受け取っています！明日また来てね。",
            ephemeral=True
        )
        return

    db.update_balance(uid, gid, 500)
    db.set_last_daily(uid, today)
    bal = db.get_balance(uid, gid)
    embed = discord.Embed(title="🎁 デイリーボーナス！",
        description=f"**+500 コイン** ゲット！\n残高: **{bal:,} コイン**",
        color=discord.Color.green())
    view = BackToMenuView()
    await interaction.response.send_message(embed=embed, view=view)


async def run_ranking(interaction: discord.Interaction):
    gid = str(interaction.guild.id)
    rows = db.get_ranking(gid, 10)
    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(title="🏆 コインランキング", color=discord.Color.gold())
    if not rows:
        embed.description = "まだデータがありません"
    else:
        lines = []
        for i, (uid, bal) in enumerate(rows):
            m = medals[i] if i < 3 else f"{i+1}."
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"ID:{uid}"
            lines.append(f"{m} **{name}** — {bal:,} コイン")
        embed.description = "\n".join(lines)
    view = BackToMenuView()
    await interaction.response.send_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 共通「メニューへ戻る」ビュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BackToMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="メニューへ戻る", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await send_menu(interaction, edit=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メインメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮 BOTメニュー",
        description="ボタンを押して各機能を使ってね！",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="🎮 ゲーム",
        value="スロット・コインフリップ・ブラックジャック・ポーカー・数字当て",
        inline=False
    )
    embed.add_field(
        name="💰 コイン",
        value="残高確認・デイリーボーナス・ランキング",
        inline=False
    )
    embed.add_field(
        name="✨ その他",
        value="占い・チーム分け・AIチャット",
        inline=False
    )
    return embed


class MenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    # ── ゲーム行 ──────────────────────────
    @discord.ui.button(label="スロット", style=discord.ButtonStyle.primary, emoji="🎰", row=0)
    async def slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("slot"))

    @discord.ui.button(label="コインフリップ", style=discord.ButtonStyle.primary, emoji="🪙", row=0)
    async def coinflip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("coinflip"))

    @discord.ui.button(label="ブラックジャック", style=discord.ButtonStyle.primary, emoji="🃏", row=0)
    async def blackjack(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("blackjack"))

    @discord.ui.button(label="数字当て", style=discord.ButtonStyle.primary, emoji="🎯", row=1)
    async def numguess(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BetModal("numguess"))

    @discord.ui.button(label="ポーカー", style=discord.ButtonStyle.primary, emoji="♠️", row=1)
    async def poker(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "ポーカーは `/poker [アンティ]` で開始できます！複数人で遊んでね🃏",
            ephemeral=True
        )

    # ── コイン行 ──────────────────────────
    @discord.ui.button(label="残高確認", style=discord.ButtonStyle.secondary, emoji="💰", row=2)
    async def balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_balance(interaction)

    @discord.ui.button(label="デイリーボーナス", style=discord.ButtonStyle.success, emoji="🎁", row=2)
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_daily(interaction)

    @discord.ui.button(label="ランキング", style=discord.ButtonStyle.secondary, emoji="🏆", row=2)
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_ranking(interaction)

    # ── その他行 ──────────────────────────
    @discord.ui.button(label="占い", style=discord.ButtonStyle.secondary, emoji="🔮", row=3)
    async def fortune(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_fortune(interaction)

    @discord.ui.button(label="チーム分け", style=discord.ButtonStyle.secondary, emoji="⚔️", row=3)
    async def teamsplit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await run_teamsplit(interaction)

    @discord.ui.button(label="AIチャット", style=discord.ButtonStyle.secondary, emoji="🤖", row=3)
    async def aichat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "AIチャットは `/chat [メッセージ]` で話しかけてね！🤖",
            ephemeral=True
        )


async def send_menu(interaction: discord.Interaction, edit: bool = False):
    embed = build_menu_embed()
    view = MenuView()
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog本体
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Menu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="menu", description="BOTのメニューを開く")
    async def menu(self, interaction: discord.Interaction):
        await send_menu(interaction)


async def setup(bot):
    await bot.add_cog(Menu(bot))
