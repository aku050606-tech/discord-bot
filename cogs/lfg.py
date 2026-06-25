"""
ゲーム募集（LFG）機能
- チャンネルに常設の「募集パネル」を置く（/募集パネル設置）
- パネルのボタンから VALORANT / LoL / その他 の募集を作成
- 募集投稿で ✋参加 / 🕐時間を指定して参加 / ❌取り消し / 📢締め切る
- すべて永続View + DB保存。Railway再デプロイ後もボタンが反応する
データは既存の bot_data.db に専用テーブルを作って保存（database.py は触らない）
"""
import sqlite3
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands

from database import DB_PATH

# 募集を必ず投稿するチャンネル（どこから募集しても、ここに集約される）
TARGET_CHANNEL_ID = 1455977803320398020

# ゲーム名 → 絵文字（その他は🎮）
GAME_EMOJI = {"VALORANT": "🔫", "LoL": "⚔️"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB（lfg専用テーブル。既存DBに同居）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _conn():
    return sqlite3.connect(DB_PATH)


def init_tables():
    conn = _conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS lfg_recruit (
        message_id TEXT PRIMARY KEY,
        channel_id TEXT, guild_id TEXT, creator_id TEXT,
        game TEXT, capacity INTEGER,
        start_time TEXT, comment TEXT,
        status TEXT DEFAULT 'open', created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lfg_participant (
        message_id TEXT, user_id TEXT, time_note TEXT, joined_at TEXT,
        PRIMARY KEY (message_id, user_id)
    )""")
    conn.commit()
    conn.close()


def create_recruit(message_id, channel_id, guild_id, creator_id,
                   game, capacity, start_time, comment):
    conn = _conn()
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO lfg_recruit
        (message_id, channel_id, guild_id, creator_id, game, capacity,
         start_time, comment, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)""",
              (str(message_id), str(channel_id), str(guild_id), str(creator_id),
               game, int(capacity), start_time or None, comment or None,
               datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def load_recruit(message_id):
    """(recruit_dict | None, participants_list) を返す"""
    conn = _conn()
    c = conn.cursor()
    c.execute("""SELECT message_id, channel_id, guild_id, creator_id, game,
                 capacity, start_time, comment, status
                 FROM lfg_recruit WHERE message_id = ?""", (str(message_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return None, []
    r = {
        "message_id": row[0], "channel_id": row[1], "guild_id": row[2],
        "creator_id": row[3], "game": row[4], "capacity": row[5],
        "start_time": row[6], "comment": row[7], "status": row[8],
    }
    c.execute("""SELECT user_id, time_note FROM lfg_participant
                 WHERE message_id = ? ORDER BY joined_at ASC""", (str(message_id),))
    parts = [{"user_id": p[0], "time_note": p[1]} for p in c.fetchall()]
    conn.close()
    return r, parts


def add_participant(message_id, user_id, note):
    conn = _conn()
    c = conn.cursor()
    try:
        c.execute("""INSERT INTO lfg_participant (message_id, user_id, time_note, joined_at)
                     VALUES (?, ?, ?, ?)""",
                  (str(message_id), str(user_id), note or "", datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        return "ok"
    except sqlite3.IntegrityError:
        conn.close()
        return "dup"


def update_note(message_id, user_id, note):
    conn = _conn()
    c = conn.cursor()
    c.execute("UPDATE lfg_participant SET time_note = ? WHERE message_id = ? AND user_id = ?",
              (note or "", str(message_id), str(user_id)))
    conn.commit()
    conn.close()


def remove_participant(message_id, user_id):
    conn = _conn()
    c = conn.cursor()
    c.execute("DELETE FROM lfg_participant WHERE message_id = ? AND user_id = ?",
              (str(message_id), str(user_id)))
    n = c.rowcount
    conn.commit()
    conn.close()
    return n > 0


def set_status(message_id, status):
    conn = _conn()
    c = conn.cursor()
    c.execute("UPDATE lfg_recruit SET status = ? WHERE message_id = ?", (status, str(message_id)))
    conn.commit()
    conn.close()


def try_join(message_id, user_id, note):
    """参加処理。戻り値: (status, recruit, participants)
       status: invalid / closed / full / updated / ok / ok_full"""
    r, parts = load_recruit(message_id)
    if not r:
        return "invalid", r, parts
    if r["status"] != "open":
        return "closed", r, parts
    if any(p["user_id"] == str(user_id) for p in parts):
        update_note(message_id, user_id, note)  # すでに参加 → 時間だけ更新
        r, parts = load_recruit(message_id)
        return "updated", r, parts
    total = r["capacity"] + 1  # 募集主を含めた定員
    if len(parts) >= total:
        return "full", r, parts
    add_participant(message_id, user_id, note)
    r, parts = load_recruit(message_id)
    return ("ok_full" if len(parts) >= total else "ok"), r, parts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# embed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_recruit_embed(r, parts):
    cap = r["capacity"]
    total = cap + 1
    cur = len(parts)
    closed = r["status"] == "closed"
    full = cur >= total

    if closed:
        color = discord.Color.dark_grey()
        state = "🔒 締め切り"
    elif full:
        color = discord.Color.green()
        state = "🎉 満員！"
    else:
        color = discord.Color.blurple()
        state = f"あと{total - cur}人！"

    emoji = GAME_EMOJI.get(r["game"], "🎮")
    embed = discord.Embed(title=f"{emoji} {r['game']} 募集　@{cap}募集", color=color)
    embed.add_field(name="👑 募集主", value=f"<@{r['creator_id']}>", inline=True)
    if r["start_time"]:
        embed.add_field(name="🕐 開始", value=r["start_time"], inline=True)
    if r["comment"]:
        embed.add_field(name="💬 コメント", value=r["comment"], inline=False)

    if parts:
        lines = []
        for p in parts:
            mark = "👑" if p["user_id"] == r["creator_id"] else "✋"
            note = f"　…　{p['time_note']}" if p["time_note"] else ""
            lines.append(f"{mark} <@{p['user_id']}>{note}")
        plist = "\n".join(lines)
    else:
        plist = "まだいません"

    embed.add_field(name=f"👥 参加者 ({cur}/{total})　{state}", value=plist, inline=False)
    if not closed:
        embed.set_footer(text="✋参加 ／ 🕐時間を指定して参加 ／ ❌取り消し")
    else:
        embed.set_footer(text="この募集は締め切られました")
    return embed


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 募集投稿のView（永続）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class RecruitView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="参加", style=discord.ButtonStyle.success,
                       emoji="✋", custom_id="lfg:join", row=0)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        status, r, parts = try_join(interaction.message.id, interaction.user.id, "今すぐOK")
        if status == "invalid":
            return await interaction.response.send_message("❌ この募集は無効だよ", ephemeral=True)
        if status == "closed":
            return await interaction.response.send_message("🔒 この募集は締め切られてるよ", ephemeral=True)
        if status == "full":
            return await interaction.response.send_message("🈵 満員だよ！", ephemeral=True)

        await interaction.response.edit_message(embed=build_recruit_embed(r, parts), view=self)
        if status == "ok_full":
            await _announce_full(interaction.channel, r, parts)

    @discord.ui.button(label="時間を指定して参加", style=discord.ButtonStyle.secondary,
                       emoji="🕐", custom_id="lfg:join_time", row=0)
    async def join_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            JoinTimeModal(interaction.channel.id, interaction.message.id))

    @discord.ui.button(label="取り消し", style=discord.ButtonStyle.danger,
                       emoji="❌", custom_id="lfg:leave", row=0)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        r, _ = load_recruit(interaction.message.id)
        if not r:
            return await interaction.response.send_message("❌ この募集は無効だよ", ephemeral=True)
        if not remove_participant(interaction.message.id, interaction.user.id):
            return await interaction.response.send_message("参加してないよ", ephemeral=True)
        r, parts = load_recruit(interaction.message.id)
        await interaction.response.edit_message(embed=build_recruit_embed(r, parts), view=self)

    @discord.ui.button(label="締め切る", style=discord.ButtonStyle.secondary,
                       emoji="📢", custom_id="lfg:close", row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        r, _ = load_recruit(interaction.message.id)
        if not r:
            return await interaction.response.send_message("❌ この募集は無効だよ", ephemeral=True)
        if str(interaction.user.id) != r["creator_id"]:
            return await interaction.response.send_message("❌ 募集主だけが締め切れるよ", ephemeral=True)
        set_status(interaction.message.id, "closed")
        r, parts = load_recruit(interaction.message.id)
        await interaction.response.edit_message(embed=build_recruit_embed(r, parts), view=None)


async def _announce_full(channel, r, parts):
    """満員になった瞬間に参加者へメンション通知"""
    mentions = " ".join(f"<@{p['user_id']}>" for p in parts)
    emoji = GAME_EMOJI.get(r["game"], "🎮")
    try:
        await channel.send(f"{emoji} **{r['game']}** が満員になったよ！集合〜\n{mentions}")
    except discord.HTTPException:
        pass


class JoinTimeModal(discord.ui.Modal, title="何時なら参加できる？"):
    answer = discord.ui.TextInput(
        label="参加できる時間",
        placeholder="例: 21時〜 ／ 今すぐOK ／ バイト後22時",
        max_length=40,
        required=True,
    )

    def __init__(self, channel_id, message_id):
        super().__init__()
        self.channel_id = channel_id
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        note = str(self.answer.value).strip() or "時間指定あり"
        status, r, parts = try_join(self.message_id, interaction.user.id, note)
        await interaction.response.defer()
        if status == "invalid":
            return await interaction.followup.send("❌ この募集は無効だよ", ephemeral=True)
        if status == "closed":
            return await interaction.followup.send("🔒 この募集は締め切られてるよ", ephemeral=True)
        if status == "full":
            return await interaction.followup.send("🈵 満員だよ！", ephemeral=True)

        msg = interaction.channel.get_partial_message(int(self.message_id))
        await msg.edit(embed=build_recruit_embed(r, parts), view=RecruitView())
        verb = "時間を更新したよ" if status == "updated" else "参加したよ"
        await interaction.followup.send(f"✅ {verb}！（{note}）", ephemeral=True)
        if status == "ok_full":
            await _announce_full(interaction.channel, r, parts)


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
# 募集作成画面（本人だけに見えるephemeral・一時的なのでtimeoutでOK）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class CreateView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=300)
        self.author_id = str(author_id)
        self.game = None
        self.capacity = None
        self.start_time = None
        self.comment = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.author_id:
            await interaction.response.send_message("これはあなたの作成画面じゃないよ", ephemeral=True)
            return False
        return True

    def status_embed(self):
        game = self.game or "未選択"
        cap = f"@{self.capacity}募集（自分含め{self.capacity + 1}人）" if self.capacity else "未選択"
        embed = discord.Embed(
            title="🎮 募集を作成",
            description="項目を選んで **✅ 募集する** を押してね",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="ゲーム", value=game, inline=True)
        embed.add_field(name="募集人数", value=cap, inline=True)
        embed.add_field(name="開始時間", value=self.start_time or "指定なし", inline=True)
        embed.add_field(name="コメント", value=self.comment or "なし", inline=False)
        return embed

    async def refresh(self):
        if self.message:
            await self.message.edit(embed=self.status_embed(), view=self)

    @discord.ui.select(
        placeholder="🎮 ゲームを選択",
        row=0,
        options=[
            discord.SelectOption(label="VALORANT", value="VALORANT", emoji="🔫"),
            discord.SelectOption(label="LoL", value="LoL", emoji="⚔️"),
            discord.SelectOption(label="その他（自分で入力）", value="__other__", emoji="✏️"),
        ],
    )
    async def game_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        if select.values[0] == "__other__":
            return await interaction.response.send_modal(OtherGameModal(self))
        self.game = select.values[0]
        await interaction.response.edit_message(embed=self.status_embed(), view=self)

    @discord.ui.select(
        placeholder="👥 募集人数を選択",
        row=1,
        options=[
            discord.SelectOption(label=f"@{n}募集", value=str(n),
                                 description=f"自分含め{n + 1}人")
            for n in range(1, 10)
        ],
    )
    async def cap_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.capacity = int(select.values[0])
        await interaction.response.edit_message(embed=self.status_embed(), view=self)

    @discord.ui.button(label="開始時間・コメント", style=discord.ButtonStyle.secondary,
                       emoji="📝", row=2)
    async def details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DetailsModal(self))

    @discord.ui.button(label="募集する", style=discord.ButtonStyle.success,
                       emoji="✅", row=2)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.game or not self.capacity:
            return await interaction.response.send_message("⚠️ ゲームと人数を選んでね", ephemeral=True)
        await interaction.response.defer()

        # どこから募集しても、必ず固定チャンネルに投稿する
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
        # 募集主だけが入った状態のembedを先に組んでから投稿（@everyoneは1回だけ飛ぶ）
        r_preview = {"creator_id": creator_id, "game": self.game, "capacity": self.capacity,
                     "start_time": self.start_time, "comment": self.comment, "status": "open"}
        parts_preview = [{"user_id": creator_id, "time_note": self.start_time or ""}]
        msg = await target.send(
            content="@everyone",
            embed=build_recruit_embed(r_preview, parts_preview),
            view=RecruitView(),
            allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=False),
        )
        create_recruit(msg.id, target.id, interaction.guild.id, creator_id,
                       self.game, self.capacity, self.start_time, self.comment)
        add_participant(msg.id, creator_id, self.start_time or "")

        done = discord.Embed(title="✅ 募集を立てたよ！",
                             description=f"{target.mention} に投稿したよ",
                             color=discord.Color.green())
        await interaction.edit_original_response(embed=done, view=None)
        self.stop()


class OtherGameModal(discord.ui.Modal, title="ゲーム名を入力"):
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
        self.parent.game = str(self.gamename.value).strip()
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
        # 永続Viewを登録（再起動後もボタンが効くようにする）
        self.bot.add_view(PanelView())
        self.bot.add_view(RecruitView())

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
                "🔫 **VALORANT** ／ ⚔️ **LoL** ／ ✏️ **その他**（自由入力）\n"
                "参加はボタン1つ。`🕐時間を指定して参加` で「何時なら行けるか」も伝えられるよ。"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.channel.send(embed=embed, view=PanelView())
        await interaction.response.send_message("✅ 募集パネルを設置したよ！", ephemeral=True)


async def setup(bot):
    await bot.add_cog(LFG(bot))
