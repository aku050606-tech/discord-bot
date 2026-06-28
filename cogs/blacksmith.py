import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import voyage_config as V

db = Database()

COL = 0x8e5a2a

def _mat_line(mid, need, have):
    m = V.MATERIALS.get(mid, {"name": mid, "emoji":"❔"})
    ok = "✅" if have >= need else "❌"
    return f"{ok} {m['emoji']} **{m['name']}** {have}/{need}"

def _recipe_name(r):
    if r["kind"] == "weapon":
        d = V.WEAPONS[r["item"]]
        wt = V.WEAPON_TYPES.get(d["wtype"], {}).get("name", d["wtype"])
        return f"{V.rarity_stars(d['rank'])} {d['name']}（{wt}）"
    d = V.ARMOR_PARTS[r["part"]]["items"][r["item"]]
    part = V.ARMOR_PARTS[r["part"]]["name"]
    return f"{V.rarity_stars(d['rank'])} {d['name']}（{part}）"

def build_blacksmith_embed(uid, selected=None):
    vp = db.get_voyage(uid)
    mats = vp.get("materials", {})
    emb = discord.Embed(
        title="⚒️ 鍛冶屋",
        color=COL,
        description=("素材を集めて、鍛冶屋だけの装備を作れる。\n"
                     "入手場所はあえて詳しくは書かれていない。名前と説明から探してみよう。\n"
                     "※細かい性能値は表示せず、使って確かめる方針。鍛冶☆3は未来目標。")
    )
    if selected and selected in V.CRAFT_RECIPES:
        r = V.CRAFT_RECIPES[selected]
        can = all(mats.get(mid,0) >= need for mid, need in r["cost"].items())
        emb.add_field(name="作成候補", value=_recipe_name(r), inline=False)
        emb.add_field(name="必要素材", value="\n".join(_mat_line(mid, need, mats.get(mid,0)) for mid, need in r["cost"].items()), inline=False)
        hints = []
        for mid in r["cost"]:
            m = V.MATERIALS.get(mid, {})
            hints.append(f"{m.get('emoji','❔')} **{m.get('name',mid)}**：{m.get('hint','どこかで見つかりそうだ。')}")
        emb.add_field(name="鍛冶師のひとこと", value="\n".join(hints[:5]), inline=False)
        emb.set_footer(text="作成可能" if can else "素材が足りない")
    else:
        r2 = [r for r in V.CRAFT_RECIPES.values() if r["rank"] == 2]
        r3 = [r for r in V.CRAFT_RECIPES.values() if r["rank"] == 3]
        emb.add_field(name="★2 レシピ", value=f"{len(r2)}種類。平原は約1000周、浅瀬は約300周が目安。腰を据えて作る職人装備。", inline=False)
        emb.add_field(name="★3 レシピ", value=f"{len(r3)}種類。森と大洋の素材が必要。現状は基本作れない未来目標。", inline=False)
        owned = []
        for mid, n in mats.items():
            if n > 0 and mid in V.MATERIALS:
                m = V.MATERIALS[mid]
                owned.append(f"{m['emoji']} {m['name']}×{n}")
        emb.add_field(name="手持ち素材", value="　".join(owned[:40]) if owned else "まだ素材を持っていない。", inline=False)
    return emb

class RecipeSelect(discord.ui.Select):
    def __init__(self, uid, selected=None):
        self.uid = str(uid)
        opts = []
        for key, r in V.CRAFT_RECIPES.items():
            label = _recipe_name(r).replace("★", "").replace("**", "")[:95]
            opts.append(discord.SelectOption(label=label, value=key, description=("★2 作成可を目指せ" if r["rank"]==2 else "★3 未来目標")))
        super().__init__(placeholder="作りたい装備を選ぶ", options=opts[:25], row=0)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの鍛冶屋ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_blacksmith_embed(self.uid, self.values[0]), view=BlacksmithView(self.uid, self.values[0]))

class BlacksmithView(discord.ui.View):
    def __init__(self, uid, selected=None):
        super().__init__(timeout=900)
        self.uid = str(uid); self.selected = selected
        self.add_item(RecipeSelect(uid, selected))
    @discord.ui.button(label="⚒️ 作成", style=discord.ButtonStyle.success, row=1)
    async def craft(self, it, b):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの鍛冶屋ではありません", ephemeral=True); return
        if not self.selected or self.selected not in V.CRAFT_RECIPES:
            await it.response.send_message("先にレシピを選んでね。", ephemeral=True); return
        vp = db.get_voyage(self.uid); mats = vp.setdefault("materials", {})
        r = V.CRAFT_RECIPES[self.selected]
        missing = [(mid, need, mats.get(mid,0)) for mid, need in r["cost"].items() if mats.get(mid,0) < need]
        if missing:
            lines = []
            for mid, need, have in missing:
                m = V.MATERIALS[mid]
                lines.append(f"{m['emoji']} {m['name']} {have}/{need}")
            await it.response.send_message("素材が足りない！\n" + "\n".join(lines), ephemeral=True)
            return
        for mid, need in r["cost"].items():
            mats[mid] -= need
            if mats[mid] <= 0: del mats[mid]
        inv = vp.setdefault("inventory", {})
        if r["kind"] == "weapon":
            inv.setdefault("weapon", []).append({"item": r["item"], "skills": []})
            db.add_zukan(self.uid, "equip_seen", r["item"])
            name = V.WEAPONS[r["item"]]["name"]
        else:
            inv.setdefault(r["part"], []).append({"item": r["item"], "skills": []})
            db.add_zukan(self.uid, "equip_seen", r["item"])
            name = V.ARMOR_PARTS[r["part"]]["items"][r["item"]]["name"]
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(embed=build_blacksmith_embed(self.uid, self.selected), view=BlacksmithView(self.uid, self.selected))
        await it.followup.send(f"⚒️ **{name}** を作成した！", ephemeral=True)
    @discord.ui.button(label="◀ 商店街へ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, it, b):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの鍛冶屋ではありません", ephemeral=True); return
        from cogs.menu import open_shopping_street
        await open_shopping_street(it, self.uid, str(it.guild.id))

async def open_blacksmith(interaction, uid):
    await interaction.response.edit_message(embed=build_blacksmith_embed(uid), view=BlacksmithView(uid))

class Blacksmith(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @app_commands.command(name="鍛冶屋", description="素材を使って鍛冶屋装備を作る")
    async def blacksmith(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_blacksmith_embed(str(interaction.user.id)), view=BlacksmithView(str(interaction.user.id)), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Blacksmith(bot))
