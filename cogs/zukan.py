import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import LAKE_FISH, RIVER_FISH, SEA_FISH, RARITY_COLORS

db = Database()

FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}
AREA_NAMES = {"lake": "🏞️ 湖", "river": "🏔️ 川", "sea": "🌊 海"}
RARITY_ORDER = ["common", "uncommon", "rare", "super_rare", "legend"]
RARITY_LABELS = {
    "common": "コモン", "uncommon": "アンコモン", "rare": "レア",
    "super_rare": "スーパーレア", "legend": "レジェンド"
}

class ZukanAreaView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def show_zukan(self, interaction: discord.Interaction, area: str):
        uid = self.user_id
        caught = set(db.get_zukan(uid, area))
        fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
        total = len(fish_list)
        caught_count = len([f for f in fish_list if f["name"] in caught])

        embed = discord.Embed(
            title=f"📖 図鑑 — {AREA_NAMES[area]}",
            color=discord.Color.blue()
        )
        embed.description = f"**{caught_count}/{total}** 種類釣り上げ済み"

        for rarity in RARITY_ORDER:
            fishes = [f for f in fish_list if f["rarity"] == rarity]
            if not fishes:
                continue
            lines = []
            for f in fishes:
                if f["name"] in caught:
                    lines.append(f"{f['emoji']} {f['name']} — {f['value']:,}コイン")
                else:
                    lines.append("❓ ???")
            embed.add_field(
                name=f"{RARITY_LABELS[rarity]}（{len([f for f in fishes if f['name'] in caught])}/{len(fishes)}）",
                value="\n".join(lines),
                inline=False
            )

        if caught_count == total:
            embed.set_footer(text="🎊 コンプリート済み！")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏞️ 湖", style=discord.ButtonStyle.success)
    async def lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_zukan(interaction, "lake")

    @discord.ui.button(label="🏔️ 川", style=discord.ButtonStyle.primary)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_zukan(interaction, "river")

    @discord.ui.button(label="🌊 海", style=discord.ButtonStyle.danger)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await self.show_zukan(interaction, "sea")

class Zukan(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="zukan", description="釣り図鑑を見る")
    async def zukan(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        embed = discord.Embed(
            title="📖 釣り図鑑",
            description="エリアを選んで図鑑を見よう！",
            color=discord.Color.blue()
        )
        for area in ["lake", "river", "sea"]:
            caught = db.get_zukan(uid, area)
            fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
            embed.add_field(
                name=AREA_NAMES[area],
                value=f"{len(caught)}/{len(fish_list)} 種類",
                inline=True
            )
        await interaction.response.send_message(embed=embed, view=ZukanAreaView(uid))

async def setup(bot):
    await bot.add_cog(Zukan(bot))
