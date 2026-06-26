import discord
from discord.ext import commands
import random
import asyncio
import uuid
from database import Database
from config import (
    JUGGLER_BET, JUGGLER_KOYAKU, JUGGLER_BIG_NET, JUGGLER_REG_NET,
    JUGGLER_HYPER_NET, JUGGLER_BONUS, JUGGLER_PREEMPTIVE_RATE, get_juggler_setting,
    JUGGLER_WAIT, JUGGLER_PEKA_PRE, JUGGLER_PEKA_POST,
    JUGGLER_BIG_REVEAL, JUGGLER_REG_REVEAL, JUGGLER_HYPER_REVEAL, JUGGLER_MISS_LINES,
    SLOT_BET,
)
from cogs.embed_utils import pad_embed
from quest_tracker import record as quest_record

db = Database()

# ジャグラーのセッション（GRAVITASの active_slots とは別管理）
active_jug: dict[str, dict] = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NATOランプ演出（GitHub raw のGIFをembed画像で表示）
#   毎回URL末尾に ?v=ユニーク を付け、Discordにアニメを頭から再生させる
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LAMP_BASE = "https://raw.githubusercontent.com/aku050606-tech/discord-bot/main/assets/"
LAMP_FILES = {
    "off":     "nato_off.gif",
    "blue":    "nato_on_blue.gif",
    "fast":    "nato_on_fast.gif",
    "slow":    "nato_on_slow.gif",
    "rainbow": "nato_on_rainbow.gif",
}
# ランプ再生に合わせた待ち時間（点灯しきる＝ボタン復活まで）
# 点灯(青/先ペカ/虹)・ハズレは統一。遅れだけ長め(3秒)。
LAMP_WAIT = {
    "off":     2.2,
    "blue":    2.2,
    "fast":    2.2,
    "slow":    3.4,   # 遅れ＝暗い溜め3秒ぶん長い
    "rainbow": 2.2,
}


def _lamp_url(kind: str) -> str:
    return f"{LAMP_BASE}{LAMP_FILES[kind]}?v={uuid.uuid4().hex[:8]}"


# BIGのうちプレミア（特別な光り方）が出る割合。プレミア＝BIG確定演出。
JUGGLER_PREMIUM_RATE = 0.5
JUGGLER_PREMIUM_LAMPS = ["fast", "slow", "rainbow"]


def _lamp_kind(bonus) -> str:
    """抽選結果→ランプの光り方。
      ハズレ=off / REG=blue（常に青）
      BIG=基本blue、JUGGLER_PREMIUM_RATEでプレミア(fast/slow/rainbow)＝BIG確定演出"""
    if not bonus:
        return "off"
    if bonus == "hyper":
        return "rainbow"
    if bonus == "big" and random.random() < JUGGLER_PREMIUM_RATE:
        return random.choice(JUGGLER_PREMIUM_LAMPS)
    return "blue"


def _alive(uid: str, sid: str):
    """演出sleepをまたいでセッション同一性を確認。再起動/作り直し/時間切れなら None。"""
    g = active_jug.get(uid)
    return g if (g is not None and g.get("sid") == sid) else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 抽選（純粋ロジック・MC検証済み）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def roll_juggler(setting) -> dict:
    """1ゲーム抽選：ボーナス(BIG/REG)と子役を独立に引く。
    返り値: {bonus: None/'big'/'reg', koyaku: key/None, payout: 子役払い}"""
    b = JUGGLER_BONUS[setting]
    r = random.random()
    # ハイパー → BIG → REG → ハズレ の順で抜く（プレミアを最優先で確定）
    if r < b["hyper"]:
        bonus = "hyper"
    elif r < b["hyper"] + b["big"]:
        bonus = "big"
    elif r < b["hyper"] + b["big"] + b["reg"]:
        bonus = "reg"
    else:
        bonus = None

    # 子役（順送り・最初に当たった1役）
    rk = random.random(); acc = 0.0
    koyaku = None; payout = 0
    for key, prob, pay, disp, reel in JUGGLER_KOYAKU:
        acc += prob
        if rk < acc:
            koyaku = key; payout = pay
            break
    return {"bonus": bonus, "koyaku": koyaku, "payout": payout}


def _koyaku_info(key):
    for k, prob, pay, disp, reel in JUGGLER_KOYAKU:
        if k == key:
            return disp, reel
    return "　", ("　", "　", "　")


def _reel_str(reel) -> str:
    return f"｜ {reel[0]} ｜ {reel[1]} ｜ {reel[2]} ｜"


def _miss_reel() -> str:
    # 左リールに🍒が止まれば必ず「左チェリー成立」＝ハズレにしてはいけない。
    # よってハズレ目の左リールはチェリー以外から引く（チェリーは中・右にのみ出る）。
    left_pool  = ["🔔", "🍇", "🃏", "7️⃣", "🅱️", "🔄"]
    other_pool = ["🍒", "🔔", "🍇", "🃏", "7️⃣", "🅱️", "🔄"]
    a = random.choice(left_pool)
    b, c = random.sample([s for s in other_pool if s != a], 2)
    return f"｜ {a} ｜ {b} ｜ {c} ｜"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 描画ヘルパ（GRAVITAS render と同じ作法）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def render(interaction, uid, embed, buttons=True):
    view = JugglerGameView(uid) if buttons else discord.ui.View(timeout=1)
    msg = None
    try:
        if interaction.response.is_done():
            msg = await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
            msg = interaction.message
    except discord.HTTPException:
        try:
            msg = await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            msg = None
    try:
        if buttons and msg is not None:
            view.message = msg
    except Exception:
        pass


async def _ensure_buttons(interaction, uid):
    """演出の最後に必ず呼ぶ。何があってもボタンを復活させ固まらせない。"""
    try:
        if active_jug.get(uid):
            await interaction.edit_original_response(view=JugglerGameView(uid))
        else:
            e = discord.Embed(title="⌛ プレイ終了",
                              description="このプレイは終了しています。下のボタンか機種選択から再開できます。",
                              color=discord.Color.dark_gray())
            await interaction.edit_original_response(embed=e, view=_RecoverView())
    except Exception:
        try:
            await interaction.followup.send("⚠️ 表示の更新に失敗しました。もう一度お試しください。", ephemeral=True)
        except Exception:
            pass


async def _expire(interaction, view):
    for c in getattr(view, "children", []):
        try: c.disabled = True
        except Exception: pass
    e = discord.Embed(title="⌛ セッション終了",
                      description="再起動か時間切れで終了しています。機種選択から始めてください。",
                      color=discord.Color.dark_gray())
    try:
        await interaction.response.edit_message(embed=e, view=view)
    except discord.HTTPException:
        try:
            await interaction.response.send_message("セッションが切れました。もう一度始めてください。", ephemeral=True)
        except Exception:
            pass


def _handle_timeout_cleanup(view):
    active_jug.pop(getattr(view, "user_id", None), None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 機種選択（スロットのトップ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_kishu_embed() -> discord.Embed:
    E = "\u001b"
    G = f"{E}[1;33m"   # ゴールド
    P = f"{E}[1;35m"   # 紫（神々しさ）
    Y = f"{E}[1;33m"   # 黄
    W = f"{E}[1;37m"   # 白
    K = f"{E}[1;30m"   # グレー
    X = f"{E}[0m"
    desc = (
        "```ansi\n"
        f"{G}╔══════════════════════════════╗{X}\n"
        f"{W}        1 回　{SLOT_BET} ナトコイン{X}\n"
        f"{G}╚══════════════════════════════╝{X}\n"
        "\n"
        f"{P}🌌 ＧＲＡＶＩＴＡＳ   {K}［ AT機 ］{X}\n"
        f"{W}   GRAVITAS GAME の継続ループで一撃を狙う{X}\n"
        "\n"
        f"{Y}🃏 ジャグラー        {K}［ ノーマル機 ］{X}\n"
        f"{W}   GOGOランプを光らせ、コツコツ積む{X}\n"
        "\n"
        f"{G}━━━━━━━━━━━━━━━━━━━━━━━━━━━━{X}\n"
        f"{K}      さあ、今日の一台を選べ{X}\n"
        "```"
    )
    return discord.Embed(
        title="🎰　Ｓ Ｌ Ｏ Ｔ　Ｃ Ｏ Ｒ Ｎ Ｅ Ｒ",
        description=desc,
        color=0xD4AF37,  # ゴールド
    )


class KishuSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🌌 GRAVITAS（AT機）", style=discord.ButtonStyle.primary, row=0)
    async def gravitas(self, interaction, button):
        from cogs.slot import active_slots, SlotSelectView, build_select_embed
        active_slots.pop(str(interaction.user.id), None)
        await interaction.response.edit_message(embed=build_select_embed(), view=SlotSelectView())

    @discord.ui.button(label="🃏 ジャグラー（ノーマル機）", style=discord.ButtonStyle.success, row=0)
    async def juggler(self, interaction, button):
        active_jug.pop(str(interaction.user.id), None)
        await interaction.response.edit_message(embed=build_jug_select_embed(), view=JugglerSelectView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction, button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(
            embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(str(interaction.user.id), str(interaction.guild.id)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ジャグラー台選択
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_jug_select_embed() -> discord.Embed:
    return discord.Embed(
        title="🃏 ジャグラー — 台選択",
        description=f"**{JUGGLER_BET}ナトコイン**掛け\n1〜5番台から選んでください！\nGOGOランプを光らせろ💡",
        color=discord.Color.gold(),
    )


class JugglerMachineButton(discord.ui.Button):
    def __init__(self, machine_no: int):
        super().__init__(label=f"{machine_no}番台", style=discord.ButtonStyle.primary,
                         row=(machine_no - 1) // 5)
        self.machine_no = machine_no

    async def callback(self, interaction):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        if uid in active_jug:
            await interaction.response.send_message("❌ すでにプレイ中です", ephemeral=True); return
        bal = db.get_balance(uid, guild_id)
        if bal < JUGGLER_BET:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True); return
        setting = get_juggler_setting(self.machine_no)
        active_jug[uid] = {
            "machine": self.machine_no, "setting": setting, "guild_id": guild_id,
            "spinning": False, "sid": uuid.uuid4().hex,
        }
        embed = discord.Embed(
            title=f"🃏 ジャグラー — {self.machine_no}番台",
            description=(f"**{JUGGLER_BET}ナトコイン**掛け\n"
                         f"設定は回して確かめよう。\n"
                         f"💡 GOGOランプを光らせろ──"),
            color=discord.Color.gold(),
        )
        embed.add_field(name="残高", value=f"{bal:,} ナトコイン", inline=True)
        pad_embed(embed, target_fields=3)
        await interaction.response.edit_message(embed=embed, view=JugglerGameView(uid))


class JugglerSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(1, 6):
            self.add_item(JugglerMachineButton(i))

    @discord.ui.button(label="◀ 機種選択へ", style=discord.ButtonStyle.secondary, row=1)
    async def to_kishu(self, interaction, button):
        await interaction.response.edit_message(embed=build_kishu_embed(), view=KishuSelectView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction, button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(
            embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(str(interaction.user.id), str(interaction.guild.id)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# プレイ用View（回す・台選択・メニュー）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class JugglerGameView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="回す", style=discord.ButtonStyle.primary, emoji="🎰")
    async def spin(self, interaction, button):
        uid = self.user_id
        if str(interaction.user.id) != uid:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        g = active_jug.get(uid)
        if not g:
            await _expire(interaction, self); return
        if g.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True); return
        bal = db.get_balance(uid, g["guild_id"])
        if bal < JUGGLER_BET:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True); return
        g["spinning"] = True
        await interaction.response.defer()
        try:
            await _play_spin(interaction, uid)
        finally:
            gg = active_jug.get(uid)
            if gg:
                gg["spinning"] = False
            await _ensure_buttons(interaction, uid)

    @discord.ui.button(label="🃏 台選択に戻る", style=discord.ButtonStyle.secondary, row=1)
    async def to_select(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        active_jug.pop(self.user_id, None)
        await interaction.response.edit_message(embed=build_jug_select_embed(), view=JugglerSelectView())

    @discord.ui.button(label="🏠 メニューに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def to_menu(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True); return
        active_jug.pop(self.user_id, None)
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(
            embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(str(interaction.user.id), str(interaction.guild.id)))


class _RecoverView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🃏 台選択へ", style=discord.ButtonStyle.primary)
    async def again(self, interaction, button):
        active_jug.pop(str(interaction.user.id), None)
        await interaction.response.edit_message(embed=build_jug_select_embed(), view=JugglerSelectView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def home(self, interaction, button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(
            embed=build_menu_embed(interaction.user, str(interaction.guild.id)), view=MainMenuView(str(interaction.user.id), str(interaction.guild.id)))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 進行（演出）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _play_spin(interaction, uid):
    g = active_jug.get(uid)
    if not g:
        return
    sid = g["sid"]
    guild_id = g["guild_id"]

    # ベット消費 → 抽選 → 払い出しは先に確定（途中で落ちても保全）
    db.update_balance(uid, guild_id, -JUGGLER_BET)
    quest_record(uid, guild_id, "slot")
    res = roll_juggler(g["setting"])
    if res["payout"]:
        db.update_balance(uid, guild_id, res["payout"])

    bonus = res["bonus"]
    lamp = _lamp_kind(bonus)

    # リール表示（子役/ハズレ）＋ ランプGIFを画像で
    if res["koyaku"]:
        disp, reel = _koyaku_info(res["koyaku"])
        reel_str = _reel_str(reel)
        title = f"🎰 {disp}"
    else:
        reel_str = _miss_reel()
        title = "🎰 …"

    new_bal = db.get_balance(uid, guild_id)
    e = discord.Embed(title=title, description=f"```\n{reel_str}\n```",
                      color=discord.Color.from_rgb(255, 200, 0) if bonus else discord.Color.dark_gray())
    if res["payout"]:
        e.add_field(name="獲得", value=f"+{res['payout']:,} ナトコイン", inline=True)
    e.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
    e.set_image(url=_lamp_url(lamp))   # ← ここでランプGIFが暗→点灯（or 暗いまま）
    pad_embed(e, target_fields=3)

    # ランプが点灯しきる（or 暗いまま終わる）まで、ボタンを出さずに待つ＝連打防止
    await render(interaction, uid, e, buttons=False)
    await asyncio.sleep(LAMP_WAIT[lamp])
    if _alive(uid, sid) is None:
        return

    # 当たりなら BIG/REG 開示へ。ハズレならここで確定（ボタン復活）
    if bonus:
        await _reveal_bonus(interaction, uid, bonus, lamp)
        return

    if not res["payout"]:
        e.description += f"\n{random.choice(JUGGLER_MISS_LINES)}"
        pad_embed(e, target_fields=3)
    await render(interaction, uid, e)


async def _reveal_bonus(interaction, uid, bonus, lamp="blue"):
    """ペカリ後、BIG/REGを後出し開示して純増を付与する。"""
    g = active_jug.get(uid)
    if not g:
        return
    sid = g["sid"]
    guild_id = g["guild_id"]
    lit_url = _lamp_url(lamp)   # 点灯したランプを開示中も表示

    # 種別を伏せたタメ
    e = discord.Embed(title="💡 GOGO!! ", description="**BIG**か **REG**か……！",
                      color=discord.Color.from_rgb(255, 170, 0))
    e.set_image(url=lit_url)
    pad_embed(e, target_fields=3)
    await render(interaction, uid, e, buttons=False)
    await asyncio.sleep(JUGGLER_WAIT["reveal"])
    if _alive(uid, sid) is None:
        return

    if bonus == "hyper":
        net = JUGGLER_HYPER_NET
        head = random.choice(JUGGLER_HYPER_REVEAL)
        color = discord.Color.from_rgb(255, 80, 200)   # プレミア専用カラー
    elif bonus == "big":
        net = JUGGLER_BIG_NET
        head = random.choice(JUGGLER_BIG_REVEAL)
        color = discord.Color.red()
    else:
        net = JUGGLER_REG_NET
        head = random.choice(JUGGLER_REG_REVEAL)
        color = discord.Color.blue()

    db.update_balance(uid, guild_id, net)
    new_bal = db.get_balance(uid, guild_id)

    e = discord.Embed(title=head, color=color)
    e.add_field(name="獲得", value=f"**+{net:,}** ナトコイン", inline=True)
    e.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
    e.set_image(url=lit_url)
    e.set_footer(text="🎰 回す ── 次のゲームへ")
    pad_embed(e, target_fields=3)
    await render(interaction, uid, e)

    # 純増が大きければBOT告知
    from cogs.bigwin import announce_big_win
    await announce_big_win(interaction, interaction.user, "ジャグラー",
                           net, balance=new_bal)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Juggler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(Juggler(bot))
