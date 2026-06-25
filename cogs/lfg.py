"""
ゲーム募集（LFG）機能 / 複数ゲーム対応版
- /募集パネル設置 でチャンネルに常設パネルを置く（メニューの🎮ゲーム募集からも作成可）
- 作成画面でゲームを複数選択 → ゲームごとに募集人数(@N)を設定
- 募集は必ず固定チャンネル(TARGET_CHANNEL_ID)に @everyone 付きで投稿される
- 投稿では「参加するゲームを選択」セレクト→時間モーダル(空欄=今すぐ) で参加
- ❌取り消し / 📢締め切る(募集主のみ)
- 各ゲームが満員になった瞬間にその枠の参加者へメンション通知
- 永続View + DB保存（database.py は触らない。bot_data.db に専用テーブルを同居）
"""
import sqlite3
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

from database import DB_PATH

# 募集を必ず投稿するチャンネル（どこから募集しても、ここに集約される）
TARGET_CHANNEL_ID = 1455977803320398020

# 同時に選べるゲーム数の上限（選択肢が VALO/LoL/その他 の3つなので3）
MAX_GAMES = 3

# ゲーム名 → 絵文字（その他/カスタムは🎮）
GAME_EMOJI = {"VALORANT": "🔫", "LoL": "⚔️"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB（lfg専用テーブル。既存DBに同居 / 複数ゲーム対応スキーマ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _conn():
    return sqlite3.connect(DB_PATH)


def init_tables():
    conn = _conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS lfg_post (
        message_id TEXT PRIMARY KEY,
        channel_id TEXT, guild_id TEXT, creator_id TEXT,
        start_time TEXT, comment TEXT,
        status TEXT DEFAULT 'open', created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lfg_post_game (
        message_id TEXT, game TEXT, capacity INTEGER, ord INTEGER,
        PRIMARY KEY (message_id, game)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lfg_member (
        message_id TEXT, game TEXT, user_id TEXT, time_note TEXT, joined_at TEXT,
        PRIMARY KEY (message_id, game, user_id)
    )""")
    conn.commit()
    conn.close()


def create_post(message_id, channel_id, guild_id, creator_id, start_time, comment):
    conn = _conn()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO lfg_post
        (message_id, channel_id, guild_id, creator_id, start_time, comment, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'open', ?)""",
              (str(message_id), str(channel_id), str(guild_id), str(creator_id),
               start_time or None, comment or None, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def add_game(message_id, game, capacity, ord_):
    conn = _conn()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO lfg_post_game (message_id, game, capacity, ord)
                 VALUES (?, ?, ?, ?)""",
              (str(message_id), game, int(capacity), int(ord_)))
    conn.commit()
    conn.close()


def load_post(message_id):
    """(post_dict | None, games[(game,cap,ord)], members{game:[{user_id,time_note}]})"""
    mid = str(message_id)
    conn = _conn()
    c = conn.cursor()
    c.execute("""SELECT message_id, channel_id, guild_id, creator_id, start_time, comment, status
                 FROM lfg_post WHERE message_id = ?""", (mid,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, [], {}
    post = {
        "message_id": row[0], "channel_id": row[1], "guild_id": row[2],
        "creator_id": row[3], "start_time": row[4], "comment": row[5], "status": row[6],
    }
    c.execute("SELECT game, capacity, ord FROM lfg_post_game WHERE message_id = ? ORDER BY ord ASC", (mid,))
    games = [(r[0], r[1], r[2]) for r in c.fetchall()]
    c.execute("SELECT game, user_id, time_note FROM lfg_member WHERE message_id = ? ORDER BY joined_at ASC", (mid,))
    members = {}
    for g, u, n in c.fetchall():
        members.setdefault(g, []).append({"user_id": u, "time_note": n})
    conn.close()
    return post, games, members


def _add_member(message_id, game, user_id, note):
    conn = _conn()
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO lfg_member (message_id, game, user_id, time_note, joined_at)
                 VALUES (?, ?, ?, ?, ?)""",
              (str(message_id), game, str(user_id), note or "", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def _update_member_note(message_id, game, user_id, note):
    conn = _conn()
    c = conn.cursor()
    c.execute("UPDATE lfg_member SET time_note = ? WHERE message_id = ? AND game = ? AND user_id = ?",
              (note or "", str(message_id), game, str(user_id)))
    conn.commit()
    conn.close()


def remove_member_all(message_id, user_id):
    """この募集の全ゲームからユーザーを外す。外した件数を返す"""
    conn = _conn()
    c = conn.cursor()
    c.execute("DELETE FROM lfg_member WHERE message_id = ? AND user_id = ?",
              (str(message_id), str(user_id)))
    n = c.rowcount
    conn.commit()
    conn.close()
    return n


def set_post_status(message_id, status):
    conn = _conn()
    c = conn.cursor()
    c.execute("UPDATE lfg_post SET status = ? WHERE message_id = ?", (status, str(message_id)))
    conn.commit()
    conn.close()


def join_games(message_id, user_id, games, note):
    """選んだ複数ゲームに参加。
       戻り値: {"status": invalid|closed|done, "results": {game: ok|updated|full|nogame}, "newly_full": [game...]}"""
    post, gameinfo, members = load_post(message_id)
    if not post:
        return {"status": "invalid"}
    if post["status"] != "open":
        return {"status": "closed"}
    cap_map = {g: cap for g, cap, _ in gameinfo}
    results = {}
    newly_full = []
    for g in games:
        if g not in cap_map:
            results[g] = "nogame"
            continue
        cur = members.get(g, [])
        if any(m["user_id"] == str(user_id) for m in cur):
            _update_member_note(message_id, g, user_id, note)
            results[g] = "updated"
            continue
        if len(cur) >= cap_map[g]:
            results[g] = "full"
            continue
        _add_member(message_id, g, user_id, note)
        cur.append({"user_id": str(user_id), "time_note": note})
        members[g] = cur
        results[g] = "ok"
        if len(cur) >= cap_map[g]:
            newly_full.append(g)
    return {"status": "done", "results": results, "newly_full": newly_full}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# embed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_post_embed(post, gameinfo, members):
    closed = post["status"] == "closed"
    total_slots = sum(cap for _, cap, _ in gameinfo)
    total_filled = sum(len(members.get(g, [])) for g, _, _ in gameinfo)
    all_full = bool(gameinfo) and total_filled >= total_slots

    if closed:
        color = discord.Color.dark_grey()
    elif all_full:
        color = discord.Color.green()
    else:
        color = discord.Color.blurple()

    embed = discord.Embed(
        title="🎮 ゲーム募集" + ("（締め切り）" if closed else ""),
        color=color,
    )
    embed.add_field(name="👑 募集主", value=f"<@{post['creator_id']}>", inline=True)
    if post["start_time"]:
        embed.add_field(name="🕐 開始", value=post["start_time"], inline=True)
    if post["comment"]:
        embed.add_field(name="💬 コメント", value=post["comment"], inline=False)

    for g, cap, _ in gameinfo:
        ms = members.get(g, [])
        cur = len(ms)
        full = cur >= cap
        emoji = GAME_EMOJI.get(g, "🎮")
        if closed:
            state = ""
        elif full:
            state = "🎉満員"
        else:
            state = f"あと{cap - cur}人"
        if ms:
            body = "\n".join(
                f"・<@{m['user_id']}>" + (f"（{m['time_note']}）" if m["time_note"] else "")
                for m in ms)
        else:
            body = "まだいません"
        embed.add_field(name=f"{emoji} {g}　@{cap}　({cur}/{cap}) {state}", value=body, inline=False)

    if closed:
        embed.set_footer(text="この募集は締め切られました")
    else:
        embed.set_footer(text="🎮参加するゲームを選択 ／ ❌取り消し")
    return embed


async def _announce_full(channel, post, game, members):
    mentions = " ".join(f"<@{m['user_id']}>" for m in members)
    emoji = GAME_EMOJI.get(game, "🎮")
    try:
        await channel.send(f"{emoji} **{game}** が満員になったよ！集合〜\n{mentions}")
    except discord.HTTPException:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 募集投稿のView（永続）
#   参加セレクトは投稿ごとにゲームが違うので options を動的に差し替える。
#   custom_id は固定なので、永続Viewとして1個登録すれば全投稿を捌ける。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class GameJoinSelect(discord.ui.Select):
    def __init__(self, games=None):
        if games:
            options = [
                discord.SelectOption(label=g[:100], value=g[:100], emoji=GAME_EMOJI.get(g))
                for g in games
            ]
            max_values = len(options)
        else:
            # 永続View登録用のダミー（実際の投稿では本物のoptionsに差し替わる）
            options = [discord.SelectOption(label="-", value="-")]
            max_values = 1
        super().__init__(placeholder="🎮 参加するゲームを選択", min_values=1,
                         max_values=max_values, options=options,
                         custom_id="lfg:join", row=0)

    async def callback(self, interaction: discord.Interaction):
        selected = list(self.values)
        await interaction.response.send_modal(
            JoinTimeModal(interaction.channel.id, interaction.message.id, selected))


class LeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="取り消し", style=discord.ButtonStyle.danger,
                         emoji="❌", custom_id="lfg:leave", row=1)

    async def callback(self, interaction: discord.Interaction):
        post, _, _ = load_post(interaction.message.id)
        if not post:
            return await interaction.response.send_message("❌ この募集は無効だよ", ephemeral=True)
        if remove_member_all(interaction.message.id, interaction.user.id) == 0:
            return await interaction.response.send_message("参加してないよ", ephemeral=True)
        post, gameinfo, members = load_post(interaction.message.id)
        cur_games = [g for g, _, _ in gameinfo]
        await interaction.response.edit_message(
            embed=build_post_embed(post, gameinfo, members), view=PostView(cur_games))


class CloseButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="締め切る", style=discord.ButtonStyle.secondary,
                         emoji="📢", custom_id="lfg:close", row=1)

    async def callback(self, interaction: discord.Interaction):
        post, _, _ = load_post(interaction.message.id)
        if not post:
            return await interaction.response.send_message("❌ この募集は無効だよ", ephemeral=True)
        if str(interaction.user.id) != post["creator_id"]:
            return await interaction.response.send_message("❌ 募集主だけが締め切れるよ", ephemeral=True)
        set_post_status(interaction.message.id, "closed")
        post, gameinfo, members = load_post(interaction.message.id)
        await interaction.response.edit_message(
            embed=build_post_embed(post, gameinfo, members), view=None)


class PostView(discord.ui.View):
    def __init__(self, games=None):
        super().__init__(timeout=None)
        self.add_item(GameJoinSelect(games))
        self.add_item(LeaveButton())
        self.add_item(CloseButton())


class JoinTimeModal(discord.ui.Modal, title="参加時間を入力"):
    answer = discord.ui.TextInput(
        label="参加できる時間（空欄=今すぐOK）",
        placeholder="例: 21時〜 ／ 22時 ／ バイト後23時",
        max_length=40,
        required=False,
    )

    def __init__(self, channel_id, message_id, games):
        super().__init__()
        self.channel_id = channel_id
        self.message_id = message_id
        self.games = games

    async def on_submit(self, interaction: discord.Interaction):
        note = str(self.answer.value).strip() or "今すぐOK"
        await interaction.response.defer()
        res = join_games(self.message_id, interaction.user.id, self.games, note)
        if res["status"] == "invalid":
            return await interaction.followup.send("❌ この募集は無効だよ", ephemeral=True)
        if res["status"] == "closed":
            return await interaction.followup.send("🔒 この募集は締め切られてるよ", ephemeral=True)

        post, gameinfo, members = load_post(self.message_id)
        cur_games = [g for g, _, _ in gameinfo]
        msg = interaction.channel.get_partial_message(int(self.message_id))
        await msg.edit(embed=build_post_embed(post, gameinfo, members), view=PostView(cur_games))

        lines = []
        for g, st in res["results"].items():
            if st == "ok":
                lines.append(f"✅ {g} に参加（{note}）")
            elif st == "updated":
                lines.append(f"🔄 {g} の時間を更新（{note}）")
            elif st == "full":
                lines.append(f"🈵 {g} は満員")
            elif st == "nogame":
                lines.append(f"⚠️ {g} はこの募集に無いよ")
        await interaction.followup.send("\n".join(lines) or "変更なし", ephemeral=True)

        for g in res.get("newly_full", []):
            await _announce_full(interaction.channel, post, g, members.get(g, []))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 募集パネル（常設・永続）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="募集を立てる", style=discord.ButtonStyle.success,
                       emoji="🎮", custom_id="lfg:create")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = CreateView(interaction.user.id)
        await interaction.response.send_message(embed=view.status_embed(), view=view, ephemeral=True)
        view.message = await interaction.original_response()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 募集作成画面（本人だけのephemeral・一時的なのでtimeoutでOK）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CreateView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=300)
        self.author_id = str(author_id)
        self.raw_games = []        # セレクトの生の値（__other__ を含む）
        self.other_name = None     # その他で入力したゲーム名
        self.games = []            # 解決後のゲーム名リスト
        self.caps = {}             # game -> 募集人数
        self.start_time = None
        self.comment = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.author_id:
            await interaction.response.send_message("これはあなたの作成画面じゃないよ", ephemeral=True)
            return False
        return True

    def _resolve_games(self):
        resolved = []
        for v in self.raw_games:
            if v == "__other__":
                if self.other_name:
                    resolved.append(self.other_name)
            else:
                resolved.append(v)
        seen = set()
        self.games = []
        for g in resolved:
            if g not in seen:
                seen.add(g)
                self.games.append(g)
        self.caps = {g: c for g, c in self.caps.items() if g in self.games}

    def status_embed(self):
        if not self.games:
            gtxt = "未選択"
        else:
            gtxt = "\n".join(
                f"{GAME_EMOJI.get(g, '🎮')} {g} … "
                + (f"**@{self.caps[g]}募集**" if g in self.caps else "⚠️人数未設定")
                for g in self.games)
        embed = discord.Embed(
            title="🎮 募集を作成",
            description="① ゲームを選ぶ（複数可）　② 👥人数を設定　③ ✅募集する",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="ゲーム / 人数", value=gtxt, inline=False)
        embed.add_field(name="開始時間", value=self.start_time or "指定なし", inline=True)
        embed.add_field(name="コメント", value=self.comment or "なし", inline=False)
        return embed

    async def refresh(self):
        if self.message:
            await self.message.edit(embed=self.status_embed(), view=self)

    @discord.ui.select(
        placeholder="🎮 ゲームを選択（複数選択OK）",
        min_values=1, max_values=MAX_GAMES, row=0,
        options=[
            discord.SelectOption(label="VALORANT", value="VALORANT", emoji="🔫"),
            discord.SelectOption(label="LoL", value="LoL", emoji="⚔️"),
            discord.SelectOption(label="その他（自分で入力）", value="__other__", emoji="✏️"),
        ],
    )
    async def game_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.raw_games = list(select.values)
        if "__other__" in self.raw_games and not self.other_name:
            return await interaction.response.send_modal(OtherGameModal(self))
        self._resolve_games()
        await interaction.response.edit_message(embed=self.status_embed(), view=self)

    @discord.ui.button(label="人数を設定", style=discord.ButtonStyle.primary, emoji="👥", row=1)
    async def set_caps(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.games:
            return await interaction.response.send_message("先にゲームを選んでね", ephemeral=True)
        await interaction.response.send_modal(CapacityModal(self))

    @discord.ui.button(label="開始時間・コメント", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DetailsModal(self))

    @discord.ui.button(label="募集する", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.games:
            return await interaction.response.send_message("⚠️ ゲームを選んでね", ephemeral=True)
        missing = [g for g in self.games if g not in self.caps]
        if missing:
            return await interaction.response.send_message(
                f"⚠️ 人数未設定のゲームがあるよ：{', '.join(missing)}\n「👥人数を設定」を押してね",
                ephemeral=True)

        await interaction.response.defer()
        target = interaction.client.get_channel(TARGET_CHANNEL_ID)
        if target is None:
            return await interaction.edit_original_response(
                embed=discord.Embed(
                    title="❌ 募集チャンネルが見つからない",
                    description=(f"ID `{TARGET_CHANNEL_ID}` のチャンネルが見つからないよ。\n"
                                 "BOTがそのチャンネルを見える状態か確認してね。"),
                    color=discord.Color.red()),
                view=None)

        creator_id = str(interaction.user.id)
        gameinfo = [(g, self.caps[g], i) for i, g in enumerate(self.games)]
        post_preview = {"creator_id": creator_id, "start_time": self.start_time,
                        "comment": self.comment, "status": "open"}
        msg = await target.send(
            content="@everyone",
            embed=build_post_embed(post_preview, gameinfo, {}),
            view=PostView(self.games),
            allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=False),
        )
        create_post(msg.id, target.id, interaction.guild.id, creator_id,
                    self.start_time, self.comment)
        for g, cap, ord_ in gameinfo:
            add_game(msg.id, g, cap, ord_)

        done = discord.Embed(title="✅ 募集を立てたよ！",
                             description=f"{target.mention} に投稿したよ",
                             color=discord.Color.green())
        await interaction.edit_original_response(embed=done, view=None)
        self.stop()


class OtherGameModal(discord.ui.Modal, title="その他のゲーム名を入力"):
    gamename = discord.ui.TextInput(
        label="ゲーム名",
        placeholder="例: Apex / Overwatch / マイクラ / スプラ",
        max_length=40,
        required=True,
    )

    def __init__(self, parent: CreateView):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        self.parent.other_name = str(self.gamename.value).strip()
        self.parent._resolve_games()
        await interaction.response.defer()
        await self.parent.refresh()


class CapacityModal(discord.ui.Modal, title="ゲームごとの募集人数"):
    def __init__(self, parent: CreateView):
        super().__init__()
        self.parent = parent
        self.fields = {}
        for g in parent.games:
            ti = discord.ui.TextInput(
                label=f"{g}の人数"[:45],
                default=str(parent.caps.get(g, 4)),
                placeholder="1〜20の数字",
                max_length=2,
                required=True,
            )
            self.add_item(ti)
            self.fields[g] = ti

    async def on_submit(self, interaction: discord.Interaction):
        for g, ti in self.fields.items():
            try:
                n = int(str(ti.value).strip())
            except ValueError:
                n = 4
            self.parent.caps[g] = max(1, min(20, n))
        await interaction.response.defer()
        await self.parent.refresh()


class DetailsModal(discord.ui.Modal, title="開始時間・コメント（任意）"):
    start = discord.ui.TextInput(
        label="開始時間",
        placeholder="例: 21時〜 ／ 今すぐ ／ 22時以降",
        max_length=40,
        required=False,
    )
    comment = discord.ui.TextInput(
        label="コメント",
        placeholder="例: ランク回したい！初心者歓迎",
        style=discord.TextStyle.paragraph,
        max_length=100,
        required=False,
    )

    def __init__(self, parent: CreateView):
        super().__init__()
        self.parent = parent

    async def on_submit(self, interaction: discord.Interaction):
        self.parent.start_time = str(self.start.value).strip() or None
        self.parent.comment = str(self.comment.value).strip() or None
        await interaction.response.defer()
        await self.parent.refresh()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class LFG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        init_tables()
        self.bot.add_view(PanelView())
        self.bot.add_view(PostView())  # 参加/取消/締切（永続）

    @app_commands.command(name="募集パネル設置",
                          description="このチャンネルにゲーム募集パネルを設置します")
    async def setup_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message(
                "❌ このコマンドはサーバー管理権限が必要だよ", ephemeral=True)
        embed = discord.Embed(
            title="🎮 ゲーム募集パネル",
            description=(
                "下のボタンから募集を立てよう！\n\n"
                "・ゲームは**複数選択OK**（🔫VALORANT ／ ⚔️LoL ／ ✏️その他）\n"
                "・ゲームごとに募集人数(@N)を設定できる\n"
                "・参加は「🎮参加するゲームを選択」→ 時間入力（空欄=今すぐ）"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=PanelView())
        await interaction.response.send_message("✅ 募集パネルを設置したよ！", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LFG(bot))
