import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
import asyncio
from datetime import datetime, timezone, timedelta
from cogs.embed_utils import pad_embed

db = Database()
JST = timezone(timedelta(hours=9))

active_slots: dict[str, dict] = {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 抽選ロジック（純粋関数・MC検証済み）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_machine_setting(machine_no: int) -> int:
    return get_daily_machines()[machine_no - 1]


def get_reel(reel_key: str) -> str:
    s = REELS.get(reel_key, REELS["blank"])
    return f"｜ {s[0]} ｜ {s[1]} ｜ {s[2]} ｜"


def _weighted_choice(weights: dict):
    r = random.random()
    acc = 0.0
    last = None
    for k, w in weights.items():
        acc += w
        last = k
        if r < acc:
            return k
    return last


def roll_normal_spin(setting: int) -> dict:
    """通常1回転：聖域GOD / レア役GOD / 小役 / ハズレ"""
    cfg = SLOT_SETTINGS[setting]
    if random.random() < 1 / cfg["premium_per"]:
        return {"type": "god", "premium": True, "yaku": None, "payout": 0}
    for key, pay, prob in SLOT_KOYAKU:
        if random.random() < prob:
            payout = int(pay * cfg["koyaku_mult"])
            if random.random() < GOD_TRIGGER_RATE.get(key, 0) * cfg["god_mult"]:
                return {"type": "god", "premium": False, "yaku": key, "payout": payout}
            return {"type": "koyaku", "yaku": key, "payout": payout}
    return {"type": "blank", "yaku": None, "payout": 0}


def make_god_state(premium: bool, yaku):
    if premium:
        return {"premium": True, "rank_idx": None, "rate": GOD_SINGULARITY["rate"],
                "total": 0, "sets": 0, "max_idx": None}
    grp = GOD_TRIGGER_GROUP.get(yaku, "soft")
    w = GOD_ENTRY_WEIGHTS[grp]
    r = random.random(); acc = 0; idx = len(w) - 1
    for i, x in enumerate(w):
        acc += x
        if r < acc:
            idx = i; break
    return {"premium": False, "rank_idx": idx, "rate": GOD_RANKS[idx]["rate"],
            "total": 0, "sets": 0, "max_idx": idx}


def _draw_up(up) -> int:
    r = random.random(); acc = 0
    for amt, pr in up:
        acc += pr
        if r < acc:
            return amt
    return up[-1][0]


def god_rank_info(g):
    return GOD_SINGULARITY if g["premium"] else GOD_RANKS[g["rank_idx"]]


def god_max_rank_info(g):
    return GOD_SINGULARITY if g["premium"] else GOD_RANKS[g["max_idx"]]


def god_play_set(g, up):
    payout = GOD_SET_BASE + _draw_up(up)
    g["total"] += payout
    g["sets"] += 1
    rankup_to = None
    rankup_yaku = None
    if not g["premium"] and g["rank_idx"] < len(GOD_RANKS) - 1:
        for key, p, upr, disp, emo in GOD_SET_KOYAKU:
            if random.random() < p:
                if random.random() < upr and g["rank_idx"] < len(GOD_RANKS) - 1:
                    g["rank_idx"] += 1
                    g["rate"] = GOD_RANKS[g["rank_idx"]]["rate"]
                    g["max_idx"] = g["rank_idx"]
                    rankup_to = GOD_RANKS[g["rank_idx"]]["key"]
                    rankup_yaku = (disp, emo)
                break
    continued = random.random() < g["rate"]
    return {"payout": payout, "continued": continued,
            "rankup_to": rankup_to, "rankup_yaku": rankup_yaku}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View 構築（状態ごとに別View・デコレータ方式）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_view(uid: str) -> discord.ui.View:
    g = active_slots.get(uid)
    state = g["state"] if g else "normal"
    if state == "route":
        return SlotRouteView(uid)
    if state == "aim":
        return SlotAimView(uid)
    return SlotGameView(uid)


async def render(interaction: discord.Interaction, uid: str, embed: discord.Embed):
    """現在の状態に応じたViewでメッセージを更新（環境差に強い確実な方式）"""
    view = build_view(uid)
    try:
        if interaction.response.is_done():
            # defer済み or 2回目以降の更新 → 元メッセージを直接編集
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            # 最初の更新 → コンポーネント応答で即編集
            await interaction.response.edit_message(embed=embed, view=view)
    except discord.HTTPException:
        # 念のためのフォールバック
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass


def _set_auto_label(view: discord.ui.View, uid: str):
    g = active_slots.get(uid)
    auto = g["auto"] if g else False
    for c in view.children:
        if getattr(c, "custom_id", None) == "slot_auto":
            c.label = "🕹️ 手動" if auto else "⏩ オート"


async def _toggle_auto(interaction: discord.Interaction, uid: str):
    """オートボタン共通処理"""
    g = active_slots.get(uid)
    if not g:
        await interaction.response.send_message("ゲームが見つかりません", ephemeral=True); return
    g["auto"] = not g["auto"]
    if g["auto"] and g["state"] in ("god", "aim", "route"):
        if g.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True); return
        g["spinning"] = True
        await interaction.response.defer()
        try:
            await _resolve_god_auto(interaction, uid)
        finally:
            gg = active_slots.get(uid)
            if gg:
                gg["spinning"] = False
        return
    # 通常時のトグル：ラベル更新して再描画
    view = build_view(uid)
    await interaction.response.edit_message(view=view)


# ── 台選択 ──
class SlotMachineButton(discord.ui.Button):
    def __init__(self, machine_no: int):
        super().__init__(label=f"{machine_no}番台", style=discord.ButtonStyle.primary,
                         row=(machine_no - 1) // 5)
        self.machine_no = machine_no

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        if uid in active_slots:
            await interaction.response.send_message("❌ すでにプレイ中です", ephemeral=True); return
        bal = db.get_balance(uid, guild_id)
        if bal < SLOT_BET:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True); return
        setting = get_machine_setting(self.machine_no)
        active_slots[uid] = {
            "machine": self.machine_no, "setting": setting, "guild_id": guild_id,
            "state": "normal", "auto": False, "god": None, "up": None,
            "pending": None, "spinning": False,
        }
        embed = discord.Embed(
            title=f"🎰 SLOT — {self.machine_no}番台",
            description=(f"**{SLOT_BET}コイン**掛け\n"
                         f"設定は回して確かめよう。\n"
                         f"☯️ **{GOD_ZONE_NAME}** を目指せ──"),
            color=discord.Color.dark_purple()
        )
        embed.add_field(name="残高", value=f"{bal:,} コイン", inline=True)
        embed.add_field(name="モード", value="🕹️ 手動", inline=True)
        await interaction.response.edit_message(embed=embed, view=SlotGameView(uid))


class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for i in range(1, 11):
            self.add_item(SlotMachineButton(i))

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())


# ── 通常/GOD進行用View（回す・オート・やめる）──
class SlotGameView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        _set_auto_label(self, user_id)

    @discord.ui.button(label="回す", style=discord.ButtonStyle.primary, emoji="🎰")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = self.user_id
        if str(interaction.user.id) != uid:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        g = active_slots.get(uid)
        if not g:
            await interaction.response.send_message("ゲームが見つかりません", ephemeral=True); return
        if g.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True); return
        g["spinning"] = True
        await interaction.response.defer()
        try:
            if g["state"] == "god":
                await _advance_god(interaction, uid)
            else:
                await _normal_spin(interaction, uid)
        finally:
            gg = active_slots.get(uid)
            if gg:
                gg["spinning"] = False

    @discord.ui.button(label="⏩ オート", style=discord.ButtonStyle.secondary, custom_id="slot_auto")
    async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        await _toggle_auto(interaction, self.user_id)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def quit_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        active_slots.pop(self.user_id, None)
        embed = discord.Embed(title="🚪 終了", description="またね！", color=discord.Color.dark_gray())
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        active_slots.pop(self.user_id, None)


# ── ルート選択用View（ORBIT・BIG BANG・オート）──
class SlotRouteView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        _set_auto_label(self, user_id)

    async def _choose(self, interaction, up):
        uid = self.user_id
        g = active_slots.get(uid)
        if not g or g["state"] != "route":
            await interaction.response.send_message("選択できません", ephemeral=True); return
        if g.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True); return
        g["spinning"] = True
        g["up"] = up
        g["state"] = "god"
        await interaction.response.defer()
        try:
            await _advance_god(interaction, uid)
        finally:
            gg = active_slots.get(uid)
            if gg:
                gg["spinning"] = False

    @discord.ui.button(label="🛰️ ORBIT", style=discord.ButtonStyle.primary)
    async def orbit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        await self._choose(interaction, GOD_UP_ORBIT)

    @discord.ui.button(label="💥 BIG BANG", style=discord.ButtonStyle.danger)
    async def bigbang(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        await self._choose(interaction, GOD_UP_BIGBANG)

    @discord.ui.button(label="⏩ オート", style=discord.ButtonStyle.secondary, custom_id="slot_auto")
    async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        await _toggle_auto(interaction, self.user_id)


# ── 「狙え」用View（狙え・オート）──
class SlotAimView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        _set_auto_label(self, user_id)
        # 狙えボタンのラベルをランク連動に
        g = active_slots.get(user_id)
        if g and g.get("god"):
            info = god_rank_info(g["god"])
            for c in self.children:
                if getattr(c, "custom_id", None) == "slot_aim":
                    c.label = GOD_AIM_LABELS.get(info["key"], "☯️ 狙え")

    @discord.ui.button(label="☯️ 狙え", style=discord.ButtonStyle.success, custom_id="slot_aim")
    async def aim(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = self.user_id
        if str(interaction.user.id) != uid:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        g = active_slots.get(uid)
        if not g or g["state"] != "aim":
            await interaction.response.send_message("いま狙えません", ephemeral=True); return
        if g.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True); return
        g["spinning"] = True
        await interaction.response.defer()
        try:
            await _reveal_aim(interaction, uid)
        finally:
            gg = active_slots.get(uid)
            if gg:
                gg["spinning"] = False

    @discord.ui.button(label="⏩ オート", style=discord.ButtonStyle.secondary, custom_id="slot_auto")
    async def auto(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        await _toggle_auto(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 進行ロジック（演出）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _normal_spin(interaction, uid):
    g = active_slots.get(uid)
    guild_id = g["guild_id"]
    bal = db.get_balance(uid, guild_id)
    if bal < SLOT_BET:
        await interaction.followup.send("❌ コインが足りません", ephemeral=True); return
    db.update_balance(uid, guild_id, -SLOT_BET)
    res = roll_normal_spin(g["setting"])

    # 聖域は専用突入へ直行
    if res["type"] == "god" and res["premium"]:
        if res["payout"]:
            db.update_balance(uid, guild_id, res["payout"])
        g["god"] = make_god_state(True, None)
        await _enter_holy(interaction, uid)
        return

    # 溜め演出
    wkey = "god" if res["type"] == "god" else (res.get("yaku") or "blank")
    weights = SLOT_EFFECT_WEIGHTS.get(wkey, SLOT_EFFECT_WEIGHTS["blank"])
    tier = _weighted_choice(weights)
    eff_text = random.choice(SLOT_EFFECTS[tier])
    wait = SLOT_WAIT["god"] if tier == "god_confirm" else SLOT_WAIT[tier]
    e1 = discord.Embed(description=eff_text,
                       color=discord.Color.from_rgb(80, 0, 140) if tier in ("hot", "superhot", "god_confirm")
                       else discord.Color.dark_gray())
    pad_embed(e1, target_fields=4)
    await render(interaction, uid, e1)
    await asyncio.sleep(wait)

    # 通常GOD突入
    if res["type"] == "god":
        if res["payout"]:
            db.update_balance(uid, guild_id, res["payout"])
        g["god"] = make_god_state(False, res["yaku"])
        await _enter_god(interaction, uid)
        return

    # 小役 / ハズレ
    payout = res.get("payout", 0)
    if payout > 0:
        db.update_balance(uid, guild_id, payout)
    new_bal = db.get_balance(uid, guild_id)
    reel_key = res["yaku"] if res["type"] == "koyaku" else "blank"
    labels = {"replay": "🔄 リプレイ", "bell": "🔔 ベル", "cherry": "🍒 チェリー",
              "suika": "🍉 スイカ！", "weak": "⭐ チャンス目", "schk": "🌠 強チャンス目！",
              "schy": "🍒 強チェリー！"}
    title = labels.get(res.get("yaku"), "　")
    e = discord.Embed(title=title, description=f"```\n{get_reel(reel_key)}\n```",
                      color=discord.Color.blue() if payout else discord.Color.dark_gray())
    if payout:
        e.add_field(name="獲得", value=f"+{payout:,} コイン", inline=True)
    e.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)
    pad_embed(e, target_fields=4)
    await render(interaction, uid, e)


async def _enter_god(interaction, uid):
    g = active_slots.get(uid)
    emo, l1, l2 = random.choice(GOD_ENTRY_EFFECTS)
    e = discord.Embed(title=f"{emo} {l1}",
                      description=f"```\n{get_reel('entry')}\n```\n{l2}",
                      color=discord.Color.from_rgb(120, 0, 200))
    pad_embed(e, target_fields=3)
    await render(interaction, uid, e)
    await asyncio.sleep(SLOT_WAIT["god"])

    if g["auto"]:
        g["up"] = GOD_UP_BALANCED
        g["state"] = "god"
        await _resolve_god_auto(interaction, uid)
    else:
        g["state"] = "route"
        e2 = discord.Embed(
            title="🧭 ROUTE SELECT",
            description=("打ち方を選べ。\n\n"
                         "🛰️ **ORBIT（軌道）** … コツコツ安定して伸ばす\n"
                         "💥 **BIG BANG（爆発）** … 一撃に全振り、荒く跳ねる\n\n"
                         "*期待値は同じ。変わるのは波の荒さだけ。*"),
            color=discord.Color.from_rgb(120, 0, 200))
        pad_embed(e2, target_fields=3)
        await render(interaction, uid, e2)


async def _enter_holy(interaction, uid):
    g = active_slots.get(uid)
    for i, (emo, l1, l2) in enumerate(GOD_HOLY_BEATS, start=1):
        if i == 1:
            title = emo
            desc = f"```\n{get_reel('dark')}\n```\n{l2}"
        elif i == 3:
            title = f"{emo}　{l1}"
            desc = f"```\n{get_reel('singularity')}\n```\n{l2}"
        else:
            title = f"{emo} {l1}"
            desc = l2
        e = discord.Embed(title=title, description=desc,
                          color=discord.Color.from_rgb(255, 215, 0) if i == 3
                          else discord.Color.from_rgb(20, 0, 40))
        pad_embed(e, target_fields=3)
        await render(interaction, uid, e)
        await asyncio.sleep(SLOT_WAIT[f"holy_{i}"])

    g["up"] = GOD_UP_BALANCED
    g["state"] = "god"
    if g["auto"]:
        await _resolve_god_auto(interaction, uid)
    else:
        await _advance_god(interaction, uid)


def _aim_wait(g):
    info = god_rank_info(g)
    if info["key"] == "singularity":
        return SLOT_WAIT["aim_singularity"]
    if info["key"] == "pulsar":
        return SLOT_WAIT["aim_pulsar"]
    return SLOT_WAIT["aim"]


async def _advance_god(interaction, uid):
    g = active_slots.get(uid)
    if g["auto"]:
        await _resolve_god_auto(interaction, uid); return
    r = god_play_set(g["god"], g["up"])
    db.update_balance(uid, g["guild_id"], r["payout"])
    g["pending"] = r

    info = god_rank_info(g["god"])
    desc = f"```\n{get_reel(info['key'])}\n```"
    if r["rankup_to"]:
        emo, txt = GOD_RANKUP_EFFECTS.get(r["rankup_to"], ("📈", "RANK UP"))
        yaku_disp, yaku_emo = r["rankup_yaku"]
        desc += f"\n{yaku_emo} {yaku_disp}！\n📈 **{emo} {txt}！！**"
    e = discord.Embed(title=f"{info['emoji']} {info['name']}", description=desc,
                      color=discord.Color.from_rgb(150, 60, 220))
    e.add_field(name="今回", value=f"+{r['payout']:,}", inline=True)
    e.add_field(name="セット", value=f"{g['god']['sets']}", inline=True)
    e.add_field(name="累計", value=f"{g['god']['total']:,} コイン", inline=True)
    e.set_footer(text=f"{GOD_AIM_LABELS.get(info['key'], '☯️ 狙え')} ── 継続を掴め")
    pad_embed(e, target_fields=4)
    g["state"] = "aim"
    await render(interaction, uid, e)
    if r["rankup_to"]:
        await asyncio.sleep(SLOT_WAIT["rankup"])


async def _reveal_aim(interaction, uid):
    g = active_slots.get(uid)
    r = g.get("pending") or {}
    continued = r.get("continued", False)
    feint = random.random() < GOD_FEINT_RATE

    if feint:
        emo, txt = GOD_FEINT_INTRO
        e0 = discord.Embed(title=emo, description=txt, color=discord.Color.dark_gray())
        pad_embed(e0, target_fields=3)
        await render(interaction, uid, e0)
        await asyncio.sleep(SLOT_WAIT["feint"])
    else:
        await asyncio.sleep(_aim_wait(g["god"]))

    if continued:
        g["state"] = "god"
        new_bal = db.get_balance(uid, g["guild_id"])
        info = god_rank_info(g["god"])
        if feint:
            emo, txt = GOD_FEINT_CONTINUE
            title, sub, color = txt, "", discord.Color.gold()
        else:
            kind = _weighted_choice({c[0]: c[1] for c in GOD_CONTINUE_EFFECTS})
            cut = next(c for c in GOD_CONTINUE_EFFECTS if c[0] == kind)
            title, sub = cut[2], cut[3]
            color = discord.Color.from_rgb(255, 0, 90) if kind == "rainbow" else discord.Color.gold()
        e = discord.Embed(title=title,
                          description=f"```\n{get_reel(info['key'])}\n```" + (f"\n{sub}" if sub else ""),
                          color=color)
        e.add_field(name="ランク", value=f"{info['emoji']} **{info['name']}**", inline=True)
        e.add_field(name="セット", value=f"{g['god']['sets']}", inline=True)
        e.add_field(name="累計", value=f"{g['god']['total']:,} コイン", inline=True)
        e.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
        pad_embed(e, target_fields=5)
        await render(interaction, uid, e)
    else:
        await _finish_god(interaction, uid, feint=feint)


async def _resolve_god_auto(interaction, uid):
    g = active_slots.get(uid)
    if g.get("up") is None:
        g["up"] = GOD_UP_BALANCED
    pend = g.pop("pending", None)
    if pend is not None and pend.get("continued") is False:
        await _finish_god(interaction, uid); return
    while True:
        r = god_play_set(g["god"], g["up"])
        db.update_balance(uid, g["guild_id"], r["payout"])
        if not r["continued"]:
            break
    await _finish_god(interaction, uid)


async def _finish_god(interaction, uid, feint=False):
    g = active_slots.get(uid)
    new_bal = db.get_balance(uid, g["guild_id"])
    god = g["god"]
    mx = god_max_rank_info(god)
    total, sets, premium = god["total"], god["sets"], god["premium"]

    if not g["auto"]:
        if feint:
            emo, txt = GOD_FEINT_END
        else:
            emo, txt = random.choice(GOD_END_EFFECTS)
        e0 = discord.Embed(title=emo, description=txt, color=discord.Color.dark_gray())
        pad_embed(e0, target_fields=3)
        await render(interaction, uid, e0)
        await asyncio.sleep(1.0)

    if premium:
        finish_line = GOD_FINISH_HOLY
        color = discord.Color.from_rgb(255, 215, 0)
        head = "🌌 SINGULARITY 制覇 🌌"
    else:
        finish_line = next(line for thr, line in GOD_FINISH_LINES if total >= thr)
        if total >= 30000:
            color = discord.Color.from_rgb(255, 180, 0)
        elif total >= 10000:
            color = discord.Color.orange()
        else:
            color = discord.Color.dark_teal()
        head = f"☄️ {GOD_ZONE_NAME} 終了"

    e = discord.Embed(title=head, description=finish_line, color=color)
    e.add_field(name="到達ランク", value=f"{mx['emoji']} **{mx['name']}**", inline=True)
    e.add_field(name="セット数", value=f"{sets}", inline=True)
    e.add_field(name="💰 一撃合計", value=f"**{total:,}** コイン", inline=False)
    e.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
    pad_embed(e, target_fields=5)

    g["state"] = "normal"
    g["god"] = None
    g["up"] = None
    g["pending"] = None
    await render(interaction, uid, e)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Slot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slot", description="スロット — EVENT HORIZONを目指せ")
    async def slot(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        # 古い(固まった)セッションが残っていれば自動クリアして必ず始められるように
        active_slots.pop(uid, None)
        embed = discord.Embed(
            title="🎰 SLOT — 台選択",
            description=f"**{SLOT_BET}コイン**掛け\n1〜10番台から選んでください！",
            color=discord.Color.dark_purple()
        )
        await interaction.response.send_message(embed=embed, view=SlotSelectView())


async def setup(bot):
    await bot.add_cog(Slot(bot))
