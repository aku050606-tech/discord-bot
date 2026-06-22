import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os

# ログを送るチャンネル名（存在しない場合は自動作成）
LOG_CHANNEL_NAME = "📋bot-log"

async def get_log_channel(guild: discord.Guild) -> discord.TextChannel:
    """ログチャンネルを取得、なければ作成"""
    channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME.replace("📋", "").strip())
    # 名前が絵文字入りの場合も探す
    for ch in guild.text_channels:
        if "bot-log" in ch.name:
            return ch

    # なければ作成（管理者のみ閲覧可能）
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    # 管理者ロールにも権限付与
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True)

    channel = await guild.create_text_channel(
        "bot-log",
        overwrites=overwrites,
        topic="BOTによる入退室・VC自動ログ"
    )
    return channel


def jst_now() -> str:
    """現在時刻をJSTで返す"""
    from datetime import timezone, timedelta
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y/%m/%d %H:%M:%S")


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # サーバー入退室ログ
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ch = await get_log_channel(member.guild)
        embed = discord.Embed(
            title="📥 メンバー参加",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=f"{member.mention}\n({member.name})", inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="アカウント作成日", value=member.created_at.strftime("%Y/%m/%d"), inline=True)
        embed.add_field(
            name="サーバー人数",
            value=f"{member.guild.member_count}人",
            inline=True
        )
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        ch = await get_log_channel(member.guild)
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        embed = discord.Embed(
            title="📤 メンバー退室",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=f"{member.name}", inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(
            name="参加日",
            value=member.joined_at.strftime("%Y/%m/%d") if member.joined_at else "不明",
            inline=True
        )
        embed.add_field(
            name="所持ロール",
            value=", ".join(roles) if roles else "なし",
            inline=False
        )
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # VC 入退室ログ
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        # 変化なし
        if before.channel == after.channel:
            return

        ch = await get_log_channel(member.guild)

        if before.channel is None and after.channel is not None:
            # VC参加
            embed = discord.Embed(
                title="🔊 VC参加",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="チャンネル", value=after.channel.name, inline=True)
            embed.set_footer(text=jst_now())
            await ch.send(embed=embed)

        elif before.channel is not None and after.channel is None:
            # VC退出
            embed = discord.Embed(
                title="🔇 VC退出",
                color=discord.Color.greyple(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="チャンネル", value=before.channel.name, inline=True)
            embed.set_footer(text=jst_now())
            await ch.send(embed=embed)

        else:
            # VCチャンネル移動
            embed = discord.Embed(
                title="🔀 VC移動",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="移動前", value=before.channel.name, inline=True)
            embed.add_field(name="移動後", value=after.channel.name, inline=True)
            embed.set_footer(text=jst_now())
            await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # コマンド：ログチャンネル確認
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @app_commands.command(name="logchannel", description="ログチャンネルの場所を確認・作成する（管理者用）")
    @app_commands.checks.has_permissions(administrator=True)
    async def logchannel(self, interaction: discord.Interaction):
        ch = await get_log_channel(interaction.guild)
        await interaction.response.send_message(
            f"✅ ログチャンネル: {ch.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Logger(bot))
