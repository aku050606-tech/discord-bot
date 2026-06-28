"""
🛤️ 街道（陸の冒険）── 海の白兵戦エンジンを流用したレベル上げの場
探索 → 敵(白兵戦)/陸ストーリー/採取/平穏。
・HPは持ち越し（毎戦は回復しない）。タウンに戻れば全快、道中は🍖食料で回復。
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

def _heal_full(uid):
    """タウン帰還で全快。"""
    vp = db.get_voyage(uid)
    vp["cur_hp"] = max_hp(vp)
    db.save_voyage(uid, vp)


# ━━━ 探索の収穫トラッキング（死亡で50%失う対象） ━━━
import math

def _run(vp):
    """今回の探索セッションの収穫（コイン＋装備ドロップ）。"""
    return vp.setdefault("land_run", {"coin": 0, "drops": []})

def _run_add_coin(vp, amount):
    _run(vp)["coin"] += int(amount)

def _run_add_drop(uid, vp, area, spec=None):
    """装備ドロップ抽選（当たれば付与＆収穫に記録）。戻り＝表示名 or None。
    中レアは spec['drop_table'] を使う／雑魚は LAND_EQUIP_DROP（0.1%）。"""
    table = (spec or {}).get("drop_table") or L.LAND_EQUIP_DROP.get(area, [])
    for star, rate in table:
        if random.random() < rate:
            part, ikey, label = _pick_equip(star)
            if not ikey:
                return None
            vp.setdefault("inventory", {}).setdefault(part, []).append({"item": ikey, "skills": []})
            db.add_zukan(uid, "equip_seen", ikey)
            _run(vp)["drops"].append({"part": part, "item": ikey, "label": label})
            return f"{label}（★{star}）"
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
    rows = []
    for area, a in L.LAND_AREAS.items():
        if vp["level"] >= a["req_lv"]:
            rows.append(f"{a['emoji']} **{a['name']}**（Lv{a['req_lv']}〜）")
        else:
            rows.append(f"🔒 {a['emoji']} {a['name']}（Lv{a['req_lv']}で解放）")
    e.add_field(name="🗺️ 行き先", value="\n".join(rows), inline=False)
    e.set_footer(text="HPは持ち越し。タウンに戻れば全快／道中は🍖食料で回復")
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
    """陸→タウン：収穫を確定（コイン入金）→全快→タウンへ。"""
    vp = db.get_voyage(uid)
    _run_settle_town(uid, str(interaction.guild.id), vp)
    vp["cur_hp"] = max_hp(vp)
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


# ━━━ エリア内（探索ループ）━━━
class LandAreaView(discord.ui.View):
    def __init__(self, uid, gid, area):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area
        self.add_item(_ExploreBtn())
        self.add_item(_ChangeBtn())
        self.add_item(_TownBtn())
        if _has_food(uid):
            self.add_item(LandFoodSelect(uid, gid, area, LandAreaView))

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    async def _play_and_resolve(self, interaction):
        """先にイベント種別を決めて、その種類に合う演出を固定枠で見せてから結果へ。"""
        kind = L.land_encounter_pick(self.area)
        spec = None
        ev = None
        theater = kind
        if kind == "combat":
            spec = L.make_land_enemy(self.area)
            if spec.get("is_rare"):
                theater = "rare"
            elif spec.get("is_midrare"):
                theater = "midrare"
            else:
                theater = "combat"
        elif kind == "story":
            ev = L.pick_story(self.area); theater = "story"
        elif kind == "event":
            ev = L.pick_event(self.area); theater = "event"
        elif kind == "gather":
            theater = "gather"
        else:
            theater = "calm"

        vp = db.get_voyage(self.uid)
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
        if kind == "combat":
            await self._start_combat(interaction, vp, spec=spec)
        elif kind == "story":
            await self._show_narrative(interaction, vp, ev or L.pick_story(self.area))
        elif kind == "event":
            await self._show_narrative(interaction, vp, ev or L.pick_event(self.area))
        elif kind == "gather":
            coin = random.randint(*L.LAND_GATHER_COIN[self.area])
            _run_add_coin(vp, coin); db.save_voyage(self.uid, vp)
            flav = random.choice(L.LAND_GATHER[self.area])
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, f"## 🌿 採取\n{flav}\n**💰 +{coin:,}**", LAND_COL_GATHER),
                view=LandResultView(self.uid, self.gid, self.area))
        else:  # calm
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, _pad_note(random.choice(L.LAND_CALM), 5), LAND_COL_CALM),
                view=LandResultView(self.uid, self.gid, self.area))

    async def _start_combat(self, interaction, vp, spec=None):
        spec = spec or L.make_land_enemy(self.area)
        if spec.get("key"):
            db.add_zukan(self.uid, "enemy_seen", spec["key"])   # 📖 図鑑：遭遇を記録
        if spec.get("is_rare"):
            # ✨ 激レア＝戦闘前に「挑む／見送る」を選べる（基本は見送り推奨の強敵）
            intro = spec.get("rare_intro") or "見慣れない“なにか”が、行く手に立っている。"
            st = "★" * int(spec.get("stars", 4))
            note = (f"## ✨ {spec['emoji']} {spec['name']} {st}\n\n{intro}\n\n"
                    f"⚠️ **見るからに強い。生半可な装備では、まず勝てない。**")
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, note, LAND_COL_EVENT),
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
        col = LAND_COL_EVENT if ev.get("id", "").startswith("e_") else LAND_COL_STORY
        if ev["type"] == "choice":
            await interaction.edit_original_response(
                embed=build_area_embed(vp, self.area, head + ev["flavor"], col),
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
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, _pad_note(f"## {random.choice(LAND_WAITS)}", 5), LAND_COL_NORMAL),
            view=LandTheaterView(view.uid, view.gid, view.area))
        await asyncio.sleep(0.45)
        await view._play_and_resolve(interaction)

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
    st = "★" * int(spec.get("stars", 1))
    emb = build_combat_embed(state)
    if spec.get("is_rare"):
        emb.description = f"✨ **{spec['emoji']} {spec['name']}** {st} との戦い！"
    elif spec.get("is_midrare"):
        emb.description = f"🔸 **{spec['emoji']} {spec['name']}** {st} ── 強そうな個体だ！"
    else:
        emb.description = f"{spec['emoji']} **{spec['name']}** {st} が現れた！"
    view = CombatView(uid, gid, state,
                      on_end=land_on_end(uid, gid, area, spec),
                      flee_cb=_land_flee_cb(uid, gid, area))
    return emb, view


async def do_land_fight(interaction, uid, gid, area, spec):
    """フレッシュなインタラクションから戦闘へ（激レアの『挑む』用）。"""
    emb, view = _build_fight(uid, gid, area, spec)
    await interaction.response.edit_message(embed=emb, view=view)


def _land_flee_cb(uid, gid, area):
    """戦闘中の🏳️撤退：陸は確実に逃げられる（HPはそのまま持ち越し）。"""
    async def _flee(it, state):
        vp = db.get_voyage(uid)
        vp["cur_hp"] = max(1, state["ally"]["hp"])  # 逃げてもHPは戦闘時点のまま
        db.save_voyage(uid, vp)
        await it.response.edit_message(
            embed=build_area_embed(vp, area, "🏳️ 隙を突いて、その場を離脱した。"),
            view=LandResultView(uid, gid, area))
    return _flee


class RareEncounterView(discord.ui.View):
    """✨ 激レア遭遇：挑む／見送る（確実に逃げられる）。"""
    def __init__(self, uid, gid, area, spec):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.spec = spec
        self.add_item(_RareFightBtn())
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

class _RareFleeBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏃 見送る", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction):
        view: RareEncounterView = self.view
        vp = db.get_voyage(view.uid)
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, "🏃 関わらないのが賢明だ。そっと、その場を離れた。"),
            view=LandResultView(view.uid, view.gid, view.area))


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
        lines = [f"## {view.ev['emoji']} {view.ev['title']}", "", ch["result"]]
        if ch.get("coin"):
            coin = random.randint(*ch["coin"])
            _run_add_coin(vp, coin)
            lines.append(f"## 💰 +{coin:,}")
        if ch.get("xp"):
            xp = random.randint(*ch["xp"])
            leveled = add_xp(vp, xp)
            lines.append(f"## ✨ XP +{xp}")
            if leveled:
                lines.append(f"## 🎉 レベルアップ！ → Lv{vp['level']}")
        if ch.get("heal"):
            mh = max_hp(vp); cur = _cur_hp(vp)
            heal = int(mh * ch["heal"]); before = cur
            vp["cur_hp"] = min(mh, cur + heal)
            lines.append(f"## ❤️ HP +{vp['cur_hp']-before}（{vp['cur_hp']}/{mh}）")
        if ch.get("dmg"):
            mh = max_hp(vp); cur = _cur_hp(vp)
            vp["cur_hp"] = max(1, cur - int(ch["dmg"]))
            lines.append(f"## 💢 -{cur-vp['cur_hp']}（{vp['cur_hp']}/{mh}）")
        if ch.get("food"):
            fid = ch["food"]
            if fid in V.FOODS:
                vp.setdefault("foods", {}); vp["foods"][fid] = vp["foods"].get(fid, 0) + 1
                db.add_zukan(view.uid, "item_seen", fid)
                lines.append(f"## 🍖 {V.FOODS[fid]['name']} を手に入れた！")
        db.save_voyage(view.uid, vp)
        col = LAND_COL_EVENT if view.ev.get("id", "").startswith("e_") else LAND_COL_STORY
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
        if state["result"] == "win":
            # 📖 図鑑（討伐の証）
            if spec.get("key"):
                db.add_zukan(uid, "enemy_kill", spec["key"])
            if spec.get("is_rare"):
                xp = random.randint(*(spec.get("rare_xp") or a["xp"]))
                coin = random.randint(*(spec.get("rare_coin") or a["coin"]))
            elif spec.get("is_midrare"):
                xp = random.randint(*(spec.get("mid_xp") or a["xp"]))
                coin = random.randint(*(spec.get("mid_coin") or a["coin"]))
            else:
                xp = random.randint(*a["xp"]); coin = random.randint(*a["coin"])
            leveled = add_xp(vp, xp)
            _run_add_coin(vp, coin)                 # 💰 収穫に貯める（タウン帰還で確定／死ぬと半分失う）
            drop = _run_add_drop(uid, vp, area, spec)   # 🎁 装備ドロップ（中レアは高確率）
            db.save_voyage(uid, vp)
            if spec.get("is_rare"):
                head = f"## ✨🏆 レアな {spec['emoji']} {spec['name']} を討ち取った！"
            elif spec.get("is_midrare"):
                head = f"## 🔸🏆 {spec['emoji']} {spec['name']} を討ち取った！"
            else:
                head = f"## 🏆 {spec['emoji']} {spec['name']} を倒した！"
            lines = [head, f"**✨ XP +{xp}　💰 +{coin:,}**"]
            if leveled:
                lines.append(f"## 🎉 レベルアップ！ → Lv{vp['level']}")
            if drop:
                lines.append(f"## 🎁 {drop} を手に入れた！")
            if spec.get("is_rare") and spec.get("rare_story"):
                lines.append("")
                lines.append(f"> {spec['rare_story']}")
            emb.description = "\n".join(lines)
            view = LandResultView(uid, gid, area)
        else:
            xp = max(2, a_lose_xp(area)); add_xp(vp, xp)
            vp["cur_hp"] = max(1, max_hp(vp) // 4)   # 帰宅後の残HP（家マークや食料で立て直す）
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
        await interaction.response.edit_message(
            embed=build_area_embed(vp, view.area, _pad_note(f"## {random.choice(LAND_WAITS)}", 5), LAND_COL_NORMAL),
            view=LandTheaterView(view.uid, view.gid, view.area))
        await asyncio.sleep(0.45)
        av = LandAreaView(view.uid, view.gid, view.area)
        await av._play_and_resolve(interaction)


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
    cat += [(f"land{area}_{e['name']}", e, "rare") for e in L.LAND_RARES.get(area, [])]
    total = len(cat)
    seen_n = len([1 for k, _, _ in cat if k in seen])
    kill_n = len([1 for k, _, _ in cat if k in killed])
    emb = discord.Embed(
        title=f"📖 街道図鑑 — {a['emoji']} {a['name']}",
        description=f"遭遇 **{seen_n}/{total}** ・ 討伐 **{kill_n}/{total}**\n（★は強さ。🔸中レア／✨レア＝ボス級）",
        color=LAND_ZUKAN_COLOR.get(area, 0x4f9d69))
    by_star = {}
    for k, e, kind in cat:
        star = int(e.get("stars", 1))
        if k in seen:
            mark = " ⚔️**討伐済**" if k in killed else ""
            pre = {"mid": "🔸", "rare": "✨"}.get(kind, "")
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
