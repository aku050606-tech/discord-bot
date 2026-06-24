import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random

db = Database()

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "⭐", "💎", "7️⃣"]

PAYOUTS = {
    "💎💎💎": 50,
    "7️⃣7️⃣7️⃣": 30,
    "⭐⭐⭐": 15,
    "🍇🍇🍇": 10,
    "🍊🍊🍊": 8,
    "🍋🍋🍋": 5,
    "🍒🍒🍒": 3,
}

def spin_slots():
    return [random.choice(SLOT_SYMBOLS) for _ in range(3)]

def calculate_payout(reels: list, bet: int) -> tuple[int, str]:
    combo = "".join(reels)
    for pattern, multiplier in PAYOUTS.items():
        if combo == pattern:
            return bet * multiplier, pattern
    # 2つ揃いは1.5倍返し
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return int(bet * 1.5), "ペア"
    return 0, "ハズレ"


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slot", description="スロットマシンを回す！")
    @app_commands.describe(bet="賭けるナトコイン数（最低10）")
    async def slot(self, interaction: discord.Interaction, bet: int):
        if bet < 10:
            await interaction.response.send_message("❌ 最低10ナトコインから賭けられます", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)

        if bal < bet:
            await interaction.response.send_message(
                f"❌ ナトコインが足りません（残高: {bal:,} ナトコイン）", ephemeral=True
            )
            return

        # スピン
        reels = spin_slots()
        won, combo = calculate_payout(reels, bet)
        net = won - bet
        db.update_balance(user_id, guild_id, net)
        new_bal = db.get_balance(user_id, guild_id)

        # 結果表示
        reels_display = " | ".join(reels)

        if won > bet:
            color = discord.Color.gold()
            result_text = f"🎉 **{combo} 当たり！** +{won:,} ナトコイン (×{won//bet}倍)"
        elif won == bet:
            color = discord.Color.blue()
            result_text = f"😐 ペア！ 賭け金返還"
        else:
            color = discord.Color.red()
            result_text = f"😢 ハズレ... -{bet:,} ナトコイン"

        embed = discord.Embed(title="🎰 スロットマシン", color=color)
        embed.add_field(name="リール", value=f"[ {reels_display} ]", inline=False)
        embed.add_field(name="結果", value=result_text, inline=False)
        embed.add_field(
            name="残高",
            value=f"{new_bal:,} ナトコイン（{'+' if net >= 0 else ''}{net:,}）",
            inline=False
        )
        embed.set_footer(text=f"賭け: {bet:,} ナトコイン")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="coinflip", description="ナトコインを投げて賭けをする")
    @app_commands.describe(choice="表(heads)か裏(tails)か", bet="賭けるナトコイン数")
    @app_commands.choices(choice=[
        app_commands.Choice(name="表 (Heads)", value="heads"),
        app_commands.Choice(name="裏 (Tails)", value="tails"),
    ])
    async def coinflip(self, interaction: discord.Interaction, choice: str, bet: int):
        if bet < 10:
            await interaction.response.send_message("❌ 最低10ナトコインから賭けられます", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)

        if bal < bet:
            await interaction.response.send_message(
                f"❌ ナトコインが足りません（残高: {bal:,} ナトコイン）", ephemeral=True
            )
            return

        result = random.choice(["heads", "tails"])
        won = choice == result

        if won:
            db.update_balance(user_id, guild_id, bet)
            color = discord.Color.green()
            result_text = f"🎉 **当たり！** +{bet:,} ナトコイン"
        else:
            db.update_balance(user_id, guild_id, -bet)
            color = discord.Color.red()
            result_text = f"😢 **ハズレ！** -{bet:,} ナトコイン"

        result_emoji = "🪙表" if result == "heads" else "🪙裏"
        new_bal = db.get_balance(user_id, guild_id)

        embed = discord.Embed(title="🪙 コインフリップ", color=color)
        embed.add_field(name="結果", value=result_emoji, inline=True)
        embed.add_field(name="あなたの選択", value="表" if choice == "heads" else "裏", inline=True)
        embed.add_field(name="判定", value=result_text, inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Games(bot))
