"""⚓ 航海システム（さびれた港 再興後コンテンツ）── Phase 1: 単独航海コア。
船購入 → 装備 → 出航 → 進む/引き返す → 釣り/上陸/海賊戦(2層) → 船倉を銀行入金。
敗北で失うのは航海中の船倉のみ。船戦は勝敗問わず船装備の耐久がガッツリ減る＝修理代シンク。
ネット≈105%（voyage_config の数値で制御・モンテカルロ検算済み）。
※ ガチャ/マーケット/協力航海は Phase2+ で実装予定。
"""
import random
import discord
from discord.ext import commands
from database import Database
import voyage_config as V

db = Database()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 計算ヘルパ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _tier(slot_group, t):
    """SHIP_EQUIP / PERSONAL_EQUIP の tier dict を取得（t は 1始まり）。"""
    return slot_group["tiers"][t - 1]

def ship_power(vp):
    p = V.SHIP_BASE_POWER
    for slot in ("cannon", "armor", "hull"):
        e = vp["ship_equip"].get(slot)
        if e:
            p += _tier(V.SHIP_EQUIP[slot], e["t"])["power"]
    return p

def personal_power(vp):
    p = V.LEVEL_BASE_POWER * vp["level"]
    if vp["personal"]["weapon"]:
        p += _tier(V.PERSONAL_EQUIP["weapon"], vp["personal"]["weapon"])["power"]
    if vp["personal"]["armor"]:
        p += _tier(V.PERSONAL_EQUIP["armor"], vp["personal"]["armor"])["power"]
    return p

def win_prob(me, foe):
    k = V.COMBAT_K
    p = (me ** k) / ((me ** k) + (foe ** k)) if (me + foe) > 0 else 0.5
    lo, hi = V.COMBAT_WIN_CLAMP
    return max(lo, min(hi, p))

def hull_tier(vp):
    e = vp["ship_equip"].get("hull")
    return e["t"] if e else 0

def can_enter_sea(vp, sea):
    return hull_tier(vp) >= V.SEAS[sea]["unlock_hull"]

def add_xp(vp, amount):
    """XPを加算しレベルアップ処理。レベルアップしたら True を返す。"""
    leveled = False
    vp["xp"] += amount
    while vp["level"] < V.LEVEL_MAX and vp["xp"] >= V.xp_to_next(vp["level"]):
        vp["xp"] -= V.xp_to_next(vp["level"])
        vp["level"] += 1
        leveled = True
    return leveled

def dura_bar(cur, mx, width=8):
    if mx <= 0:
        return "—"
    ratio = max(0.0, min(1.0, cur / mx))
    filled = round(width * ratio)
    mark = "🟩" if ratio > 0.5 else ("🟨" if ratio > 0.2 else "🟥")
    return mark * filled + "⬛" * (width - filled)

def repair_cost(vp):
    """全船装備＋船本体を満タンに戻すのに必要なコイン。"""
    cost = 0
    for slot in ("cannon", "armor", "hull"):
        e = vp["ship_equip"].get(slot)
        if e:
            mx = _tier(V.SHIP_EQUIP[slot], e["t"])["dura"]
            cost += max(0, mx - e["dura"]) * V.SHIP_REPAIR_PER_DURA
    hmax = V.SHIP_HULL_DURA
    cost += max(0, hmax - vp["hull_dura"]) * V.SHIP_REPAIR_PER_DURA
    return cost

def any_part_broken(vp):
    """船装備のどれかが耐久0なら True（出航不可）。"""
    for slot in ("cannon", "armor", "hull"):
        e = vp["ship_equip"].get(slot)
        if e and e["dura"] <= 0:
            return True
    return vp["hull_dura"] <= 0

def _scaled(rng, vm):
    return int(random.uniform(rng["base_min"], rng["base_max"]) * vm)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 出航中の1手（進む）の解決
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def resolve_advance(vp):
    """vp['voyage'] を進めて結果テキストを返す（DB保存は呼び出し側）。"""
    v = vp["voyage"]
    sea = v["sea"]; s = V.SEAS[sea]; vm = s["val_mult"]
    v["leg"] += 1
    # 航海消耗（船本体）
    vp["hull_dura"] = max(0, vp["hull_dura"] - V.SAIL_DURA_COST)

    enc = random.choices(list(V.ENCOUNTER_WEIGHTS),
                         weights=list(V.ENCOUNTER_WEIGHTS.values()))[0]

    if enc == "calm":
        return "🌅 凪。穏やかな海をしばし進む…"

    if enc == "fish":
        tier = random.choices(list(V.FISH_HAUL),
                              weights=[V.FISH_HAUL[k]["weight"] for k in V.FISH_HAUL])[0]
        val = _scaled(V.FISH_HAUL[tier], vm)
        v["hold"] += val
        add_xp(vp, V.XP_PER_FISH)
        label = {"common":"🐟 雑魚","good":"🐠 大物","rare":"✨ レア物","legend":"🌈 伝説の獲物"}[tier]
        return f"{label}が網にかかった！ 船倉に **+{val:,}** ナトコイン相当"

    if enc == "island":
        if random.random() < V.ISLAND_TREASURE_RATE:
            val = _scaled(V.ISLAND_TREASURE, vm)
            v["hold"] += val
            add_xp(vp, V.XP_PER_ISLAND)
            return f"🏝️ 無人島に上陸…**お宝発見！** 船倉に **+{val:,}**"
        add_xp(vp, V.XP_PER_ISLAND)
        return "🏝️ 無人島に上陸したが…めぼしい物は無かった。"

    # ── 海賊戦（2層）──
    pr = random.choices(V.PIRATE_RANKS, weights=V.PIRATE_TABLE[sea])[0]
    sp = ship_power(vp); pp = personal_power(vp)
    danger = s["danger"]
    lines = [f"{pr['emoji']} **{pr['name']}** が現れた！（海戦力 {int(pr['sea_power']*danger)}）"]

    # 船戦は勝敗問わず船装備が削れる
    for slot in ("cannon", "armor", "hull"):
        e = vp["ship_equip"].get(slot)
        if e:
            e["dura"] = max(0, e["dura"] - V.NAVAL_DURA_COST)
    vp["hull_dura"] = max(0, vp["hull_dura"] - V.BOARD_DURA_COST)

    naval = win_prob(sp, pr["sea_power"] * danger)
    if random.random() < naval:
        # ① 海戦勝ち → こちらが乗り込む
        lines.append(f"⚓ 砲撃戦を制した！（船 {sp} vs {int(pr['sea_power']*danger)}）斬り込みだ！")
        board = win_prob(pp, pr["crew_power"] * danger)
        if random.random() < board:
            base = random.uniform(V.PIRATE_BASE_REWARD["base_min"], V.PIRATE_BASE_REWARD["base_max"])
            rew = int(base * pr["reward_mult"] * vm)
            v["hold"] += rew
            add_xp(vp, V.XP_PER_PIRATE_WIN)
            lines.append(f"🗡️ 白兵戦も制圧！（個人 {pp} vs {int(pr['crew_power']*danger)}）"
                         f"敵船を鹵獲、**+{rew:,}** ナトコインを積み込んだ！")
        else:
            add_xp(vp, V.XP_PER_PIRATE_LOSE)
            lines.append(f"💢 乗り込んだが返り討ち…（個人 {pp} vs {int(pr['crew_power']*danger)}）"
                         "撤退した。船倉は守った。")
    else:
        # ① 海戦負け → 乗り込まれる（防衛戦）
        lines.append(f"🔥 砲撃戦で押し負けた…（船 {sp} vs {int(pr['sea_power']*danger)}）乗り込まれる！")
        board = win_prob(pp, pr["crew_power"] * danger)
        if random.random() < board:
            add_xp(vp, V.XP_PER_PIRATE_WIN)
            lines.append(f"🛡️ 白兵戦で撃退に成功！（個人 {pp} vs {int(pr['crew_power']*danger)}）"
                         "積み荷は無事だ。")
        else:
            add_xp(vp, V.XP_PER_PIRATE_LOSE)
            # 船倉ロスト抽選（戦闘力差で重み・装甲で軽減）
            diff = (pr["sea_power"] * danger) / max(sp, 1)
            weights = [max(0.1, diff), 1, 1, max(0.1, 1 / diff)]
            rate = random.choices(V.LOSS_TIERS, weights=weights)[0]
            armor_t = vp["ship_equip"]["armor"]["t"] if vp["ship_equip"].get("armor") else 0
            if random.random() < V.ARMOR_MITIGATE_CHANCE.get(armor_t, 0):
                idx = V.LOSS_TIERS.index(rate)
                rate = V.LOSS_TIERS[min(idx + 1, len(V.LOSS_TIERS) - 1)]
            lost = int(v["hold"] * rate)
            v["hold"] -= lost
            lines.append(f"💀 防衛に失敗（個人 {pp} vs {int(pr['crew_power']*danger)}）"
                         f"…船倉の **{int(rate*100)}%**＝**{lost:,}** を奪われた！")
    return "\n".join(lines)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Embed ビルダー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_port_embed(vp):
    if not vp["has_ship"]:
        return discord.Embed(
            title="⚓ 港 ── 造船所",
            description=("船はまだ無いようだな。\n"
                         f"**🚢 帆船**を **{V.SHIP_PRICE:,}** ナトコインで仕立てれば、"
                         "未知の海へ漕ぎ出せる。\n（標準で 小型船体tier1 が付く＝🌊大海原に出られる）"),
            color=0x16a085)
    lv_need = V.xp_to_next(vp["level"]) if vp["level"] < V.LEVEL_MAX else 0
    e = discord.Embed(title="⚓ 港 ── 母港", color=0x16a085,
                      description="航海の準備を整えよう。出航で船倉を満たし、引き返して入金だ。")
    e.add_field(name="🚢 船 戦闘力", value=f"**{ship_power(vp)}**", inline=True)
    e.add_field(name="🗡️ 個人 戦闘力", value=f"**{personal_power(vp)}**", inline=True)
    e.add_field(name="📊 レベル",
                value=f"Lv.**{vp['level']}**" + (f"（XP {vp['xp']}/{lv_need}）" if lv_need else "（MAX）"),
                inline=True)
    # 装備一覧
    eq = []
    for slot in ("cannon", "armor", "hull"):
        info = V.SHIP_EQUIP[slot]; cur = vp["ship_equip"].get(slot)
        if cur:
            t = _tier(info, cur["t"])
            eq.append(f"{info['emoji']} {t['name']}（{dura_bar(cur['dura'], t['dura'])}）")
        else:
            eq.append(f"{info['emoji']} なし")
    eq.append(f"⚓ 船体耐久（{dura_bar(vp['hull_dura'], V.SHIP_HULL_DURA)}）")
    e.add_field(name="🚢 船の装備", value="\n".join(eq), inline=False)
    pe = []
    for slot in ("weapon", "armor"):
        info = V.PERSONAL_EQUIP[slot]; t = vp["personal"][slot]
        pe.append(f"{info['emoji']} {_tier(info, t)['name']}" if t else f"{info['emoji']} なし")
    e.add_field(name="🧍 個人の装備", value="　".join(pe), inline=False)
    rc = repair_cost(vp)
    if rc > 0:
        e.add_field(name="🔧 修理見積", value=f"満タンまで **{rc:,}** ナトコイン", inline=False)
    return e

def build_voyage_embed(vp, last_msg=None):
    v = vp["voyage"]; s = V.SEAS[v["sea"]]
    e = discord.Embed(
        title=f"{s['name']} ── 航海中",
        description=last_msg or s["flavor"], color=discord.Color.dark_teal())
    e.add_field(name="🧭 航行", value=f"{v['leg']} 海里", inline=True)
    e.add_field(name="📦 船倉（未確定）", value=f"**{v['hold']:,}** ナトコイン", inline=True)
    e.add_field(name="⛽ 次の燃料", value=f"{s['fuel']:,}", inline=True)
    cond = []
    for slot in ("cannon", "armor", "hull"):
        cur = vp["ship_equip"].get(slot)
        if cur:
            t = _tier(V.SHIP_EQUIP[slot], cur["t"])
            cond.append(f"{V.SHIP_EQUIP[slot]['emoji']}{dura_bar(cur['dura'], t['dura'])}")
    cond.append(f"⚓{dura_bar(vp['hull_dura'], V.SHIP_HULL_DURA)}")
    e.add_field(name="🛠️ 船の状態", value=" ".join(cond), inline=False)
    e.set_footer(text="⛵ 進む＝燃料を払って海里を稼ぐ／⚓ 引き返す＝船倉を銀行に入金")
    return e

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 母港ハブ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class PortView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(self.user_id)
        if not vp["has_ship"]:
            self.add_item(BuyShipButton())
        else:
            self.add_item(SailButton())
            self.add_item(ShopButton())
            self.add_item(RepairButton())
        self.add_item(LeaveButton())

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class BuyShipButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=f"🚢 船を仕立てる（{V.SHIP_PRICE:,}）", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        uid, gid = view.user_id, view.gid
        if db.get_balance(uid, gid) < V.SHIP_PRICE:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{V.SHIP_PRICE:,} 必要）", ephemeral=True); return
        vp = db.get_voyage(uid)
        if vp["has_ship"]:
            await interaction.response.send_message("もう船を持っている", ephemeral=True); return
        db.update_balance(uid, gid, -V.SHIP_PRICE)
        vp["has_ship"] = True
        t1 = _tier(V.SHIP_EQUIP["hull"], 1)
        vp["ship_equip"]["hull"] = {"t": 1, "dura": t1["dura"]}
        vp["hull_dura"] = V.SHIP_HULL_DURA
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid))
        await interaction.followup.send("🚢 船を仕立てた！砲と装甲をショップで積もう。", ephemeral=True)

class SailButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🧭 出航", style=discord.ButtonStyle.primary)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        vp = db.get_voyage(view.user_id)
        if any_part_broken(vp):
            await interaction.response.send_message(
                "🔧 装備が壊れている。先に修理しないと出航できない。", ephemeral=True); return
        await interaction.response.edit_message(
            embed=discord.Embed(title="🧭 出航 ── 海を選べ", color=discord.Color.teal(),
                                description="奥の海ほど高リターン・高リスク。船体tierで解放される。"),
            view=SeaSelectView(view.user_id, view.gid))

class ShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏪 ショップ", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(view.user_id)),
            view=ShopView(view.user_id, view.gid))

class RepairButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔧 修理", style=discord.ButtonStyle.secondary)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        uid, gid = view.user_id, view.gid
        vp = db.get_voyage(uid)
        cost = repair_cost(vp)
        if cost <= 0:
            await interaction.response.send_message("✅ どこも傷んでいない。", ephemeral=True); return
        if db.get_balance(uid, gid) < cost:
            await interaction.response.send_message(
                f"❌ 修理代が足りない（{cost:,} 必要）", ephemeral=True); return
        db.update_balance(uid, gid, -cost)
        for slot in ("cannon", "armor", "hull"):
            e = vp["ship_equip"].get(slot)
            if e:
                e["dura"] = _tier(V.SHIP_EQUIP[slot], e["t"])["dura"]
        vp["hull_dura"] = V.SHIP_HULL_DURA
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid))
        await interaction.followup.send(f"🔧 全装備を修理した（-{cost:,}）", ephemeral=True)

class LeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚪 立ち去る", style=discord.ButtonStyle.secondary, row=2)
    async def callback(self, interaction):
        view = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(content="港を後にした。", embed=None, view=None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 海セレクト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SeaSelectView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(self.user_id)
        for sea in V.SEA_ORDER:
            self.add_item(SeaButton(sea, can_enter_sea(vp, sea)))
        back = discord.ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)), view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class SeaButton(discord.ui.Button):
    def __init__(self, sea, unlocked):
        s = V.SEAS[sea]
        super().__init__(label=("" if unlocked else "🔒 ") + s["name"],
                         style=discord.ButtonStyle.primary if unlocked else discord.ButtonStyle.secondary,
                         disabled=not unlocked)
        self.sea = sea
    async def callback(self, interaction):
        view: SeaSelectView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid = view.user_id, view.gid
        vp = db.get_voyage(uid)
        if not can_enter_sea(vp, self.sea):
            await interaction.response.send_message("🔒 船体tierが足りない（ショップで船体を強化しよう）", ephemeral=True); return
        vp["voyage"] = {"sea": self.sea, "leg": 0, "hold": 0}
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_voyage_embed(vp, f"⛵ {V.SEAS[self.sea]['name']} へ出航した！"),
            view=VoyageView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 航海中
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class VoyageView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⛵ 進む", style=discord.ButtonStyle.primary)
    async def advance(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if not vp.get("voyage"):
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        sea = vp["voyage"]["sea"]; fuel = V.SEAS[sea]["fuel"]
        if db.get_balance(uid, gid) < fuel:
            await interaction.response.send_message(
                f"⛽ 燃料代が払えない（{fuel:,} 必要）。引き返すしかない…", ephemeral=True); return
        if any_part_broken(vp):
            await interaction.response.send_message(
                "🛠️ 装備が壊れた！これ以上は進めない。引き返して修理を。", ephemeral=True); return
        db.update_balance(uid, gid, -fuel)
        msg = resolve_advance(vp)
        db.save_voyage(uid, vp)
        # 装備破損で進行不可になったら警告を添える
        if any_part_broken(vp):
            msg += "\n\n🛠️ **装備が限界だ…！引き返すしかない。**"
        await interaction.response.edit_message(embed=build_voyage_embed(vp, msg), view=self)

    @discord.ui.button(label="⚓ 引き返す（入金）", style=discord.ButtonStyle.success)
    async def go_back(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        v = vp.get("voyage")
        hold = v["hold"] if v else 0
        leg = v["leg"] if v else 0
        if hold > 0:
            db.update_balance(uid, gid, hold)
        vp["voyage"] = None
        db.save_voyage(uid, vp)
        e = discord.Embed(
            title="⚓ 帰港",
            description=(f"{leg} 海里の航海を終えた。\n"
                         f"船倉の **{hold:,}** ナトコインを銀行に入金した！"),
            color=discord.Color.gold())
        rc = repair_cost(vp)
        if rc > 0:
            e.add_field(name="🔧 整備", value=f"装備が傷んでいる（修理 **{rc:,}**）", inline=False)
        await interaction.response.edit_message(embed=e, view=PortView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: ショップ（船装備＋個人装備の購入/強化）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_shop_embed(vp):
    e = discord.Embed(title="🏪 港の総合ショップ", color=discord.Color.gold(),
                      description="装備を買って強くなろう。船体を上げると奥の海が解放される。\n"
                                  "（将来はガチャ＆マーケットでも入手可）")
    e.add_field(name="所持金参照", value="購入はスロットを選択", inline=False)
    return e

class ShopView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(EquipSelect(user_id, gid))
        back = discord.ui.Button(label="◀ 港へ戻る", style=discord.ButtonStyle.secondary, row=1)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)), view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class EquipSelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = [
            discord.SelectOption(label="💥 砲（海戦の攻撃）", value="ship:cannon"),
            discord.SelectOption(label="🛡️ 装甲（被害軽減）", value="ship:armor"),
            discord.SelectOption(label="⛵ 船体（戦闘力＋海の解放）", value="ship:hull"),
            discord.SelectOption(label="⚔️ 武器（白兵の攻撃）", value="pers:weapon"),
            discord.SelectOption(label="🥼 防具（白兵の防御）", value="pers:armor"),
        ]
        super().__init__(placeholder="強化する装備スロットを選ぶ", options=opts)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        kind, slot = self.values[0].split(":")
        await interaction.response.edit_message(
            embed=build_tier_embed(db.get_voyage(self.user_id), kind, slot),
            view=TierBuyView(self.user_id, self.gid, kind, slot))

def build_tier_embed(vp, kind, slot):
    if kind == "ship":
        info = V.SHIP_EQUIP[slot]; cur = vp["ship_equip"].get(slot); cur_t = cur["t"] if cur else 0
    else:
        info = V.PERSONAL_EQUIP[slot]; cur_t = vp["personal"][slot]
    e = discord.Embed(title=f"{info['emoji']} {info['name']} ── {info['role']}",
                      color=discord.Color.gold())
    lines = []
    for t in info["tiers"]:
        tag = "✅所持" if t["t"] <= cur_t else f"{t['price']:,}"
        extra = ""
        if kind == "ship" and slot == "hull":
            sea = next((sk for sk in V.SEA_ORDER if V.SEAS[sk]["unlock_hull"] == t["t"]), None)
            if sea: extra = f"　→ {V.SEAS[sea]['name']} 解放"
        if kind == "pers":
            extra = f"　(必要Lv{t['req_lv']})"
        lines.append(f"**t{t['t']} {t['name']}**　戦闘力+{t['power']}　{tag}{extra}")
    e.add_field(name="ラインナップ（下のボタンで購入）", value="\n".join(lines), inline=False)
    return e

class TierBuyView(discord.ui.View):
    def __init__(self, user_id, gid, kind, slot):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.kind = kind; self.slot = slot
        info = V.SHIP_EQUIP[slot] if kind == "ship" else V.PERSONAL_EQUIP[slot]
        vp = db.get_voyage(self.user_id)
        cur_t = (vp["ship_equip"].get(slot)["t"] if (kind == "ship" and vp["ship_equip"].get(slot)) else
                 (vp["personal"][slot] if kind == "pers" else 0))
        for t in info["tiers"]:
            owned = t["t"] <= cur_t
            self.add_item(BuyTierButton(t["t"], t["name"], owned))
        back = discord.ui.Button(label="◀ スロット選択へ", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShopView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class BuyTierButton(discord.ui.Button):
    def __init__(self, tier, name, owned):
        super().__init__(label=("✅ " if owned else f"t{tier} ") + name,
                         style=discord.ButtonStyle.secondary if owned else discord.ButtonStyle.success,
                         disabled=owned, row=(tier - 1) // 5)
        self.tier = tier
    async def callback(self, interaction):
        view: TierBuyView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, kind, slot = view.user_id, view.gid, view.kind, view.slot
        vp = db.get_voyage(uid)
        info = V.SHIP_EQUIP[slot] if kind == "ship" else V.PERSONAL_EQUIP[slot]
        t = _tier(info, self.tier)
        # 個人装備はレベル制限
        if kind == "pers" and vp["level"] < t["req_lv"]:
            await interaction.response.send_message(
                f"🔒 Lv{t['req_lv']} 必要（現在 Lv{vp['level']}）", ephemeral=True); return
        if db.get_balance(uid, gid) < t["price"]:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{t['price']:,} 必要）", ephemeral=True); return
        db.update_balance(uid, gid, -t["price"])
        if kind == "ship":
            vp["ship_equip"][slot] = {"t": self.tier, "dura": t["dura"]}
        else:
            vp["personal"][slot] = self.tier
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_tier_embed(vp, kind, slot), view=TierBuyView(uid, gid, kind, slot))
        await interaction.followup.send(f"🛒 **{t['name']}** を購入・装備した！（-{t['price']:,}）", ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 公開エントリ（fund.py の港ハブから呼ばれる）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def open_voyage(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    # 航海中だった場合は航海画面へ復帰
    if vp.get("voyage"):
        embed = build_voyage_embed(vp, "⛵ 航海の続きだ。")
        view = VoyageView(uid, gid)
    else:
        embed = build_port_embed(vp); view = PortView(uid, gid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class Voyage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Voyage(bot))
