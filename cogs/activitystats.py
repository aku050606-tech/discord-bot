"""アクティビティ統計（VC在室・チャット）。

メニューの「📊 アクティビティ」から開く。タブ切替で4種類を表示：
  🎙️ VCランキング ／ 💬 チャットランキング ／ 📈 VCグラフ ／ 📊 チャットグラフ
各タブに期間（1日 / 1週間 / 1カ月）を用意。グラフはブロック文字のバー。
"""
import time
import io
import os
import textwrap
from datetime import datetime, timezone, timedelta
import discord
from PIL import Image, ImageDraw, ImageFont, ImageOps
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
    await _register_public_ranking(bot)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 公開ランキング /ranking ━━
def _all_rank_rows(guild_id: str, kind: str, since_hour: int):
    """順位計算用に対象期間の全ユーザーを取得する。"""
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT user_id, SUM(amount) AS total
               FROM activity_log
               WHERE guild_id=? AND kind=? AND ts_hour>=?
               GROUP BY user_id
               ORDER BY total DESC, user_id ASC""",
            (str(guild_id), kind, int(since_hour)),
        )
        return [(str(uid), int(total or 0)) for uid, total in cur.fetchall()]
    finally:
        conn.close()


_FONT_CANDIDATES = (
    # Railway / Debian: nixpacks.toml で fonts-noto-cjk を導入
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
)


def _font(size: int, bold: bool = False):
    ordered = list(_FONT_CANDIDATES)
    if bold:
        ordered.sort(key=lambda path: "Bold" not in path)
    else:
        ordered.sort(key=lambda path: "Regular" not in path)
    for path in ordered:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    raise RuntimeError(
        "日本語フォントが見つかりません。Railwayで fonts-noto-cjk を導入してください。"
    )


def _fit_text(draw, text, font, max_width):
    text = str(text)
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    while text and draw.textbbox((0, 0), text + "…", font=font)[2] > max_width:
        text = text[:-1]
    return text + "…"


async def _avatar_image(member: discord.Member | None, size: int):
    if member is None:
        return None
    try:
        raw = await member.display_avatar.with_size(128).read()
        avatar = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
        avatar.putalpha(mask)
        return avatar
    except Exception:
        return None


async def _guild_icon(guild: discord.Guild, size: int):
    try:
        if guild.icon is None:
            return None
        raw = await guild.icon.with_size(128).read()
        icon = Image.open(io.BytesIO(raw)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=14, fill=255)
        icon.putalpha(mask)
        return icon
    except Exception:
        return None


def _format_compact(total: int, is_vc: bool):
    if is_vc:
        hours, rem = divmod(total, 3600)
        minutes = rem // 60
        if hours:
            return f"{hours}時間 {minutes}分"
        return f"{minutes}分"
    return f"{total:,}件"


async def build_public_rank_card(guild: discord.Guild, viewer_id: int, kind: str, period_key: str):
    label, hours = PERIODS[period_key]
    since = _now_hour() - hours
    rows = _all_rank_rows(str(guild.id), kind, since)
    top_rows = rows[:10]
    is_vc = kind == "vc"

    width = 920
    margin = 34
    header_h = 150
    column_h = 40
    row_h = 72
    visible_rows = max(1, len(top_rows))
    footer_h = 105
    height = margin * 2 + header_h + column_h + visible_rows * row_h + footer_h

    bg = (20, 22, 28)
    panel = (31, 34, 42)
    row_a = (42, 46, 57)
    row_b = (37, 40, 50)
    text_main = (244, 245, 248)
    text_sub = (157, 166, 190)
    accent = (88, 101, 242) if is_vc else (63, 185, 118)

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (18, 18, width - 18, height - 18),
        radius=26,
        fill=panel,
        outline=(72, 78, 94),
        width=2,
    )

    title_font = _font(31, bold=True)
    subtitle_font = _font(19)
    header_font = _font(16, bold=True)
    rank_font = _font(22, bold=True)
    name_font = _font(22, bold=True)
    value_font = _font(20, bold=True)
    small_font = _font(16)

    icon = await _guild_icon(guild, 62)
    text_x = 65
    if icon:
        image.paste(icon, (58, 53), icon)
        text_x = 137
    draw.text((text_x, 52), _fit_text(draw, guild.name, title_font, 650), font=title_font, fill=text_main)
    kind_jp = "VC時間ランキング" if is_vc else "チャットランキング"
    draw.text((text_x, 96), f"{kind_jp} ・ {label}", font=subtitle_font, fill=text_sub)
    draw.rounded_rectangle((58, 132, width - 58, 138), radius=3, fill=accent)

    col_y = margin + header_h
    draw.text((72, col_y), "順位", font=header_font, fill=text_sub)
    draw.text((180, col_y), "メンバー", font=header_font, fill=text_sub)
    value_header = "VC時間" if is_vc else "メッセージ数"
    value_width = draw.textbbox((0, 0), value_header, font=header_font)[2]
    draw.text((width - 72 - value_width, col_y), value_header, font=header_font, fill=text_sub)

    viewer_rank = None
    viewer_total = 0
    for idx, (uid, total) in enumerate(rows, start=1):
        if uid == str(viewer_id):
            viewer_rank, viewer_total = idx, total
            break

    start_y = col_y + column_h
    if not top_rows:
        y = start_y
        draw.rounded_rectangle((58, y, width - 58, y + 58), radius=14, fill=row_a)
        no_data = "まだ集計データがありません"
        tw = draw.textbbox((0, 0), no_data, font=name_font)[2]
        draw.text(((width - tw) / 2, y + 15), no_data, font=name_font, fill=text_sub)
    else:
        for i, (uid, total) in enumerate(top_rows):
            y = start_y + i * row_h
            member = guild.get_member(int(uid))
            is_viewer = uid == str(viewer_id)
            fill = (50, 56, 88) if is_viewer else (row_a if i % 2 == 0 else row_b)
            draw.rounded_rectangle((58, y, width - 58, y + 58), radius=14, fill=fill)

            rank = i + 1
            medal_colors = {1: (255, 205, 74), 2: (207, 215, 228), 3: (210, 142, 92)}
            draw.text((78, y + 14), str(rank), font=rank_font, fill=medal_colors.get(rank, text_sub))

            avatar = await _avatar_image(member, 42)
            if avatar:
                image.paste(avatar, (127, y + 8), avatar)
            else:
                draw.ellipse((127, y + 8, 169, y + 50), fill=(78, 84, 103))

            name = member.display_name if member else f"ユーザー {uid[-6:]}"
            draw.text((185, y + 13), _fit_text(draw, name, name_font, 475), font=name_font, fill=text_main)
            value = _format_compact(total, is_vc)
            vw = draw.textbbox((0, 0), value, font=value_font)[2]
            draw.text((width - 72 - vw, y + 15), value, font=value_font, fill=text_main)

    footer_y = start_y + visible_rows * row_h + 14
    draw.rounded_rectangle(
        (58, footer_y, width - 58, footer_y + 78),
        radius=16,
        fill=(26, 29, 36),
        outline=accent,
        width=2,
    )
    draw.text((78, footer_y + 12), "あなたの順位", font=small_font, fill=text_sub)
    self_text = "集計データなし" if viewer_rank is None else f"{viewer_rank}位　{_format_compact(viewer_total, is_vc)}"
    draw.text((78, footer_y + 37), self_text, font=value_font, fill=text_main)

    period_text = f"過去{label}"
    pw = draw.textbbox((0, 0), period_text, font=small_font)[2]
    draw.text((width - 78 - pw, footer_y + 42), period_text, font=small_font, fill=text_sub)

    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    out.seek(0)
    return discord.File(out, filename="ranking.png")


class PublicRankingView(discord.ui.View):
    def __init__(self, owner_id: int, kind: str = "vc", period: str = "1w"):
        super().__init__(timeout=300)
        self.owner_id = int(owner_id)
        self.kind = kind
        self.period = period
        self._rebuild()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "ランキングを切り替える場合は、自分で `/ranking` を実行してください。",
                ephemeral=True,
            )
            return False
        return True

    async def _update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self._rebuild()
        file = await build_public_rank_card(
            interaction.guild, interaction.user.id, self.kind, self.period
        )
        embed = discord.Embed(color=0x5865F2 if self.kind == "vc" else 0x57F287)
        embed.set_image(url="attachment://ranking.png")
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    def _rebuild(self):
        self.clear_items()
        vc_button = discord.ui.Button(label="VC時間", style=discord.ButtonStyle.primary if self.kind == "vc" else discord.ButtonStyle.secondary, row=0)
        chat_button = discord.ui.Button(label="チャット数", style=discord.ButtonStyle.primary if self.kind == "chat" else discord.ButtonStyle.secondary, row=0)

        async def set_vc(interaction: discord.Interaction):
            self.kind = "vc"
            await self._update(interaction)

        async def set_chat(interaction: discord.Interaction):
            self.kind = "chat"
            await self._update(interaction)

        vc_button.callback = set_vc
        chat_button.callback = set_chat
        self.add_item(vc_button)
        self.add_item(chat_button)

        for period_key, period_label in (("1d", "1日"), ("1w", "1週間"), ("1m", "1カ月")):
            button = discord.ui.Button(label=period_label, style=discord.ButtonStyle.success if self.period == period_key else discord.ButtonStyle.secondary, row=1)

            async def set_period(interaction: discord.Interaction, key=period_key):
                self.period = key
                await self._update(interaction)

            button.callback = set_period
            self.add_item(button)


async def _register_public_ranking(bot: commands.Bot):
    existing = bot.tree.get_command("ranking")
    if existing is not None:
        bot.tree.remove_command("ranking")

    @bot.tree.command(name="ranking", description="VC時間・チャット数ランキングを表示します")
    async def ranking(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("このコマンドはサーバー内で使用してください。", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            db.prune_activity(_now_hour() - 24 * 40)
        except Exception:
            pass
        view = PublicRankingView(interaction.user.id, kind="vc", period="1w")
        file = await build_public_rank_card(interaction.guild, interaction.user.id, view.kind, view.period)
        embed = discord.Embed(color=0x5865F2)
        embed.set_image(url="attachment://ranking.png")
        await interaction.followup.send(embed=embed, file=file, view=view)

