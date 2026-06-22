import discord
from discord.ext import commands, tasks
from database import Database
from config import VC_REWARD_COINS, VC_REWARD_INTERVAL, CHAT_REWARD_COINS
from datetime import datetime, timezone, timedelta
import asyncio

db = Database()
JST = timezone(timedelta(hours=9))

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

async def setup(bot):
    await bot.add_cog(Rewards(bot))
