import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from datetime import date
from config import DAILY_AMOUNT
from quest_tracker import record as quest_record

db = Database()

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="balance", description="所持ナトコインを確認する")
    async def balance(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)

        embed = discord.Embed(title="💰 残高確認", color=discord.Color.gold())
        embed.add_field(name=interaction.user.display_name, value=f"**{bal:,} ナトコイン**", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description=f"毎日のボーナスナトコインをもらう（{DAILY_AMOUNT}ナトコイン）")
    async def daily(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        today = str(date.today())
        last = db.get_last_daily(user_id, guild_id)

        if last == today:
            await interaction.response.send_message(
                "⏰ 今日はすでにデイリーボーナスを受け取っています！明日また来てね。",
                ephemeral=True
            )
            return

        db.update_balance(user_id, guild_id, DAILY_AMOUNT)
        db.set_last_daily(user_id, guild_id, today)
        bal = db.get_balance(user_id, guild_id)

        embed = discord.Embed(
            title="🎁 デイリーボーナス！",
            description=f"**+{DAILY_AMOUNT} ナトコイン** をゲット！\n現在の残高: **{bal:,} ナトコイン**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="send_coin", description="他のユーザーにナトコインを送る")
    @app_commands.describe(target="送り先ユーザー", amount="送るナトコイン数")
    async def send_coin(self, interaction: discord.Interaction, target: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ 1以上の数を指定してください", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("❌ BOTには送れません", ephemeral=True)
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message("❌ 自分自身には送れません", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        target_id = str(target.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)

        if bal < amount:
            await interaction.response.send_message(
                f"❌ ナトコインが足りません（残高: {bal:,} ナトコイン）", ephemeral=True
            )
            return

        db.update_balance(user_id, guild_id, -amount)
        db.update_balance(target_id, guild_id, amount)
        quest_record(user_id, guild_id, "send")   # 送金クエスト

        embed = discord.Embed(
            title="💸 送金完了",
            description=(
                f"{interaction.user.mention} → {target.mention}\n"
                f"**{amount:,} ナトコイン** を送りました！"
            ),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ranking", description="ナトコインランキングを表示する")
    async def ranking(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        rows = db.get_ranking(guild_id, limit=10)

        embed = discord.Embed(title="🏆 ナトコインランキング", color=discord.Color.gold())
        medals = ["🥇", "🥈", "🥉"]

        if not rows:
            embed.description = "まだデータがありません"
        else:
            lines = []
            for i, (uid, bal) in enumerate(rows):
                medal = medals[i] if i < 3 else f"{i+1}."
                try:
                    member = interaction.guild.get_member(int(uid))
                    name = member.display_name if member else f"ID:{uid}"
                except:
                    name = f"ID:{uid}"
                lines.append(f"{medal} **{name}** — {bal:,} ナトコイン")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
