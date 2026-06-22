import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
from datetime import datetime, timezone, timedelta

db = Database()
JST = timezone(timedelta(hours=9))

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}

def get_boosted_probs(area: str) -> dict:
    base = dict(FISHING_PROBS[area])
    now = datetime.now(JST)
    hour, weekday = now.hour, now.weekday()
    month_day = (now.month, now.day)

    # 特定日ボーナス
    if month_day in FISHING_SPECIAL_DAYS:
        for rarity, mult in FISHING_SPECIAL_DAYS[month_day]["boost"].items():
            if rarity in base:
                base[rarity] *= mult

    # 曜日ボーナス
    if weekday in FISHING_WEEKDAY_BONUS:
        for rarity, mult in FISHING_WEEKDAY_BONUS[weekday]["boost"].items():
            if rarity in base:
                base[rarity] *= mult

    # 時間帯ボーナス
    for period, info in FISHING_TIME_BONUS.items():
        if hour in info["hours"]:
            for rarity, mult in info["boost"].items():
                if rarity in base:
                    base[rarity] *= mult

    # 正規化
    total = sum(base.values())
    return {k: v/total for k, v in base.items()}

def pick_rarity(probs: dict) -> str:
    r = random.random()
    cumulative = 0
    for rarity, prob in probs.items():
        cumulative += prob
        if r < cumulative:
            return rarity
    return "trash"

def pick_fish(area: str, rarity: str) -> dict:
    candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == rarity]
    if not candidates:
        candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == "common"]
    return random.choice(candidates)

def get_fishing_effect(rarity: str) -> str | None:
    if random.random() > FISHING_EFFECT_CHANCE:
        return None

    rarity_map = {
        "trash":      ["trash", "trash_certain", "both_extreme"],
        "common":     ["common", "random"],
        "uncommon":   ["uncommon", "common", "random"],
        "rare":       ["rare", "uncommon"],
        "super_rare": ["super_rare", "rare", "super_certain"],
        "legend":     ["legend", "legend_certain", "both_extreme", "super_rare"],
    }
    valid_types = rarity_map.get(rarity, ["random"])
    candidates = [e for e in FISHING_EFFECTS if e[1] in valid_types]
    if not candidates:
        return None
    return random.choice(candidates)[0]

async def do_fish(interaction: discord.Interaction, area: str, edit: bool = False):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    area_info = FISHING_AREAS[area]
    cost = area_info["cost"]

    bal = db.get_balance(uid, guild_id)
    if bal < cost:
        msg = f"❌ コインが足りません（残高: {bal:,}）"
        if edit:
            await interaction.response.edit_message(content=msg, embed=None, view=None)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if cost > 0:
        db.update_balance(uid, guild_id, -cost)

    probs = get_boosted_probs(area)
    rarity = pick_rarity(probs)
    fish = pick_fish(area, rarity)
    value = fish["value"]

    if value > 0:
        db.update_balance(uid, guild_id, value)

    # 図鑑登録
    is_new = db.add_zukan(uid, area, fish["name"])
    new_bal = db.get_balance(uid, guild_id)

    # 図鑑コンプチェック
    bonus_msg = ""
    fish_list = FISH_BY_AREA[area]
    all_fish_names = [f["name"] for f in fish_list if f["rarity"] != "trash"]
    caught = db.get_zukan(uid, area)
    if set(all_fish_names).issubset(set(caught)):
        if not db.check_zukan_bonus(uid, f"complete_{area}"):
            db.set_zukan_bonus(uid, f"complete_{area}")
            db.update_balance(uid, guild_id, ZUKAN_COMPLETE_BONUS)
            new_bal = db.get_balance(uid, guild_id)
            bonus_msg = f"\n🎊 **{area_info['name']}図鑑コンプリート！** +{ZUKAN_COMPLETE_BONUS:,} コイン！"

    # 全エリアコンプチェック
    if not db.check_zukan_bonus(uid, "complete_all"):
        all_complete = True
        for a in ["lake", "river", "sea"]:
            a_fish = [f["name"] for f in FISH_BY_AREA[a] if f["rarity"] != "trash"]
            a_caught = db.get_zukan(uid, a)
            if not set(a_fish).issubset(set(a_caught)):
                all_complete = False
                break
        if all_complete:
            db.set_zukan_bonus(uid, "complete_all")
            db.update_balance(uid, guild_id, ZUKAN_ALL_BONUS)
            new_bal = db.get_balance(uid, guild_id)
            bonus_msg += f"\n🌟 **全図鑑コンプリート！** +{ZUKAN_ALL_BONUS:,} コイン！！"

    # 演出
    effect = get_fishing_effect(rarity)

    color = RARITY_COLORS.get(rarity, 0x95a5a6)
    rarity_label = {
        "trash": "ゴミ", "common": "コモン", "uncommon": "アンコモン",
        "rare": "レア", "super_rare": "スーパーレア", "legend": "レジェンド"
    }.get(rarity, rarity)

    embed = discord.Embed(color=color)

    if effect:
        embed.description = f"{effect}\n\n"
    else:
        embed.description = ""

    if rarity == "trash":
        embed.title = f"{fish['emoji']} {fish['name']}"
        embed.description += f"ゴミだった...\n換金額: **0コイン**"
    else:
        embed.title = f"{fish['emoji']} {fish['name']} を釣り上げた！"
        embed.description += f"レアリティ: **{rarity_label}**\n換金額: **{value:,} コイン**"
        if is_new:
            embed.description += "\n📖 **図鑑に新しく登録されました！**"

    if bonus_msg:
        embed.description += bonus_msg

    embed.set_footer(text=f"残高: {new_bal:,} コイン | {area_info['name']}")

    # 特定日表示
    now = datetime.now(JST)
    month_day = (now.month, now.day)
    if month_day in FISHING_SPECIAL_DAYS:
        embed.set_author(name=FISHING_SPECIAL_DAYS[month_day]["label"])

    view = FishAgainView(area)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)

class FishAgainView(discord.ui.View):
    def __init__(self, area: str):
        super().__init__(timeout=60)
        self.area = area

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎣")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, self.area, edit=True)

    @discord.ui.button(label="エリア選択へ", style=discord.ButtonStyle.secondary, emoji="🏠")
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🎣 釣り — エリア選択", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="無料", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=FishAreaView())

class FishAreaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🏞️ 湖（無料）", style=discord.ButtonStyle.success)
    async def lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, "lake", edit=True)

    @discord.ui.button(label="🏔️ 川（50コイン）", style=discord.ButtonStyle.primary)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, "river", edit=True)

    @discord.ui.button(label="🌊 海（100コイン）", style=discord.ButtonStyle.danger)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, "sea", edit=True)

class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fish", description="釣りをする！湖・川・海から選ぼう")
    async def fish(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎣 釣り — エリア選択",
            color=discord.Color.blue()
        )
        embed.add_field(name="🏞️ 湖", value="無料 | 出率110%", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン | 出率110%", inline=True)
        embed.add_field(name="🌊 海", value="100コイン | 出率110%", inline=True)
        await interaction.response.send_message(embed=embed, view=FishAreaView())

async def setup(bot):
    await bot.add_cog(Fishing(bot))
