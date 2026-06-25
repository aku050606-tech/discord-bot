import discord
from discord.ext import commands, tasks
from database import Database
from config import VC_REWARD_COINS, VC_REWARD_INTERVAL, CHAT_REWARD_COINS
from datetime import datetime, timezone, timedelta
import asyncio
import time
from quest_tracker import record as quest_record

db = Database()
JST = timezone(timedelta(hours=9))

# VC自動ロールの設定（log_config を汎用KVとして流用）
VC_AUTOROLE_ROLE = "vc_autorole_role"    # ロールID or 'OFF'
VC_AUTOROLE_HOURS = "vc_autorole_hours"  # 必要時間（時間・文字列）

class Rewards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vc_reward_loop.start()

    def cog_unload(self):
        self.vc_reward_loop.cancel()

    # VC入室記録
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        uid = str(member.id)
        gid = str(member.guild.id)
        now = datetime.now(JST).isoformat()

        if before.channel is None and after.channel is not None:
            db.set_vc_join(uid, gid, now)
        elif before.channel is not None and after.channel is None:
            db.remove_vc_join(uid, gid)

    # 5分ごとにVC報酬付与
    @tasks.loop(seconds=VC_REWARD_INTERVAL)
    async def vc_reward_loop(self):
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    uid = str(member.id)
                    gid = str(guild.id)
                    if db.get_vc_join(uid, gid):
                        db.update_balance(uid, gid, VC_REWARD_COINS)
                        quest_record(uid, gid, "vc")   # VC5分参加クエスト
                        # 累計VC時間を加算（5分=VC_REWARD_INTERVAL秒）
                        now_iso = datetime.now(JST).isoformat()
                        db.add_vc_seconds(uid, gid, VC_REWARD_INTERVAL, now_iso)
                        db.log_activity(gid, uid, "vc", VC_REWARD_INTERVAL, time.time())
                        await self._check_vc_autorole(member, gid)

    async def _check_vc_autorole(self, member, gid):
        """累計VC時間が閾値を超えたら、設定ロールを自動付与する。"""
        role_id = db.get_log_channel_id(gid, VC_AUTOROLE_ROLE)
        if not role_id or role_id == "OFF":
            return
        hours_raw = db.get_log_channel_id(gid, VC_AUTOROLE_HOURS)
        try:
            need_secs = float(hours_raw) * 3600 if hours_raw else None
        except (TypeError, ValueError):
            need_secs = None
        if not need_secs:
            return
        if db.get_vc_seconds(member.id, gid) < need_secs:
            return
        role = member.guild.get_role(int(role_id))
        if role is None or role in member.roles:
            return
        try:
            await member.add_roles(role, reason=f"VC累計{hours_raw}時間達成")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @vc_reward_loop.before_loop
    async def before_vc_loop(self):
        await self.bot.wait_until_ready()

    # チャット報酬
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return
        uid = str(message.author.id)
        gid = str(message.guild.id)
        db.update_balance(uid, gid, CHAT_REWARD_COINS)
        quest_record(uid, gid, "chat")   # チャットクエスト
        db.touch_active(uid, gid, datetime.now(JST).isoformat())   # 最終活動を更新
        db.log_activity(gid, uid, "chat", 1, time.time())          # 時間帯別チャット数

async def setup(bot):
    await bot.add_cog(Rewards(bot))
