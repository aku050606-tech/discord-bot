import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from database import Database

# ボット設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()

# Cogを読み込む
async def load_extensions():
    await bot.load_extension("cogs.economy")
    await bot.load_extension("cogs.fortune")
    await bot.load_extension("cogs.auto_reply")
    await bot.load_extension("cogs.blackjack")
    await bot.load_extension("cogs.poker")
    await bot.load_extension("cogs.numguess")
    await bot.load_extension("cogs.teamsplit")
    await bot.load_extension("cogs.logger")
    await bot.load_extension("cogs.rewards")
    await bot.load_extension("cogs.slot")
    await bot.load_extension("cogs.fishing")
    await bot.load_extension("cogs.zukan")
    await bot.load_extension("cogs.chinchiro")
    await bot.load_extension("cogs.shop")
    await bot.load_extension("cogs.menu")
    await bot.load_extension("cogs.admin")

@bot.event
async def on_ready():
    print(f"✅ {bot.user} がオンラインになりました！")
    await bot.tree.sync()
    print("✅ スラッシュコマンドを同期しました")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

async def main():
    db.initialize()
    await load_extensions()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN が設定されていません")
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
