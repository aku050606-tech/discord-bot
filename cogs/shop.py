import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import FISHING_RODS, FISHING_REELS, FISHING_LINES

db = Database()

# 効果量を具体的な％で出さず、★段階でぼかして表示するための補助
def _stars(value, max_value, tiers=3):
    if value <= 0 or max_value <= 0:
        return 0
    return max(1, min(tiers, round(value / max_value * tiers)))

_REEL_BOSS_MAX  = max(r.get("boss_appear_bonus", 0) for r in FISHING_REELS.values())
_REEL_CROWN_MAX = max(r.get("crown_bonus", 0) for r in FISHING_REELS.values())
_LINE_CROWN_MAX = max(l.get("crown_bonus", 0) for l in FISHING_LINES.values())

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="🎋 釣り竿", style=discord.ButtonStyle.primary, row=0)
    async def rod_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_rod_shop(interaction)

    @discord.ui.button(label="🎡 リール", style=discord.ButtonStyle.primary, row=0)
    async def reel_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_reel_shop(interaction)

    @discord.ui.button(label="🧵 ライン", style=discord.ButtonStyle.primary, row=0)
    async def line_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_line_shop(interaction)

    @discord.ui.button(label="⚙️ 装備変更", style=discord.ButtonStyle.secondary, row=1)
    async def equip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_equip(interaction)

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView())


async def show_rod_shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    gear = db.get_gear(uid)
    bal = db.get_balance(uid, guild_id)

    embed = discord.Embed(
        title="🎋 釣り竿ショップ",
        description="竿には【得意な場所】があります。得意エリアなら消耗が軽くしっかり稼げる。\nそれ以外でも釣れるが、消耗が増えて収支はトントン（得しにくい）。",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"残高: {bal:,} ナトコイン | 現在の装備: {FISHING_RODS[gear['rod_id']]['name']}（耐久 {int(gear['rod_uses']) if gear['rod_uses'] < 999999 else '∞'}）")

    AREA_LABEL = {"lake": "🏞️湖", "river": "🏔️川", "sea": "🌊海"}
    for rod_id, rod in FISHING_RODS.items():
        inv_uses = gear["rod_inventory"].get(rod_id, 0)
        status = f"所持中（耐久 {int(inv_uses)}）" if inv_uses > 0 else "未所持"
        equipped = "✅ 装備中" if gear["rod_id"] == rod_id else ""
        price_str = "無料" if rod["price"] == 0 else f"{rod['price']:,}ナトコイン"
        if rod.get("river_ban"):
            area_str = "行ける場所: 🏞️湖 のみ"
        elif rod.get("sea_ban"):
            area_str = "行ける場所: 🏞️湖・🏔️川"
        else:
            area_str = "行ける場所: 🏞️湖・🏔️川・🌊海（全エリア）"
        home_lbl = AREA_LABEL.get(rod.get("home"), "")
        if rod_id == "legend":
            home_str = "⭐ 得意な場所: 🌊海（完全に海用。湖・川でも伝説級は釣れるが収支はトントン）"
        elif home_lbl:
            home_str = f"⭐ 得意な場所: {home_lbl}（ここなら消耗が軽くしっかり稼げる）"
        else:
            home_str = ""
        embed.add_field(
            name=f"{rod['emoji']} {rod['name']} {equipped}",
            value=f"価格: {price_str}\n{area_str}\n{home_str}\n{status}",
            inline=False
        )

    view = RodShopView(uid, guild_id, gear, bal)
    await interaction.response.edit_message(embed=embed, view=view)


async def show_reel_shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    gear = db.get_gear(uid)
    bal = db.get_balance(uid, guild_id)

    embed = discord.Embed(title="🎡 リールショップ", color=discord.Color.blue())
    embed.set_footer(text=f"残高: {bal:,} ナトコイン | 現在: {FISHING_REELS[gear['reel_id']]['name']}（残り{gear['reel_uses'] if gear['reel_uses'] < 999999 else '∞'}回）")

    for reel_id, reel in FISHING_REELS.items():
        inv_uses = gear["reel_inventory"].get(reel_id, 0)
        status = f"所持中（残り{inv_uses}回）" if inv_uses > 0 else "未所持"
        equipped = "✅ 装備中" if gear["reel_id"] == reel_id else ""
        price_str = "無料" if reel["price"] == 0 else f"{reel['price']:,}ナトコイン"
        parts = []
        bs = _stars(reel.get("boss_appear_bonus", 0), _REEL_BOSS_MAX)
        cs = _stars(reel.get("crown_bonus", 0), _REEL_CROWN_MAX)
        if bs:
            parts.append(f"主が出やすい {'★' * bs}")
        if cs:
            parts.append(f"金冠が出やすい {'★' * cs}")
        effect = " / ".join(parts) if parts else "効果なし"
        embed.add_field(
            name=f"{reel['emoji']} {reel['name']} {equipped}",
            value=f"価格: {price_str} | {effect}\n{status}",
            inline=False
        )

    view = ReelShopView(uid, guild_id, gear, bal)
    await interaction.response.edit_message(embed=embed, view=view)


async def show_line_shop(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    gear = db.get_gear(uid)
    bal = db.get_balance(uid, guild_id)

    embed = discord.Embed(title="🧵 ラインショップ", color=discord.Color.purple())
    embed.set_footer(text=f"残高: {bal:,} ナトコイン | 現在: {FISHING_LINES[gear['line_id']]['name']}（残り{gear['line_uses'] if gear['line_uses'] < 999999 else '∞'}回）")

    for line_id, line in FISHING_LINES.items():
        inv_uses = gear["line_inventory"].get(line_id, 0)
        status = f"所持中（残り{inv_uses}回）" if inv_uses > 0 else "未所持"
        equipped = "✅ 装備中" if gear["line_id"] == line_id else ""
        price_str = "無料" if line["price"] == 0 else f"{line['price']:,}ナトコイン"
        parts = []
        cs = _stars(line.get("crown_bonus", 0), _LINE_CROWN_MAX)
        if cs:
            parts.append(f"金冠が出やすい {'★' * cs}")
        if line.get("boss_success_bonus", 0) > 0:
            parts.append("主が釣りやすくなる")
        effect = " / ".join(parts) if parts else "効果なし"
        embed.add_field(
            name=f"{line['emoji']} {line['name']} {equipped}",
            value=f"価格: {price_str} | {effect}\n{status}",
            inline=False
        )

    view = LineShopView(uid, guild_id, gear, bal)
    await interaction.response.edit_message(embed=embed, view=view)


async def show_equip(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    gear = db.get_gear(uid)

    embed = discord.Embed(title="⚙️ 装備変更", color=discord.Color.gold())
    embed.add_field(
        name="現在の装備",
        value=f"竿: {FISHING_RODS[gear['rod_id']]['name']}（耐久 {int(gear['rod_uses']) if gear['rod_uses'] < 999999 else '∞'}）\n"
              f"リール: {FISHING_REELS[gear['reel_id']]['name']}（残り{gear['reel_uses'] if gear['reel_uses'] < 999999 else '∞'}回）\n"
              f"ライン: {FISHING_LINES[gear['line_id']]['name']}（残り{gear['line_uses'] if gear['line_uses'] < 999999 else '∞'}回）",
        inline=False
    )

    # 所持品一覧
    rod_inv = []
    for rod_id, uses in gear["rod_inventory"].items():
        rod_inv.append(f"{FISHING_RODS[rod_id]['name']}（耐久 {int(uses)}）{'✅' if gear['rod_id'] == rod_id else ''}")

    reel_inv = []
    for reel_id, uses in gear["reel_inventory"].items():
        reel_inv.append(f"{FISHING_REELS[reel_id]['name']}（{uses}回）{'✅' if gear['reel_id'] == reel_id else ''}")

    line_inv = []
    for line_id, uses in gear["line_inventory"].items():
        line_inv.append(f"{FISHING_LINES[line_id]['name']}（{uses}回）{'✅' if gear['line_id'] == line_id else ''}")

    if rod_inv:
        embed.add_field(name="🎋 所持中の竿", value="\n".join(rod_inv), inline=False)
    if reel_inv:
        embed.add_field(name="🎡 所持中のリール", value="\n".join(reel_inv), inline=False)
    if line_inv:
        embed.add_field(name="🧵 所持中のライン", value="\n".join(line_inv), inline=False)

    view = EquipView(uid, gear)
    await interaction.response.edit_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ショップビュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RodShopView(discord.ui.View):
    def __init__(self, uid, guild_id, gear, bal):
        super().__init__(timeout=900)
        self.uid = uid
        self.guild_id = guild_id
        self.gear = gear
        self.bal = bal

        for rod_id, rod in FISHING_RODS.items():
            if rod["price"] > 0:
                self.add_item(BuyRodButton(rod_id, rod, uid, guild_id))

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())


class BuyRodButton(discord.ui.Button):
    def __init__(self, rod_id, rod, uid, guild_id):
        super().__init__(label=f"{rod['name']} {rod['price']:,}ナトコイン", style=discord.ButtonStyle.success)
        self.rod_id = rod_id
        self.rod = rod
        self.uid = uid
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたのショップではありません", ephemeral=True)
            return

        bal = db.get_balance(self.uid, self.guild_id)
        if bal < self.rod["price"]:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        gear = db.get_gear(self.uid)
        inv = gear["rod_inventory"]

        if self.rod_id in inv:
            # 既に所持→耐久を加算
            inv[self.rod_id] += self.rod["uses"]
            msg = f"✅ {self.rod['name']}を購入！\n耐久 {int(inv[self.rod_id])} になりました！"
        else:
            inv[self.rod_id] = self.rod["uses"]
            msg = f"✅ {self.rod['name']}を購入！\nインベントリに追加されました（耐久 {self.rod['uses']}）"

        db.update_balance(self.uid, self.guild_id, -self.rod["price"])
        db.save_gear(self.uid, gear)
        await interaction.response.send_message(msg, ephemeral=True)


class ReelShopView(discord.ui.View):
    def __init__(self, uid, guild_id, gear, bal):
        super().__init__(timeout=900)
        self.uid = uid
        self.guild_id = guild_id

        for reel_id, reel in FISHING_REELS.items():
            if reel["price"] > 0:
                self.add_item(BuyReelButton(reel_id, reel, uid, guild_id))

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())


class BuyReelButton(discord.ui.Button):
    def __init__(self, reel_id, reel, uid, guild_id):
        super().__init__(label=f"{reel['name']} {reel['price']:,}ナトコイン", style=discord.ButtonStyle.success)
        self.reel_id = reel_id
        self.reel = reel
        self.uid = uid
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたのショップではありません", ephemeral=True)
            return

        bal = db.get_balance(self.uid, self.guild_id)
        if bal < self.reel["price"]:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        gear = db.get_gear(self.uid)
        inv = gear["reel_inventory"]

        if self.reel_id in inv:
            inv[self.reel_id] += self.reel["uses"]
            msg = f"✅ {self.reel['name']}を購入！\n残り回数: {inv[self.reel_id]}回になりました！"
        else:
            inv[self.reel_id] = self.reel["uses"]
            msg = f"✅ {self.reel['name']}を購入！\nインベントリに追加されました（{self.reel['uses']}回）"

        db.update_balance(self.uid, self.guild_id, -self.reel["price"])
        db.save_gear(self.uid, gear)
        await interaction.response.send_message(msg, ephemeral=True)


class LineShopView(discord.ui.View):
    def __init__(self, uid, guild_id, gear, bal):
        super().__init__(timeout=900)
        self.uid = uid
        self.guild_id = guild_id

        for line_id, line in FISHING_LINES.items():
            if line["price"] > 0:
                self.add_item(BuyLineButton(line_id, line, uid, guild_id))

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())


class BuyLineButton(discord.ui.Button):
    def __init__(self, line_id, line, uid, guild_id):
        super().__init__(label=f"{line['name']} {line['price']:,}ナトコイン", style=discord.ButtonStyle.success)
        self.line_id = line_id
        self.line = line
        self.uid = uid
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたのショップではありません", ephemeral=True)
            return

        bal = db.get_balance(self.uid, self.guild_id)
        if bal < self.line["price"]:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        gear = db.get_gear(self.uid)
        inv = gear["line_inventory"]

        if self.line_id in inv:
            inv[self.line_id] += self.line["uses"]
            msg = f"✅ {self.line['name']}を購入！\n残り回数: {inv[self.line_id]}回になりました！"
        else:
            inv[self.line_id] = self.line["uses"]
            msg = f"✅ {self.line['name']}を購入！\nインベントリに追加されました（{self.line['uses']}回）"

        db.update_balance(self.uid, self.guild_id, -self.line["price"])
        db.save_gear(self.uid, gear)
        await interaction.response.send_message(msg, ephemeral=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 装備変更ビュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class EquipView(discord.ui.View):
    def __init__(self, uid, gear):
        super().__init__(timeout=900)
        self.uid = uid
        self.gear = gear

        # 所持中の竿ボタン
        for rod_id, uses in gear["rod_inventory"].items():
            if uses > 0:
                rod = FISHING_RODS[rod_id]
                equipped = gear["rod_id"] == rod_id
                self.add_item(EquipRodButton(rod_id, rod, uid, equipped))

    @discord.ui.button(label="🎡 リール変更", style=discord.ButtonStyle.primary, row=2)
    async def change_reel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたの装備ではありません", ephemeral=True)
            return
        gear = db.get_gear(self.uid)
        embed = discord.Embed(title="🎡 リール変更", color=discord.Color.blue())
        view = EquipReelView(self.uid, gear)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🧵 ライン変更", style=discord.ButtonStyle.primary, row=2)
    async def change_line(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたの装備ではありません", ephemeral=True)
            return
        gear = db.get_gear(self.uid)
        embed = discord.Embed(title="🧵 ライン変更", color=discord.Color.purple())
        view = EquipLineView(self.uid, gear)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())


class EquipRodButton(discord.ui.Button):
    def __init__(self, rod_id, rod, uid, equipped):
        label = f"{'✅ ' if equipped else ''}{rod['name']}"
        super().__init__(
            label=label,
            style=discord.ButtonStyle.success if equipped else discord.ButtonStyle.secondary,
            row=0
        )
        self.rod_id = rod_id
        self.uid = uid

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたの装備ではありません", ephemeral=True)
            return
        gear = db.get_gear(self.uid)

        if gear["rod_id"] == self.rod_id:
            await interaction.response.send_message("すでに装備中です", ephemeral=True)
            return

        # 現在の竿の残り回数を保存
        gear["rod_inventory"][gear["rod_id"]] = gear["rod_uses"]
        # 新しい竿を装備
        gear["rod_id"] = self.rod_id
        gear["rod_uses"] = gear["rod_inventory"][self.rod_id]
        db.save_gear(self.uid, gear)

        rod_name = FISHING_RODS[self.rod_id]["name"]
        await interaction.response.send_message(f"✅ {rod_name}に変更しました！（耐久 {int(gear['rod_uses']) if gear['rod_uses'] < 999999 else '∞'}）", ephemeral=True)


class EquipReelView(discord.ui.View):
    def __init__(self, uid, gear):
        super().__init__(timeout=900)
        self.uid = uid
        for reel_id, uses in gear["reel_inventory"].items():
            if uses > 0:
                reel = FISHING_REELS[reel_id]
                equipped = gear["reel_id"] == reel_id
                self.add_item(EquipReelButton(reel_id, reel, uid, equipped))

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        gear = db.get_gear(self.uid)
        await show_equip(interaction)


class EquipReelButton(discord.ui.Button):
    def __init__(self, reel_id, reel, uid, equipped):
        super().__init__(
            label=f"{'✅ ' if equipped else ''}{reel['name']}",
            style=discord.ButtonStyle.success if equipped else discord.ButtonStyle.secondary,
            row=0
        )
        self.reel_id = reel_id
        self.uid = uid

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたの装備ではありません", ephemeral=True)
            return
        gear = db.get_gear(self.uid)
        if gear["reel_id"] == self.reel_id:
            await interaction.response.send_message("すでに装備中です", ephemeral=True)
            return
        gear["reel_inventory"][gear["reel_id"]] = gear["reel_uses"]
        gear["reel_id"] = self.reel_id
        gear["reel_uses"] = gear["reel_inventory"][self.reel_id]
        db.save_gear(self.uid, gear)
        reel_name = FISHING_REELS[self.reel_id]["name"]
        await interaction.response.send_message(f"✅ {reel_name}に変更しました！", ephemeral=True)


class EquipLineView(discord.ui.View):
    def __init__(self, uid, gear):
        super().__init__(timeout=900)
        self.uid = uid
        for line_id, uses in gear["line_inventory"].items():
            if uses > 0:
                line = FISHING_LINES[line_id]
                equipped = gear["line_id"] == line_id
                self.add_item(EquipLineButton(line_id, line, uid, equipped))

    @discord.ui.button(label="🔙 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await show_equip(interaction)


class EquipLineButton(discord.ui.Button):
    def __init__(self, line_id, line, uid, equipped):
        super().__init__(
            label=f"{'✅ ' if equipped else ''}{line['name']}",
            style=discord.ButtonStyle.success if equipped else discord.ButtonStyle.secondary,
            row=0
        )
        self.line_id = line_id
        self.uid = uid

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたの装備ではありません", ephemeral=True)
            return
        gear = db.get_gear(self.uid)
        if gear["line_id"] == self.line_id:
            await interaction.response.send_message("すでに装備中です", ephemeral=True)
            return
        gear["line_inventory"][gear["line_id"]] = gear["line_uses"]
        gear["line_id"] = self.line_id
        gear["line_uses"] = gear["line_inventory"][self.line_id]
        db.save_gear(self.uid, gear)
        line_name = FISHING_LINES[self.line_id]["name"]
        await interaction.response.send_message(f"✅ {line_name}に変更しました！", ephemeral=True)


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="釣具屋でアイテムを購入する")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=ShopView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Shop(bot))
