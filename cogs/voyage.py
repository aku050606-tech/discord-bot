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
    """SHIP_EQUIP の tier dict を取得（t は 1始まり）。"""
    return slot_group["tiers"][t - 1]

def ship_power(vp):
    p = V.SHIP_BASE_POWER
    for slot in ("cannon", "armor", "hull"):
        e = vp["ship_equip"].get(slot)
        if e:
            p += _tier(V.SHIP_EQUIP[slot], e["t"])["power"]
    return p

# インベントリ枠上限
INV_CAP = {"weapon": 5, "torso": 3, "legs": 3}
SKILL_CAP = 5

def max_hp(vp):
    return 100 + (vp.get("level", 1) - 1) * 10

def equipped_inst(vp, part):
    """装備中インスタンス {"item":id,"skills":[...]} を返す（未装備=None）。"""
    idx = vp["equipped"].get(part)
    lst = vp["inventory"].get(part, [])
    if idx is None or not (0 <= idx < len(lst)):
        return None
    return lst[idx]

def attack_power(vp):
    w = equipped_inst(vp, "weapon")
    base = V.WEAPONS[w["item"]]["power"] if (w and w["item"] in V.WEAPONS) else 0
    return V.LEVEL_BASE_POWER * vp["level"] + base

def defense_power(vp):
    d = 0
    for part in ("torso", "legs"):
        it = equipped_inst(vp, part)
        if it and it["item"] in V.ARMOR_PARTS[part]["items"]:
            d += V.ARMOR_PARTS[part]["items"][it["item"]]["power"]
    return d

def personal_power(vp):
    return attack_power(vp) + defense_power(vp)

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
    w = equipped_inst(vp, "weapon")
    if w and w["item"] in V.WEAPONS:
        wd = V.WEAPONS[w["item"]]; wt = V.WEAPON_TYPES[wd["wtype"]]
        pe.append(f"⚔️ {V.rarity_stars(wd['rank'])} {wd['name']}（{wt['name']}）")
    else:
        pe.append("⚔️ 武器：なし")
    for part in V.ARMOR_PART_ORDER:
        info = V.ARMOR_PARTS[part]; it = equipped_inst(vp, part)
        if it and it["item"] in info["items"]:
            idd = info["items"][it["item"]]
            pe.append(f"{info['emoji']} {V.rarity_stars(idd['rank'])} {idd['name']}")
        else:
            pe.append(f"{info['emoji']} {info['name']}：なし")
    e.add_field(name="🧍 個人の装備", value="\n".join(pe), inline=False)
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
        ]
        super().__init__(placeholder="強化する船装備スロットを選ぶ", options=opts)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        kind, slot = self.values[0].split(":")
        await interaction.response.edit_message(
            embed=build_tier_embed(db.get_voyage(self.user_id), kind, slot),
            view=TierBuyView(self.user_id, self.gid, kind, slot))

def build_tier_embed(vp, kind, slot):
    info = V.SHIP_EQUIP[slot]; cur = vp["ship_equip"].get(slot); cur_t = cur["t"] if cur else 0
    e = discord.Embed(title=f"{info['emoji']} {info['name']} ── {info['role']}",
                      color=discord.Color.gold())
    lines = []
    for t in info["tiers"]:
        tag = "✅所持" if t["t"] <= cur_t else f"{t['price']:,}"
        extra = ""
        if slot == "hull":
            sea = next((sk for sk in V.SEA_ORDER if V.SEAS[sk]["unlock_hull"] == t["t"]), None)
            if sea: extra = f"　→ {V.SEAS[sea]['name']} 解放"
        lines.append(f"**t{t['t']} {t['name']}**　戦闘力+{t['power']}　{tag}{extra}")
    e.add_field(name="ラインナップ（下のボタンで購入）", value="\n".join(lines), inline=False)
    return e

class TierBuyView(discord.ui.View):
    def __init__(self, user_id, gid, kind, slot):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.kind = kind; self.slot = slot
        info = V.SHIP_EQUIP[slot]
        vp = db.get_voyage(self.user_id)
        cur = vp["ship_equip"].get(slot); cur_t = cur["t"] if cur else 0
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
        uid, gid, slot = view.user_id, view.gid, view.slot
        vp = db.get_voyage(uid)
        info = V.SHIP_EQUIP[slot]
        t = _tier(info, self.tier)
        if db.get_balance(uid, gid) < t["price"]:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{t['price']:,} 必要）", ephemeral=True); return
        db.update_balance(uid, gid, -t["price"])
        vp["ship_equip"][slot] = {"t": self.tier, "dura": t["dura"]}
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_tier_embed(vp, view.kind, slot), view=TierBuyView(uid, gid, view.kind, slot))
        await interaction.followup.send(f"🛒 **{t['name']}** を購入・装備した！（-{t['price']:,}）", ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚒️ 装備屋 ＆ 📦 インベントリ（部位別・最大枠・装備/解除・売却・刻印）
#   装備は買うとインベントリに入る（武器5/胴3/脚3）。満杯は入れ替え（売却）。
#   技は装備中インスタンスに刻む（武器種別＆枠チェック）。技は装備について回る。
#   売却＝(装備価格＋刻んだ技価格の合計)÷10。技単体＝技価格÷10。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import voyage_skills as VS

def item_def(part, item_id):
    return V.WEAPONS.get(item_id) if part == "weapon" else V.ARMOR_PARTS[part]["items"].get(item_id)

def item_slots(part, item_id):
    d = item_def(part, item_id)
    return d.get("slots", 1) if d else 1

def item_label(part, inst, with_skills=True):
    d = item_def(part, inst["item"])
    if not d:
        return "不明な装備"
    star = V.rarity_stars(d["rank"])
    if part == "weapon":
        wt = V.WEAPON_TYPES[d["wtype"]]["name"]
        s = f"{star} {d['name']}（{wt}・攻{d['power']}・枠{d.get('slots',1)}）"
    else:
        s = f"{star} {d['name']}（防{d['power']}）"
    if with_skills and inst.get("skills"):
        s += " {" + "".join(VS.SKILLS[x]["emoji"] for x in inst["skills"]) + "}"
    return s

def inst_sell_value(part, inst):
    total = item_def(part, inst["item"])["price"]
    for sid in inst.get("skills", []):
        total += VS.SKILLS.get(sid, {}).get("price", 0)
    return total // 10

def _remove_item(vp, part, idx):
    """インベントリから装備を取り除き、装備中インデックスを補正して返す。"""
    lst = vp["inventory"][part]
    inst = lst.pop(idx)
    eq = vp["equipped"][part]
    if eq is not None:
        if eq == idx: vp["equipped"][part] = None
        elif eq > idx: vp["equipped"][part] = eq - 1
    return inst

def _return_skills(vp, inst):
    """装備に刻まれた技を手元(learned_skills)に戻す。"""
    for sid in inst.get("skills", []):
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
    inst["skills"] = []

PART_NAMES = {"weapon": "⚔️ 武器", "torso": "🦺 胴", "legs": "🦵 脚"}

def _skill_fits(part, item_id, sid):
    s = VS.SKILLS.get(sid)
    if not s: return False
    if part == "weapon":
        return s["slot"] == "weapon" and V.WEAPONS[item_id]["wtype"] in s.get("wtypes", [])
    return s["slot"] == "armor"

# ━━━━━━━━ 装備屋 ━━━━━━━━
def build_equipshop_embed(vp):
    e = discord.Embed(title="⚒️ 装備屋",
                      color=discord.Color.dark_orange(),
                      description="武器・防具・技を買い、装備に技を刻もう。\n"
                                  "武器の種別に合う技だけ刻める（杖＝回復専用 等）。持ち替え・売却はインベントリで。")
    for part in ("weapon", "torso", "legs"):
        cnt = len(vp["inventory"][part])
        e.add_field(name=f"{PART_NAMES[part]}（所持 {cnt}/{INV_CAP[part]}）",
                    value="（インベントリで管理）", inline=True)
    inv = vp.get("learned_skills", {})
    have = [f"{VS.SKILLS[s]['emoji']}{VS.SKILLS[s]['name']}×{n}" for s, n in inv.items() if n > 0]
    e.add_field(name=f"🎒 所持技 {sum(inv.values())}/{SKILL_CAP}",
                value="　".join(have) if have else "なし", inline=False)
    e.add_field(name="🧰 技外しキット", value=f"{vp.get('unequip_kits',0)} 個", inline=True)
    return e

def _eqshop_back(user_id, gid):
    btn = discord.ui.Button(label="◀ 装備屋トップ", style=discord.ButtonStyle.secondary, row=2)
    async def _cb(it):
        if str(it.user.id) != str(user_id):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(user_id)),
                                       view=EquipShopView(user_id, gid))
    btn.callback = _cb
    return btn

class EquipShopView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
    async def guard(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return False
        return True

    @discord.ui.button(label="🗡️ 武器を買う", style=discord.ButtonStyle.success, row=0)
    async def bw(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=BuyView(self.user_id, self.gid, "weapon"))
    @discord.ui.button(label="🛡️ 防具を買う", style=discord.ButtonStyle.success, row=0)
    async def ba(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=BuyView(self.user_id, self.gid, "armor"))
    @discord.ui.button(label="📜 技を買う", style=discord.ButtonStyle.success, row=0)
    async def bs(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=SkillBuyView(self.user_id, self.gid))
    @discord.ui.button(label="⚒️ 技を刻む", style=discord.ButtonStyle.primary, row=1)
    async def en(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=EngravePartView(self.user_id, self.gid))
    @discord.ui.button(label="🔧 技を外す", style=discord.ButtonStyle.secondary, row=1)
    async def un(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=UnengraveView(self.user_id, self.gid))
    @discord.ui.button(label="🧰 外しキット購入", style=discord.ButtonStyle.success, row=1)
    async def bk(self, it, b):
        if not await self.guard(it): return
        uid, gid = self.user_id, self.gid
        if db.get_balance(uid, gid) < VS.UNEQUIP_KIT_PRICE:
            await it.response.send_message(f"❌ コインが足りない（{VS.UNEQUIP_KIT_PRICE:,}）", ephemeral=True); return
        db.update_balance(uid, gid, -VS.UNEQUIP_KIT_PRICE)
        vp = db.get_voyage(uid); vp["unequip_kits"] = vp.get("unequip_kits", 0) + 1; db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=self)
        await it.followup.send(f"🧰 技外しキット購入（-{VS.UNEQUIP_KIT_PRICE:,}）", ephemeral=True)
    @discord.ui.button(label="📦 インベントリ", style=discord.ButtonStyle.primary, row=2)
    async def inv(self, it, b):
        if not await self.guard(it): return
        await open_inventory(it, self.user_id, back="equip")
    @discord.ui.button(label="◀ タウンへ", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, it, b):
        if not await self.guard(it): return
        from cogs.menu import go_town
        await go_town(it, self.user_id)

# ── 装備購入（武器/防具）。満杯なら入れ替え ──
class BuyView(discord.ui.View):
    def __init__(self, user_id, gid, cat):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.cat = cat
        self.add_item(BuySelect(user_id, gid, cat))
        self.add_item(_eqshop_back(user_id, gid))

class BuySelect(discord.ui.Select):
    def __init__(self, user_id, gid, cat):
        self.user_id = str(user_id); self.gid = str(gid); self.cat = cat
        opts = []
        if cat == "weapon":
            for wid, wd in V.WEAPONS.items():
                wt = V.WEAPON_TYPES[wd["wtype"]]["name"]
                opts.append(discord.SelectOption(
                    label=f"{V.rarity_stars(wd['rank'])} {wd['name']}（{wt}）", value=f"weapon:{wid}",
                    description=f"攻{wd['power']}・技枠{wd['slots']}・{wd['price']:,}コイン"))
        else:
            for part in V.ARMOR_PART_ORDER:
                info = V.ARMOR_PARTS[part]
                for iid, idd in info["items"].items():
                    opts.append(discord.SelectOption(
                        label=f"{V.rarity_stars(idd['rank'])} {idd['name']}（{info['name']}）", value=f"{part}:{iid}",
                        description=f"防{idd['power']}・{idd['price']:,}コイン"))
        super().__init__(placeholder="買う装備を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, iid = self.values[0].split(":")
        d = item_def(part, iid); uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if db.get_balance(uid, gid) < d["price"]:
            await it.response.send_message(f"❌ コインが足りない（{d['price']:,}）", ephemeral=True); return
        if len(vp["inventory"][part]) >= INV_CAP[part]:
            # 満杯 → 入れ替えフロー
            await it.response.edit_message(
                embed=build_equipshop_embed(vp),
                view=SwapView(uid, gid, part, iid)); return
        db.update_balance(uid, gid, -d["price"])
        vp["inventory"][part].append({"item": iid, "skills": []})
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=BuyView(uid, gid, self.cat))
        await it.followup.send(f"🛒 **{d['name']}** を購入！インベントリに追加（-{d['price']:,}）", ephemeral=True)

class SwapView(discord.ui.View):
    def __init__(self, user_id, gid, part, new_iid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(SwapSelect(user_id, gid, part, new_iid))
        self.add_item(_eqshop_back(user_id, gid))

class SwapSelect(discord.ui.Select):
    def __init__(self, user_id, gid, part, new_iid):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part; self.new_iid = new_iid
        vp = db.get_voyage(user_id)
        opts = []
        for i, inst in enumerate(vp["inventory"][part]):
            opts.append(discord.SelectOption(
                label=f"{item_label(part, inst, with_skills=False)[:80]}",
                value=str(i),
                description=f"売値 {inst_sell_value(part, inst):,}（これを売って入れ替え）"))
        super().__init__(placeholder=f"{PART_NAMES[part]}が満杯。どれと入れ替える？", options=opts[:25])
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, part = self.user_id, self.gid, self.part
        vp = db.get_voyage(uid); idx = int(self.values[0])
        d = item_def(part, self.new_iid)
        if db.get_balance(uid, gid) < d["price"]:
            await it.response.send_message(f"❌ コインが足りない（{d['price']:,}）", ephemeral=True); return
        old = vp["inventory"][part][idx]
        sell = inst_sell_value(part, old)
        _return_skills(vp, old)          # 売る前に刻印技は手元に戻す（技は失わない）
        _remove_item(vp, part, idx)
        db.update_balance(uid, gid, -d["price"] + sell)
        vp["inventory"][part].append({"item": self.new_iid, "skills": []})
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=EquipShopView(uid, gid))
        await it.followup.send(
            f"🔄 入れ替え完了：**{d['name']}** を購入（-{d['price']:,}）／古い装備を売却（+{sell:,}）。"
            "刻んでた技は手元に戻したよ。", ephemeral=True)

# ── 技購入 ──
class SkillBuyView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(SkillBuySelect(user_id, gid)); self.add_item(_eqshop_back(user_id, gid))

class SkillBuySelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = []
        for sid, s in VS.SKILLS.items():
            if s["slot"] == "weapon":
                tags = "・".join(V.WEAPON_TYPES[w]["name"] for w in s["wtypes"])
            elif s["slot"] == "armor":
                tags = "胴・脚"
            else:
                tags = "船"
            opts.append(discord.SelectOption(label=f"{s['name']}（{s['price']:,}）", emoji=s["emoji"],
                        value=sid, description=f"[{tags}] {s['desc'][:46]}"))
        super().__init__(placeholder="買う技を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        sid = self.values[0]; s = VS.SKILLS[sid]; uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if sum(vp["learned_skills"].values()) >= SKILL_CAP:
            await it.response.send_message(f"🎒 所持技が満杯（{SKILL_CAP}）。インベントリで技を売るか刻んで空けて。", ephemeral=True); return
        if db.get_balance(uid, gid) < s["price"]:
            await it.response.send_message(f"❌ コインが足りない（{s['price']:,}）", ephemeral=True); return
        db.update_balance(uid, gid, -s["price"])
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=SkillBuyView(uid, gid))
        await it.followup.send(f"📜 **{s['name']}** 購入！「技を刻む」で装備にセット（-{s['price']:,}）", ephemeral=True)

# ── 技を刻む（装備中の武器/防具インスタンスに）──
class EngravePartView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); usable = []
        for part in ("weapon", "torso", "legs"):
            inst = equipped_inst(vp, part)
            if not inst: continue
            if len(inst.get("skills", [])) >= item_slots(part, inst["item"]): continue
            if any(vp["learned_skills"].get(sid, 0) > 0 and _skill_fits(part, inst["item"], sid)
                   for sid in vp["learned_skills"]):
                usable.append(part)
        if usable: self.add_item(EngravePartSelect(user_id, gid, usable))
        self.add_item(_eqshop_back(user_id, gid))

class EngravePartSelect(discord.ui.Select):
    def __init__(self, user_id, gid, parts):
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id)
        opts = []
        for p in parts:
            inst = equipped_inst(vp, p)
            opts.append(discord.SelectOption(label=f"{PART_NAMES[p]}：{item_label(p, inst, False)[:70]}", value=p))
        super().__init__(placeholder="刻む装備（装備中）を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                       view=EngraveSkillView(self.user_id, self.gid, self.values[0]))

class EngraveSkillView(discord.ui.View):
    def __init__(self, user_id, gid, part):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        vp = db.get_voyage(user_id); inst = equipped_inst(vp, part)
        owned = [sid for sid in vp["learned_skills"]
                 if vp["learned_skills"].get(sid, 0) > 0 and inst and _skill_fits(part, inst["item"], sid)]
        if owned: self.add_item(EngraveSkillSelect(user_id, gid, part, owned))
        self.add_item(_eqshop_back(user_id, gid))

class EngraveSkillSelect(discord.ui.Select):
    def __init__(self, user_id, gid, part, skills):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        opts = [discord.SelectOption(label=VS.SKILLS[s]["name"], emoji=VS.SKILLS[s]["emoji"],
                value=s, description=VS.SKILLS[s]["desc"][:60]) for s in skills]
        super().__init__(placeholder="刻む技を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, part = self.user_id, self.gid, self.part; sid = self.values[0]
        vp = db.get_voyage(uid); inst = equipped_inst(vp, part)
        if not inst:
            await it.response.send_message("装備していない", ephemeral=True); return
        if len(inst.get("skills", [])) >= item_slots(part, inst["item"]):
            await it.response.send_message("⚠️ 枠が満杯。先に外して（キット）", ephemeral=True); return
        if vp["learned_skills"].get(sid, 0) <= 0 or not _skill_fits(part, inst["item"], sid):
            await it.response.send_message("❌ ここには刻めない技", ephemeral=True); return
        vp["learned_skills"][sid] -= 1
        if vp["learned_skills"][sid] <= 0: del vp["learned_skills"][sid]
        inst.setdefault("skills", []).append(sid)
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=EquipShopView(uid, gid))
        await it.followup.send(f"⚒️ {PART_NAMES[part]} に **{VS.SKILLS[sid]['name']}** を刻んだ！", ephemeral=True)

# ── 技を外す（キット消費・装備中インスタンスから）──
class UnengraveView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); pairs = []
        for part in ("weapon", "torso", "legs"):
            inst = equipped_inst(vp, part)
            if inst:
                for i, sid in enumerate(inst.get("skills", [])):
                    pairs.append((part, i, sid))
        if pairs: self.add_item(UnengraveSelect(user_id, gid, pairs))
        self.add_item(_eqshop_back(user_id, gid))

class UnengraveSelect(discord.ui.Select):
    def __init__(self, user_id, gid, pairs):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = [discord.SelectOption(label=f"{PART_NAMES[p]}：{VS.SKILLS[sid]['name']} を外す", value=f"{p}:{i}")
                for p, i, sid in pairs]
        super().__init__(placeholder="外す技を選ぶ（キット1個）", options=opts[:25])
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid = self.user_id, self.gid; part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(uid)
        if vp.get("unequip_kits", 0) <= 0:
            await it.response.send_message("🧰 キットが無い", ephemeral=True); return
        inst = equipped_inst(vp, part)
        if not inst or i >= len(inst.get("skills", [])):
            await it.response.send_message("もう外れている", ephemeral=True); return
        sid = inst["skills"].pop(i); vp["unequip_kits"] -= 1
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp), view=EquipShopView(uid, gid))
        await it.followup.send(f"🔧 **{VS.SKILLS[sid]['name']}** を外した（キット-1）。技は手元へ。", ephemeral=True)

# ━━━━━━━━ 📦 インベントリ（タブ：装備/技/消耗品/船）━━━━━━━━
def build_inv_embed(vp, tab):
    if tab == "equip":
        e = discord.Embed(title="📦 インベントリ ── 🗡️ 装備", color=0x2E86C1)
        e.add_field(name="📊 ステータス",
                    value=(f"❤️ HP {vp.get('cur_hp', max_hp(vp))}/{max_hp(vp)}\n"
                           f"⚔️ 攻撃力 {attack_power(vp)}\n"
                           f"🛡️ 防御力 {defense_power(vp)}\n"
                           f"📊 レベル {vp['level']}（XP {vp['xp']}/{V.xp_to_next(vp['level'])}）\n"
                           f"🗡️ 総合戦闘力 **{personal_power(vp)}**"), inline=False)
        for part in ("weapon", "torso", "legs"):
            lst = vp["inventory"][part]; eq = vp["equipped"][part]
            if lst:
                lines = []
                for i, inst in enumerate(lst):
                    mark = "✅" if eq == i else "・"
                    lines.append(f"{mark} {item_label(part, inst)}")
                val = "\n".join(lines)
            else:
                val = "（なし）"
            e.add_field(name=f"{PART_NAMES[part]} {len(lst)}/{INV_CAP[part]}", value=val, inline=False)
    elif tab == "skill":
        e = discord.Embed(title="📦 インベントリ ── ⚔️ 技（未刻印）", color=0x2E86C1)
        inv = vp.get("learned_skills", {})
        lines = [f"{VS.SKILLS[s]['emoji']} {VS.SKILLS[s]['name']} ×{n}（売値 {VS.SKILLS[s]['price']//10:,}）"
                 for s, n in inv.items() if n > 0]
        e.description = "\n".join(lines) if lines else "未刻印の技はなし"
        e.set_footer(text=f"所持 {sum(inv.values())}/{SKILL_CAP}　※刻んだ技は装備側に付く")
    elif tab == "item":
        e = discord.Embed(title="📦 インベントリ ── 🧪 消耗品", color=0x2E86C1)
        e.description = f"🧰 技外しキット ×{vp.get('unequip_kits',0)}\n（食料・回復アイテムは今後実装）"
    else:  # ship
        e = discord.Embed(title="📦 インベントリ ── 🚢 船", color=0x2E86C1,
                          description="船・船装備は **港** でいじれる（ここでは閲覧のみ）。")
        if not vp["has_ship"]:
            e.add_field(name="船", value="未所持（港で仕立てる）", inline=False)
        else:
            lines = []
            for slot in ("cannon", "armor", "hull"):
                cur = vp["ship_equip"].get(slot)
                nm = V.SHIP_EQUIP[slot]["name"]; emj = V.SHIP_EQUIP[slot]["emoji"]
                if cur:
                    t = _tier(V.SHIP_EQUIP[slot], cur["t"])
                    lines.append(f"{emj} {nm}：{t['name']}（耐久 {cur['dura']}/{t['dura']}）")
                else:
                    lines.append(f"{emj} {nm}：なし")
            lines.append(f"⚓ 船体耐久：{vp['hull_dura']}/{V.SHIP_HULL_DURA}")
            e.add_field(name="🚢 船の状態", value="\n".join(lines), inline=False)
    return e

class InventoryView(discord.ui.View):
    def __init__(self, user_id, gid, tab="equip", back="town"):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.tab = tab; self.back = back
        # タブ
        for key, label in [("equip", "🗡️ 装備"), ("skill", "⚔️ 技"), ("item", "🧪 消耗品"), ("ship", "🚢 船")]:
            self.add_item(InvTabButton(key, label, key == tab))
        # 装備タブ専用：持ち替え・外す・売却
        vp = db.get_voyage(user_id)
        if tab == "equip":
            if any(vp["inventory"][p] for p in ("weapon", "torso", "legs")):
                self.add_item(EquipSwitchSelect(user_id, gid, back))
            if any(vp["equipped"][p] is not None for p in ("weapon", "torso", "legs")):
                self.add_item(UnequipPartSelect(user_id, gid, back))
            if any(vp["inventory"][p] for p in ("weapon", "torso", "legs")):
                self.add_item(SellEquipSelect(user_id, gid, back))
        elif tab == "skill":
            if any(n > 0 for n in vp.get("learned_skills", {}).values()):
                self.add_item(SellSkillSelect(user_id, gid, back))
        self.add_item(InvBackButton(user_id, gid, back))

class InvTabButton(discord.ui.Button):
    def __init__(self, key, label, active):
        super().__init__(label=label, style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
                         row=0, disabled=active)
        self.key = key
    async def callback(self, it):
        v = self.view
        if str(it.user.id) != v.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_inv_embed(db.get_voyage(v.user_id), self.key),
                                       view=InventoryView(v.user_id, v.gid, self.key, v.back))

class EquipSwitchSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            for i, inst in enumerate(vp["inventory"][part]):
                eqmark = "（装備中）" if vp["equipped"][part] == i else ""
                opts.append(discord.SelectOption(
                    label=f"{PART_NAMES[part].split(' ')[1]}: {item_label(part, inst, False)[:70]}{eqmark}",
                    value=f"{part}:{i}"))
        super().__init__(placeholder="装備する（持ち替え）", options=opts[:25], row=1)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(self.user_id); vp["equipped"][part] = i; db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "equip"),
                                       view=InventoryView(self.user_id, self.gid, "equip", self.back))

class UnequipPartSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            if vp["equipped"][part] is not None:
                opts.append(discord.SelectOption(label=f"{PART_NAMES[part]} を外す", value=part))
        super().__init__(placeholder="装備を外す", options=opts, row=2)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part = self.values[0]
        vp = db.get_voyage(self.user_id); vp["equipped"][part] = None; db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "equip"),
                                       view=InventoryView(self.user_id, self.gid, "equip", self.back))

class SellEquipSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            for i, inst in enumerate(vp["inventory"][part]):
                sv = inst_sell_value(part, inst)
                opts.append(discord.SelectOption(
                    label=f"売却: {item_label(part, inst, False)[:60]}",
                    value=f"{part}:{i}", description=f"売値 {sv:,}（刻んだ技は手元に戻る）"))
        super().__init__(placeholder="装備を売る", options=opts[:25], row=3)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(self.user_id)
        if i >= len(vp["inventory"][part]):
            await it.response.send_message("もう無い", ephemeral=True); return
        inst = vp["inventory"][part][i]; sv = inst_sell_value(part, inst)
        nm = item_def(part, inst["item"])["name"]; had = bool(inst.get("skills"))
        _return_skills(vp, inst)
        _remove_item(vp, part, i)
        db.update_balance(self.user_id, self.gid, sv)
        db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "equip"),
                                       view=InventoryView(self.user_id, self.gid, "equip", self.back))
        msg = f"💰 **{nm}** を売却（+{sv:,}）"
        if had: msg += "。刻んでた技は手元に戻したよ"
        await it.followup.send(msg, ephemeral=True)

class SellSkillSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id)
        opts = [discord.SelectOption(label=f"売却: {VS.SKILLS[s]['name']}", value=s,
                description=f"売値 {VS.SKILLS[s]['price']//10:,}")
                for s, n in vp.get("learned_skills", {}).items() if n > 0]
        super().__init__(placeholder="技を売る", options=opts[:25], row=1)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        sid = self.values[0]; vp = db.get_voyage(self.user_id)
        if vp["learned_skills"].get(sid, 0) <= 0:
            await it.response.send_message("もう無い", ephemeral=True); return
        sv = VS.SKILLS[sid]["price"] // 10
        vp["learned_skills"][sid] -= 1
        if vp["learned_skills"][sid] <= 0: del vp["learned_skills"][sid]
        db.update_balance(self.user_id, self.gid, sv); db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "skill"),
                                       view=InventoryView(self.user_id, self.gid, "skill", self.back))
        await it.followup.send(f"💰 **{VS.SKILLS[sid]['name']}** を売却（+{sv:,}）", ephemeral=True)

class InvBackButton(discord.ui.Button):
    def __init__(self, user_id, gid, back):
        super().__init__(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=4)
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        if self.back == "equip":
            await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id)),
                                           view=EquipShopView(self.user_id, self.gid))
        else:
            from cogs.menu import go_town
            await go_town(it, self.user_id)

async def open_inventory(interaction, user_id=None, back="town"):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    embed = build_inv_embed(vp, "equip"); view = InventoryView(uid, gid, "equip", back)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def open_equip_shop(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    embed = build_equipshop_embed(vp); view = EquipShopView(uid, gid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
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
