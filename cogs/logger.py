import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
from database import Database

db = Database()

# ── ログのカテゴリ（キー → 表示名）。すべて個別に送信先指定／OFF可能 ──
#   デフォルトは全カテゴリ未設定＝OFF（設定するまで何も出ない）。
LOG_CATEGORIES = {
    "member_join":    "📥 サーバー入室",
    "member_leave":   "📤 サーバー退室",
    "vc_join":        "🔊 VC入室",
    "vc_leave":       "🔇 VC退室",
    "vc_move":        "🔀 VC移動",
    "message_delete": "🗑️ メッセージ削除",
    "message_edit":   "🖊️ メッセージ編集",
    "ban":            "🔨 BAN",
    "kick":           "👢 KICK",
    "admin":          "🛠 管理操作",
    "announce":       "📣 手動アナウンス送信先",
    "bigwin":         "🎣 釣果・大勝利アナウンス送信先",
    "twitter":        "🐦 ツイート投稿先",
    "lfg":            "🎮 募集の投稿先",
}


async def resolve_log_channel(guild: discord.Guild, category: str):
    """カテゴリの送信先を解決する。
    ・ch指定あり → そのch
    ・未設定 / 'OFF' → None（送らない）  ※デフォルトは全部OFF
    """
    cid = db.get_log_channel_id(str(guild.id), category)
    if not cid or cid == "OFF":
        return None
    ch = guild.get_channel(int(cid))
    return ch  # 消えていれば None


def jst_now() -> str:
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst).strftime("%Y/%m/%d %H:%M:%S")


async def _recent_audit_actor(guild, action, target_id, within=12):
    """監査ログから、対象ユーザーへの直近アクションの実行者・理由を返す。
    取得できない（権限不足等）場合は (None, None)。"""
    try:
        async for entry in guild.audit_logs(limit=6, action=action):
            if entry.target and entry.target.id == target_id:
                age = (discord.utils.utcnow() - entry.created_at).total_seconds()
                if age <= within:
                    return entry.user, entry.reason
    except (discord.Forbidden, discord.HTTPException, Exception):
        pass
    return None, None


class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ サーバー入室 ━━
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ch = await resolve_log_channel(member.guild, "member_join")
        if ch is None:
            return
        embed = discord.Embed(title="📥 サーバー入室", color=discord.Color.green(),
                              timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=f"{member.mention}\n({member.name})", inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="アカウント作成日", value=member.created_at.strftime("%Y/%m/%d"), inline=True)
        embed.add_field(name="サーバー人数", value=f"{member.guild.member_count}人", inline=True)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ サーバー退室 / KICK ━━
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # kickか自主退室かを監査ログで判定
        actor, reason = await _recent_audit_actor(
            member.guild, discord.AuditLogAction.kick, member.id)

        if actor is not None:
            # KICK
            ch = await resolve_log_channel(member.guild, "kick")
            if ch is None:
                return
            embed = discord.Embed(title="👢 KICK", color=discord.Color.orange(),
                                  timestamp=discord.utils.utcnow())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="対象", value=f"{member.name}", inline=True)
            embed.add_field(name="ID", value=str(member.id), inline=True)
            embed.add_field(name="実行者", value=actor.mention, inline=True)
            embed.add_field(name="理由", value=reason or "（なし）", inline=False)
            embed.set_footer(text=jst_now())
            await ch.send(embed=embed)
            return

        # BAN由来の退室は on_member_ban 側で記録するのでここでは出さない（二重防止）
        ban_actor, _ = await _recent_audit_actor(
            member.guild, discord.AuditLogAction.ban, member.id)
        if ban_actor is not None:
            return

        # 通常退室
        ch = await resolve_log_channel(member.guild, "member_leave")
        if ch is None:
            return
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        embed = discord.Embed(title="📤 サーバー退室", color=discord.Color.red(),
                              timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ユーザー", value=f"{member.name}", inline=True)
        embed.add_field(name="ID", value=str(member.id), inline=True)
        embed.add_field(name="参加日",
                        value=member.joined_at.strftime("%Y/%m/%d") if member.joined_at else "不明",
                        inline=True)
        embed.add_field(name="所持ロール", value=", ".join(roles) if roles else "なし", inline=False)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ BAN ━━
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        actor, reason = await _recent_audit_actor(guild, discord.AuditLogAction.ban, user.id)
        ch = await resolve_log_channel(guild, "ban")
        if ch is None:
            return
        embed = discord.Embed(title="🔨 BAN", color=discord.Color.dark_red(),
                              timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="対象", value=f"{user.name}", inline=True)
        embed.add_field(name="ID", value=str(user.id), inline=True)
        embed.add_field(name="実行者", value=actor.mention if actor else "不明", inline=True)
        embed.add_field(name="理由", value=reason or "（なし）", inline=False)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ VC 入室 / 退室 / 移動 ━━
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return

        if before.channel is None and after.channel is not None:
            # VC入室
            ch = await resolve_log_channel(member.guild, "vc_join")
            if ch is None:
                return
            embed = discord.Embed(title="🔊 VC入室", color=discord.Color.blurple(),
                                  timestamp=discord.utils.utcnow())
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="チャンネル", value=after.channel.name, inline=True)

        elif before.channel is not None and after.channel is None:
            # VC退室
            ch = await resolve_log_channel(member.guild, "vc_leave")
            if ch is None:
                return
            embed = discord.Embed(title="🔇 VC退室", color=discord.Color.greyple(),
                                  timestamp=discord.utils.utcnow())
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="チャンネル", value=before.channel.name, inline=True)

        else:
            # VC移動
            ch = await resolve_log_channel(member.guild, "vc_move")
            if ch is None:
                return
            embed = discord.Embed(title="🔀 VC移動", color=discord.Color.orange(),
                                  timestamp=discord.utils.utcnow())
            embed.add_field(name="ユーザー", value=f"{member.mention} ({member.name})", inline=True)
            embed.add_field(name="移動前", value=before.channel.name, inline=True)
            embed.add_field(name="移動後", value=after.channel.name, inline=True)

        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ メッセージ削除 ━━
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        ch = await resolve_log_channel(message.guild, "message_delete")
        if ch is None or ch.id == message.channel.id:
            return
        content = message.content or "（本文なし／取得不可）"
        if len(content) > 1000:
            content = content[:1000] + " …"
        embed = discord.Embed(title="🗑️ メッセージ削除", color=discord.Color.dark_grey(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="投稿者", value=f"{message.author.mention} ({message.author.name})", inline=True)
        embed.add_field(name="チャンネル", value=message.channel.mention, inline=True)
        embed.add_field(name="内容", value=content, inline=False)
        if message.attachments:
            files = "\n".join(a.filename for a in message.attachments)
            embed.add_field(name="添付", value=files, inline=False)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ メッセージ編集 ━━
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild is None or after.author.bot:
            return
        # 本文に変化がない（埋め込み展開やピン留め等）は無視
        if before.content == after.content:
            return
        ch = await resolve_log_channel(after.guild, "message_edit")
        if ch is None or ch.id == after.channel.id:
            return
        b = before.content or "（取得不可）"
        a = after.content or "（取得不可）"
        if len(b) > 500:
            b = b[:500] + " …"
        if len(a) > 500:
            a = a[:500] + " …"
        embed = discord.Embed(title="🖊️ メッセージ編集", color=discord.Color.gold(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="投稿者", value=f"{after.author.mention} ({after.author.name})", inline=True)
        embed.add_field(name="チャンネル", value=after.channel.mention, inline=True)
        embed.add_field(name="編集前", value=b, inline=False)
        embed.add_field(name="編集後", value=a, inline=False)
        embed.add_field(name="メッセージ", value=f"[ジャンプ]({after.jump_url})", inline=False)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ コマンド ━━
    @app_commands.command(name="logchannel", description="ログchの現在設定を表示する（管理者用）")
    @app_commands.checks.has_permissions(administrator=True)
    async def logchannel(self, interaction: discord.Interaction):
        cfg = db.get_all_log_config(str(interaction.guild.id))
        lines = []
        for key, name in LOG_CATEGORIES.items():
            cid = cfg.get(key)
            if cid and cid != "OFF":
                ch = interaction.guild.get_channel(int(cid))
                state = ch.mention if ch else "⚠️ ch消失"
            else:
                state = "🔕 OFF"
            lines.append(f"{name}： {state}")
        embed = discord.Embed(title="📋 ログ設定", description="\n".join(lines),
                              color=discord.Color.blurple())
        embed.set_footer(text="設定変更は /admin の「📋 ログ設定」から")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Logger(bot))
