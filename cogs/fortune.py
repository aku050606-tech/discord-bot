import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import date

FORTUNES = [
    ("大吉", discord.Color.gold(), "🌟", "最高の一日になりそう！何でも積極的に挑戦しよう！"),
    ("吉",   discord.Color.green(), "✨", "良いことが起きる予感。前向きに過ごそう！"),
    ("中吉", discord.Color.blue(), "💙", "まずまずの運勢。コツコツと努力が報われる。"),
    ("小吉", discord.Color.teal(), "🌀", "小さな幸せを大切に。油断は禁物。"),
    ("末吉", discord.Color.blurple(), "🌙", "今日は慎重に行動すると吉。"),
    ("凶",   discord.Color.orange(), "⚠️", "少し運が弱い日。無理せず休息を。"),
    ("大凶", discord.Color.red(), "💀", "要注意の一日。慎重に、でも大丈夫！明日はきっと良くなる。"),
]

LUCKY_ITEMS = ["コーヒー", "青色のペン", "ネコ", "左手", "古い本", "星形のもの", "水", "音楽"]
LUCKY_COLORS = ["赤", "青", "緑", "金", "白", "黒", "紫", "オレンジ"]
LUCKY_NUMBERS = list(range(1, 100))

ASPECTS = {
    "💰 金運": ["最高潮！", "良好", "普通", "節約が吉", "出費に注意"],
    "❤️ 恋愛運": ["ドキドキの展開が！", "良い出会いの予感", "現状維持", "すれ違いに注意", "焦らずに"],
    "💼 仕事運": ["大チャンス！", "努力が実る", "着実に前進", "ミスに注意", "休息が必要"],
    "🏃 健康運": ["絶好調！", "元気いっぱい", "無理しない", "休息が大事", "体調管理を"],
}


class Fortune(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fortune", description="今日の運勢を占う")
    async def fortune(self, interaction: discord.Interaction):
        # ユーザーID + 日付でシードを固定（1日1回同じ結果）
        seed = int(str(interaction.user.id) + str(date.today()).replace("-", ""))
        rng = random.Random(seed)

        name, color, emoji, message = rng.choice(FORTUNES)
        lucky_item = rng.choice(LUCKY_ITEMS)
        lucky_color = rng.choice(LUCKY_COLORS)
        lucky_number = rng.choice(LUCKY_NUMBERS)

        embed = discord.Embed(
            title=f"{emoji} 今日の運勢: **{name}**",
            description=message,
            color=color
        )
        embed.set_author(
            name=f"{interaction.user.display_name} の運勢",
            icon_url=interaction.user.display_avatar.url
        )

        # 各運勢
        for aspect, options in ASPECTS.items():
            val = rng.choice(options)
            embed.add_field(name=aspect, value=val, inline=True)

        embed.add_field(name="🍀 ラッキーアイテム", value=lucky_item, inline=True)
        embed.add_field(name="🎨 ラッキーカラー", value=lucky_color, inline=True)
        embed.add_field(name="🔢 ラッキーナンバー", value=str(lucky_number), inline=True)
        embed.set_footer(text=f"📅 {date.today()} の運勢（毎日更新）")

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Fortune(bot))
