import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
import asyncio
from datetime import datetime, timezone, timedelta

db = Database()
JST = timezone(timedelta(hours=9))

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}

def get_gear_probs(area: str, gear: dict) -> dict:
    """装備込みの確率を計算"""
    rod_id = gear["rod_id"]
    rod = FISHING_RODS[rod_id]

    # 竿の基本確率
    if rod.get("sea_ban") and area == "sea":
        return None  # 海禁止

    base = dict(rod["probs"])

    # リールのスーパーレアボーナス
    reel = FISHING_REELS[gear["reel_id"]]
    if reel["super_rare_bonus"] > 0:
        bonus = reel["super_rare_bonus"]
        base["super_rare"] = base.get("super_rare", 0) + bonus
        # 増加分をゴミ・コモン・アンコモンから比率で引く
        total_reducible = base.get("trash",0) + base.get("common",0) + base.get("uncommon",0)
        if total_reducible > 0:
            for k in ["trash","common","uncommon"]:
                if k in base:
                    base[k] -= bonus * (base[k] / total_reducible)

    # ボスボーナス
    boss_bonus = reel.get("boss_bonus", 0)
    if boss_bonus > 0 and rod_id in ["titanium","legend"]:
        base["boss"] = base.get("boss", 0) + boss_bonus

    # 時間帯・曜日・特定日ボーナス
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

    # 正規化
    total = sum(v for v in base.values() if v > 0)
    return {k: max(0, v/total) for k, v in base.items()}

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

def get_fishing_effect(rarity: str) -> str:
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
        candidates = [e for e in FISHING_EFFECTS if e[1] == "random"]
    return random.choice(candidates)[0]

async def do_fish(interaction: discord.Interaction, area: str, edit: bool = False):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    area_info = FISHING_AREAS[area]
    cost = area_info["cost"]

    # 装備取得
    gear = db.get_gear(uid)

    # 海禁止チェック
    rod = FISHING_RODS[gear["rod_id"]]
    if rod.get("sea_ban") and area == "sea":
        msg = "❌ 竹竿では海に行けません！グラスロッド以上が必要です。"
        if edit:
            await interaction.response.edit_message(content=msg, embed=None, view=None)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

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

    # 確率計算
    probs = get_gear_probs(area, gear)

    # 装備使用回数を減らす
    if gear["rod_uses"] < 999999:
        gear["rod_uses"] -= 1
        if gear["rod_uses"] <= 0:
            # 竿切れ→次の竿に切り替え or 竹竿に戻る
            inv = gear["rod_inventory"]
            inv.pop(gear["rod_id"], None)
            if inv:
                next_rod = max(inv.keys(), key=lambda r: FISHING_RODS[r]["price"])
                gear["rod_id"] = next_rod
                gear["rod_uses"] = inv[next_rod]
            else:
                gear["rod_id"] = "bamboo"
                gear["rod_uses"] = 999999
                gear["rod_inventory"] = {"bamboo": 999999}

    if gear["reel_uses"] < 999999:
        gear["reel_uses"] -= 1
        if gear["reel_uses"] <= 0:
            gear["reel_id"] = "spinning"
            gear["reel_uses"] = 999999
            gear["reel_inventory"] = {"spinning": 999999}

    if gear["line_uses"] < 999999:
        gear["line_uses"] -= 1
        if gear["line_uses"] <= 0:
            gear["line_id"] = "nylon"
            gear["line_uses"] = 999999
            gear["line_inventory"] = {"nylon": 999999}

    db.save_gear(uid, gear)

    # 釣り結果
    rarity = pick_rarity(probs)

    # ボス処理
    show_shadow = False
    if rarity == "boss":
        show_shadow = True
        rarity = pick_rarity({k:v for k,v in probs.items() if k != "boss"})

    # コモン・アンコモン時も主の影チェック
    if rarity in ["common","uncommon"] and random.random() < SHADOW_CHANCE:
        rod_id = gear["rod_id"]
        if rod_id in ["titanium","legend"]:
            show_shadow = True

    fish = pick_fish(area, rarity)
    value = fish["value"]

    # 金冠判定
    line = FISHING_LINES[gear["line_id"]]
    crown_chance = GOLDEN_CROWN_CHANCE + line["crown_bonus"]
    is_golden = rarity != "trash" and random.random() < crown_chance
    if is_golden:
        value = value * 2

    if value > 0:
        db.update_balance(uid, guild_id, value)

    # 図鑑登録
    is_new = db.add_zukan(uid, area, fish["name"])
    new_crown = False
    if is_golden:
        new_crown = db.add_crown(uid, area, fish["name"])

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

    # 演出
    effect = get_fishing_effect(rarity)
    wait_time = FISHING_WAIT_SUPER if rarity in ["super_rare","legend","boss"] else FISHING_WAIT_NORMAL

    color = RARITY_COLORS.get(rarity, 0x95a5a6)
    rarity_label = {
        "trash":"ゴミ","common":"コモン","uncommon":"アンコモン",
        "rare":"レア","super_rare":"スーパーレア","legend":"レジェンド","boss":"???",
    }.get(rarity, rarity)

    display_name = f"大きな{fish['name']}" if is_golden else fish["name"]
    display_emoji = "👑" if is_golden else fish["emoji"]

    # 演出→待機→・・・→待機→結果
    # まず演出を表示
    embed1 = discord.Embed(description=effect, color=color)
    embed1.set_footer(text=area_info["name"])

    if edit:
        await interaction.response.edit_message(embed=embed1, view=None)
    else:
        await interaction.response.send_message(embed=embed1, view=None, ephemeral=True)

    await asyncio.sleep(wait_time)

    # ・・・
    embed2 = discord.Embed(description="・・・", color=color)
    await interaction.edit_original_response(embed=embed2)

    await asyncio.sleep(wait_time)

    # 結果表示
    embed3 = discord.Embed(color=color)
    desc = ""
    if rarity == "trash":
        embed3.title = f"{fish['emoji']} {fish['name']}"
        desc = f"ゴミだった...\n換金額: **0コイン**"
    else:
        embed3.title = f"{display_emoji} {display_name} を釣り上げた！"
        desc = f"レアリティ: **{rarity_label}**\n換金額: **{value:,} コイン**"
        if is_golden:
            desc += "\n👑 **金冠！** 通常の2倍！"
        if is_new:
            desc += "\n📖 **図鑑に新しく登録されました！**"
        if new_crown:
            desc += "\n👑 **図鑑に金冠マークが付きました！**"

    if bonus_msg:
        desc += bonus_msg

    # 装備残り回数表示
    rod_name = FISHING_RODS[gear["rod_id"]]["name"]
    rod_uses = gear["rod_uses"] if gear["rod_uses"] < 999999 else "∞"
    embed3.description = desc
    embed3.set_footer(text=f"残高: {new_bal:,} コイン | {area_info['name']} | 竿:{rod_name}({rod_uses}回)")

    now = datetime.now(JST)
    month_day = (now.month, now.day)
    if month_day in FISHING_SPECIAL_DAYS:
        embed3.set_author(name=FISHING_SPECIAL_DAYS[month_day]["label"])

    view = FishResultView(area, show_shadow, uid, guild_id)
    await interaction.edit_original_response(embed=embed3, view=view)


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
        super().__init__(label="⚠️ 不穏な影が見える...垂らし続けますか？", style=discord.ButtonStyle.danger, row=0)
        self.area = area
        self.uid = uid
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ DANGER!!!!",
            description="何か不穏な影が見える...\nこのまま釣竿を垂らしておきますか？",
            color=discord.Color.dark_red()
        )
        await interaction.response.edit_message(embed=embed, view=ShadowChoiceView(self.area, self.uid, self.guild_id))


class ShadowChoiceView(discord.ui.View):
    def __init__(self, area, uid, guild_id):
        super().__init__(timeout=30)
        self.area = area
        self.uid = uid
        self.guild_id = guild_id

    @discord.ui.button(label="垂らし続ける", style=discord.ButtonStyle.danger, emoji="🎣")
    async def keep(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        boss = AREA_BOSS[self.area]

        # ライン装備で成功率UP
        gear = db.get_gear(self.uid)
        line = FISHING_LINES[gear["line_id"]]
        success_rate = SHADOW_SUCCESS_RATE + line["boss_success_bonus"]

        if random.random() < success_rate:
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
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=BackToFishView(self.area))

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

    @app_commands.command(name="fish", description="釣りをする！")
    async def fish(self, interaction: discord.Interaction):
        from cogs.menu import FishMenuView
        embed = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="10コイン", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.send_message(embed=embed, view=FishMenuView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Fishing(bot))
