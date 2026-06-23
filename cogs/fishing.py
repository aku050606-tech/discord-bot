import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
import asyncio
from datetime import datetime, timezone, timedelta
from cogs.embed_utils import pad_embed

db = Database()
JST = timezone(timedelta(hours=9))

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}

def pick_effect_by_rarity(rarity: str) -> str:
    """結果のレアリティに応じて演出テキストを抽選（FISHING_EFFECT_POOL）。
    フェイント・不意打ち・確定演出はこのプールの％で表現される。"""
    pool = FISHING_EFFECT_POOL.get(rarity, FISHING_EFFECT_POOL["common"])
    total = sum(p for _, p in pool)
    r = random.random() * total
    cumulative = 0
    for key, p in pool:
        cumulative += p
        if r < cumulative:
            return FISHING_EFFECTS.get(key, FISHING_EFFECTS["common_1"])
    return FISHING_EFFECTS.get(pool[-1][0], FISHING_EFFECTS["common_1"])

def pick_rarity_direct(rod_id: str) -> str:
    """竿別レアリティ出率テーブル（FISHING_RARITY）からレアリティを決定"""
    table = FISHING_RARITY.get(rod_id, FISHING_RARITY["bamboo"])
    r = random.random()
    cumulative = 0
    for rarity, prob in table.items():
        cumulative += prob
        if r < cumulative:
            return rarity
    return "common"

def pick_fish(area: str, rarity: str) -> dict:
    candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == rarity]
    if not candidates:
        candidates = [f for f in FISH_BY_AREA[area] if f["rarity"] == "common"]
    return random.choice(candidates)

active_fishing: set = set()  # 釣り中のユーザーID

async def do_fish(interaction: discord.Interaction, area: str, edit: bool = False):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    # 連打防止
    if uid in active_fishing:
        await interaction.response.send_message("⏳ 釣り中です...", ephemeral=True)
        return
    active_fishing.add(uid)

    # エラーは必ず本人だけに表示し、釣りメニュー（共有メッセージ）はそのまま残す
    async def _send_error(msg: str):
        active_fishing.discard(uid)
        await interaction.response.send_message(msg, ephemeral=True)

    area_info = FISHING_AREAS[area]
    cost = area_info["cost"]

    # 装備取得
    gear = db.get_gear(uid)

    # エリア禁止チェック（どの竿で行けるかを明示）
    rod = FISHING_RODS[gear["rod_id"]]
    if rod.get("sea_ban") and area == "sea":
        await _send_error(
            f"❌ 今の竿「{rod['name']}」では🌊海に行けません。\n"
            f"海にはカーボンロッド以上が必要です（/shop で購入）。"
        )
        return
    if rod.get("river_ban") and area == "river":
        await _send_error(
            f"❌ 今の竿「{rod['name']}」では🏔️川に行けません。\n"
            f"川にはグラスロッド以上が必要です（/shop で購入）。"
        )
        return

    bal = db.get_balance(uid, guild_id)
    if bal < cost:
        await _send_error(f"❌ コインが足りません（{area_info['name']}は{cost}コイン / 残高: {bal:,}）")
        return

    if cost > 0:
        db.update_balance(uid, guild_id, -cost)

    # 装備使用回数を減らす（竿は耐久制：海3・川2・湖1）
    dura_cost = ROD_DURABILITY_COST.get(area, 1)
    if gear["rod_uses"] < 999999:
        gear["rod_uses"] -= dura_cost
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

    # レアリティは竿別の直接テーブルで決定
    rarity = pick_rarity_direct(gear["rod_id"])

    # 結果のレアリティに応じて演出テキストを選択（見せ方のみ。フェイント/確定込み）
    effect_text = pick_effect_by_rarity(rarity)

    # 主（ぬし）の影：コモンを釣った時だけ抽選。リールで出現率UP
    reel = FISHING_REELS[gear["reel_id"]]
    show_shadow = False
    if rarity == "common":
        appear_chance = SHADOW_CHANCE + reel["boss_appear_bonus"]
        if random.random() < appear_chance:
            show_shadow = True

    fish = pick_fish(area, rarity)
    value = fish["value"]

    # 金冠判定（基礎 + ライン + リール）
    line = FISHING_LINES[gear["line_id"]]
    crown_chance = GOLDEN_CROWN_CHANCE + line["crown_bonus"] + reel["crown_bonus"]
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

    # ウェイト時間（レア度に応じて：SR以上は長めの溜め）
    wait_time = FISHING_WAIT_SUPER if rarity in ("super_rare", "legend") else FISHING_WAIT_NORMAL

    color = RARITY_COLORS.get(rarity, 0x95a5a6)
    rarity_label = {
        "trash":"ゴミ","common":"コモン","uncommon":"アンコモン",
        "rare":"レア","super_rare":"スーパーレア","legend":"レジェンド","boss":"???",
    }.get(rarity, rarity)

    display_name = f"大きな{fish['name']}" if is_golden else fish["name"]
    display_emoji = "👑" if is_golden else fish["emoji"]

    # 演出表示（中間なし：演出→待機→結果）
    # 当たり待ち中はレア度が分からないよう中立色で統一（結果表示はレアリティ色）
    embed1 = discord.Embed(description=effect_text, color=SUSPENSE_COLOR)
    embed1.set_footer(text=area_info["name"])
    pad_embed(embed1, target_fields=4)

    if edit:
        await interaction.response.edit_message(embed=embed1, view=None)
    else:
        await interaction.response.send_message(embed=embed1, view=None)

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
    embed3.set_footer(text=f"残高: {new_bal:,} コイン | {area_info['name']} | 竿:{rod_name}(耐久{rod_uses})")
    pad_embed(embed3, target_fields=4)

    view = FishResultView(area, show_shadow, uid, guild_id)
    await interaction.edit_original_response(embed=embed3, view=view)
    active_fishing.discard(uid)


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
        embed.add_field(name="🏞️ 湖", value="10コイン\n竹竿でOK", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン\nグラス竿以上", inline=True)
        embed.add_field(name="🌊 海", value="100コイン\nカーボン竿以上", inline=True)
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
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ これはあなたの釣りではありません", ephemeral=True)
            return
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
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ これはあなたの釣りではありません", ephemeral=True)
            return
        await interaction.response.defer()
        boss = AREA_BOSS[self.area]

        # ライン装備で成功率UP
        gear = db.get_gear(self.uid)
        line = FISHING_LINES[gear["line_id"]]
        base_success = SHADOW_SUCCESS_RATES.get(gear["rod_id"], 0.01)
        success_rate = base_success + line["boss_success_bonus"]

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
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("❌ これはあなたの釣りではありません", ephemeral=True)
            return
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
        embed.add_field(name="🏞️ 湖", value="10コイン\n竹竿でOK", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン\nグラス竿以上", inline=True)
        embed.add_field(name="🌊 海", value="100コイン\nカーボン竿以上", inline=True)
        await interaction.response.send_message(embed=embed, view=FishMenuView())

async def setup(bot):
    await bot.add_cog(Fishing(bot))
