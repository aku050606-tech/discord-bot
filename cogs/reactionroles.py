import discord
from discord.ext import commands
from database import Database

db = Database()


def emoji_key(emoji) -> str:
    """PartialEmoji/Emoji を保存・照合用のキーに正規化する。
    ・カスタム絵文字 → ID文字列
    ・標準（Unicode）絵文字 → その文字そのもの
    """
    if getattr(emoji, "id", None):
        return str(emoji.id)
    return emoji.name


class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        if payload.member and payload.member.bot:
            return
        role_id = db.get_reaction_role_id(str(payload.message_id), emoji_key(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        role = guild.get_role(int(role_id))
        member = payload.member or guild.get_member(payload.user_id)
        if role is None or member is None:
            return
        try:
            await member.add_roles(role, reason="リアクションロール")
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None:
            return
        role_id = db.get_reaction_role_id(str(payload.message_id), emoji_key(payload.emoji))
        if not role_id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        role = guild.get_role(int(role_id))
        member = guild.get_member(payload.user_id)
        if role is None or member is None:
            return
        try:
            await member.remove_roles(role, reason="リアクションロール解除")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
