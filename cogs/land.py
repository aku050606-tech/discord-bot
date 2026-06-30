"""
🛤️ 街道（陸の冒険）── 海の白兵戦エンジンを流用したレベル上げの場
探索 → 敵(白兵戦)/陸ストーリー/採取/平穏。
・HPは持ち越し（毎戦は回復しない）。タウンに戻っても全快しない。回復は🏨宿屋/🍖食料で行う。
・敵の攻撃は低め＝あまり食らわない。きついのは「装備が足りない」とき。
・XPは一旦“海レンジ（数十）”。大きく稼ぐのはレアキャラで後から調整。
※ 今は管理者のみ解放（menu.py の街道ボタンでゲート）。
"""
import random
import asyncio
import discord
from discord.ext import commands

from database import Database
import land_config as L
import voyage_config as V
import voyage_combat as C
from cogs.voyage import (
    make_board_enemy, build_combat_embed, CombatView,
    add_xp, max_hp, grant_random_equip, build_wait_embed,
    attack_power, defense_power, board_skills,
    equipped_inst, hp_bar,
)

db = Database()

LAND_WAITS = [
    "🥾 街道を、てくてく歩いていく……",
    "👀 草むらの先に、目を凝らす……",
    "🧭 道なき道を、慎重に進む……",
    "🍃 風の匂いを確かめながら、歩を進める……",
]


# ━━━ HP（持ち越し）ヘルパー ━━━
def _cur_hp(vp):
    mh = max_hp(vp)
    return max(0, min(mh, vp.get("cur_hp", mh)))


# ━━━ 🐾 ペット効果（犬＋猫を両方所持で、2探索に1回HP3%回復）━━━
def _pet_counts(vp):
    counts = {}
    for pid in vp.get("special_items", []) or []:
        if pid in getattr(V, "PETS", {}):
            counts[pid] = counts.get(pid, 0) + 1
    return counts

def _pet_line(vp):
    counts = _pet_counts(vp)
    if not counts:
        return "なし"
    parts = []
    for pid, n in counts.items():
        if n > 0 and pid in V.PETS:
            p = V.PETS[pid]
            parts.append(f"{p['emoji']} {p['name']}" + (f"×{n}" if n > 1 else ""))
    return " / ".join(parts) if parts else "なし"

def _has_dog_and_cat(vp):
    counts = _pet_counts(vp)
    return counts.get("pet_dog", 0) > 0 and counts.get("pet_cat", 0) > 0

def _apply_pet_explore_heal(uid, vp):
    """探索開始ごとのペット回復。ハムスターは毎回3%、犬＋猫は2探索に1回3%。"""
    notes = []
    counts = _pet_counts(vp)
    mh = max_hp(vp)

    if counts.get("pet_hamster", 0) > 0:
        cur = _cur_hp(vp)
        if cur < mh:
            heal = max(1, int(mh * 0.03))
            before = cur
            vp["cur_hp"] = min(mh, cur + heal)
            notes.append(f"🐹 ハムスターが癒してくれた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）")

    if _has_dog_and_cat(vp):
        step = int(vp.get("land_pet_steps", 0)) + 1
        vp["land_pet_steps"] = step
        if step % 2 == 0:
            cur = _cur_hp(vp)
            if cur < mh:
                heal = max(1, int(mh * 0.03))
                before = cur
                vp["cur_hp"] = min(mh, cur + heal)
                notes.append(f"🐾 犬と猫が寄り添ってくれた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）")
    return "\n".join(notes) if notes else None

def _heal_full(uid):
    """タウン帰還で全快。"""
    vp = db.get_voyage(uid)
    vp["cur_hp"] = max_hp(vp)
    db.save_voyage(uid, vp)


def _land_xp_amount(vp, area, raw_xp):
    """街道XP補正。
    平原はLv5からかなり重く、Lv10以降はほぼ育たない。
    補正値は land_config.LAND_XP_AREA_SCALE で調整する。
    """
    lv = int(vp.get("level", 1))
    raw_xp = int(raw_xp)
    mult = 1.0
    if hasattr(L, "land_xp_scale"):
        mult = float(L.land_xp_scale(area, lv))
    amt = int(raw_xp * mult)
    if raw_xp > 0 and mult > 0:
        return max(1, amt)
    return max(0, amt)


# ━━━ 探索の収穫トラッキング（死亡で50%失う対象） ━━━
import math

def _run(vp):
    """今回の探索セッションの収穫（コイン＋装備ドロップ）。"""
    return vp.setdefault("land_run", {"coin": 0, "drops": []})

def _run_add_coin(vp, amount):
    _run(vp)["coin"] += int(amount)

def _roll_star_from_distribution(distribution):
    stars = [int(x[0]) for x in distribution]
    weights = [float(x[1]) for x in distribution]
    return random.choices(stars, weights=weights)[0]

def _drop_rarity_text(star):
    if star >= 3:
        return "## 🌈 眩い光が辺りを包む……！"
    if star == 2:
        return "## ✨ 光る装備を発見！"
    return "## 🎁 何かを見つけた"

def _run_add_drop(uid, vp, area, spec=None):
    """装備ドロップ抽選（当たれば付与＆収穫に記録）。戻り＝表示名 or None。

    形式は2種類対応：
      (star, rate)                        … 旧式。rateでstar装備。
      ("dist", rate, [(star, weight), ...]) … 新式。rateで装備ドロップ後、星を重み抽選。

    現行方針：
      雑魚    0.1% → ☆1 99% / ☆2 1% / ☆3以上0%
      中ボス  3.0% → ☆1 70% / ☆2 29% / ☆3 1%
      大ボス 20.0% → ☆2 95% / ☆3 5%
    """
    table = (spec or {}).get("drop_table") or L.LAND_EQUIP_DROP.get(area, [])
    for entry in table:
        if not entry:
            continue
        if entry[0] == "dist":
            _, rate, distribution = entry
            if random.random() >= float(rate):
                continue
            star = _roll_star_from_distribution(distribution)
        else:
            star, rate = entry
            if random.random() >= float(rate):
                continue
        part, ikey, label = _pick_equip(int(star))
        if not ikey:
            return None
        vp.setdefault("inventory", {}).setdefault(part, []).append({"item": ikey, "skills": []})
        db.add_zukan(uid, "equip_seen", ikey)
        _run(vp)["drops"].append({"part": part, "item": ikey, "label": label, "star": int(star)})
        return f"{_drop_rarity_text(int(star))}\n{label}（★{int(star)}）"
    return None

def _pick_equip(star):
    pool = []
    for wid, w in V.WEAPONS.items():
        if w["rank"] == star:
            pool.append(("weapon", wid, f"🗡️ {w['name']}"))
    for part in ("torso", "legs"):
        for iid, d in V.ARMOR_PARTS[part]["items"].items():
            if d["rank"] == star:
                pool.append((part, iid, f"🛡️ {d['name']}"))
    return random.choice(pool) if pool else (None, None, None)

def _run_settle_town(uid, gid, vp):
    """タウン帰還：収穫を確定（コインを銀行入金・装備はそのまま）。"""
    run = _run(vp); coin = run.get("coin", 0)
    if coin > 0:
        db.update_balance(uid, gid, coin)
    vp["land_run"] = {"coin": 0, "drops": []}

def _run_settle_death(uid, gid, vp):
    """死亡：収穫の50%を失う。残り50%を確定。戻り＝喪失の説明行リスト。"""
    run = _run(vp); coin = run.get("coin", 0); drops = list(run.get("drops", []))
    lost_lines = []
    # 💰 コインは半分失う
    keep_coin = coin // 2; lost_coin = coin - keep_coin
    if keep_coin > 0:
        db.update_balance(uid, gid, keep_coin)
    if coin > 0:
        lost_lines.append(f"💰 持ち帰ったコイン {coin:,} のうち **{lost_coin:,} を失った**（{keep_coin:,} は銀行へ）")
    # 🎁 装備は個数の50%を失う（端数は50%で繰り上げ：1個→50%で1個、3個→1個＋50%で2個目）
    n = len(drops)
    if n > 0:
        lose_n = n // 2
        if (n % 2 == 1) and random.random() < 0.5:
            lose_n += 1
        if lose_n > 0:
            to_lose = random.sample(drops, lose_n)
            for d in to_lose:
                _remove_one_item(vp, d["part"], d["item"])
            names = "・".join(d["label"] for d in to_lose)
            lost_lines.append(f"🎁 拾った装備 {n}個 のうち **{lose_n}個 を失った**（{names}）")
        else:
            lost_lines.append(f"🎁 拾った装備 {n}個 は無事だった")
    vp["land_run"] = {"coin": 0, "drops": []}
    return lost_lines

def _remove_one_item(vp, part, ikey):
    lst = vp.get("inventory", {}).get(part, [])
    for i in range(len(lst) - 1, -1, -1):   # 後ろから（ドロップは末尾に積まれている）
        if lst[i].get("item") == ikey and not lst[i].get("skills"):
            # 装備中なら外す
            eq = vp.get("equipped", {})
            if eq.get(part) == i:
                eq[part] = None
            del lst[i]
            return True
    return False

def _harvest_footer(vp):
    run = _run(vp); coin = run.get("coin", 0); n = len(run.get("drops", []))
    return f"📦 今回の収穫：💰{coin:,} ・ 🎁装備{n}個　※倒れると半分失う"


# ━━━ 表示 ━━━
def _gear_line(vp):
    """装備中の武器・防具を1行で。"""
    w = equipped_inst(vp, "weapon")
    wn = V.WEAPONS[w["item"]]["name"] if (w and w["item"] in V.WEAPONS) else "素手"
    nm = []
    for p in ("torso", "legs"):
        it = equipped_inst(vp, p)
        if it and it["item"] in V.ARMOR_PARTS[p]["items"]:
            nm.append(V.ARMOR_PARTS[p]["items"][it["item"]]["name"])
        else:
            nm.append("なし")
    return f"⚔️ {wn}\n🛡️ {nm[0]} / {nm[1]}"

def _stat_line(vp):
    cur = _cur_hp(vp); mh = max_hp(vp)
    return (f"📊 レベル {vp['level']}（XP {vp['xp']}/{C_xp(vp)}）\n"
            f"❤️ {cur}/{mh}\n{hp_bar(cur, mh, 12)}\n"
            f"⚔️ 攻 {_atk(vp)}　🛡️ 防 {_dfn(vp)}")

def build_land_home_embed(vp):
    e = discord.Embed(
        title="🛤️ 街道 ── 陸の冒険",
        description="徒歩で冒険に出る。倒した敵から経験値がもらえる。\nどの地へ向かう？",
        color=0x8d6e63)
    e.add_field(name="📊 あなた", value=_stat_line(vp), inline=False)
    e.add_field(name="🐾 所持ペット", value=_pet_line(vp), inline=False)
    rows = []
    for area, a in L.LAND_AREAS.items():
        if vp["level"] >= a["req_lv"]:
            rows.append(f"{a['emoji']} **{a['name']}**（Lv{a['req_lv']}〜）")
        else:
            rows.append(f"🔒 {a['emoji']} {a['name']}（Lv{a['req_lv']}で解放）")
    e.add_field(name="🗺️ 行き先", value="\n".join(rows), inline=False)
    e.set_footer(text="HPは持ち越し。タウン帰還では回復しない／🏨宿屋・🍖食料で回復")
    return e


# 演出の色（種別ごとに帯の色を変えて“何か起きた”と一目で分かるように）
LAND_COL_NORMAL = 0x8d6e63   # 通常（茶）
LAND_COL_EVENT  = 0xe1a740   # 発見・イベント（金）
LAND_COL_GATHER = 0x4f9d69   # 採取（緑）
LAND_COL_STORY  = 0x8e7cc3   # ストーリー（紫）
LAND_COL_CALM   = 0x566b5f   # 何もない（しょぼめ・鈍い緑）
LAND_COL_COMBAT = 0xd97706   # 通常戦闘（橙）
LAND_COL_MID    = 0xb45309   # 中レア（濃い橙）
LAND_COL_RARE   = 0xb91c1c   # 激レア（赤）

def _pad_note(note, min_lines=5):
    """Discordの高さブレを抑えるため、演出文の行数をだいたい固定する。
    空行だけだと潰れることがあるのでゼロ幅スペースを使う。"""
    text = str(note or "")
    lines = text.splitlines() if text else []
    while len(lines) < min_lines:
        lines.append("\u200b")
    return "\n".join(lines)

def _theater_note(kind):
    """探索前の演出。種類ごとに文字の大きさ・色・雰囲気を変える。"""
    table = {
        "calm": (LAND_COL_CALM, "… 静かな道", "風が草を撫でていく。\n今のところ、嫌な気配はない。"),
        "gather": (LAND_COL_GATHER, "## 🍃 何かを見つけた……", "足元の草が、不自然に倒れている。\n近づいて、そっと確かめる。"),
        "story": (LAND_COL_STORY, "## 📖 古い気配がある……", "道の先に、誰かの痕跡が残っている。\nこれは、ただの寄り道ではなさそうだ。"),
        "event": (LAND_COL_EVENT, "## ✦ 何かが起きそうだ……", "空気が少しだけ変わった。\n足を止めて、周囲を見渡す。"),
        "combat": (LAND_COL_COMBAT, "## ⚔️ 物音がした……", "茂みの奥で、何かが動く。\n手に力が入る。"),
        "midrare": (LAND_COL_MID, "## 🔸 ……静かすぎる。", "鳥の声が消えた。\n普通の獣ではない。気を抜くな。"),
        "rare": (LAND_COL_RARE, "## ⚠️ 異様な気配", "風が止んだ。\n空気が重い。\n逃げるなら、今しかない。"),
    }
    col, head, body = table.get(kind, table["event"])
    return col, _pad_note(f"{head}\n{body}", 5)

def build_area_embed(vp, area, note="", color=LAND_COL_NORMAL):
    """探索中の固定枠。枠（フィールド構成）は常に同じ＝チャットが上下に揺れない。
    目立たせるのは枠を大きくするのではなく、見出し(##)と帯の色で。"""
    a = L.LAND_AREAS[area]
    desc = note if note else a["intro"]
    desc = _pad_note(desc, 5)
    e = discord.Embed(title=f"{a['emoji']} {a['name']} ── 探索中", description=desc, color=color)
    cur = _cur_hp(vp); mh = max_hp(vp)
    e.add_field(name="❤️ HP", value=f"{cur}/{mh}\n{hp_bar(cur, mh, 12)}", inline=True)
    e.add_field(name="📊 レベル", value=f"Lv{vp['level']}\nXP {vp['xp']}/{C_xp(vp)}", inline=True)
    e.add_field(name="🎒 装備", value=_gear_line(vp), inline=True)
    e.add_field(name="🐾 所持ペット", value=_pet_line(vp), inline=False)
    buffs = vp.get("land_buffs", {}) or {}
    if buffs:
        bmeta = {"lucky_charm":"🍀幸運", "old_map":"🗺️地図", "lantern":"🔦ランタン", "gold_compass":"🧭羅針盤", "smoke_bomb":"💨煙玉"}
        bline = " / ".join(f"{bmeta.get(k,k)} 残り{v}" for k, v in buffs.items() if v > 0)
        if bline:
            e.add_field(name="✨ 発動中", value=bline, inline=False)
    e.set_footer(text=_harvest_footer(vp))
    return e


# voyage の内部関数に依存しすぎないための薄いラッパ
def C_xp(vp):
    return V.xp_to_next(vp["level"])

def _atk(vp):
    return attack_power(vp)

def _dfn(vp):
    return defense_power(vp)


def land_make_ally(vp):
    """白兵コンバタント。HPは cur_hp 持ち越し（毎戦全快はしない）。
    通常攻撃の多段・技基礎値は make_board_ally と同じ式。"""
    c = C.make_combatant("あなた", "🧑", max_hp(vp),
                         attack_power(vp), defense_power(vp), board_skills(vp))
    c["hp"] = max(1, _cur_hp(vp))   # 0だと戦闘不能なので最低1（タウンで回復前提）
    lv_atk = V.LEVEL_BASE_POWER * vp["level"]
    w = equipped_inst(vp, "weapon")
    if w and w["item"] in V.WEAPONS:
        wd = V.WEAPONS[w["item"]]
        c["base_hits"] = wd.get("hits", 1)
        c["offhand_power"] = round(wd["power"] * V.OFFHAND_HIT_MULT)
        c["skill_base"] = lv_atk + V.SKILL_BASE_BY_RANK.get(wd["rank"], 30)
    else:
        c["skill_base"] = lv_atk
    return c


# ━━━ エントリ ━━━
async def open_land(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    # 入口でHPが未設定なら全快で初期化（タウン経由で来るので基本は満タン）
    vp = db.get_voyage(uid)
    if "cur_hp" not in vp:
        vp["cur_hp"] = max_hp(vp); db.save_voyage(uid, vp)
    embed = build_land_home_embed(vp); view = LandHomeView(uid, gid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


async def _back_to_town(interaction, uid):
    """陸→タウン：収穫を確定（コイン入金）してタウンへ。HPは回復しない。"""
    vp = db.get_voyage(uid)
    _run_settle_town(uid, str(interaction.guild.id), vp)
    # タウン帰還ではHPを全快させない。回復は🏨宿屋（有料・時間制限なし）または食料で行う。
    vp["cur_hp"] = max(1, min(_cur_hp(vp), max_hp(vp)))
    db.save_voyage(uid, vp)
    from cogs.menu import go_town
    await go_town(interaction, uid)


class LandHomeView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(uid)
        for area, a in L.LAND_AREAS.items():
            locked = vp["level"] < a["req_lv"]
            self.add_item(AreaButton(area, a, locked))
        self.add_item(LandTownButton())

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True


class AreaButton(discord.ui.Button):
    def __init__(self, area, a, locked):
        label = f"{a['emoji']} {a['name']}" + (f"（Lv{a['req_lv']}）" if locked else "")
        super().__init__(label=label, style=discord.ButtonStyle.secondary if locked else discord.ButtonStyle.primary,
                         disabled=locked, row=0)
        self.area = area
    async def callback(self, interaction):
        view: LandHomeView = self.view
        await interaction.response.edit_message(
            embed=build_area_embed(db.get_voyage(view.uid), self.area),
            view=LandAreaView(view.uid, view.gid, self.area))


class LandTownButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view = self.view
        await _back_to_town(interaction, view.uid)


# ━━━ 演出中の固定UI（ボタンを消さず無効化して高さブレを防ぐ）━━━
class LandTheaterView(discord.ui.View):
    def __init__(self, uid, gid, area):
        super().__init__(timeout=30)
        self.uid = str(uid); self.gid = str(gid); self.area = area
        self.add_item(discord.ui.Button(label="🥾 探索中…", style=discord.ButtonStyle.secondary, disabled=True, row=0))
        self.add_item(discord.ui.Button(label="🗺️ 行き先を変える", style=discord.ButtonStyle.secondary, disabled=True, row=1))
        self.add_item(discord.ui.Button(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary, disabled=True, row=1))
        if _has_food(uid):
            self.add_item(LandFoodDisabledSelect())

class LandFoodDisabledSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="🍖 食料を食べる（HP回復）",
            options=[discord.SelectOption(label="演出中…", value="wait")],
            disabled=True, row=2)

# ━━━ 食料で回復（道中） ━━━
class LandFoodSelect(discord.ui.Select):
    """🍖 食料を食べてHP回復。戻り先の view を作り直して再描画する。"""
    def __init__(self, uid, gid, area, rebuild):
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.rebuild = rebuild
        vp = db.get_voyage(uid); opts = []
        for fid, n in vp.get("foods", {}).items():
            if n > 0 and fid in V.FOODS:
                f = V.FOODS[fid]
                opts.append(discord.SelectOption(
                    label=f"{f['name']} ×{n}（HP+{int(f['heal_pct']*100)}%）",
                    emoji=f["emoji"], value=fid))
        if not opts:
            opts = [discord.SelectOption(label="食料がない", value="__none__")]
        super().__init__(placeholder="🍖 食料を食べる（HP回復）", options=opts[:25], row=2)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        fid = self.values[0]
        vp = db.get_voyage(self.uid)
        if fid == "__none__" or vp.get("foods", {}).get(fid, 0) <= 0:
            await it.response.send_message("🍖 食べられる食料がない。", ephemeral=True); return
        f = V.FOODS[fid]; mh = max_hp(vp); cur = _cur_hp(vp)
        if cur >= mh:
            await it.response.send_message("❤️ HPは満タンだ。今は食べなくていい。", ephemeral=True); return
        heal = int(mh * f["heal_pct"]); before = cur
        vp["cur_hp"] = min(mh, cur + heal)
        vp["foods"][fid] -= 1
        if vp["foods"][fid] <= 0: del vp["foods"][fid]
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_area_embed(vp, self.area, f"🍖 **{f['name']}** を食べた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）"),
            view=self.rebuild(self.uid, self.gid, self.area))


def _has_food(uid):
    vp = db.get_voyage(uid)
    return any(n > 0 for n in vp.get("foods", {}).values())


# ━━━ 街道消耗品 helper ━━━
def _land_items(vp):
    return vp.setdefault("land_items", {})

def _land_buffs(vp):
    return vp.setdefault("land_buffs", {})

def _add_land_item(uid, vp, item_id, n=1):
    if item_id not in getattr(L, "LAND_ITEMS", {}):
        return None
    inv = _land_items(vp)
    inv[item_id] = inv.get(item_id, 0) + int(n)
    db.add_zukan(uid, "item_seen", item_id)
    it = L.LAND_ITEMS[item_id]
    return f"{it['emoji']} {it['name']}"

def _roll_land_item_drop(uid, vp, tier="zako"):
    got = []
    for item_id, rate in getattr(L, "LAND_ITEM_DROP_RATES", {}).get(tier, []):
        if random.random() < rate:
            name = _add_land_item(uid, vp, item_id, 1)
            if name: got.append(name)
    return got

def _add_craft_material(uid, vp, mat_id, n=1):
    if mat_id not in getattr(V, "MATERIALS", {}):
        return None
    mats = vp.setdefault("materials", {})
    mats[mat_id] = mats.get(mat_id, 0) + int(n)
    db.add_zukan(uid, "item_seen", mat_id)
    m = V.MATERIALS[mat_id]
    return f"{m['emoji']} **{m['name']}**（素材）"

def _roll_land_craft_material(uid, vp, area, bonus=1.0):
    mat = V.roll_craft_material("land", int(area), bonus=bonus) if hasattr(V, "roll_craft_material") else None
    return _add_craft_material(uid, vp, mat, 1) if mat else None

def _has_land_items(uid):
    vp = db.get_voyage(uid)
    return any(n > 0 for n in vp.get("land_items", {}).values())

def _consume_buff_once(vp, key):
    buffs = _land_buffs(vp)
    if buffs.get(key, 0) > 0:
        buffs[key] -= 1
        if buffs[key] <= 0: del buffs[key]
        return True
    return False

def _consume_explore_buffs_once(vp):
    """探索1回につき、探索回数制のバフを必ず1消費する。
    その探索で有効だったバフ状態を返すので、残り1回の効果もきちんと乗る。
    ※ 煙玉は「次の雑魚戦を回避」なので、戦闘発生時だけ消費のまま。
    """
    buffs = _land_buffs(vp)
    active = {k: int(v) for k, v in buffs.items() if int(v) > 0}
    for key in ("lucky_charm", "old_map", "lantern", "gold_compass"):
        if buffs.get(key, 0) > 0:
            buffs[key] -= 1
            if buffs[key] <= 0:
                del buffs[key]
    return active

def _apply_coin_buff(vp, coin, active_buffs=None):
    active_buffs = active_buffs if active_buffs is not None else (vp.get("land_buffs", {}) or {})
    if active_buffs.get("gold_compass", 0) > 0:
        return int(coin * 1.6), True
    return coin, False



class LandItemSelect(discord.ui.Select):
    """街道専用消耗品を使う。"""
    def __init__(self, uid, gid, area, rebuild):
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.rebuild = rebuild
        vp = db.get_voyage(uid); opts=[]
        for iid, n in vp.get("land_items", {}).items():
            if n > 0 and iid in L.LAND_ITEMS:
                it = L.LAND_ITEMS[iid]
                opts.append(discord.SelectOption(label=f"{it['name']} ×{n}", emoji=it['emoji'], value=iid, description=it.get('desc','')[:90]))
        if not opts:
            opts=[discord.SelectOption(label="探索アイテムがない", value="__none__")]
        super().__init__(placeholder="🎒 探索アイテムを使う", options=opts[:25], row=3)
    async def callback(self, itx):
        if str(itx.user.id) != self.uid:
            await itx.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        iid = self.values[0]
        vp = db.get_voyage(self.uid)
        if iid == "__none__" or vp.get("land_items", {}).get(iid, 0) <= 0:
            await itx.response.send_message("使える探索アイテムがない。", ephemeral=True); return
        meta = L.LAND_ITEMS.get(iid)
        if not meta:
            await itx.response.send_message("そのアイテムは使えない。", ephemeral=True); return
        msg = ""
        if iid == "bandage":
            mh=max_hp(vp); cur=_cur_hp(vp)
            if cur >= mh:
                await itx.response.send_message("❤️ HPは満タンだ。", ephemeral=True); return
            before=cur; vp["cur_hp"]=min(mh, cur+int(mh*0.25))
            msg=f"🩹 **包帯** を巻いた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）"
        elif iid == "smoke_bomb":
            _land_buffs(vp)["smoke_bomb"] = _land_buffs(vp).get("smoke_bomb",0)+1
            msg="💨 **煙玉** を構えた。次の雑魚戦を煙に紛れて回避する。"
        elif iid == "lucky_charm":
            _land_buffs(vp)["lucky_charm"] = _land_buffs(vp).get("lucky_charm",0)+10
            msg="🍀 **幸運のお守り** が淡く光った。10探索のあいだ、強敵と良い発見の気配が濃くなる。"
        elif iid == "old_map":
            _land_buffs(vp)["old_map"] = _land_buffs(vp).get("old_map",0)+10
            msg="🗺️ **古びた地図** を広げた。10探索のあいだ、隠れた道や出来事を拾いやすくなる。"
        elif iid == "lantern":
            _land_buffs(vp)["lantern"] = _land_buffs(vp).get("lantern",0)+20
            msg="🔦 **探索ランタン** に火を入れた。20探索のあいだ、何もない道を避けやすくなる。"
        elif iid == "gold_compass":
            _land_buffs(vp)["gold_compass"] = _land_buffs(vp).get("gold_compass",0)+20
            msg="🧭 **黄金の羅針盤** が震えた。20探索のあいだ、コイン収穫が大きく増える。"
        elif iid in ("decoy_doll", "guardian_feather"):
            await itx.response.send_message("これは死亡時に効果を発揮する貴重品。今は使わない方がいい。", ephemeral=True); return
        else:
            await itx.response.send_message("そのアイテムはまだ使えない。", ephemeral=True); return
        vp["land_items"][iid] -= 1
        if vp["land_items"][iid] <= 0: del vp["land_items"][iid]
        db.save_voyage(self.uid, vp)
        await itx.response.edit_message(embed=build_area_embed(vp, self.area, f"## 🎒 アイテム使用\n{msg}", LAND_COL_EVENT), view=self.rebuild(self.uid, self.gid, self.area))

# ━━━ エリア内（探索ループ）━━━
class LandAreaView(discord.ui.View):
    def __init__(self, uid, gid, area):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area
        self.add_item(_ExploreBtn())
        self.add_item(_ChangeBtn())
        self.add_item(_TownBtn())
        if _has_land_items(uid):
            self.add_item(LandItemSelect(uid, gid, area, LandAreaView))
        if _has_food(uid):
            self.add_item(LandFoodSelect(uid, gid, area, LandAreaView))

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    async def _play_and_resolve(self, interaction):
        """先にイベント種別を決めて、その種類に合う演出を固定枠で見せてから結果へ。"""
        vp = db.get_voyage(self.uid)
        buffs = dict(vp.get("land_buffs", {}))
        kind = L.land_encounter_pick(self.area, buffs)
        spec = None
        ev = None
        theater = kind
        if kind in ("combat", "midrare", "rare"):
            force = "combat" if kind == "combat" else kind
            spec = L.make_land_enemy(self.area, force=force, buffs=buffs)
            kind = "combat"
            if spec.get("is_rare"):
                theater = "rare"
            elif spec.get("is_midrare"):
                theater = "midrare"
            else:
                theater = "combat"
        elif kind == "story":
            ev = L.pick_story(self.area); theater = "story"
        elif kind == "event":
            ev = L.pick_random_event(self.area); theater = "event"
        elif kind == "item":
            theater = "gather"
        elif kind == "coin":
            theater = "event"
        elif kind == "gather":
            theater = "gather"
        else:
            theater = "calm"

        col, note = _theater_note(theater)
        await interaction.edit_original_response(
            embed=build_area_embed(vp, self.area, note, col),
            view=LandTheaterView(self.uid, self.gid, self.area))
        await asyncio.sleep(1.6 if theater in ("rare", "midrare") else 1.15)
        await self._resolve_prepared(interaction, kind, spec=spec, ev=ev)

    async def _resolve(self, interaction):
        # 旧呼び出し互換。新規は _play_and_resolve を使う。
        await self._play_and_resolve(interaction)

    async def _resolve_prepared(self, interaction, kind, spec=None, ev=None):
        vp = db.get_voyage(self.uid)
        active_buffs = _consume_explore_buffs_once(vp)
        coin_boost_active = active_buffs.get("gold_compass", 0) > 0
        if spec is not None:
            spec = dict(spec)
            spec["_coin_boost_active"] = coin_boost_active
        if kind == "combat":
            if spec and (not spec.get("is_rare")) and (not spec.get("is_midrare")) and _consume_buff_once(vp, "smoke_bomb"):
                db.save_voyage(self.uid, vp)
                await interaction.edit_original_response(
                    embed=build_area_embed(vp, self.area, "## 💨 煙玉\n敵の気配が近づいた瞬間、煙を放って身を隠した。\n雑魚との戦闘を回避した。", LAND_COL_CALM),
                    view=LandResultView(self.uid, self.gid, self.area))
                return
            db.save_voyage(self.uid, vp)
            await self._start_combat(interaction, vp, spec=spec)
        elif kind == "story":
            db.save_voyage(self.uid, vp)
            ev2 = ev or L.pick_story(self.area)
            if isinstance(ev2, dict):
                ev2 = dict(ev2); ev2["_active_buffs"] = active_buffs
            await self._show_narrative(interaction, vp, ev2)
        elif kind == "event":
            db.save_voyage(self.uid, vp)
            ev2 = ev or L.pick_random_event(self.area)
            if isinstance(ev2, dict):
                ev2 = dict(ev2); ev2["_active_buffs"] = active_buffs
            await self._show_narrative(interaction, vp, ev2)
        elif kind == "item":
            iid = L.pick_land_item(self.area); got = _add_land_item(self.uid, vp, iid, 1)
            mat_got = _roll_land_craft_material(self.uid, vp, self.area, bonus=1.2)
            db.save_voyage(self.uid, vp)
            extra = f"\nさらに {mat_got} も拾った。" if mat_got else ""
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, f"## 🎁 道端の発見\n草陰から **{got}** を見つけた。{extra}\n価値があるかどうかは、使う時になってわかる。", LAND_COL_EVENT),
                view=LandResultView(self.uid, self.gid, self.area))
        elif kind == "coin":
            coin = random.randint(*L.LAND_COIN_EVENT.get(self.area, [300, 1000]))
            coin, boosted = _apply_coin_buff(vp, coin, active_buffs)
            _run_add_coin(vp, coin); db.save_voyage(self.uid, vp)
            plus = "\n🧭 羅針盤が反応した。" if boosted else ""
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, f"## 💰 小さな収穫\n古い革袋を見つけた。{plus}\n中には **{coin:,}** コインが入っていた。", LAND_COL_EVENT),
                view=LandResultView(self.uid, self.gid, self.area))
        elif kind == "gather":
            coin = random.randint(*L.LAND_GATHER_COIN[self.area])
            coin, boosted = _apply_coin_buff(vp, coin, active_buffs)
            mat_got = _roll_land_craft_material(self.uid, vp, self.area, bonus=1.35)
            # まれに大量採取。1000周想定でも「進んでる感」を作る。
            bonus_line = ""
            if random.random() < 0.06:
                extra = []
                for _ in range(random.randint(2, 4)):
                    g = _roll_land_craft_material(self.uid, vp, self.area, bonus=1.0)
                    if g: extra.append(g)
                if extra:
                    bonus_line = "\n✨ 大量採取！ " + " / ".join(extra)
            _run_add_coin(vp, coin); db.save_voyage(self.uid, vp)
            flav = random.choice(L.LAND_GATHER[self.area])
            plus = "\n🧭 羅針盤が反応した。" if boosted else ""
            mat_line = f"\n{mat_got} を手に入れた。" if mat_got else ""
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, f"## 🌿 採取\n{flav}{plus}{mat_line}{bonus_line}\n**💰 +{coin:,}**", LAND_COL_GATHER),
                view=LandResultView(self.uid, self.gid, self.area))
        else:  # calm
            db.save_voyage(self.uid, vp)
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, _pad_note(random.choice(L.LAND_CALM), 5), LAND_COL_CALM),
                view=LandResultView(self.uid, self.gid, self.area))

    async def _start_combat(self, interaction, vp, spec=None):
        spec = spec or L.make_land_enemy(self.area)
        if spec.get("key"):
            db.add_zukan(self.uid, "enemy_seen", spec["key"])   # 📖 図鑑：遭遇を記録
        if _needs_danger_land_event(spec):
            # ★4以上＋固有強敵＝専用演出イベントを挟む。戦闘は「挑む」選択時だけ開始。
            note = _land_danger_note(self.area, spec)
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, note, LAND_COL_RARE),
                view=RareEncounterView(self.uid, self.gid, self.area, spec))
            return
        # 雑魚＝強制戦闘（戦闘中の🏳️撤退は可能）
        await self._begin_fight(interaction, vp, spec)

    async def _begin_fight(self, interaction, vp, spec):
        emb, view = _build_fight(self.uid, self.gid, self.area, spec)
        await interaction.edit_original_response(embed=emb, view=view)

    async def _show_narrative(self, interaction, vp, ev):
        """陸ストーリー／寄り道イベントを、探索枠（固定サイズ）＋色で見せる。"""
        if not ev:
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, random.choice(L.LAND_CALM)),
                view=LandResultView(self.uid, self.gid, self.area)); return
        head = f"## {ev['emoji']} {ev['title']}\n\n"
        prelude = ev.get("prelude") or []
        prelude_txt = ("\n".join(f"> {x}" for x in prelude) + "\n\n") if prelude else ""
        col = LAND_COL_RARE if ev.get("hot") else (LAND_COL_EVENT if ev.get("id", "").startswith("e_") else LAND_COL_STORY)
        if ev.get("type", "choice") == "choice":
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, head + prelude_txt + ev["flavor"], col),
                view=LandStoryView(self.uid, self.gid, self.area, ev))
        else:  # text
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, head + ev["body"], col),
                view=LandResultView(self.uid, self.gid, self.area))


class _ExploreBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🥾 探索する", style=discord.ButtonStyle.success, row=0)
    async def callback(self, interaction):
        view: LandAreaView = self.view
        vp = db.get_voyage(view.uid)
        pet_note = _apply_pet_explore_heal(view.uid, vp)
        db.save_voyage(view.uid, vp)
        # ここで先に defer しておく。
        # response.edit_message → sleep → edit_original_response の混在で、
        # Discord側のタイミング次第で演出画面のまま止まることがあったため、
        # 以降の画面更新は edit_original_response に統一する。
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=build_area_embed(vp, view.area, _pad_note(f"## {random.choice(LAND_WAITS)}" + (f"\n{pet_note}" if pet_note else ""), 5), LAND_COL_NORMAL),
            view=LandTheaterView(view.uid, view.gid, view.area))
        await asyncio.sleep(0.45)
        try:
            await view._play_and_resolve(interaction)
        except Exception:
            # 万一イベント解決で落ちても、無効ボタンの演出画面に取り残されないよう復帰させる。
            vp = db.get_voyage(view.uid)
            await interaction.edit_original_response(
                embed=build_area_embed(vp, view.area, "## 🌿 足を止めた……\n嫌な予感がして、いったん周囲を見直した。\nもう一度探索できる。", LAND_COL_CALM),
                view=LandResultView(view.uid, view.gid, view.area))

class _ChangeBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🗺️ 行き先を変える", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view = self.view
        await interaction.response.edit_message(
            embed=build_land_home_embed(db.get_voyage(view.uid)), view=LandHomeView(view.uid, view.gid))

class _TownBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view = self.view
        await _back_to_town(interaction, view.uid)


# ━━━ 陸の戦闘開始／撤退／激レア前哨 ━━━
def _build_fight(uid, gid, area, spec):
    """敵スペックから戦闘embed＋CombatViewを組む（雑魚・激レア共通）。戦闘中の撤退OK。"""
    vp = db.get_voyage(uid)
    a = L.LAND_AREAS[area]
    ally = land_make_ally(vp)
    scale = spec.get("scale_override", a["scale"])   # レアは共通ボスscale
    enemy = make_board_enemy(spec, scale)
    state = C.new_battle("board", ally, enemy)
    state["land_spec"] = dict(spec)
    st = "★" * int(spec.get("stars", 1))
    emb = build_combat_embed(state)
    if spec.get("is_xp_runner"):
        if spec.get("is_king_runner"):
            emb.description = (
                f"## 👑💎 伝説級の経験値モンスター！\n"
                f"**{spec['emoji']} {spec['name']}** {st} が現れた！\n"
                "逃げ足が異常に速い。倒せば莫大な経験値だ。"
            )
        else:
            emb.description = (
                f"## 💎 強い生命反応！\n"
                f"**{spec['emoji']} {spec['name']}** {st} が現れた！\n"
                "逃げ足が非常に速い。3ターン以内に仕留めたい。"
            )
    elif spec.get("is_rare"):
        emb.description = f"✨ **{spec['emoji']} {spec['name']}** {st} との戦い！"
    elif spec.get("is_midrare"):
        emb.description = f"🔸 **{spec['emoji']} {spec['name']}** {st} ── 強そうな個体だ！"
    else:
        emb.description = f"{spec['emoji']} **{spec['name']}** {st} が現れた！"
    view = CombatView(uid, gid, state,
                      on_end=land_on_end(uid, gid, area, spec),
                      flee_cb=_land_flee_cb(uid, gid, area),
                      flee_pct=_land_flee_pct(uid, area, state))
    return emb, view


async def do_land_fight(interaction, uid, gid, area, spec):
    """フレッシュなインタラクションから戦闘へ（激レアの『挑む』用）。"""
    emb, view = _build_fight(uid, gid, area, spec)
    await interaction.response.edit_message(embed=emb, view=view)


def _land_escape_power(vp):
    """陸の逃走判定に使うプレイヤー側戦力。海の ship_power と同じく攻＋防で見る。"""
    return max(1.0, float(attack_power(vp) + defense_power(vp)))


def _land_enemy_escape_power(area, spec):
    """陸敵の逃走判定用戦力。実戦用ステータスを作り、攻＋防で海と同じ式に渡す。"""
    a = L.LAND_AREAS[area]
    scale = spec.get("scale_override", a["scale"])
    enemy = make_board_enemy(spec, scale)
    return max(1.0, float(enemy.get("atk", 1) + enemy.get("def", 0)))


def _land_flee_pct(uid, area, spec_or_state):
    vp = db.get_voyage(uid)
    enemy_power = None
    if isinstance(spec_or_state, dict) and "enemy" in spec_or_state:
        e = spec_or_state.get("enemy", {})
        enemy_power = float(e.get("atk", 1) + e.get("def", 0))
    elif isinstance(spec_or_state, dict):
        enemy_power = _land_enemy_escape_power(area, spec_or_state)
    chance = V.flee_success_chance(_land_escape_power(vp), max(1.0, enemy_power or 1.0))
    return min(0.95, chance + 0.15)


def _land_apply_enemy_first_strike(state):
    """逃走失敗時の敵先制行動。海の撤退失敗と同じ流れで戦闘継続させる。"""
    state["log"] = ["🏃💨 逃走失敗！隙を突かれた…"]
    if not state.get("over"):
        C.resolve_action(state, "enemy", C.enemy_action(state))
    if not state.get("over"):
        C.end_round(state)


def _land_flee_cb(uid, gid, area):
    """戦闘中の🏳️撤退：海と同じ成功率判定。煙玉だけは state フラグで100%成功。"""
    async def _flee(it, state):
        vp = db.get_voyage(uid)
        force_success = bool(state.pop("_force_flee_success_once", False))
        chance = 1.0 if force_success else _land_flee_pct(uid, area, state)
        if force_success or random.random() < chance:
            vp["cur_hp"] = max(1, state["ally"]["hp"])  # 逃げてもHPは戦闘時点のまま
            db.save_voyage(uid, vp)
            title = "💨 煙玉" if force_success else "🏳️ 撤退成功"
            body = "煙に紛れて、確実にその場を離脱した。" if force_success else "隙を突いて、その場を離脱した。"
            await it.response.edit_message(
                embed=build_area_embed(vp, area, f"## {title}\n{body}"),
                view=LandResultView(uid, gid, area))
            return

        _land_apply_enemy_first_strike(state)
        vp["cur_hp"] = max(1, state["ally"]["hp"])
        db.save_voyage(uid, vp)
        spec = state.get("land_spec") or {"name": state["enemy"].get("name", "敵"), "emoji": state["enemy"].get("emoji", "⚔️"), "no_item_drop": True}
        if state.get("over"):
            await land_on_end(uid, gid, area, spec)(it, state)
        else:
            await it.response.edit_message(
                embed=build_combat_embed(state),
                view=CombatView(uid, gid, state, on_end=land_on_end(uid, gid, area, spec), flee_cb=_land_flee_cb(uid, gid, area), flee_pct=chance))
    return _flee


def _needs_danger_land_event(spec):
    """★4以上の敵と、固有名つき中ボスは通常戦闘前に専用イベント化する。"""
    try:
        stars = int(spec.get("stars", 1))
    except Exception:
        stars = 1
    if stars >= 4:
        return True
    # 依頼文の例に合わせ、山の固有強敵など☆3中レアも「危険演出」対象にする。
    return bool(spec.get("is_midrare"))


def _land_danger_note(area, spec):
    name = spec.get("name", "敵")
    emoji = spec.get("emoji", "⚠️")
    st = "★" * int(spec.get("stars", 4))
    rare_intro = spec.get("rare_intro")
    texts = {
        "迷い込んだ白鹿": (
            "草原を渡る風が、急に音を失った。\n"
            "白い鹿がこちらを見る。獣の目ではない。こちらの罪まで見透かすような、静かな瞳だ。\n"
            "不用意に踏み込めば、草原そのものを敵に回す気がする。"),
        "森番のフードの男": (
            "木々のざわめきが、一本ずつ消えていく。\n"
            "フードを目深にかぶった男が、道の真ん中に立っていた。弓は構えていない。だが、すでに射抜かれているような圧がある。\n"
            "この先へ行くなら、森の許しを得る必要がある。力ずくでも、沈黙でも。"),
        "塔の伝令騎士": (
            "山道の石が、かすかに震えた。\n"
            "塔の紋章を掲げた騎士が、霧の中から現れる。剣は抜かれていない。抜かせた時点で、もう戻れない。\n"
            "彼は伝令だ。だが、伝える相手を生かして帰す気があるのかはわからない。"),
        "古竜のなりそこない": (
            "崖の一部だと思っていた岩肌が、ゆっくりと呼吸した。\n"
            "割れた鱗の奥で、古い火がくすぶっている。竜になれなかったもの――それでも、人が触れていい存在ではない。\n"
            "一歩進めば、山そのものが牙を剥く。"),
        "石の巨人": (
            "谷底から、石臼を引きずるような音が響く。\n"
            "巨大な岩が立ち上がった。苔むした顔の奥で、古い怒りだけがまだ動いている。\n"
            "近づくなら、踏み潰される覚悟がいる。"),
        "山の魔女": (
            "山霧が、甘い薬草の匂いに変わった。\n"
            "枯れ木の杖をついた女が、笑っている。親切そうな声なのに、足元の影だけがこちらへ伸びてくる。\n"
            "会話で済むか、呪いで終わるか。判断を間違えるな。"),
        "森の主・大熊": (
            "枝が折れる音が、やけに大きく響いた。\n"
            "森の奥から、異様に大きな熊が姿を現す。逃げる獲物を見る目ではない。縄張りを侵した者への裁きだ。"),
        "毒蜘蛛の女王": (
            "木漏れ日が、白い糸に遮られている。\n"
            "足元の草まで粘つき、頭上で巨大な影が揺れた。巣の中心から、毒蜘蛛の女王が降りてくる。"),
        "山賊の頭目": (
            "獣道の両側から、笑い声がした。\n"
            "道を塞ぐ男は、ただの山賊ではない。背後の部下たちが、彼の一挙手一投足を待っている。"),
    }
    body = texts.get(name) or rare_intro or "空気が重く沈む。目の前の相手は、普段の獣や賊とは明らかに違う。"
    return (f"## ⚠️ {emoji} {name} {st}\n\n{body}\n\n"
            "**この先は非常に危険そうだ。どう動く？**")


def _land_minor_reward(uid, vp, area):
    roll = random.random()
    if roll < 0.34:
        coin = max(50, random.randint(*L.LAND_COIN_EVENT.get(area, [300, 1000])) // 4)
        _run_add_coin(vp, coin)
        return f"💰 慎重に動いたおかげで、足元の古い革袋を拾った。 **+{coin:,}**"
    if roll < 0.58:
        got = _roll_land_craft_material(uid, vp, area, bonus=0.85)
        return f"💎 気配が去ったあと、痕跡から {got} を拾った。" if got else "気配が去ったあと、折れた枝だけが残っていた。"
    if roll < 0.78:
        xp = _land_xp_amount(vp, area, random.randint(2, 5))
        add_xp(vp, xp)
        return f"✨ 危険を読む勘が少しだけ研ぎ澄まされた。 **XP +{xp}**"
    return "何も得られなかった。だが、命を拾っただけでも十分だ。"


class RareEncounterView(discord.ui.View):
    """危険遭遇：3〜4択。戦闘は『挑む』選択時だけ開始。"""
    def __init__(self, uid, gid, area, spec):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.spec = spec
        self.add_item(_RareFightBtn())
        self.add_item(_RareObserveBtn())
        self.add_item(_RareAvoidBtn())
        self.add_item(_RareFleeBtn())

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class _RareFightBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚔️ 挑む", style=discord.ButtonStyle.danger, row=0)
    async def callback(self, interaction):
        view: RareEncounterView = self.view
        await do_land_fight(interaction, view.uid, view.gid, view.area, view.spec)

class _RareObserveBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="👁️ 様子を見る", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction):
        view: RareEncounterView = self.view
        vp = db.get_voyage(view.uid)
        line = _land_minor_reward(view.uid, vp, view.area)
        db.save_voyage(view.uid, vp)
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, f"## 👁️ 様子を見る\n距離を保ち、相手の出方をうかがった。\n{line}", LAND_COL_EVENT),
            view=LandResultView(view.uid, view.gid, view.area))

class _RareAvoidBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🌿 やり過ごす", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction):
        view: RareEncounterView = self.view
        vp = db.get_voyage(view.uid)
        line = _land_minor_reward(view.uid, vp, view.area) if random.random() < 0.45 else "息を殺して待つ。やがて危険な気配は、ゆっくりと遠ざかった。"
        db.save_voyage(view.uid, vp)
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, f"## 🌿 やり過ごす\n{line}", LAND_COL_CALM),
            view=LandResultView(view.uid, view.gid, view.area))

class _RareFleeBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏃 逃げる", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction):
        view: RareEncounterView = self.view
        vp = db.get_voyage(view.uid)
        chance = _land_flee_pct(view.uid, view.area, view.spec)
        if random.random() < chance:
            await interaction.response.edit_message(
                embed=build_area_embed(vp, view.area, f"## 🏳️ 逃走成功（成功率{int(round(chance * 100))}%）\n関わらないのが賢明だ。背後を振り返らず、その場を離れた。", LAND_COL_CALM),
                view=LandResultView(view.uid, view.gid, view.area))
            return

        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, f"## 🏃💨 逃走失敗（成功率{int(round(chance * 100))}%）\n背を向けた瞬間、敵に距離を詰められた。", LAND_COL_COMBAT),
            view=LandTheaterView(view.uid, view.gid, view.area))
        await asyncio.sleep(1.0)
        emb, fight_view = _build_fight(view.uid, view.gid, view.area, view.spec)
        _land_apply_enemy_first_strike(fight_view.state)
        await interaction.edit_original_response(embed=build_combat_embed(fight_view.state), view=fight_view)



# ━━━ イベントのサブ抽選（イベントは「きっかけ」、結果は毎回揺れる）━━━
def _choice_outcome(ch):
    outs = ch.get("outcomes")
    if not outs:
        return None
    keys = [x[0] for x in outs]; wts = [x[1] for x in outs]
    return random.choices(keys, weights=wts)[0]

def _apply_event_outcome(uid, gid, vp, area, outcome, event=None, choice=None):
    lines = []
    start_combat = None
    event = event or {}
    reward_mult = int(event.get("reward_mult", 1) or 1)
    risk_mult = int(event.get("risk_mult", 1) or 1)
    is_hot = bool(event.get("hot"))
    if not outcome or outcome == "nothing":
        lines.append("何も見つからなかった。けれど、空気だけは少し重い。")
    elif outcome == "coin":
        coin = random.randint(*L.LAND_COIN_EVENT.get(area, [300,1000])) * reward_mult
        coin, boosted = _apply_coin_buff(vp, coin, (event or {}).get("_active_buffs", {}))
        _run_add_coin(vp, coin)
        lines.append(f"## 💰 +{coin:,}" + ("\n🧭 羅針盤が反応した。" if boosted else ""))
    elif outcome == "item":
        if is_hot and hasattr(L, "pick_hot_land_item"):
            iid = L.pick_hot_land_item(area)
        else:
            iid = L.pick_land_item(area)
        got = _add_land_item(uid, vp, iid, 1)
        lines.append(f"## 🎁 {got} を手に入れた！")
    elif outcome == "xp":
        xp = (random.randint(2, 6) if area == 1 else random.randint(5, 12) if area == 2 else random.randint(8, 18)) * reward_mult
        xp = _land_xp_amount(vp, area, xp)
        leveled = add_xp(vp, xp); lines.append(f"## ✨ XP +{xp}")
        if leveled: lines.append(f"## 🎉 レベルアップ！ → Lv{vp['level']}")
    elif outcome == "heal":
        mh=max_hp(vp); cur=_cur_hp(vp); heal=int(mh*(0.15+0.05*area)*reward_mult); vp["cur_hp"]=min(mh, cur+heal)
        lines.append(f"## ❤️ HP +{vp['cur_hp']-cur}（{vp['cur_hp']}/{mh}）")
    elif outcome == "damage":
        mh=max_hp(vp); cur=_cur_hp(vp); dmg=(random.randint(5, 12) if area == 1 else random.randint(10, 22) if area == 2 else random.randint(16, 34)) * risk_mult
        vp["cur_hp"] = max(1, cur-dmg); lines.append(f"## 💢 罠で -{cur-vp['cur_hp']}（{vp['cur_hp']}/{mh}）")
    elif outcome == "combat":
        lines.append("## ⚔️ 物音がした……\nイベントの気配に釣られて、敵が飛び出してきた！")
        start_combat = L.make_land_enemy(area, force=("hot_midrare" if is_hot else "combat"), buffs=vp.get("land_buffs", {}))
    elif outcome == "mid_hint":
        lines.append("## 🔸 強い気配\n普通の獣ではない足跡を見つけた。今日は深入りしない方がいいかもしれない。")
    elif outcome == "story":
        lines.append("## 📖 塔の痕跡\n古い文字が残っている。意味はわからない。だが、海を嫌っていることだけは伝わってくる。")
    return lines, start_combat



def _is_land_escape_choice(label):
    """イベント選択肢の逃げる系を通常撤退と同じ判定に統一する。"""
    text = str(label or "")
    return any(k in text for k in ("逃げ", "立ち去", "撤退", "退く", "離れる", "やめる"))

# ━━━ 陸ストーリー（選択肢）━━━
class LandStoryView(discord.ui.View):
    def __init__(self, uid, gid, area, ev):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.ev = ev
        for i, ch in enumerate(ev["choices"]):
            self.add_item(_StoryChoiceBtn(i, ch["label"], row=0))
        # 選択イベント中も通常探索と近いコンポーネント行数を保つ。
        # 操作は選択肢だけ、下段は視覚的な高さ維持用の無効ボタン。
        self.add_item(discord.ui.Button(label="🗺️ 行き先を変える", style=discord.ButtonStyle.secondary, disabled=True, row=1))
        self.add_item(discord.ui.Button(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary, disabled=True, row=1))
        if _has_food(uid):
            self.add_item(LandFoodDisabledSelect())

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class _StoryChoiceBtn(discord.ui.Button):
    def __init__(self, idx, label, row=0):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.idx = idx
    async def callback(self, interaction):
        view: LandStoryView = self.view
        ch = view.ev["choices"][self.idx]
        vp = db.get_voyage(view.uid)
        prelude = view.ev.get("prelude") or []
        lines = [f"## {view.ev['emoji']} {view.ev['title']}"]
        if prelude:
            lines += ["", *[f"> {x}" for x in prelude]]
        lines += ["", ch["result"]]

        # 「逃げる／立ち去る／撤退する」系のイベント選択肢も、通常戦闘の撤退と同じ成功率判定に統一。
        # 成功時だけ元の選択肢処理へ進む。失敗時は報酬や安全な離脱を無効化し、敵の先制行動つきで戦闘へ。
        if _is_land_escape_choice(ch.get("label")):
            flee_spec = L.make_land_enemy(view.area, force=("hot_midrare" if view.ev.get("hot") else "combat"), buffs=vp.get("land_buffs", {}))
            chance = _land_flee_pct(view.uid, view.area, flee_spec)
            if random.random() >= chance:
                lines.append("")
                lines.append(f"## 🏃💨 逃走失敗（成功率{int(round(chance * 100))}%）")
                lines.append("背を向けた瞬間、敵に距離を詰められた。")
                db.save_voyage(view.uid, vp)
                await interaction.response.edit_message(
                    embed=build_area_embed(vp, view.area, "\n".join(lines), LAND_COL_COMBAT),
                    view=LandTheaterView(view.uid, view.gid, view.area))
                await asyncio.sleep(1.0)
                emb, fight_view = _build_fight(view.uid, view.gid, view.area, flee_spec)
                _land_apply_enemy_first_strike(fight_view.state)
                await interaction.edit_original_response(embed=build_combat_embed(fight_view.state), view=fight_view)
                return
            lines.append("")
            lines.append(f"## 🏳️ 逃走成功（成功率{int(round(chance * 100))}%）")

        hot_reward_mult = int(view.ev.get("reward_mult", 1) or 1)
        hot_risk_mult = int(view.ev.get("risk_mult", 1) or 1)
        if ch.get("coin"):
            coin = random.randint(*ch["coin"]) * hot_reward_mult
            _run_add_coin(vp, coin)
            lines.append(f"## 💰 +{coin:,}")
        if ch.get("xp"):
            xp = random.randint(*ch["xp"]) * hot_reward_mult
            xp = _land_xp_amount(vp, view.area, xp)
            leveled = add_xp(vp, xp)
            lines.append(f"## ✨ XP +{xp}")
            if leveled:
                lines.append(f"## 🎉 レベルアップ！ → Lv{vp['level']}")
        if ch.get("heal"):
            mh = max_hp(vp); cur = _cur_hp(vp)
            heal = int(mh * ch["heal"] * hot_reward_mult); before = cur
            vp["cur_hp"] = min(mh, cur + heal)
            lines.append(f"## ❤️ HP +{vp['cur_hp']-before}（{vp['cur_hp']}/{mh}）")
        if ch.get("dmg"):
            mh = max_hp(vp); cur = _cur_hp(vp)
            vp["cur_hp"] = max(1, cur - int(ch["dmg"] * hot_risk_mult))
            lines.append(f"## 💢 -{cur-vp['cur_hp']}（{vp['cur_hp']}/{mh}）")
        if ch.get("food"):
            fid = ch["food"]
            if fid in V.FOODS:
                vp.setdefault("foods", {}); vp["foods"][fid] = vp["foods"].get(fid, 0) + 1
                db.add_zukan(view.uid, "item_seen", fid)
                lines.append(f"## 🍖 {V.FOODS[fid]['name']} を手に入れた！")
        if ch.get("cost"):
            cost = random.randint(*ch["cost"])
            bal = db.get_balance(view.uid, view.gid)
            pay = min(bal, cost)
            if pay > 0:
                db.update_balance(view.uid, view.gid, -pay)
                lines.append(f"💸 -{pay:,} コイン")
        out = _choice_outcome(ch)
        extra, start_combat = _apply_event_outcome(view.uid, view.gid, vp, view.area, out, view.ev, ch)
        if extra:
            lines.append(""); lines.extend(extra)
        db.save_voyage(view.uid, vp)
        if start_combat:
            await interaction.response.edit_message(embed=build_area_embed(vp, view.area, "\n".join(lines), LAND_COL_COMBAT), view=LandTheaterView(view.uid, view.gid, view.area))
            await asyncio.sleep(1.0)
            emb, fight_view = _build_fight(view.uid, view.gid, view.area, start_combat)
            await interaction.edit_original_response(embed=emb, view=fight_view)
            return
        col = LAND_COL_EVENT if view.ev.get("id", "").startswith(("e_", "rv_")) else LAND_COL_STORY
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, "\n".join(lines), col),
            view=LandResultView(view.uid, view.gid, view.area))


def land_on_end(uid, gid, area, spec):
    """白兵戦の決着コールバック。結果テキストは description（航海中と同じ大きさ）で見せる。
    HPは戦闘後の残量を cur_hp に持ち越す。"""
    async def _end(interaction, state):
        vp = db.get_voyage(uid)
        # 🩸 戦闘後HPを持ち越し
        vp["cur_hp"] = max(0, state["ally"]["hp"])
        a = L.LAND_AREAS[area]
        emb = build_combat_embed(state)
        if state.get("result") == "escaped":
            db.save_voyage(uid, vp)
            emb.description = f"## 💨 {spec.get('emoji','')} {spec.get('name','敵')} は逃げ去った！\n\n光の粒だけが、空気に残っている。\n**報酬は得られなかった。**"
            await interaction.response.edit_message(embed=emb, view=LandResultView(uid, gid, area))
            return
        if state["result"] == "win":
            # 📖 図鑑（討伐の証）
            if spec.get("key"):
                db.add_zukan(uid, "enemy_kill", spec["key"])
            if spec.get("is_xp_runner"):
                xp = random.randint(*a["xp"]) * int(spec.get("xp_mult", 20))
                coin = max(0, int(random.randint(*a["coin"]) * float(spec.get("coin_mult", 0.25))))
            elif spec.get("is_rare"):
                xp = random.randint(*(spec.get("rare_xp") or a["xp"]))
                coin = random.randint(*(spec.get("rare_coin") or a["coin"]))
            elif spec.get("is_midrare"):
                xp = random.randint(*(spec.get("mid_xp") or a["xp"]))
                coin = random.randint(*(spec.get("mid_coin") or a["coin"]))
            else:
                xp = random.randint(*a["xp"]); coin = random.randint(*a["coin"])
            if not spec.get("is_xp_runner"):
                xp = int(xp * float(spec.get("reward_ratio", 1.0)))
            xp = _land_xp_amount(vp, area, xp)
            coin, coin_boosted = _apply_coin_buff(vp, coin, {"gold_compass": 1} if spec.get("_coin_boost_active") else {})
            leveled = add_xp(vp, xp)
            _run_add_coin(vp, coin)                 # 💰 収穫に貯める（タウン帰還で確定／死ぬと半分失う）
            drop = None if spec.get("no_item_drop") else _run_add_drop(uid, vp, area, spec)   # 🎁 装備ドロップ（中レアは高確率）
            tier = "rare" if spec.get("is_rare") else "mid" if spec.get("is_midrare") else "zako"
            item_drops = [] if spec.get("no_item_drop") else _roll_land_item_drop(uid, vp, tier)
            craft_mat = None if spec.get("no_item_drop") else _roll_land_craft_material(uid, vp, area, bonus=(1.5 if tier != "zako" else 1.0))
            db.save_voyage(uid, vp)
            if spec.get("is_xp_runner"):
                head = f"## {'👑' if spec.get('is_king_runner') else '💎'}🏆 {spec['emoji']} {spec['name']} を逃がさず仕留めた！"
            elif spec.get("is_rare"):
                head = f"## ✨🏆 レアな {spec['emoji']} {spec['name']} を討ち取った！"
            elif spec.get("is_midrare"):
                head = f"## 🔸🏆 {spec['emoji']} {spec['name']} を討ち取った！"
            else:
                head = f"## 🏆 {spec['emoji']} {spec['name']} を倒した！"
            lines = [head, f"**✨ XP +{xp}　💰 +{coin:,}**" + ("\n🧭 羅針盤が反応した。" if coin_boosted else "")]
            if leveled:
                lines.append(f"## 🎉 レベルアップ！ → Lv{vp['level']}")
            if drop:
                lines.append(f"## 🎁 {drop} を手に入れた！")
            for got_item in item_drops:
                lines.append(f"## 🎒 {got_item} を手に入れた！")
            if craft_mat:
                lines.append(f"## 💎 {craft_mat} を手に入れた！")
            if spec.get("is_rare") and spec.get("rare_story"):
                lines.append("")
                lines.append(f"> {spec['rare_story']}")
            emb.description = "\n".join(lines)
            view = LandResultView(uid, gid, area)
        else:
            xp = _land_xp_amount(vp, area, max(2, a_lose_xp(area))); add_xp(vp, xp)
            vp["cur_hp"] = max(1, max_hp(vp) // 4)   # 帰還後の残HP（宿屋や食料で立て直す）
            if vp.get("land_items", {}).get("decoy_doll", 0) > 0:
                vp["land_items"]["decoy_doll"] -= 1
                if vp["land_items"]["decoy_doll"] <= 0: del vp["land_items"]["decoy_doll"]
                _run_settle_town(uid, gid, vp)
                lost = ["🪆 **身代わり人形** が砕け、収穫ロストを防いだ。"]
                db.save_voyage(uid, vp)
            elif vp.get("land_items", {}).get("guardian_feather", 0) > 0:
                db.save_voyage(uid, vp)
                emb.description = "## 💀 …目の前が、すうっと暗くなった。\n\n👼 **守護の羽** が震えている。\n使えば今回の収穫ロストを防げる。"
                await interaction.response.edit_message(embed=emb, view=FeatherChoiceView(uid, gid))
                return
            else:
                lost = _run_settle_death(uid, gid, vp)   # 💀 収穫の50%を失う
                db.save_voyage(uid, vp)
            body = [
                "## 💀 …目の前が、すうっと暗くなった。",
                "",
                "🌀 ――気づくと、見覚えのある我が家の寝床に倒れていた。",
                "誰が、どうやって運んだのか。**思い出せない。**",
                "（陸でも、海でも……お前は、まだ“終わらせて”もらえないらしい）",
            ]
            if lost:
                body.append("")
                body.append("## 💔 持ち物を半分、どこかへ落としてきた…")
                body += lost
            body.append("")
            body.append(f"（XP +{xp}）")
            emb.description = "\n".join(body)
            view = WakeHomeView(uid, gid)
        await interaction.response.edit_message(embed=emb, view=view)
    return _end



class FeatherChoiceView(discord.ui.View):
    """守護の羽は死亡時に使う/使わないを選択できる。"""
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid=str(uid); self.gid=str(gid)
        self.add_item(_UseFeatherBtn())
        self.add_item(_NoFeatherBtn())
    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return False
        return True

class _UseFeatherBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="👼 守護の羽を使う", style=discord.ButtonStyle.primary, row=0)
    async def callback(self, it):
        view: FeatherChoiceView = self.view
        vp = db.get_voyage(view.uid)
        if vp.get("land_items", {}).get("guardian_feather", 0) <= 0:
            await it.response.send_message("守護の羽がない。", ephemeral=True); return
        vp["land_items"]["guardian_feather"] -= 1
        if vp["land_items"]["guardian_feather"] <= 0: del vp["land_items"]["guardian_feather"]
        _run_settle_town(view.uid, view.gid, vp)
        vp["cur_hp"] = max(1, max_hp(vp)//4)
        db.save_voyage(view.uid, vp)
        e = discord.Embed(title="👼 守護の羽", color=0xf5d76e, description="## 👼 羽が光にほどけた。\n今回の収穫は失われなかった。\n気づけば、見覚えのある我が家の寝床に倒れていた。")
        await it.response.edit_message(embed=e, view=WakeHomeView(view.uid, view.gid))

class _NoFeatherBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="使わない", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, it):
        view: FeatherChoiceView = self.view
        vp = db.get_voyage(view.uid)
        lost = _run_settle_death(view.uid, view.gid, vp)
        vp["cur_hp"] = max(1, max_hp(vp)//4)
        db.save_voyage(view.uid, vp)
        body = ["## 💀 羽は使わなかった。", "🌀 気づくと、見覚えのある我が家の寝床に倒れていた。"]
        if lost:
            body.append(""); body.append("## 💔 持ち物を半分、どこかへ落としてきた…"); body += lost
        e = discord.Embed(title="💀 戦闘不能", color=0x7f1d1d, description="\n".join(body))
        await it.response.edit_message(embed=e, view=WakeHomeView(view.uid, view.gid))

class WakeHomeView(discord.ui.View):
    """敗北後：不思議な力で家に戻された → 目を覚ましてタウンへ。"""
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        b = discord.ui.Button(label="▶ 目を覚ます", style=discord.ButtonStyle.primary)
        async def _wake(it):
            if str(it.user.id) != self.uid:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await _back_to_town(it, self.uid)
        b.callback = _wake
        self.add_item(b)

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True


def a_lose_xp(area):
    return {1: 6, 2: 10, 3: 16}.get(area, 6)


class LandResultView(discord.ui.View):
    """戦闘・ストーリー・採取のあと：続けて探索／行き先変更／食料／タウン。"""
    def __init__(self, uid, gid, area):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area
        self.add_item(_AgainBtn())
        self.add_item(_ChangeBtn())
        self.add_item(_TownBtn())
        if _has_land_items(uid):
            self.add_item(LandItemSelect(uid, gid, area, LandResultView))
        if _has_food(uid):
            self.add_item(LandFoodSelect(uid, gid, area, LandResultView))

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True


class _AgainBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🥾 続けて探索", style=discord.ButtonStyle.success, row=0)
    async def callback(self, interaction):
        view: LandResultView = self.view
        vp = db.get_voyage(view.uid)
        pet_note = _apply_pet_explore_heal(view.uid, vp)
        db.save_voyage(view.uid, vp)
        await interaction.response.defer()
        await interaction.edit_original_response(
            embed=build_area_embed(vp, view.area, _pad_note(f"## {random.choice(LAND_WAITS)}" + (f"\n{pet_note}" if pet_note else ""), 5), LAND_COL_NORMAL),
            view=LandTheaterView(view.uid, view.gid, view.area))
        await asyncio.sleep(0.45)
        try:
            av = LandAreaView(view.uid, view.gid, view.area)
            await av._play_and_resolve(interaction)
        except Exception:
            vp = db.get_voyage(view.uid)
            await interaction.edit_original_response(
                embed=build_area_embed(vp, view.area, "## 🌿 足を止めた……\n嫌な予感がして、いったん周囲を見直した。\nもう一度探索できる。", LAND_COL_CALM),
                view=LandResultView(view.uid, view.gid, view.area))


class Land(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# ━━━ 📖 街道図鑑（海洋と同じく 遭遇／討伐 を表示・エリア別タブ）━━━
LAND_ZUKAN_COLOR = {1: 0x4f9d69, 2: 0x2e7d4f, 3: 0x6d5a45}

def build_land_zukan_embed(uid, area=1):
    a = L.LAND_AREAS[area]
    seen = set(db.get_zukan(uid, "enemy_seen")) if uid else set()
    killed = set(db.get_zukan(uid, "enemy_kill")) if uid else set()
    cat = [(f"land{area}_{e['name']}", e, "zako") for e in L.LAND_ENEMIES[area]]
    cat += [(f"landmid{area}_{e['name']}", e, "mid") for e in L.LAND_MIDRARES.get(area, [])]
    # 💎 経験値逃走モンスターも、遭遇/討伐時に記録される key と同じ形式で図鑑に載せる
    for _runner_kind, e in (L.XP_RUNNERS.get(area, {}) or {}).items():
        cat.append((f"landrunner{area}_{e['name']}", e, "runner"))
    cat += [(f"land{area}_{e['name']}", e, "rare") for e in L.LAND_RARES.get(area, [])]
    total = len(cat)
    seen_n = len([1 for k, _, _ in cat if k in seen])
    kill_n = len([1 for k, _, _ in cat if k in killed])
    emb = discord.Embed(
        title=f"📖 街道図鑑 — {a['emoji']} {a['name']}",
        description=f"遭遇 **{seen_n}/{total}** ・ 討伐 **{kill_n}/{total}**\n（★は強さ。🔸中レア／💎経験値／✨レア＝ボス級）",
        color=LAND_ZUKAN_COLOR.get(area, 0x4f9d69))
    by_star = {}
    for k, e, kind in cat:
        star = int(e.get("stars", 1))
        if k in seen:
            mark = " ⚔️**討伐済**" if k in killed else ""
            pre = {"mid": "🔸", "runner": "💎", "rare": "✨"}.get(kind, "")
            nm = f"{pre}{e['emoji']} {e['name']}{mark}"
        else:
            nm = "❔ ？？？"
        by_star.setdefault(star, []).append(nm)
    for star in sorted(by_star):
        emb.add_field(name="★" * star, value="\n".join(by_star[star]), inline=False)
    return emb

class LandZukanView(discord.ui.View):
    def __init__(self, user_id, area=1):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.area = area
        for a in (1, 2, 3):
            b = discord.ui.Button(
                label=f"{L.LAND_AREAS[a]['emoji']} {L.LAND_AREAS[a]['name']}",
                style=discord.ButtonStyle.primary if a == area else discord.ButtonStyle.secondary, row=0)
            b.callback = self._mk(a); self.add_item(b)
        back = discord.ui.Button(label="◀ 図鑑トップへ", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._back; self.add_item(back)
    def _mk(self, a):
        async def cb(it):
            if str(it.user.id) != self.user_id:
                await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
            await it.response.edit_message(embed=build_land_zukan_embed(self.user_id, a), view=LandZukanView(self.user_id, a))
        return cb
    async def _back(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.zukan import build_category_embed, ZukanCategoryView
        await it.response.edit_message(embed=build_category_embed(self.user_id), view=ZukanCategoryView(self.user_id))


async def setup(bot):
    await bot.add_cog(Land(bot))
