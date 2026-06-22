import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random

db = Database()

# 進行中ゲーム: {user_id: {answer, tries, bet, max_tries}}
active_games: dict[str, dict] = {}

MAX_TRIES = 7

class NumberGuess(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="numguess", description="1〜100の数字を当てよう！当てるほど高配当")
    @app_commands.describe(bet="賭けるコイン数（最低10）")
    async def numguess(self, interaction: discord.Interaction, bet: int):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if user_id in active_games:
            await interaction.response.send_message(
                "❌ すでにゲーム中です。`/guess [数字]` で続けてください", ephemeral=True
            )
            return

        if bet < 10:
            await interaction.response.send_message("❌ 最低10コインから", ephemeral=True)
            return

        bal = db.get_balance(user_id, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(user_id, guild_id, -bet)
        answer = random.randint(1, 100)
        active_games[user_id] = {
            "answer": answer,
            "tries": 0,
            "bet": bet,
            "guild_id": guild_id,
            "hints": []
        }

        embed = discord.Embed(
            title="🎯 数字当てゲーム",
            description=(
                f"1〜100の数字を当ててください！\n"
                f"最大 **{MAX_TRIES}回** まで挑戦できます。\n"
                f"早く当てるほど配当アップ！\n\n"
                f"`/guess [数字]` で答えを入力してね"
            ),
            color=discord.Color.blurple()
        )

        multipliers = {1: "×20", 2: "×15", 3: "×10", 4: "×7", 5: "×5", 6: "×3", 7: "×1.5"}
        table = "\n".join(f"{t}回目 → {m}" for t, m in multipliers.items())
        embed.add_field(name="💰 配当表", value=table, inline=False)
        embed.set_footer(text=f"賭け: {bet:,} コイン")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="guess", description="数字当てゲームで数字を入力する")
    @app_commands.describe(number="予想する数字（1〜100）")
    async def guess(self, interaction: discord.Interaction, number: int):
        user_id = str(interaction.user.id)

        if user_id not in active_games:
            await interaction.response.send_message(
                "❌ ゲームが始まっていません。`/numguess` でスタート", ephemeral=True
            )
            return

        if number < 1 or number > 100:
            await interaction.response.send_message("❌ 1〜100の数字を入力してください", ephemeral=True)
            return

        game = active_games[user_id]
        game["tries"] += 1
        answer = game["answer"]
        tries = game["tries"]
        bet = game["bet"]
        guild_id = game["guild_id"]

        multipliers = {1: 20, 2: 15, 3: 10, 4: 7, 5: 5, 6: 3, 7: 1.5}

        if number == answer:
            mult = multipliers.get(tries, 1)
            winnings = int(bet * mult)
            db.update_balance(user_id, guild_id, winnings)
            new_bal = db.get_balance(user_id, guild_id)
            active_games.pop(user_id)

            embed = discord.Embed(
                title="🎯 正解！",
                description=f"答えは **{answer}** でした！\n{tries}回目で正解 → **{mult}倍** 配当！",
                color=discord.Color.gold()
            )
            embed.add_field(name="獲得コイン", value=f"+{winnings:,} コイン", inline=True)
            embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)
            await interaction.response.send_message(embed=embed)

        elif tries >= MAX_TRIES:
            active_games.pop(user_id)
            embed = discord.Embed(
                title="💀 ゲームオーバー",
                description=f"正解は **{answer}** でした！\n{MAX_TRIES}回全て外れ... -{bet:,} コイン",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

        else:
            hint = "📈 もっと大きい！" if number < answer else "📉 もっと小さい！"
            remaining = MAX_TRIES - tries
            embed = discord.Embed(
                title="🎯 数字当てゲーム",
                description=f"**{number}** は違います。{hint}",
                color=discord.Color.blurple()
            )
            embed.add_field(name="残り回数", value=f"{remaining}回", inline=True)
            embed.add_field(name="次の配当", value=f"×{multipliers.get(tries+1, 1)}", inline=True)
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="guess_quit", description="数字当てゲームを途中でやめる（賭け金没収）")
    async def guess_quit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if user_id not in active_games:
            await interaction.response.send_message("❌ ゲームが始まっていません", ephemeral=True)
            return
        game = active_games.pop(user_id)
        await interaction.response.send_message(
            f"🏳️ ゲームを終了しました。答えは **{game['answer']}** でした（賭け金 {game['bet']:,} コイン没収）",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(NumberGuess(bot))
