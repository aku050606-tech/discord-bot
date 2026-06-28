"""アクティビティ統計（VC在室・チャット）。

メニューの「📊 アクティビティ」から開く。タブ切替で4種類を表示：
  🎙️ VCランキング ／ 💬 チャットランキング ／ 📈 VCグラフ ／ 📊 チャットグラフ
各タブに期間（1日 / 1週間 / 1カ月）を用意。グラフはブロック文字のバー。
"""
import time
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
from database import Database

db = Database()
JST = timezone(timedelta(hours=9))

PERIODS = {"1d": ("1日", 24), "1w": ("1週間", 24 * 7), "1m": ("1カ月", 24 * 30)}


def _now_hour():
    return int(time.time()) // 3600


def _fmt_hms(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h > 0:
        return f"{h}時間{m}分"
    return f"{m}分"


def _bar(value, maxv, width=12):
    if maxv <= 0:
        return "░" * width
    n = int(round(value / maxv * width))
    n = max(0, min(width, n))
    return "█" * n + "░" * (width - n)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ランキング ━━
def build_rank_embed(guild, kind, period_key) -> discord.Embed:
    label, hours = PERIODS[period_key]
    since = _now_hour() - hours
    rows = db.rank_activity(str(guild.id), kind, since, limit=10)
    is_vc = (kind == "vc")
    title = ("🎙️ VC在室ランキング" if is_vc else "💬 チャットランキング") + f"（{label}）"
    if not rows:
        desc = "まだデータがありません。\n（集計はデプロイ後から始まります）"
    else:
        medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
        lines = []
        for i, (uid, total) in enumerate(rows):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"ユーザー({uid})"
            val = _fmt_hms(total) if is_vc else f"{total:,} 発言"
            lines.append(f"{medals[i]} **{name}** — {val}")
        desc = "\n".join(lines)
    e = discord.Embed(title=title, description=desc, color=0x5865F2)
    e.set_footer(text="タブと期間を切り替えて他の統計も見られます")
    return e


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ グラフ ━━
def build_graph_embed(guild, kind, period_key) -> discord.Embed:
    label, hours = PERIODS[period_key]
    since = _now_hour() - hours
    buckets = db.activity_buckets(str(guild.id), kind, since)  # [(ts_hour, amount)]
    is_vc = (kind == "vc")
    title = ("📈 VC時間帯グラフ" if is_vc else "📊 チャット時間帯グラフ") + f"（{label}）"

    # 期間に応じて集計の粒度を変える
    agg = {}      # ラベル -> 合計
    order = []    # 表示順のラベル
    if period_key == "1d":
        # 時刻別（0〜23時 JST）
        for h in range(24):
            lbl = f"{h:02d}時"
            agg[lbl] = 0
            order.append(lbl)
        for ts_hour, amt in buckets:
            jst_hour = (ts_hour + 9) % 24
            agg[f"{jst_hour:02d}時"] += amt
    else:
        # 日別
        ndays = 7 if period_key == "1w" else 30
        today = datetime.now(JST).date()
        for d in range(ndays - 1, -1, -1):
            day = today - timedelta(days=d)
            lbl = day.strftime("%m/%d")
            agg[lbl] = 0
            order.append(lbl)
        for ts_hour, amt in buckets:
            dt = datetime.fromtimestamp(ts_hour * 3600, tz=JST)
            lbl = dt.strftime("%m/%d")
            if lbl in agg:
                agg[lbl] += amt

    total_all = sum(agg.values())
    if total_all == 0:
        desc = "まだデータがありません。\n（集計はデプロイ後から始まります）"
    else:
        maxv = max(agg.values()) or 1
        lines = []
        for lbl in order:
            v = agg[lbl]
            valtxt = _fmt_hms(v) if is_vc else f"{v}"
            lines.append(f"`{lbl}` {_bar(v, maxv)} {valtxt}")
        # 1カ月の日別は30行と長いので、活動がある範囲だけに絞らずそのまま全表示
        body = "\n".join(lines)
        total_txt = _fmt_hms(total_all) if is_vc else f"{total_all:,} 発言"
        desc = f"サーバー全体の活動量（{label}・合計 {total_txt}）\n\n{body}"

    e = discord.Embed(title=title, description=desc[:4090], color=0x57F287 if is_vc else 0xFEE75C)
    e.set_footer(text="█が多いほど活発な時間帯です")
    return e


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ View ━━
TABS = {
    "vc_rank": "🎙️ VC順位",
    "chat_rank": "💬 チャット順位",
    "vc_graph": "📈 VC推移",
    "chat_graph": "📊 チャット推移",
}


def render(guild, tab, period):
    if tab == "vc_rank":
        return build_rank_embed(guild, "vc", period)
    if tab == "chat_rank":
        return build_rank_embed(guild, "chat", period)
    if tab == "vc_graph":
        return build_graph_embed(guild, "vc", period)
    return build_graph_embed(guild, "chat", period)


class StatsView(discord.ui.View):
    def __init__(self, user_id: str, tab="vc_rank", period="1w"):
        super().__init__(timeout=300)
        self.user_id = str(user_id)
        self.tab = tab
        self.period = period
        self._build()

    async def _check(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの画面ではありません", ephemeral=True)
            return False
        return True

    def _build(self):
        self.clear_items()
        # 行0-1：タブ
        for i, (key, lbl) in enumerate(TABS.items()):
            btn = discord.ui.Button(
                label=lbl, row=0 if i < 2 else 1,
                style=discord.ButtonStyle.primary if key == self.tab else discord.ButtonStyle.secondary)
            btn.callback = self._make_tab_cb(key)
            self.add_item(btn)
        # 行2：期間
        for pkey, (plabel, _) in PERIODS.items():
            btn = discord.ui.Button(
                label=plabel, row=2,
                style=discord.ButtonStyle.success if pkey == self.period else discord.ButtonStyle.secondary)
            btn.callback = self._make_period_cb(pkey)
            self.add_item(btn)
        # 行3：戻る
        home = discord.ui.Button(label="🏠 ホームへ戻る", row=3, style=discord.ButtonStyle.secondary)
        home.callback = self._home_cb
        self.add_item(home)

    def _make_tab_cb(self, key):
        async def cb(interaction):
            if not await self._check(interaction):
                return
            self.tab = key
            self._build()
            await interaction.response.edit_message(
                embed=render(interaction.guild, self.tab, self.period), view=self)
        return cb

    def _make_period_cb(self, key):
        async def cb(interaction):
            if not await self._check(interaction):
                return
            self.period = key
            self._build()
            await interaction.response.edit_message(
                embed=render(interaction.guild, self.tab, self.period), view=self)
        return cb

    async def _home_cb(self, interaction):
        if not await self._check(interaction):
            return
        from cogs.phone import open_phone
        await open_phone(interaction, self.user_id)


async def open_stats(interaction: discord.Interaction, uid: str = None):
    uid = uid or str(interaction.user.id)
    # 古いデータの掃除（40日より前）
    try:
        db.prune_activity(_now_hour() - 24 * 40)
    except Exception:
        pass
    view = StatsView(uid, tab="vc_rank", period="1w")
    embed = render(interaction.guild, view.tab, view.period)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class ActivityStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(ActivityStats(bot))
