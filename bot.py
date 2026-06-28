import os
import time
# ── タイムゾーン補助（保険）──
#   日替わりリセットは config.jst_today() の固定オフセット(+9)で判定しており、
#   システムTZやtzdataの有無に依存しない（Nixpacksにtzdataが無くても正しく0時JSTで切替）。
#   下の tzset はログ等の naive な時刻表示を一応JST寄りにするだけの保険。
os.environ["TZ"] = "Asia/Tokyo"
try:
    time.tzset()
except Exception:
    pass

import discord
from discord.ext import commands
from discord import app_commands
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
    await bot.load_extension("cogs.juggler")
    await bot.load_extension("cogs.fishing")
    await bot.load_extension("cogs.zukan")
    await bot.load_extension("cogs.chinchiro")
    await bot.load_extension("cogs.shop")
    await bot.load_extension("cogs.lfg")
    await bot.load_extension("cogs.fund")
    await bot.load_extension("cogs.voyage")
    await bot.load_extension("cogs.land")
    await bot.load_extension("cogs.blacksmith")
    await bot.load_extension("cogs.menu")
    await bot.load_extension("cogs.admin")
    await bot.load_extension("cogs.quests")
    await bot.load_extension("cogs.reactionroles")
    await bot.load_extension("cogs.tempvc")
    await bot.load_extension("cogs.activitystats")

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
