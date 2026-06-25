"""📱 スマホ（旧ウォレット）。

ホームにアプリを並べる：
  🏦 銀行    … 残高・デイリー・送金・ランキング（menu.WalletMenuView を流用）
  💬 LINE   … 指定相手に文章を送る／受信箱で読む（bot内メッセージ）
  🐦 ツイッター … admin指定chに“ツイート”を投稿

循環import回避のため、menu.py の関数はメソッド内で遅延importする。
"""
import time
from datetime import datetime, timezone, timedelta, date
import discord
from database import Database
from config import DAILY_AMOUNT

db = Database()
JST = timezone(timedelta(hours=9))

TWITTER_CHANNEL = "twitter_channel"   # log_config を流用して保存
_tweet_cooldown = {}                  # {user_id: last_epoch}
TWEET_COOLDOWN_SEC = 60


def _now_jst():
    return datetime.now(JST).strftime("%m/%d %H:%M")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ スマホ ホーム ━━
def build_phone_embed(user, guild) -> discord.Embed:
    gid = str(guild.id)
    bal = db.get_balance(str(user.id), gid)
    unread = db.line_unread_count(gid, str(user.id))
    daily_done = db.get_last_daily(str(user.id), gid) == str(date.today())
    now = datetime.now(JST)
    clock = now.strftime("%H:%M")
    batt = 70 + (now.minute % 30)  # 70〜99%で変化（演出）
    h = now.hour
    name = f"{user.display_name}さん"
    if h >= 23 or h < 4:
        greet = f"{name}、夜分遅くに"
    elif 4 <= h < 7:
        greet = f"{name}、お早うございます"
    elif 7 <= h < 11:
        greet = f"{name}、おはようございます"
    elif 11 <= h < 16:
        greet = f"{name}、ごきげんよう"
    elif 16 <= h < 19:
        greet = f"{name}、お疲れ様でございます"
    else:
        greet = f"{name}、こんばんは"

    status = (
        "```\n"
        f" {clock}              📶  🔋 {batt}% \n"
        "─────────────────────────\n"
        f" {greet} 📱\n"
        "```"
    )
    e = discord.Embed(title="📱 ＮＡＴＯ Ｐｈｏｎｅ", description=status, color=0x111827)
    e.add_field(name="🏦 銀行口座", value=f"残高 {bal:,}", inline=True)
    e.add_field(name="🏆 ランキング", value="順位を見る", inline=True)
    e.add_field(name="🎁 デイリー", value=("受取済み" if daily_done else "🔴 受取可能"), inline=True)
    e.add_field(name="📜 クエスト", value="日替わり任務", inline=True)
    e.add_field(name="💬 LINE", value=(f"📩 {unread}" if unread else "新着なし"), inline=True)
    e.add_field(name="🐦 ツイッター", value="つぶやく", inline=True)
    e.set_footer(text="タップでアプリを起動")
    return e


async def open_phone(interaction: discord.Interaction, uid: str = None):
    uid = uid or str(interaction.user.id)
    embed = build_phone_embed(interaction.user, interaction.guild)
    view = PhoneHomeView(uid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class PhoneBackView(discord.ui.View):
    """スマホに戻るボタンだけのView（アプリ表示用）。"""
    def __init__(self, user_id: str):
        super().__init__(timeout=600)
        self.user_id = str(user_id)

    @discord.ui.button(label="◀️ スマホに戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのスマホではありません", ephemeral=True)
            return
        await open_phone(interaction, self.user_id)


class PhoneHomeView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=900)
        self.user_id = str(user_id)

    async def _check(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのスマホではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏦 銀行口座", style=discord.ButtonStyle.success, row=0)
    async def bank(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.menu import WalletMenuView
        bal = db.get_balance(self.user_id, str(interaction.guild.id))
        embed = discord.Embed(title="🏦 銀行口座", color=discord.Color.gold())
        embed.add_field(name="現在の残高", value=f"**{bal:,}** ナトコイン", inline=False)
        embed.set_footer(text="残高の確認と送金ができます")
        await interaction.response.edit_message(embed=embed, view=WalletMenuView(self.user_id))

    @discord.ui.button(label="🏆 ランキング", style=discord.ButtonStyle.secondary, row=0)
    async def ranking(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.activitystats import open_stats
        await open_stats(interaction, self.user_id)

    @discord.ui.button(label="🎁 デイリー", style=discord.ButtonStyle.primary, row=0)
    async def daily(self, interaction, button):
        if not await self._check(interaction): return
        gid = str(interaction.guild.id)
        today = str(date.today())
        if db.get_last_daily(self.user_id, gid) == today:
            await interaction.response.send_message(
                "⏰ 今日はもう受け取っています！", ephemeral=True)
            return
        db.update_balance(self.user_id, gid, DAILY_AMOUNT)
        db.set_last_daily(self.user_id, gid, today)
        bal = db.get_balance(self.user_id, gid)
        embed = discord.Embed(
            title="🎁 デイリーボーナス！",
            description=f"**+{DAILY_AMOUNT:,} ナトコイン** ゲット！\n残高: **{bal:,}**",
            color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=PhoneBackView(self.user_id))

    @discord.ui.button(label="📜 クエスト", style=discord.ButtonStyle.primary, row=1)
    async def quests(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.quests import open_quests
        await open_quests(interaction, self.user_id)

    @discord.ui.button(label="💬 LINE", style=discord.ButtonStyle.primary, row=1)
    async def line(self, interaction, button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(
            embed=build_line_embed(interaction.user, interaction.guild),
            view=LineHomeView(self.user_id))

    @discord.ui.button(label="🐦 ツイッター", style=discord.ButtonStyle.primary, row=1)
    async def twitter(self, interaction, button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(
            embed=build_twitter_embed(interaction.guild),
            view=TwitterView(self.user_id))

    @discord.ui.button(label="🏠 メインメニューへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def home(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.menu import go_home
        await go_home(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ LINE ━━
def build_line_embed(user, guild) -> discord.Embed:
    unread = db.line_unread_count(str(guild.id), str(user.id))
    dm_on = db.get_line_dm(str(user.id), str(guild.id))
    e = discord.Embed(
        title="💬 LINE",
        description=("メッセージを送ったり、受信箱で読んだりできます。\n\n"
                     f"📩 未読：**{unread}** 件\n"
                     f"🔔 DM通知：{'**ON**' if dm_on else 'OFF'}"),
        color=0x06C755,
    )
    e.set_footer(text="「送る」で送信／「受信箱」で表示／「通知設定」でDM通知を切替")
    return e


class LineHomeView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=600)
        self.user_id = str(user_id)

    async def _check(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのLINEではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✉️ 送る", style=discord.ButtonStyle.success, row=0)
    async def send(self, interaction, button):
        if not await self._check(interaction): return
        v = discord.ui.View(timeout=120)
        v.add_item(LineRecipientSelect(self.user_id))
        await interaction.response.send_message("送る相手を選んでください：", view=v, ephemeral=True)

    @discord.ui.button(label="📥 受信箱", style=discord.ButtonStyle.primary, row=0)
    async def inbox(self, interaction, button):
        if not await self._check(interaction): return
        gid = str(interaction.guild.id)
        rows = db.get_line_inbox(gid, self.user_id, limit=15)
        if not rows:
            desc = "受信メッセージはありません。"
        else:
            lines = []
            for _id, from_id, body, ts, is_read in rows:
                if from_id == "announce":
                    name = "📣 お知らせ"
                else:
                    m = interaction.guild.get_member(int(from_id))
                    name = m.display_name if m else f"ID:{from_id}"
                mark = "" if is_read else "🆕 "
                short = body if len(body) <= 120 else body[:120] + "…"
                lines.append(f"{mark}**{name}**（{ts}）\n{short}")
            desc = "\n\n".join(lines)
        db.mark_line_all_read(gid, self.user_id)  # 開いたら既読
        embed = discord.Embed(title="📥 受信箱", description=desc[:4000], color=0x06C755)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔔 通知設定", style=discord.ButtonStyle.secondary, row=0)
    async def notify(self, interaction, button):
        if not await self._check(interaction): return
        v = LineNotifyView(self.user_id)
        await interaction.response.send_message(
            embed=build_notify_embed(db.get_line_dm(self.user_id, str(interaction.guild.id))),
            view=v, ephemeral=True)

    @discord.ui.button(label="◀️ スマホに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        if not await self._check(interaction): return
        await open_phone(interaction, self.user_id)


# ── DM通知 ON/OFF（個人ごと・デフォルトOFF・ONは確認警告つき）──
def build_notify_embed(enabled: bool) -> discord.Embed:
    if enabled:
        desc = ("現在：🔔 **ON**\n\n"
                "LINEが届くと、あなたのDMに通知が来ます。")
    else:
        desc = ("現在：🔕 **OFF**（初期設定）\n\n"
                "DM通知は届きません。受信箱には残るので、スマホ→LINEで確認できます。")
    return discord.Embed(title="🔔 LINE通知設定", description=desc, color=0x06C755)


class LineNotifyView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = str(user_id)

    @discord.ui.button(label="🔔 ON / 🔕 OFF を切替", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたの設定ではありません", ephemeral=True)
            return
        gid = str(interaction.guild.id)
        new_on = not db.get_line_dm(self.user_id, gid)
        db.set_line_dm(self.user_id, gid, new_on)
        if new_on:
            content = "⚠️ 通知を **ON** にしました。今後、LINEが届くとあなたのDMに通知が来ます。"
        else:
            content = "🔕 通知を **OFF** にしました。DM通知は届きません。"
        await interaction.response.edit_message(
            content=content, embed=build_notify_embed(new_on), view=self)


class LineRecipientSelect(discord.ui.UserSelect):
    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__(placeholder="相手を選択…", min_values=1, max_values=1)

    async def callback(self, interaction):
        target = self.values[0]
        if target.bot:
            await interaction.response.edit_message(content="Botには送れません。", view=None)
            return
        if str(target.id) == self.user_id:
            await interaction.response.edit_message(content="自分には送れません。", view=None)
            return
        await interaction.response.send_modal(LineComposeModal(self.user_id, target))


class LineComposeModal(discord.ui.Modal, title="✉️ メッセージを送る"):
    body = discord.ui.TextInput(label="メッセージ", style=discord.TextStyle.paragraph, max_length=1000)

    def __init__(self, from_id, target):
        super().__init__()
        self.from_id = from_id
        self.target = target

    async def on_submit(self, interaction):
        gid = str(interaction.guild.id)
        db.add_line_message(gid, self.from_id, str(self.target.id), self.body.value, _now_jst())
        # 相手がDM通知ONにしている場合のみ、ベストエフォートでDM通知
        if db.get_line_dm(str(self.target.id), gid):
            try:
                dm = discord.Embed(
                    title="💬 LINEに新着メッセージ",
                    description=(f"**{interaction.user.display_name}** さんからメッセージが届きました。\n"
                                f"（{interaction.guild.name}）\n\nスマホ→LINE→受信箱で確認できます。"),
                    color=0x06C755)
                await self.target.send(embed=dm)
            except (discord.Forbidden, discord.HTTPException):
                pass
        await interaction.response.edit_message(
            content=f"✅ {self.target.display_name} に送信しました。", view=None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ツイッター ━━
def build_twitter_embed(guild) -> discord.Embed:
    cid = db.get_log_channel_id(str(guild.id), TWITTER_CHANNEL)
    if cid and cid != "OFF":
        ch = guild.get_channel(int(cid))
        target = ch.mention if ch else "⚠️ 設定ch消失"
    else:
        target = "未設定（管理者が設定するまで投稿できません）"
    e = discord.Embed(
        title="🐦 ツイッター",
        description=f"つぶやくと、みんなが見るチャンネルに投稿されます。\n\n投稿先： {target}",
        color=0x1DA1F2,
    )
    e.set_footer(text="連投防止のため60秒に1回まで")
    return e


class TwitterView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=600)
        self.user_id = str(user_id)

    async def _check(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのスマホではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="📝 ツイートする", style=discord.ButtonStyle.primary, row=0)
    async def tweet(self, interaction, button):
        if not await self._check(interaction): return
        cid = db.get_log_channel_id(str(interaction.guild.id), TWITTER_CHANNEL)
        if not cid or cid == "OFF":
            await interaction.response.send_message(
                "⚠️ 投稿先chが未設定です。管理者に /admin →「🐦 ツイート投稿先」で設定してもらってください。",
                ephemeral=True)
            return
        last = _tweet_cooldown.get(self.user_id, 0)
        if time.time() - last < TWEET_COOLDOWN_SEC:
            wait = int(TWEET_COOLDOWN_SEC - (time.time() - last))
            await interaction.response.send_message(f"⏰ あと{wait}秒待ってね。", ephemeral=True)
            return
        await interaction.response.send_modal(TweetModal(self.user_id, cid))

    @discord.ui.button(label="◀️ スマホに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        if not await self._check(interaction): return
        await open_phone(interaction, self.user_id)


class TweetModal(discord.ui.Modal, title="📝 ツイート"):
    body = discord.ui.TextInput(label="いまどうしてる？", style=discord.TextStyle.paragraph, max_length=280)

    def __init__(self, user_id, channel_id):
        super().__init__()
        self.user_id = user_id
        self.channel_id = channel_id

    async def on_submit(self, interaction):
        ch = interaction.guild.get_channel(int(self.channel_id))
        if ch is None:
            await interaction.response.send_message("⚠️ 投稿先chが見つかりません。", ephemeral=True)
            return
        embed = discord.Embed(description=self.body.value, color=0x1DA1F2,
                              timestamp=discord.utils.utcnow())
        embed.set_author(name=f"{interaction.user.display_name} 🐦",
                         icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="ツイッター")
        try:
            await ch.send(embed=embed)
            _tweet_cooldown[self.user_id] = time.time()
            await interaction.response.send_message(f"✅ {ch.mention} に投稿しました！", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Botがそのchに投稿する権限がありません。", ephemeral=True)
