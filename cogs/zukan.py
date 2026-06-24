import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import (LAKE_FISH, RIVER_FISH, SEA_FISH, RARITY_COLORS, AREA_BOSS,
                    TREASURE_BY_AREA)

db = Database()

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}
AREA_NAMES = {"lake": "🏞️ 湖", "river": "🏔️ 川", "sea": "🌊 海"}
AREAS = ["lake", "river", "sea"]
RARITY_ORDER = ["common", "uncommon", "rare", "super_rare", "legend"]
RARITY_LABELS = {
    "common": "コモン", "uncommon": "アンコモン", "rare": "レア",
    "super_rare": "スーパーレア", "legend": "レジェンド",
}
TREASURE_RANK_LABELS = {"small": "小さな宝", "big": "大きな宝", "jackpot": "伝説の宝"}
CATEGORY_LABELS = {"fish": "🐟 魚", "trash": "🗑️ ごみ", "treasure": "💎 宝"}


# ── 各カテゴリ・エリアの「全アイテム名」と「図鑑キー」 ──
def fish_items(area):
    return [f for f in FISH_BY_AREA[area] if f["rarity"] not in ("trash", "boss")]

def trash_items(area):
    return [f for f in FISH_BY_AREA[area] if f["rarity"] == "trash"]

def treasure_items(area):
    out = []
    for rank in ("small", "big", "jackpot"):
        for t in TREASURE_BY_AREA[area].get(rank, []):
            out.append({"name": t["name"], "emoji": t["emoji"], "rank": rank})
    return out

def zukan_key(category, area):
    return area if category == "fish" else f"{area}_{category}"


def category_counts(uid, category):
    """(caught, total) をカテゴリ全エリア合計で返す。"""
    caught = total = 0
    for area in AREAS:
        if category == "fish":
            items = [f["name"] for f in fish_items(area)] + [AREA_BOSS[area]["name"]]
        elif category == "trash":
            items = [f["name"] for f in trash_items(area)]
        else:
            items = [t["name"] for t in treasure_items(area)]
        got = set(db.get_zukan(uid, zukan_key(category, area)))
        total += len(items)
        caught += len([n for n in items if n in got])
    return caught, total


def build_category_embed(uid):
    embed = discord.Embed(
        title="📖 釣り図鑑",
        description="見たい図鑑を選んでね！\n（魚・ごみ・宝、それぞれエリア別）",
        color=discord.Color.blue()
    )
    for cat in ("fish", "trash", "treasure"):
        c, t = category_counts(uid, cat)
        pct = c / t * 100 if t else 0
        embed.add_field(name=CATEGORY_LABELS[cat], value=f"{c}/{t} 種（{pct:.0f}%）", inline=True)
    return embed


class ZukanCategoryView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=900)
        self.user_id = user_id

    def _check(self, interaction):
        return str(interaction.user.id) == self.user_id

    async def _open(self, interaction, category):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        view = ZukanAreaView(self.user_id, category)
        await interaction.response.edit_message(embed=view.area_embed("lake"), view=view)

    @discord.ui.button(label="🐟 魚図鑑", style=discord.ButtonStyle.primary, row=0)
    async def fish(self, interaction, button):
        await self._open(interaction, "fish")

    @discord.ui.button(label="🗑️ ごみ図鑑", style=discord.ButtonStyle.secondary, row=0)
    async def trash(self, interaction, button):
        await self._open(interaction, "trash")

    @discord.ui.button(label="💎 宝図鑑", style=discord.ButtonStyle.success, row=0)
    async def treasure(self, interaction, button):
        await self._open(interaction, "treasure")

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(
            embed=build_menu_embed(interaction.user, str(interaction.guild.id)),
            view=MainMenuView())


class ZukanAreaView(discord.ui.View):
    def __init__(self, user_id, category="fish"):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.category = category

    def area_embed(self, area):
        uid = self.user_id
        cat = self.category
        caught = set(db.get_zukan(uid, zukan_key(cat, area)))
        title = f"{CATEGORY_LABELS[cat]} — {AREA_NAMES[area]}"
        embed = discord.Embed(title=f"📖 {title}", color=discord.Color.blue())

        if cat == "fish":
            crowns = set(db.get_crowns(uid, area))
            items = fish_items(area)
            done = len([f for f in items if f["name"] in caught])
            total = len(items) + 1  # +ボス
            if AREA_BOSS[area]["name"] in caught:
                done += 1
            embed.description = f"**完成率 {done/total*100:.0f}%**（{done}/{total}種）"
            for rarity in RARITY_ORDER:
                fishes = [f for f in items if f["rarity"] == rarity]
                if not fishes:
                    continue
                lines = []
                for f in fishes:
                    if f["name"] in caught:
                        crown = " 👑" if f["name"] in crowns else ""
                        lines.append(f"✅{crown} {f['name']} — {f['value']:,}")
                    else:
                        lines.append("❓ ???")
                got = len([f for f in fishes if f['name'] in caught])
                embed.add_field(name=f"{RARITY_LABELS[rarity]}（{got}/{len(fishes)}）",
                                value="\n".join(lines), inline=False)
            boss = AREA_BOSS[area]
            bl = (f"✅ {boss['emoji']} {boss['name']} — {boss['value']:,}"
                  if boss["name"] in caught else "❓ ???（隠し）")
            embed.add_field(name="👻 主（隠し）", value=bl, inline=False)

        elif cat == "trash":
            items = trash_items(area)
            done = len([f for f in items if f["name"] in caught])
            embed.description = f"**収集 {done}/{len(items)} 種**"
            lines = [f"✅ {f['emoji']} {f['name']}" if f["name"] in caught else "❓ ???"
                     for f in items]
            embed.add_field(name="ごみコレクション", value="\n".join(lines) or "—", inline=False)

        else:  # treasure
            items = treasure_items(area)
            done = len([t for t in items if t["name"] in caught])
            embed.description = f"**発見 {done}/{len(items)} 種**\n宝の地図から見つかる！"
            for rank in ("small", "big", "jackpot"):
                ranked = [t for t in items if t["rank"] == rank]
                if not ranked:
                    continue
                lines = [f"✅ {t['emoji']} {t['name']}" if t["name"] in caught else "❓ ???"
                         for t in ranked]
                got = len([t for t in ranked if t["name"] in caught])
                embed.add_field(name=f"{TREASURE_RANK_LABELS[rank]}（{got}/{len(ranked)}）",
                                value="\n".join(lines), inline=False)
        return embed

    async def show_area(self, interaction, area):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await interaction.response.edit_message(embed=self.area_embed(area), view=self)

    @discord.ui.button(label="🏞️ 湖", style=discord.ButtonStyle.success, row=0)
    async def lake(self, interaction, button):
        await self.show_area(interaction, "lake")

    @discord.ui.button(label="🏔️ 川", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction, button):
        await self.show_area(interaction, "river")

    @discord.ui.button(label="🌊 海", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction, button):
        await self.show_area(interaction, "sea")

    @discord.ui.button(label="◀️ 図鑑選択へ", style=discord.ButtonStyle.secondary, row=1)
    async def to_category(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=build_category_embed(self.user_id), view=ZukanCategoryView(self.user_id))


class Zukan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="zukan", description="釣り図鑑を見る")
    async def zukan(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await interaction.response.send_message(
            embed=build_category_embed(uid), view=ZukanCategoryView(uid), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Zukan(bot))
