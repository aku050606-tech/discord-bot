import discord
from discord.ext import commands
from discord import app_commands
import random

class TeamSplit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="teamsplit", description="1〜10番のプレイヤーをランダムに5:5でチーム分け")
    async def teamsplit(self, interaction: discord.Interaction):
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])

        embed = discord.Embed(
            title="⚔️ チーム分け結果",
            description="プレイヤー番号をランダムに5:5で分けました！",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔵 チーム1（ブルー）",
            value=" / ".join(f"**{p}番**" for p in team1),
            inline=False
        )
        embed.add_field(
            name="🔴 チーム2（レッド）",
            value=" / ".join(f"**{p}番**" for p in team2),
            inline=False
        )
        embed.set_footer(text="もう一度ランダムにしたい場合は /teamsplit を再実行")

        view = ResplitView()
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="teamsplit_custom", description="メンバー名を指定してチーム分け（スペース区切りで入力）")
    @app_commands.describe(members="メンバー名をスペースで区切って入力（例: Alice Bob Carol Dave Eve Frank ...）")
    async def teamsplit_custom(self, interaction: discord.Interaction, members: str):
        names = [n.strip() for n in members.split() if n.strip()]

        if len(names) < 2:
            await interaction.response.send_message("❌ 2人以上入力してください", ephemeral=True)
            return
        if len(names) > 20:
            await interaction.response.send_message("❌ 20人までです", ephemeral=True)
            return

        random.shuffle(names)
        mid = len(names) // 2
        team1 = names[:mid]
        team2 = names[mid:]

        embed = discord.Embed(
            title="⚔️ チーム分け結果",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"🔵 チーム1（{len(team1)}人）",
            value="\n".join(f"• {n}" for n in team1),
            inline=True
        )
        embed.add_field(
            name=f"🔴 チーム2（{len(team2)}人）",
            value="\n".join(f"• {n}" for n in team2),
            inline=True
        )

        await interaction.response.send_message(embed=embed)


class ResplitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="もう一度シャッフル", style=discord.ButtonStyle.secondary, emoji="🔀")
    async def resplit(self, interaction: discord.Interaction, button: discord.ui.Button):
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])

        embed = discord.Embed(
            title="⚔️ チーム分け結果",
            description="プレイヤー番号をランダムに5:5で分けました！",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🔵 チーム1（ブルー）",
            value=" / ".join(f"**{p}番**" for p in team1),
            inline=False
        )
        embed.add_field(
            name="🔴 チーム2（レッド）",
            value=" / ".join(f"**{p}番**" for p in team2),
            inline=False
        )
        embed.set_footer(text="もう一度ランダムにしたい場合はボタンを押して")
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot):
    await bot.add_cog(TeamSplit(bot))
