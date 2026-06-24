import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import LAKE_FISH, RIVER_FISH, SEA_FISH, RARITY_COLORS, AREA_BOSS

db = Database()

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}
AREA_NAMES = {"lake": "🏞️ 湖", "river": "🏔️ 川", "sea": "🌊 海"}
RARITY_ORDER = ["common", "uncommon", "rare", "super_rare", "legend"]
RARITY_LABELS = {
    "common":"コモン","uncommon":"アンコモン","rare":"レア",
    "super_rare":"スーパーレア","legend":"レジェンド",
}

def get_area_stats(uid, area):
    fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
    total = len(fish_list) + 1  # +1はボス
    caught = set(db.get_zukan(uid, area))
    crowns = set(db.get_crowns(uid, area))
    caught_count = len([f for f in fish_list if f["name"] in caught])
    # ボスチェック
    boss_name = AREA_BOSS[area]["name"]
    if boss_name in caught:
        caught_count += 1
    return total, caught_count, caught, crowns

def get_total_stats(uid):
    total_all = 0
    caught_all = 0
    for area in ["lake", "river", "sea"]:
        t, c, _, _ = get_area_stats(uid, area)
        total_all += t
        caught_all += c
    return total_all, caught_all

class ZukanAreaView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def show_area(self, interaction, area):
        uid = self.user_id
        total, caught_count, caught, crowns = get_area_stats(uid, area)
        pct = caught_count / total * 100 if total > 0 else 0

        embed = discord.Embed(
            title=f"📖 図鑑 — {AREA_NAMES[area]}",
            color=discord.Color.blue()
        )
        embed.description = f"**完成率 {pct:.1f}%**（{caught_count}/{total}種）\n"

        for rarity in RARITY_ORDER:
            fishes = [f for f in FISH_BY_AREA[area] if f["rarity"] == rarity]
            if not fishes:
                continue
            lines = []
            for f in fishes:
                if f["name"] in caught:
                    crown = " 👑" if f["name"] in crowns else ""
                    lines.append(f"✅{crown} {f['name']} — {f['value']:,}ナトコイン")
                else:
                    lines.append("❓ ???")
            embed.add_field(
                name=f"{RARITY_LABELS[rarity]}（{len([f for f in fishes if f['name'] in caught])}/{len(fishes)}）",
                value="\n".join(lines),
                inline=False
            )

        # ボス
        boss = AREA_BOSS[area]
        boss_caught = boss["name"] in caught
        boss_line = f"✅ {boss['emoji']} {boss['name']} — {boss['value']:,}ナトコイン" if boss_caught else "❓ ???（隠し）"
        embed.add_field(name="👻 主（隠し）", value=boss_line, inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏞️ 湖", style=discord.ButtonStyle.success, row=0)
    async def lake(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_area(interaction, "lake")

    @discord.ui.button(label="🏔️ 川", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_area(interaction, "river")

    @discord.ui.button(label="🌊 海", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_area(interaction, "sea")

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView())


class Zukan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="zukan", description="釣り図鑑を見る")
    async def zukan(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        total_all, caught_all = get_total_stats(uid)
        pct_all = caught_all / total_all * 100 if total_all > 0 else 0

        embed = discord.Embed(
            title="📖 釣り図鑑",
            description=f"**総合完成率 {pct_all:.1f}%**（{caught_all}/{total_all}種）\nエリアを選んで図鑑を見よう！",
            color=discord.Color.blue()
        )
        for area in ["lake", "river", "sea"]:
            total, caught_count, _, _ = get_area_stats(uid, area)
            pct = caught_count / total * 100 if total > 0 else 0
            crown_count = len(db.get_crowns(uid, area))
            embed.add_field(
                name=AREA_NAMES[area],
                value=f"{pct:.1f}%（{caught_count}/{total}種）👑{crown_count}",
                inline=True
            )
        await interaction.response.send_message(embed=embed, view=ZukanAreaView(uid), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Zukan(bot))
