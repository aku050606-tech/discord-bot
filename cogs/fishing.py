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

def get_boosted_probs(area):
    base = dict(FISHING_PROBS[area])
    now = datetime.now(JST)
    hour, weekday = now.hour, now.weekday()
    month_day = (now.month, now.day)

    if month_day in FISHING_SPECIAL_DAYS:
        for rarity, mult in FISHING_SPECIAL_DAYS[month_day]["boost"].items():
            if rarity in base:
                base[rarity] *= mult

    if weekday in FISHING_WEEKDAY_BONUS:
        for rarity, mult in FISHING_WEEKDAY_BONUS[weekday]["boost"].items():
            if rarity in base:
                base[rarity] *= mult

    for period, info in FISHING_TIME_BONUS.items():
        if hour in info["hours"]:
            for rarity, mult in info["boost"].items():
                if rarity in base:
                    base[rarity] *= mult

    total = sum(base.values())
    return {k: v/total for k, v in base.items()}

def pick_rarity(probs):
    r = random.random()
    cumulative = 0
    for rarity, prob in probs.items():
        cumulative += prob
        if r < cumulative:
            return rarity
    return "trash"

def pick_fish(area, rarity):
    candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == rarity]
    if not candidates:
        candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == "common"]
    return random.choice(candidates)

def get_fishing_effect(rarity):
    if random.random() > FISHING_EFFECT_CHANCE:
        return None
    rarity_map = {
        "trash":      ["trash","trash_certain","both_extreme"],
        "common":     ["common","random"],
        "uncommon":   ["uncommon","common","random"],
        "rare":       ["rare","uncommon"],
        "super_rare": ["super_rare","rare","super_certain"],
        "legend":     ["legend","legend_certain","both_extreme","super_rare"],
        "boss":       ["legend_certain","super_certain"],
    }
    valid_types = rarity_map.get(rarity, ["random"])
    candidates = [e for e in FISHING_EFFECTS if e[1] in valid_types]
    if not candidates:
        return None
    return random.choice(candidates)[0]

async def do_fish(interaction, area, edit=False):
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

    # 金冠判定（ゴミ以外）
    is_golden = False
    golden_name = None
    if rarity != "trash" and random.random() < GOLDEN_CROWN_CHANCE:
        is_golden = True
        golden_name = f"大きな{fish['name']}"
        value = value * 2

    # 主の影（コモン・アンコモン時）
    show_shadow = False
    if rarity in ["common", "uncommon"] and random.random() < SHADOW_CHANCE:
        show_shadow = True

    if value > 0:
        db.update_balance(uid, guild_id, value)

    # 図鑑登録
    is_new = db.add_zukan(uid, area, fish["name"])

    # 金冠登録
    new_crown = False
    if is_golden:
        new_crown = db.add_crown(uid, area, fish["name"])

    # ボス登録チェック（ボスも図鑑に）
    if rarity == "boss":
        db.add_zukan(uid, area, AREA_BOSS[area]["name"])

    new_bal = db.get_balance(uid, guild_id)

    # 図鑑コンプチェック
    bonus_msg = ""
    fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
    all_fish_names = [f["name"] for f in fish_list]
    caught = db.get_zukan(uid, area)
    if set(all_fish_names).issubset(set(caught)):
        if not db.check_zukan_bonus(uid, f"complete_{area}"):
            db.set_zukan_bonus(uid, f"complete_{area}")
            db.update_balance(uid, guild_id, ZUKAN_COMPLETE_BONUS)
            new_bal = db.get_balance(uid, guild_id)
            bonus_msg = f"\n🎊 **{area_info['name']}図鑑コンプリート！** +{ZUKAN_COMPLETE_BONUS:,} コイン！"

    if not db.check_zukan_bonus(uid, "complete_all"):
        all_complete = True
        for a in ["lake","river","sea"]:
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

    effect = get_fishing_effect(rarity)
    color = RARITY_COLORS.get(rarity, 0x95a5a6)
    rarity_label = {
        "trash":"ゴミ","common":"コモン","uncommon":"アンコモン",
        "rare":"レア","super_rare":"スーパーレア","legend":"レジェンド","boss":"???",
    }.get(rarity, rarity)

    display_name = golden_name if is_golden else fish["name"]
    display_emoji = "👑" if is_golden else fish["emoji"]

    embed = discord.Embed(color=color)
    desc = f"{effect}\n\n" if effect else ""

    if rarity == "trash":
        embed.title = f"{fish['emoji']} {fish['name']}"
        desc += f"ゴミだった...\n換金額: **0コイン**"
    else:
        embed.title = f"{display_emoji} {display_name} を釣り上げた！"
        desc += f"レアリティ: **{rarity_label}**\n換金額: **{value:,} コイン**"
        if is_golden:
            desc += "\n👑 **金冠！** 通常の2倍！"
        if is_new:
            desc += "\n📖 **図鑑に新しく登録されました！**"
        if new_crown:
            desc += "\n👑 **図鑑に金冠マークが付きました！**"

    if bonus_msg:
        desc += bonus_msg

    embed.description = desc

    now = datetime.now(JST)
    month_day = (now.month, now.day)
    if month_day in FISHING_SPECIAL_DAYS:
        embed.set_author(name=FISHING_SPECIAL_DAYS[month_day]["label"])

    embed.set_footer(text=f"残高: {new_bal:,} コイン | {area_info['name']}")

    view = FishResultView(area, show_shadow, uid, guild_id)
    if edit:
        await interaction.response.edit_message(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class FishResultView(discord.ui.View):
    def __init__(self, area, show_shadow, uid, guild_id):
        super().__init__(timeout=60)
        self.area = area
        self.uid = uid
        self.guild_id = guild_id

        if show_shadow:
            self.add_item(ShadowButton(area, uid, guild_id))

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎣", row=1)
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, self.area, edit=True)

    @discord.ui.button(label="エリア選択へ", style=discord.ButtonStyle.secondary, emoji="🔙", row=1)
    async def back_area(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import FishMenuView
        embed = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="10コイン", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=FishMenuView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())


class ShadowButton(discord.ui.Button):
    def __init__(self, area, uid, guild_id):
        super().__init__(
            label="⚠️ 不穏な影が見える...垂らし続けますか？",
            style=discord.ButtonStyle.danger,
            row=0
        )
        self.area = area
        self.uid = uid
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        boss = AREA_BOSS[self.area]
        embed = discord.Embed(
            title="⚠️ DANGER!!!!",
            description=f"何か不穏な影が見える...\nこのまま釣竿を垂らしておきますか？",
            color=discord.Color.dark_red()
        )
        await interaction.response.edit_message(
            embed=embed,
            view=ShadowChoiceView(self.area, self.uid, self.guild_id)
        )


class ShadowChoiceView(discord.ui.View):
    def __init__(self, area, uid, guild_id):
        super().__init__(timeout=30)
        self.area = area
        self.uid = uid
        self.guild_id = guild_id

    @discord.ui.button(label="垂らし続ける", style=discord.ButtonStyle.danger, emoji="🎣")
    async def keep(self, interaction: discord.Interaction, button: discord.ui.Button):
        boss = AREA_BOSS[self.area]
        if random.random() < SHADOW_SUCCESS_RATE:
            db.update_balance(self.uid, self.guild_id, BOSS_REWARD)
            db.add_zukan(self.uid, self.area, boss["name"])
            new_bal = db.get_balance(self.uid, self.guild_id)
            embed = discord.Embed(
                title=f"💥 {boss['emoji']} {boss['name']} を釣り上げた！！！",
                description=f"伝説の生物が釣れた！！！\n換金額: **{BOSS_REWARD:,} コイン**\n残高: **{new_bal:,} コイン**",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="🌊 逃げられた...",
                description="影は深みへ消えていった...\nまた会えるかもしれない。",
                color=discord.Color.dark_blue()
            )
        from cogs.menu import FishMenuView
        embed2 = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=BackToFishView(self.area))

    @discord.ui.button(label="安全に引き上げる", style=discord.ButtonStyle.secondary, emoji="✋")
    async def pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✋ 安全に引き上げた",
            description="影は消えていった...\n次は挑戦してみよう！",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=BackToFishView(self.area))


class BackToFishView(discord.ui.View):
    def __init__(self, area):
        super().__init__(timeout=60)
        self.area = area

    @discord.ui.button(label="もう一回釣る！", style=discord.ButtonStyle.primary, emoji="🎣")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        await do_fish(interaction, self.area, edit=True)

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())


class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fish", description="釣りをする！湖・川・海から選ぼう")
    async def fish(self, interaction: discord.Interaction):
        from cogs.menu import FishMenuView
        embed = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="10コイン", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.send_message(embed=embed, view=FishMenuView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Fishing(bot))
