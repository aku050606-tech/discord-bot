import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import (LAKE_FISH, RIVER_FISH, SEA_FISH, RARITY_COLORS, AREA_BOSS,
                    TREASURE_BY_AREA, RARE_TRASH_BY_AREA,
                    LIMITED_FISH, STORM_TREASURES, BLOOD_MOON_BOSS)

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
WEATHER_LABELS = {"rain": "🌧️雨", "fog": "🌫️霧", "glow": "🌅朝焼け/夕焼け",
                  "storm": "⛈️嵐", "blood_moon": "🩸赤い月"}
WEATHER_ORDER = ["rain", "fog", "glow", "storm", "blood_moon"]


# ── 各カテゴリ・エリアの「全アイテム名」と「図鑑キー」 ──
def fish_items(area):
    return [f for f in FISH_BY_AREA[area] if f["rarity"] not in ("trash", "boss")]

def trash_items(area):
    # 通常ごみ ＋ レアごみ（売値1000・各エリア2種）。レアごみには rare フラグを付ける。
    normal = [{"name": f["name"], "emoji": f["emoji"], "value": f.get("value", 0), "rare": False}
              for f in FISH_BY_AREA[area] if f["rarity"] == "trash"]
    rares = [{"name": t["name"], "emoji": t["emoji"], "value": t["value"], "rare": True}
             for t in RARE_TRASH_BY_AREA.get(area, [])]
    return normal + rares

def treasure_items(area):
    out = []
    for rank in ("small", "big", "jackpot"):
        for t in TREASURE_BY_AREA[area].get(rank, []):
            out.append({"name": t["name"], "emoji": t["emoji"], "rank": rank})
    return out

def limited_items(area):
    out = []
    for w in WEATHER_ORDER:
        for f in LIMITED_FISH.get(area, {}).get(w, []):
            out.append({**f, "weather": w})
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
        if cat == "treasure":
            sc = set(db.get_zukan(uid, "storm_treasure"))
            c += len([x for x in STORM_TREASURES if x["name"] in sc])
            t += len(STORM_TREASURES)
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
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        view = ZukanTreasureView(self.user_id)
        await interaction.response.edit_message(embed=view.build_embed(), view=view)

    @discord.ui.button(label="⚔️ 敵対図鑑", style=discord.ButtonStyle.danger, row=1)
    async def enemy(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        from cogs.voyage import build_enemy_zukan_embed, EnemyZukanView
        await interaction.response.edit_message(
            embed=build_enemy_zukan_embed(self.user_id),
            view=EnemyZukanView(self.user_id, str(interaction.guild.id)))

    @discord.ui.button(label="🗡️ 武器", style=discord.ButtonStyle.secondary, row=1)
    async def weapon(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.voyage import build_weapon_zukan_embed, SimpleZukanView
        await interaction.response.edit_message(embed=build_weapon_zukan_embed(self.user_id), view=SimpleZukanView(self.user_id))

    @discord.ui.button(label="🛡️ 防具", style=discord.ButtonStyle.secondary, row=1)
    async def armor(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.voyage import build_armor_zukan_embed, SimpleZukanView
        await interaction.response.edit_message(embed=build_armor_zukan_embed(self.user_id), view=SimpleZukanView(self.user_id))

    @discord.ui.button(label="📜 技", style=discord.ButtonStyle.secondary, row=2)
    async def skill(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.voyage import build_skill_zukan_embed, SimpleZukanView
        await interaction.response.edit_message(embed=build_skill_zukan_embed(), view=SimpleZukanView(self.user_id))

    @discord.ui.button(label="🎒 アイテム", style=discord.ButtonStyle.secondary, row=2)
    async def item(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.voyage import build_item_zukan_embed, SimpleZukanView
        await interaction.response.edit_message(embed=build_item_zukan_embed(self.user_id), view=SimpleZukanView(self.user_id))

    @discord.ui.button(label="🎣 海の幸", style=discord.ButtonStyle.primary, row=2)
    async def voyage_fish(self, interaction, button):
        if not self._check(interaction):
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.voyage import build_voyage_fish_zukan_embed, VoyageFishZukanView
        await interaction.response.edit_message(
            embed=build_voyage_fish_zukan_embed(self.user_id, 1),
            view=VoyageFishZukanView(self.user_id, 1))

    @discord.ui.button(label="◀️ スマホに戻る", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction, button):
        from cogs.phone import open_phone
        await open_phone(interaction, str(interaction.user.id))


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
            normal = [f for f in items if not f.get("rare")]
            rares  = [f for f in items if f.get("rare")]
            lines = [f"✅ {f['emoji']} {f['name']}" if f["name"] in caught else "❓ ???"
                     for f in normal]
            embed.add_field(name="ごみコレクション", value="\n".join(lines) or "—", inline=False)
            if rares:
                rlines = [f"✅ {f['emoji']} {f['name']} — {f['value']:,}"
                          if f["name"] in caught else "❓ ???"
                          for f in rares]
                got = len([f for f in rares if f["name"] in caught])
                embed.add_field(name=f"✨ レアごみ（{got}/{len(rares)}・売値1000）",
                                value="\n".join(rlines), inline=False)

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

    @discord.ui.button(label="🌦️ 限定", style=discord.ButtonStyle.primary, row=0)
    async def limited(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        if self.category != "fish":
            # 限定は魚図鑑からのみ。他カテゴリでは無視
            await interaction.response.send_message("限定図鑑は魚図鑑から見てね", ephemeral=True)
            return
        view = ZukanLimitedView(self.user_id)
        await interaction.response.edit_message(embed=view.area_embed("lake"), view=view)

    @discord.ui.button(label="◀️ 図鑑選択へ", style=discord.ButtonStyle.secondary, row=1)
    async def to_category(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=build_category_embed(self.user_id), view=ZukanCategoryView(self.user_id))


class ZukanLimitedView(discord.ui.View):
    """限定魚＋赤月主。湖/川/海で分岐。各魚は天候付き表示（未捕獲は天候だけ見せる）。"""
    def __init__(self, user_id):
        super().__init__(timeout=900)
        self.user_id = user_id

    def area_embed(self, area):
        uid = self.user_id
        caught = set(db.get_zukan(uid, f"{area}_limited"))
        bm_caught = set(db.get_zukan(uid, f"{area}_bloodmoon"))
        items = limited_items(area)
        done = len([f for f in items if f["name"] in caught])
        embed = discord.Embed(title=f"📖 🌦️ 限定 — {AREA_NAMES[area]}",
                              color=discord.Color.purple())
        embed.description = f"**収集 {done}/{len(items)} 種**\n特定の天候でだけ姿を見せる…"
        for w in WEATHER_ORDER:
            ws = [f for f in items if f["weather"] == w]
            if not ws:
                continue
            wl = WEATHER_LABELS[w]
            lines = []
            for f in ws:
                if f["name"] in caught:
                    lines.append(f"✅ {f['emoji']} {f['name']}（{wl}） — {f['value']:,}")
                else:
                    lines.append(f"❓ ???（{wl}）")
            got = len([f for f in ws if f["name"] in caught])
            embed.add_field(name=f"{wl}（{got}/{len(ws)}）", value="\n".join(lines), inline=False)
        # 赤月主（このエリア）
        bm = BLOOD_MOON_BOSS.get(area)
        if bm:
            bl = (f"✅ {bm['emoji']} {bm['name']} — {bm['value']:,}"
                  if bm["name"] in bm_caught else "🩸 ???（赤い月の主）")
            embed.add_field(name="🩸 赤月の主（隠し）", value=bl, inline=False)
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

    @discord.ui.button(label="◀️ 魚図鑑へ", style=discord.ButtonStyle.secondary, row=1)
    async def back_fish(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの図鑑ではありません", ephemeral=True)
            return
        view = ZukanAreaView(self.user_id, "fish")
        await interaction.response.edit_message(embed=view.area_embed("lake"), view=view)


class ZukanTreasureView(discord.ui.View):
    """宝図鑑：宝の地図の宝（全エリア）＋嵐のお宝を1ページに集約。"""
    def __init__(self, user_id):
        super().__init__(timeout=900)
        self.user_id = user_id

    def build_embed(self):
        uid = self.user_id
        embed = discord.Embed(title="📖 💎 宝図鑑", color=discord.Color.gold())
        total = done = 0
        for area in AREAS:
            items = treasure_items(area)
            if not items:
                continue
            caught = set(db.get_zukan(uid, f"{area}_treasure"))
            lines = []
            for rank in ("small", "big", "jackpot"):
                for t in [x for x in items if x["rank"] == rank]:
                    hit = t["name"] in caught
                    total += 1
                    done += 1 if hit else 0
                    lines.append(f"✅ {t['emoji']} {t['name']}" if hit else "❓ ???")
            embed.add_field(name=f"{AREA_NAMES[area]} の宝", value="\n".join(lines) or "—", inline=True)
        sc = set(db.get_zukan(uid, "storm_treasure"))
        slines = []
        for t in STORM_TREASURES:
            hit = t["name"] in sc
            total += 1
            done += 1 if hit else 0
            slines.append(f"✅ {t['emoji']} {t['name']} — {t['min']:,}〜{t['max']:,}" if hit else "❓ ???")
        embed.add_field(name="⛈️ 嵐のお宝（全エリア共通）", value="\n".join(slines), inline=False)
        embed.description = f"**発見 {done}/{total} 種**\n宝の地図と、嵐の宝箱から見つかる！"
        return embed

    @discord.ui.button(label="◀️ 図鑑選択へ", style=discord.ButtonStyle.secondary, row=0)
    async def back(self, interaction, button):
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
