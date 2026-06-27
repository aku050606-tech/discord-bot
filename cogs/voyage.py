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
from config import ADMIN_USER_IDS

db = Database()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 計算ヘルパ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ── 船：本体＋部位スロットから 攻撃/防御/HP を算出 ──
def ship_def_of(vp):
    """所持船の定義 dict（未所持=None）。"""
    return V.SHIPS.get(vp.get("ship")) if vp.get("ship") else None

def ship_part_inst(vp, part):
    """部位に挿した船装備インスタンス {item,skills,dura} or None。"""
    return vp["ship_parts"].get(part)

def ship_part_def(vp, part):
    inst = ship_part_inst(vp, part)
    if not inst:
        return None
    return V.SHIP_PARTS[part]["items"].get(inst["item"])

def ship_attack(vp):
    d = ship_part_def(vp, "cannon")
    return d["power"] if d else 0

def ship_defense(vp):
    sd = ship_def_of(vp)
    base = sd["base_def"] if sd else 0
    a = ship_part_def(vp, "armor")
    return base + (a["power"] if a else 0)

def ship_max_hp(vp):
    sd = ship_def_of(vp)
    return sd["base_hp"] if sd else 0

def ship_power(vp):
    """互換：海戦の総合戦闘力（攻＋防）。"""
    return ship_attack(vp) + ship_defense(vp)

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

def can_enter_sea(vp, sea):
    sd = ship_def_of(vp)
    if not sd:
        return False
    return sd.get("sea_unlock", 1) >= V.SEAS[sea]["unlock_hull"]

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
    """全船装備を満タンに戻すのに必要なコイン。"""
    cost = 0
    for part in ("cannon", "armor", "rigging"):
        inst = ship_part_inst(vp, part)
        pdef = ship_part_def(vp, part)
        if inst and pdef:
            mx = pdef.get("dura", 0)
            cost += max(0, mx - inst.get("dura", mx)) * V.SHIP_REPAIR_PER_DURA
    return cost

def any_part_broken(vp):
    """船装備のどれかが耐久0なら True（出航不可）。"""
    for part in ("cannon", "armor", "rigging"):
        inst = ship_part_inst(vp, part)
        if inst and inst.get("dura", 1) <= 0:
            return True
    return False

def _scaled(rng, vm):
    return int(random.uniform(rng["base_min"], rng["base_max"]) * vm)

# ── エリア進行ヘルパ ──
def area_of(v):
    return v.get("area", 1)

def explores_done(v):
    return v.get("explores", 0)

def can_advance(v):
    """次エリアへ進めるか（探索10回＋エリア3→4はカケラ条件）。"""
    if explores_done(v) < V.EXPLORE_TO_ADVANCE:
        return False
    if area_of(v) >= V.AREA_MAX:
        return False
    if area_of(v) == 3 and v.get("shards", 0) < V.SHARD_NEEDED:
        return False
    return True

def _try_shard(v, key):
    """エリア3でのみ薄い確率でカケラ発見。落ちたら告知文、無ければ空文字。"""
    if area_of(v) != 3:
        return ""
    if random.random() < V.SHARD_DROP.get(key, 0):
        v["shards"] = v.get("shards", 0) + 1
        got = v["shards"]
        if got >= V.SHARD_NEEDED:
            return f"\n　{V.SHARD_NAME} 発見！（{got}/{V.SHARD_NEEDED}）✨ **最深部への道が開いた！**"
        return f"\n　{V.SHARD_NAME} 発見！（{got}/{V.SHARD_NEEDED}）"
    return ""

def _pirate_fight(vp, pr, scale, vm_eff, header):
    """海賊/ボス戦（2層・確率式）。scale=敵強さ倍率, vm_eff=報酬倍率。"""
    v = vp["voyage"]
    sp = ship_power(vp); pp = personal_power(vp)
    esp = int(pr["sea_power"] * scale); ecp = int(pr["crew_power"] * scale)
    lines = [header]
    for part in ("cannon", "armor"):
        inst = vp["ship_parts"].get(part)
        if inst:
            inst["dura"] = max(0, inst.get("dura", 0) - V.NAVAL_DURA_COST)
    if random.random() < win_prob(sp, esp):
        lines.append(f"\u2693 \u7832\u6483\u6226\u3092\u5236\u3057\u305f\uff01\uff08\u8239 {sp} vs {esp}\uff09\u65ac\u308a\u8fbc\u307f\u3060\uff01")
        if random.random() < win_prob(pp, ecp):
            base = random.uniform(V.PIRATE_BASE_REWARD["base_min"], V.PIRATE_BASE_REWARD["base_max"])
            rew = int(base * pr["reward_mult"] * vm_eff)
            v["hold"] += rew
            add_xp(vp, V.XP_PER_PIRATE_WIN)
            lines.append(f"\U0001f5e1\ufe0f \u767d\u5175\u6226\u3082\u5236\u5727\uff01\uff08\u500b\u4eba {pp} vs {ecp}\uff09\u9603\u7372\u3057\u3066 **+{rew:,}**\uff01")
            s = _try_shard(v, "boss" if pr.get("is_boss") else "pirate_win")
            if s: lines.append(s.strip())
        else:
            add_xp(vp, V.XP_PER_PIRATE_LOSE)
            lines.append(f"\U0001f4a2 \u4e57\u308a\u8fbc\u3093\u3060\u304c\u8fd4\u308a\u8a0e\u3061\u2026\uff08\u500b\u4eba {pp} vs {ecp}\uff09\u64a4\u9000\u3002\u8239\u5009\u306f\u5b88\u3063\u305f\u3002")
    else:
        lines.append(f"\U0001f525 \u7832\u6483\u6226\u3067\u62bc\u3057\u8ca0\u3051\u305f\u2026\uff08\u8239 {sp} vs {esp}\uff09\u4e57\u308a\u8fbc\u307e\u308c\u308b\uff01")
        if random.random() < win_prob(pp, ecp):
            add_xp(vp, V.XP_PER_PIRATE_WIN)
            lines.append(f"\U0001f6e1\ufe0f \u767d\u5175\u3067\u6483\u9000\u6210\u529f\uff01\uff08\u500b\u4eba {pp} vs {ecp}\uff09\u7a4d\u307f\u8377\u306f\u7121\u4e8b\u3060\u3002")
        else:
            add_xp(vp, V.XP_PER_PIRATE_LOSE)
            diff = esp / max(sp, 1)
            weights = [max(0.1, diff), 1, 1, max(0.1, 1 / diff)]
            rate = random.choices(V.LOSS_TIERS, weights=weights)[0]
            armor_def = ship_part_def(vp, "armor")
            armor_t = armor_def["rank"] if armor_def else 0
            if random.random() < V.ARMOR_MITIGATE_CHANCE.get(armor_t, 0):
                idx = V.LOSS_TIERS.index(rate)
                rate = V.LOSS_TIERS[min(idx + 1, len(V.LOSS_TIERS) - 1)]
            lost = int(v["hold"] * rate)
            v["hold"] -= lost
            lines.append(f"\U0001f480 \u9632\u885b\u5931\u6557\uff08\u500b\u4eba {pp} vs {ecp}\uff09\u2026\u8239\u5009\u306e **{int(rate*100)}%\uff1d{lost:,}** \u3092\u596a\u308f\u308c\u305f\uff01")
    return "\n".join([x for x in lines if x])

# \u2501\u2501\u2501 \U0001f50d \u63a2\u7d22\uff08\u305d\u306e\u30a8\u30ea\u30a2\u3092\u63a2\u308b\uff1d\u9047\u9047\u62bd\u9078\uff09 \u2501\u2501\u2501
def resolve_explore(vp):
    """\u63a2\u7d22\u30921\u56de\u3002\u9047\u9047\u3092\u62bd\u9078\u3057\u3066\u51e6\u7406\u3057\u3001\u63a2\u7d22\u30ab\u30a6\u30f3\u30c8\u3092+1\u3057\u3066\u7d50\u679c\u30c6\u30ad\u30b9\u30c8\u3092\u8fd4\u3059\u3002"""
    v = vp["voyage"]
    sea = v["sea"]; s = V.SEAS[sea]
    area = area_of(v); amult = V.AREA_MULT[area]
    vm = s["val_mult"] * amult            # \u5831\u916c\u306f\u6d77\u00d7\u30a8\u30ea\u30a2
    scale = s["danger"] * amult           # \u6575\u5f37\u3055\u306f\u5371\u967a\u5ea6\u00d7\u30a8\u30ea\u30a2
    v["explores"] = v.get("explores", 0) + 1
    for part in ("cannon", "armor"):
        inst = vp["ship_parts"].get(part)
        if inst:
            inst["dura"] = max(0, inst.get("dura", 0) - V.SAIL_DURA_COST)

    table = V.AREA_ENCOUNTERS[area]
    enc = random.choices(list(table), weights=list(table.values()))[0]

    if enc == "calm":
        return "\U0001f305 \u7a4f\u3084\u304b\u306a\u6d77\u3002\u6c17\u306b\u306a\u308b\u3082\u306e\u306f\u898b\u5f53\u305f\u3089\u306a\u304b\u3063\u305f\u2026"
    if enc == "fish":
        tier = random.choices(list(V.FISH_HAUL), weights=[V.FISH_HAUL[k]["weight"] for k in V.FISH_HAUL])[0]
        val = _scaled(V.FISH_HAUL[tier], vm); v["hold"] += val; add_xp(vp, V.XP_PER_FISH)
        label = {"common":"\U0001f41f \u96d1\u9b5a","good":"\U0001f420 \u5927\u7269","rare":"\u2728 \u30ec\u30a2\u7269","legend":"\U0001f308 \u4f1d\u8aac\u306e\u7372\u7269"}[tier]
        return f"{label}\u304c\u7db2\u306b\u304b\u304b\u3063\u305f\uff01 \u8239\u5009\u306b **+{val:,}**" + _try_shard(v, "fish")
    if enc == "island":
        if random.random() < V.ISLAND_TREASURE_RATE:
            val = _scaled(V.ISLAND_TREASURE, vm); v["hold"] += val; add_xp(vp, V.XP_PER_ISLAND)
            return f"\U0001f3dd\ufe0f \u7121\u4eba\u5cf6\u306b\u4e0a\u9678\u2026**\u304a\u5b9d\u767a\u898b\uff01** \u8239\u5009\u306b **+{val:,}**" + _try_shard(v, "island")
        add_xp(vp, V.XP_PER_ISLAND)
        return "\U0001f3dd\ufe0f \u7121\u4eba\u5cf6\u306b\u4e0a\u9678\u3057\u305f\u304c\u2026\u3081\u307c\u3057\u3044\u7269\u306f\u7121\u304b\u3063\u305f\u3002" + _try_shard(v, "island")
    if enc == "maelstrom":
        val = _scaled(V.MAELSTROM_REWARD, vm); v["hold"] += val
        return (f"\U0001f300 \u6e26\u6f6e\u306b\u5dfb\u304d\u8fbc\u307e\u308c\u305f\uff01\u3046\u307e\u304f\u4e57\u308a\u5207\u308a\u3001\u6f02\u6d41\u7269\u304b\u3089 **+{val:,}**"
                + _try_shard(v, "maelstrom"))
    if enc == "abyss":
        val = _scaled(V.ABYSS_TREASURE, vm); v["hold"] += val
        return f"\U0001f573\ufe0f \u5149\u308b\u6d77\u6df5\u3092\u8993\u304d\u8fbc\u3080\u2026\u5438\u3044\u5bc4\u305b\u3089\u308c\u305f\u8ca1\u5b9d **+{val:,}**"
    if enc == "boss":
        boss = dict(V.AREA_BOSS[area]); boss["is_boss"] = True
        hd = f"{boss['emoji']} **{boss['name']}** \u304c\u7acb\u3061\u306f\u3060\u304b\u308b\uff01\uff08\u30a8\u30ea\u30a2{area}\u306e\u4e3b\u30fb\u6d77\u6226\u529b {int(boss['sea_power']*scale)}\uff09"
        return _pirate_fight(vp, boss, scale, vm, hd)
    pr = random.choices(V.PIRATE_RANKS, weights=V.PIRATE_TABLE[sea])[0]
    hd = f"{pr['emoji']} **{pr['name']}** \u304c\u73fe\u308c\u305f\uff01\uff08\u6d77\u6226\u529b {int(pr['sea_power']*scale)}\uff09"
    return _pirate_fight(vp, pr, scale, vm, hd)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Embed ビルダー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_port_embed(vp):
    if not vp["has_ship"]:
        return discord.Embed(
            title="⚓ 港 ── 造船所",
            description=("船はまだ無いようだな。\n"
                         f"**🚢 帆船**（☆2）を **{V.SHIPS['frigate']['price']:,}** ナトコインで仕立てれば、"
                         "未知の海へ漕ぎ出せる。\n（砲・装甲・艤装の部位に船装備を積んで戦う）"),
            color=0x16a085)
    lv_need = V.xp_to_next(vp["level"]) if vp["level"] < V.LEVEL_MAX else 0
    e = discord.Embed(title="⚓ 港 ── 母港", color=0x16a085,
                      description="航海の準備を整えよう。出航で船倉を満たし、引き返して入金だ。")
    e.add_field(name="🚢 船 攻/防/HP",
                value=f"⚔️{ship_attack(vp)} 🛡️{ship_defense(vp)} ❤️{ship_max_hp(vp)}", inline=True)
    e.add_field(name="🗡️ 個人 戦闘力", value=f"**{personal_power(vp)}**", inline=True)
    e.add_field(name="📊 レベル",
                value=f"Lv.**{vp['level']}**" + (f"（XP {vp['xp']}/{lv_need}）" if lv_need else "（MAX）"),
                inline=True)
    # 船の装備（部位）
    sd = ship_def_of(vp)
    eq = [f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']}（HP{sd['base_hp']}/防{sd['base_def']}）"]
    for part in V.SHIP_PART_ORDER:
        meta = V.SHIP_PART_META[part]; inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
        if inst and pdef:
            eq.append(f"{meta['emoji']} {V.rarity_stars(pdef['rank'])} {pdef['name']}"
                      f"（{dura_bar(inst.get('dura',0), pdef.get('dura',1))}）")
        else:
            eq.append(f"{meta['emoji']} {meta['name']}：なし")
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
    area = area_of(v); ex = explores_done(v)
    e = discord.Embed(
        title=f"{s['name']} ── 航海中",
        description=last_msg or s["flavor"], color=discord.Color.dark_teal())
    e.add_field(name="🗺️ エリア",
                value=f"{V.AREA_EMOJI[area]} **{area} {V.AREA_NAMES[area]}**", inline=True)
    prog = min(ex, V.EXPLORE_TO_ADVANCE)
    if area < V.AREA_MAX:
        e.add_field(name="🔍 探索",
                    value=f"{prog}/{V.EXPLORE_TO_ADVANCE}" + ("　⛵進める！" if can_advance(v) else ""),
                    inline=True)
    else:
        e.add_field(name="🔍 探索回数", value=f"{ex}", inline=True)
    e.add_field(name="📦 船倉（未確定）", value=f"**{v['hold']:,}**", inline=True)
    if area == 3 or v.get("shards", 0) > 0:
        tag = ""
        if area == 3 and v.get("shards", 0) >= V.SHARD_NEEDED:
            tag = "　✨ 最深部へ進める！"
        e.add_field(name="🧭 カケラ", value=f"{v.get('shards',0)}/{V.SHARD_NEEDED}{tag}", inline=True)
    e.add_field(name="⛽ 探索の燃料", value=f"{s['fuel']:,}", inline=True)
    cond = []
    for part in ("cannon", "armor"):
        inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
        if inst and pdef:
            cond.append(f"{V.SHIP_PART_META[part]['emoji']}{dura_bar(inst.get('dura',0), pdef.get('dura',1))}")
    e.add_field(name="🛠️ 船", value=" ".join(cond) if cond else "—", inline=True)
    e.set_footer(text="🔍探索＝その場を探る／⛵進む＝奥のエリアへ(探索10回)／⚓引き返す＝1つ手前へ")
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
        if str(user_id) in ADMIN_USER_IDS:
            self.add_item(MockCombatButton())
        self.add_item(LeaveButton())

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class BuyShipButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=f"🚢 帆船を仕立てる（{V.SHIPS['frigate']['price']:,}）", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        uid, gid = view.user_id, view.gid
        price = V.SHIPS["frigate"]["price"]
        if db.get_balance(uid, gid) < price:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{price:,} 必要）", ephemeral=True); return
        vp = db.get_voyage(uid)
        if vp["has_ship"]:
            await interaction.response.send_message("もう船を持っている", ephemeral=True); return
        db.update_balance(uid, gid, -price)
        vp["has_ship"] = True
        vp["ship"] = "frigate"
        vp["ship_hp_cur"] = V.SHIPS["frigate"]["base_hp"]
        vp["ship_parts"] = {"cannon": None, "armor": None, "rigging": None}
        vp["ship_skills"] = []
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid))
        await interaction.followup.send("🚢 帆船（☆2）を仕立てた！ショップで砲と装甲を積もう。", ephemeral=True)

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
        for part in ("cannon", "armor", "rigging"):
            inst = vp["ship_parts"].get(part); pdef = ship_part_def(vp, part)
            if inst and pdef:
                inst["dura"] = pdef.get("dura", inst.get("dura", 0))
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid))
        await interaction.followup.send(f"🔧 全装備を修理した（-{cost:,}）", ephemeral=True)

class MockCombatButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚔️ 模擬戦(テスト)", style=discord.ButtonStyle.danger, row=1)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await start_board_test(interaction, view.user_id)

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
            await interaction.response.send_message("🔒 この海にはまだ出られない（もっと上位の船が要る）", ephemeral=True); return
        vp["voyage"] = {"sea": self.sea, "area": 1, "explores": 0, "hold": 0, "shards": 0}
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
        # 「進む」は探索10回(＋エリア3はカケラ)で解禁。条件未達なら無効表示。
        try:
            v = db.get_voyage(str(user_id)).get("voyage") or {}
        except Exception:
            v = {}
        for child in list(self.children):
            if getattr(child, "label", "") == "⛵ 進む":
                if area_of(v) >= V.AREA_MAX or not can_advance(v):
                    child.disabled = True

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔍 探索", style=discord.ButtonStyle.primary)
    async def explore(self, interaction, button):
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
                "🛠️ 装備が壊れた！引き返して修理を。", ephemeral=True); return
        db.update_balance(uid, gid, -fuel)
        msg = resolve_explore(vp)
        db.save_voyage(uid, vp)
        if any_part_broken(vp):
            msg += "\n\n🛠️ **装備が限界だ…！引き返すしかない。**"
        await interaction.response.edit_message(embed=build_voyage_embed(vp, msg), view=VoyageView(uid, gid))

    @discord.ui.button(label="⛵ 進む", style=discord.ButtonStyle.success)
    async def advance(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        v = vp.get("voyage")
        if not v:
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        if not can_advance(v):
            if area_of(v) == 3 and v.get("shards", 0) < V.SHARD_NEEDED:
                await interaction.response.send_message(
                    f"🌟 最深部へは {V.SHARD_NAME} が {V.SHARD_NEEDED} 個必要（探索でカケラを集めよう）", ephemeral=True); return
            need = V.EXPLORE_TO_ADVANCE - explores_done(v)
            await interaction.response.send_message(
                f"🔍 このエリアをあと {max(0,need)} 回探索すれば進める", ephemeral=True); return
        v["area"] += 1; v["explores"] = 0
        nm = f"{V.AREA_EMOJI[v['area']]} {V.AREA_NAMES[v['area']]}"
        flav = ("🌟 カケラが導く光の奥へ……**最深部に到達した！** ここは特別な場所だ。"
                if v["area"] == 4 else f"⛵ さらに奥へ。**{nm}** に進んだ。")
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_voyage_embed(vp, flav), view=VoyageView(uid, gid))

    @discord.ui.button(label="⚓ 引き返す", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        v = vp.get("voyage")
        if not v:
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        if area_of(v) > 1:
            # 1つ手前のエリアへ。戻り先は探索済み扱い＝すぐ進める。
            v["area"] -= 1
            v["explores"] = V.EXPLORE_TO_ADVANCE
            db.save_voyage(uid, vp)
            nm = f"{V.AREA_EMOJI[v['area']]} {V.AREA_NAMES[v['area']]}"
            await interaction.response.edit_message(
                embed=build_voyage_embed(vp, f"⚓ 1つ手前へ。**{nm}** に戻った。"),
                view=VoyageView(uid, gid))
            return
        # エリア1で引き返す＝帰港・入金
        hold = v["hold"]
        if hold > 0:
            db.update_balance(uid, gid, hold)
        vp["voyage"] = None
        db.save_voyage(uid, vp)
        e = discord.Embed(
            title="⚓ 帰港",
            description=f"航海を終えた。\n船倉の **{hold:,}** ナトコインを銀行に入金した！",
            color=discord.Color.gold())
        rc = repair_cost(vp)
        if rc > 0:
            e.add_field(name="🔧 整備", value=f"装備が傷んでいる（修理 **{rc:,}**）", inline=False)
        await interaction.response.edit_message(embed=e, view=PortView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: ショップ（船装備＋個人装備の購入/強化）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 船装備の装着可否（船rank+2 まで）
def ship_part_allowed_rank(vp):
    sd = ship_def_of(vp)
    return (sd["rank"] + V.RARITY_ENGRAVE_GAP) if sd else 0

# 船本体に刻める技種（slot=="ship_body"）／部位に刻める技種
SHIP_PART_SKILL_SLOT = {"cannon": "ship_cannon", "armor": "ship_armor", "rigging": "ship_rigging"}

def ship_skill_fits(target, sid):
    """target: 'body' or 部位名。slotが一致すれば刻める。"""
    s = VS.SKILLS.get(sid)
    if not s: return False
    if target == "body":
        return s["slot"] == "ship_body"
    return s["slot"] == SHIP_PART_SKILL_SLOT.get(target)

def build_shop_embed(vp):
    sd = ship_def_of(vp)
    e = discord.Embed(title="🏪 港の造船ショップ", color=discord.Color.gold(),
                      description=(f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']} ── "
                                   f"☆{sd['rank']+V.RARITY_ENGRAVE_GAP}までの装備を積める。\n"
                                   "部位に船装備を挿し、船技を刻もう。"))
    for part in V.SHIP_PART_ORDER:
        meta = V.SHIP_PART_META[part]; pdef = ship_part_def(vp, part)
        if pdef:
            val = f"{V.rarity_stars(pdef['rank'])} {pdef['name']}（攻/防{pdef['power']}）"
            sk = ship_part_inst(vp, part).get("skills", [])
            if sk: val += " {" + "".join(VS.SKILLS[x]["emoji"] for x in sk) + "}"
        else:
            val = "空き"
        e.add_field(name=f"{meta['emoji']} {meta['name']}", value=val, inline=True)
    bsk = vp.get("ship_skills", [])
    e.add_field(name=f"🚢 船本体の技 [{len(bsk)}/{sd['skill_slots']}]",
                value=" ".join(VS.SKILLS[x]["name"] for x in bsk) if bsk else "空き", inline=False)
    return e

class ShopView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(ShipPartSelect(user_id, gid))
        self.add_item(ShipEngraveButton())
        back = discord.ui.Button(label="◀ 港へ戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)), view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipPartSelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = []
        for part in V.SHIP_PART_ORDER:
            meta = V.SHIP_PART_META[part]
            opts.append(discord.SelectOption(label=f"{meta['name']}スロットに挿す", emoji=meta["emoji"], value=part))
        super().__init__(placeholder="🔧 部位に船装備を挿す", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part = self.values[0]
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(self.user_id)),
            view=ShipPartBuyView(self.user_id, self.gid, part))

class ShipPartBuyView(discord.ui.View):
    def __init__(self, user_id, gid, part):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        items = V.SHIP_PARTS[part]["items"]
        if items:
            self.add_item(ShipPartBuySelect(user_id, gid, part))
        back = discord.ui.Button(label="◀ ショップへ", style=discord.ButtonStyle.secondary, row=1)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShopView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipPartBuySelect(discord.ui.Select):
    def __init__(self, user_id, gid, part):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        opts = []
        for iid, idd in V.SHIP_PARTS[part]["items"].items():
            opts.append(discord.SelectOption(
                label=f"{V.rarity_stars(idd['rank'])} {idd['name']}（{idd['power']}）", value=iid,
                description=f"耐久{idd['dura']}・{idd['price']:,}コイン"))
        super().__init__(placeholder=f"{V.SHIP_PART_META[part]['name']}を選ぶ", options=opts or [
            discord.SelectOption(label="（在庫なし）", value="none")], row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        iid = self.values[0]
        if iid == "none":
            await interaction.response.send_message("まだ在庫が無い部位だ（艤装は今後）", ephemeral=True); return
        idd = V.SHIP_PARTS[self.part]["items"][iid]
        uid, gid, part = self.user_id, self.gid, self.part
        vp = db.get_voyage(uid)
        # レア度制限：船rank+2 まで
        if idd["rank"] > ship_part_allowed_rank(vp):
            await interaction.response.send_message(
                f"🔒 この船には ☆{ship_part_allowed_rank(vp)} までの装備しか積めない", ephemeral=True); return
        if db.get_balance(uid, gid) < idd["price"]:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{idd['price']:,} 必要）", ephemeral=True); return
        # 既存装備の技は手元に戻す（装備替え）
        old = vp["ship_parts"].get(part)
        if old:
            for sid in old.get("skills", []):
                vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.update_balance(uid, gid, -idd["price"])
        vp["ship_parts"][part] = {"item": iid, "skills": [], "dura": idd["dura"]}
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_shop_embed(vp), view=ShopView(uid, gid))
        await interaction.followup.send(
            f"🔧 **{idd['name']}** を{V.SHIP_PART_META[part]['name']}に装備（-{idd['price']:,}）", ephemeral=True)

class ShipEngraveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚒️ 船技を刻む", style=discord.ButtonStyle.primary, row=1)
    async def callback(self, interaction):
        view = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(view.user_id)),
            view=ShipEngraveView(view.user_id, view.gid))

class ShipEngraveView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); sd = ship_def_of(vp)
        targets = []
        # 船本体
        if sd and len(vp.get("ship_skills", [])) < sd["skill_slots"]:
            if any(vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits("body", s) for s in vp["learned_skills"]):
                targets.append(("body", "🚢 船本体"))
        # 部位
        for part in V.SHIP_PART_ORDER:
            inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
            if inst and pdef and len(inst.get("skills", [])) < pdef.get("slots", 1):
                if any(vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits(part, s) for s in vp["learned_skills"]):
                    targets.append((part, f"{V.SHIP_PART_META[part]['emoji']} {V.SHIP_PART_META[part]['name']}"))
        if targets:
            self.add_item(ShipEngraveTargetSelect(user_id, gid, targets))
        back = discord.ui.Button(label="◀ ショップへ", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShopView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipEngraveTargetSelect(discord.ui.Select):
    def __init__(self, user_id, gid, targets):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = [discord.SelectOption(label=lbl, value=key) for key, lbl in targets]
        super().__init__(placeholder="刻む箇所を選ぶ", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(self.user_id)),
            view=ShipEngraveSkillView(self.user_id, self.gid, self.values[0]))

class ShipEngraveSkillView(discord.ui.View):
    def __init__(self, user_id, gid, target):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.target = target
        vp = db.get_voyage(user_id)
        owned = [s for s in vp["learned_skills"]
                 if vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits(target, s)]
        if owned:
            self.add_item(ShipEngraveSkillSelect(user_id, gid, target, owned))
        back = discord.ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=1)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShipEngraveView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipEngraveSkillSelect(discord.ui.Select):
    def __init__(self, user_id, gid, target, skills):
        self.user_id = str(user_id); self.gid = str(gid); self.target = target
        opts = [discord.SelectOption(label=VS.SKILLS[s]["name"], emoji=VS.SKILLS[s]["emoji"],
                value=s, description=VS.SKILLS[s]["desc"][:60]) for s in skills]
        super().__init__(placeholder="刻む船技を選ぶ", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, target = self.user_id, self.gid, self.target; sid = self.values[0]
        vp = db.get_voyage(uid)
        if vp["learned_skills"].get(sid, 0) <= 0 or not ship_skill_fits(target, sid):
            await interaction.response.send_message("❌ ここには刻めない", ephemeral=True); return
        if target == "body":
            sd = ship_def_of(vp)
            if len(vp["ship_skills"]) >= sd["skill_slots"]:
                await interaction.response.send_message("⚠️ 船本体の技枠が満杯", ephemeral=True); return
            vp["ship_skills"].append(sid)
        else:
            inst = ship_part_inst(vp, target); pdef = ship_part_def(vp, target)
            if not inst:
                await interaction.response.send_message("その部位は空き", ephemeral=True); return
            if len(inst.get("skills", [])) >= pdef.get("slots", 1):
                await interaction.response.send_message("⚠️ その部位の技枠が満杯", ephemeral=True); return
            inst.setdefault("skills", []).append(sid)
        vp["learned_skills"][sid] -= 1
        if vp["learned_skills"][sid] <= 0: del vp["learned_skills"][sid]
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_shop_embed(vp), view=ShopView(uid, gid))
        await interaction.followup.send(f"⚒️ **{VS.SKILLS[sid]['name']}** を刻んだ！", ephemeral=True)

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
            sd = ship_def_of(vp)
            e.add_field(name=f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']}",
                        value=f"❤️HP {sd['base_hp']}／🛡️基礎防御 {sd['base_def']}／攻撃 {ship_attack(vp)}・防御 {ship_defense(vp)}",
                        inline=False)
            lines = []
            for part in V.SHIP_PART_ORDER:
                meta = V.SHIP_PART_META[part]; inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
                if inst and pdef:
                    sk = "".join(VS.SKILLS[x]["emoji"] for x in inst.get("skills", []))
                    lines.append(f"{meta['emoji']} {meta['name']}：{V.rarity_stars(pdef['rank'])} {pdef['name']}"
                                 f"（耐久 {inst.get('dura',0)}/{pdef.get('dura',1)}）{sk}")
                else:
                    lines.append(f"{meta['emoji']} {meta['name']}：なし")
            bsk = vp.get("ship_skills", [])
            if bsk:
                lines.append("🚢 船本体技：" + " ".join(VS.SKILLS[x]["name"] for x in bsk))
            e.add_field(name="🔧 部位", value="\n".join(lines), inline=False)
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
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 戦闘UI（CombatView）── エンジン voyage_combat を Discord で操作
#   通常攻撃／通常防御／✨特技(刻んだ技・CD/溜め制限)／敵AI。海戦・白兵 共通。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import voyage_combat as C

def hp_bar(cur, mx, width=12):
    cur = max(0, cur); ratio = cur / mx if mx else 0
    f = round(width * ratio)
    return "🟩" * f + "⬛" * (width - f) if ratio > 0.3 else "🟥" * f + "⬛" * (width - f)

def board_skills(vp):
    """装備中の武器/胴/脚に刻まれた『白兵』技を集める。"""
    out = []
    for part in ("weapon", "torso", "legs"):
        inst = equipped_inst(vp, part)
        if inst:
            out += [s for s in inst.get("skills", []) if VS.SKILLS[s]["phase"] == "board"]
    return out

def naval_skills(vp):
    """船本体＋部位に刻まれた『海戦』技を集める。"""
    out = [s for s in vp.get("ship_skills", []) if VS.SKILLS[s]["phase"] == "naval"]
    for part in ("cannon", "armor", "rigging"):
        inst = vp["ship_parts"].get(part)
        if inst:
            out += [s for s in inst.get("skills", []) if VS.SKILLS[s]["phase"] == "naval"]
    return out

_ENEMY_SKILLS = {1: [], 2: [], 3: ["kyougeki"], 4: ["kyougeki", "shukketsu"], 5: ["kyougeki", "konshin"]}

def board_enemy_from_pirate(pr, danger=1.0):
    cp = pr["crew_power"] * danger
    return C.make_combatant(pr["name"], pr["emoji"], hp=int(cp * 5),
                            atk=int(cp), defense=int(cp * 0.5),
                            skills=_ENEMY_SKILLS.get(pr["tier"], []), ai_tier=pr["tier"])

def build_combat_embed(state):
    a = state["ally"]; e = state["enemy"]
    title = "⚔️ 白兵戦" if state["phase"] == "board" else "🚢 海戦"
    col = discord.Color.dark_red() if state["phase"] == "board" else discord.Color.dark_teal()
    emb = discord.Embed(title=f"{title} ── ターン {state['turn']}", color=col)
    emb.add_field(name=f"{e['emoji']} {e['name']}",
                  value=f"HP {max(0,e['hp'])}/{e['max_hp']}\n{hp_bar(e['hp'],e['max_hp'])}", inline=False)
    emb.add_field(name=f"🧑 あなた  ⚔️{a['atk']} 🛡️{a['def']}",
                  value=f"HP {max(0,a['hp'])}/{a['max_hp']}\n{hp_bar(a['hp'],a['max_hp'])}", inline=False)
    if state["log"]:
        emb.add_field(name="📜 経過", value="\n".join(state["log"][-8:]), inline=False)
    if a.get("charging"):
        emb.set_footer(text=f"💢 {VS.SKILLS[a['charging']]['name']} 溜め中…次の行動で解放！")
    return emb

async def _advance(interaction, holder, action):
    """味方行動を解決して再描画。終了なら結果画面へ。"""
    state = holder.state
    C.take_turn(state, action)
    if state["over"]:
        a = state["ally"]; e = state["enemy"]
        res = "🏆 勝利！" if state["result"] == "win" else "💀 敗北…"
        emb = build_combat_embed(state)
        emb.add_field(name="― 決着 ―", value=res, inline=False)
        await interaction.response.edit_message(embed=emb, view=CombatEndView(holder.user_id))
    else:
        await interaction.response.edit_message(
            embed=build_combat_embed(state), view=CombatView(holder.user_id, holder.gid, state))

class CombatView(discord.ui.View):
    def __init__(self, user_id, gid, state):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.state = state
        a = state["ally"]
        if a.get("charging"):
            self.add_item(CmdButton("💥 解放する", discord.ButtonStyle.danger, {"kind": "attack"}))
        else:
            self.add_item(CmdButton("🗡️ 攻撃", discord.ButtonStyle.danger, {"kind": "attack"}))
            self.add_item(CmdButton("🛡️ 防御", discord.ButtonStyle.primary, {"kind": "defend"}))
            us = C.usable_skills(a)
            if us:
                self.add_item(SkillCommandSelect(us))

class CmdButton(discord.ui.Button):
    def __init__(self, label, style, action):
        super().__init__(label=label, style=style, row=0)
        self.action = action
    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await _advance(it, view, self.action)

class SkillCommandSelect(discord.ui.Select):
    def __init__(self, skill_ids):
        opts = []
        for sid in skill_ids[:25]:
            s = VS.SKILLS[sid]
            note = "溜め技" if s.get("charge", 0) > 0 else (f"CD{s['cooldown']}" if s.get("cooldown", 0) else "")
            opts.append(discord.SelectOption(label=s["name"], emoji=s["emoji"], value=sid,
                                             description=f"{note}　{s['desc'][:40]}".strip()))
        super().__init__(placeholder="✨ 特技を選ぶ", options=opts, row=1)
    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await _advance(it, view, {"kind": "skill", "sid": self.values[0]})

class CombatEndView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = str(user_id)
    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.secondary)
    async def close(self, it, b):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await it.response.edit_message(content="模擬戦を終えた。", embed=None, view=None)

async def start_board_test(interaction, user_id=None):
    """admin用：装備中ロードアウトで海賊と白兵模擬戦。"""
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    ally = C.make_combatant("あなた", "🧑", max_hp(vp), attack_power(vp), defense_power(vp), board_skills(vp))
    pr = random.choice(V.PIRATE_RANKS[:3])  # 模擬戦は中堅まで
    enemy = board_enemy_from_pirate(pr)
    state = C.new_battle("board", ally, enemy)
    holder = CombatView(uid, gid, state)
    emb = build_combat_embed(state)
    emb.description = f"{pr['emoji']} **{pr['name']}** が斬りかかってきた！（模擬戦）"
    if interaction.response.is_done():
        await interaction.followup.send(embed=emb, view=holder, ephemeral=True)
    else:
        await interaction.response.send_message(embed=emb, view=holder, ephemeral=True)

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
