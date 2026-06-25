"""自由部屋（一時VC / Join-to-Create）システム。

仕組み：
 ・「作成用VC(hub)」に入ると、本人専用のVCを生成して移動＆オーナー化する。
 ・部屋が空になったら自動削除（待機部屋も連動削除）。
 ・「設定パネルch」に常設したコントロールパネルのボタンで、
   “押した人が今いる自由部屋” を操作する（TempVoice 風）。

設定（log_config テーブルを汎用KVとして流用。ログUIには出さない）：
   tempvc_hub      … 作成用VC
   tempvc_category … 生成先カテゴリ
   tempvc_panel    … パネル設置ch
"""
import discord
from discord.ext import commands
from discord import app_commands
from database import Database

db = Database()

K_HUB = "tempvc_hub"
K_CATEGORY = "tempvc_category"
K_PANEL = "tempvc_panel"

REGIONS = [
    ("🌐 自動", "auto"), ("🇯🇵 日本", "japan"), ("🇭🇰 香港", "hongkong"),
    ("🇸🇬 シンガポール", "singapore"), ("🇰🇷 韓国", "south-korea"),
    ("🇺🇸 US West", "us-west"), ("🇺🇸 US East", "us-east"),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 共通ヘルパー ━━
def _settings(guild_id):
    return (db.get_log_channel_id(guild_id, K_HUB),
            db.get_log_channel_id(guild_id, K_CATEGORY),
            db.get_log_channel_id(guild_id, K_PANEL))


def _owner_vc(member: discord.Member):
    """member が今いる自由部屋(main)と owner_id を返す。なければ (None, None)。"""
    vs = member.voice
    if vs is None or vs.channel is None:
        return None, None
    row = db.get_temp_vc_row(str(vs.channel.id))
    if row is None or row[1] != "main":
        return None, None
    return vs.channel, row[0]


async def _guard_owner(interaction):
    """オーナー本人だけ通す。OKなら channel、ダメなら None（通知済み）。"""
    ch, owner = _owner_vc(interaction.user)
    if ch is None:
        await interaction.response.send_message(
            "❌ 自由部屋に入ってから操作してください。", ephemeral=True)
        return None
    if owner != str(interaction.user.id):
        await interaction.response.send_message(
            "❌ オーナーだけが操作できます（不在なら「👑 権限取得」で引き継げます）。", ephemeral=True)
        return None
    return ch


async def _create_temp_vc(member: discord.Member, hub: discord.VoiceChannel, category):
    guild = member.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
        member: discord.PermissionOverwrite(
            connect=True, manage_channels=True, move_members=True,
            mute_members=True, deafen_members=True),
        guild.me: discord.PermissionOverwrite(
            connect=True, manage_channels=True, move_members=True, view_channel=True),
    }
    ch = await guild.create_voice_channel(
        name=f"{member.display_name}の部屋",
        category=category, overwrites=overwrites,
        user_limit=hub.user_limit or 0)
    db.add_temp_vc(str(ch.id), str(guild.id), str(member.id), kind="main")
    try:
        await member.move_to(ch)
    except discord.HTTPException:
        pass
    return ch


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ パネル ━━
def build_panel_embed(guild_name="このサーバー") -> discord.Embed:
    e = discord.Embed(
        title="🎙️ 自由部屋 コントロールパネル",
        description=(
            "この設定パネルで、あなたが今いる自由部屋を管理できます。\n"
            "操作したいボタンを押してください。\n\n"
            "🔹 まず「**作成用VC**」に入ると、自分の部屋が自動で作られます。\n"
            "🔹 部屋が空になると自動で消えます。"),
        color=0x5865F2,
    )
    e.add_field(name="使えるボタン", value=(
        "🔤 名前 ／ 👥 人数上限 ／ 🔒 プライバシー ／ 🕓 待機室 ／ 💬 チャット\n"
        "✅ 信頼 ／ 🚫 信頼解除 ／ ✉️ 招待 ／ 👢 キック ／ 🌐 地域\n"
        "⛔ ブロック ／ ♻️ ブロック解除 ／ 👑 権限取得 ／ 🤝 権限譲渡 ／ 🗑️ 消去"),
        inline=False)
    return e


class TempVoicePanel(discord.ui.View):
    """常設パネル（永続View）。custom_id で再起動後も動く。"""
    def __init__(self):
        super().__init__(timeout=None)

    # ── 行0 ──
    @discord.ui.button(emoji="🔤", label="名前", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="tvc:name")
    async def name(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await interaction.response.send_modal(RenameModal(ch))

    @discord.ui.button(emoji="👥", label="人数上限", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="tvc:limit")
    async def limit(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await interaction.response.send_modal(LimitModal(ch))

    @discord.ui.button(emoji="🔒", label="プライバシー", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="tvc:privacy")
    async def privacy(self, interaction, button):
        ch = await _guard_owner(interaction)
        if not ch:
            return
        ov = ch.overwrites_for(interaction.guild.default_role)
        locked = ov.connect is False
        ov.connect = None if locked else False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ov)
        msg = "🔓 公開しました（誰でも入れます）" if locked else "🔒 ロックしました（信頼した人だけ入れます）"
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(emoji="🕓", label="待機室", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="tvc:waiting")
    async def waiting(self, interaction, button):
        ch = await _guard_owner(interaction)
        if not ch:
            return
        existing = db.get_waiting_for(str(ch.id))
        if existing:
            wc = interaction.guild.get_channel(int(existing))
            if wc:
                try:
                    await wc.delete(reason="待機室OFF")
                except discord.HTTPException:
                    pass
            db.remove_temp_vc(existing)
            # 本体ロック解除
            ov = ch.overwrites_for(interaction.guild.default_role)
            ov.connect = None
            await ch.set_permissions(interaction.guild.default_role, overwrite=ov)
            await interaction.response.send_message("🕓 待機室をOFFにしました。", ephemeral=True)
            return
        # 待機室ON：本体をロックし、誰でも入れる待機VCを作る
        ov = ch.overwrites_for(interaction.guild.default_role)
        ov.connect = False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ov)
        wov = {interaction.guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
               interaction.guild.me: discord.PermissionOverwrite(connect=True, move_members=True)}
        wc = await interaction.guild.create_voice_channel(
            name=f"🕓待機-{interaction.user.display_name}",
            category=ch.category, overwrites=wov)
        db.add_temp_vc(str(wc.id), str(interaction.guild.id),
                       str(interaction.user.id), kind="waiting", parent_id=str(ch.id))
        await interaction.response.send_message(
            f"🕓 待機室を作りました：{wc.mention}\n「✅ 信頼」で迎え入れると本体に入れます。", ephemeral=True)

    @discord.ui.button(emoji="💬", label="チャット", style=discord.ButtonStyle.secondary,
                       row=0, custom_id="tvc:chat")
    async def chat(self, interaction, button):
        ch = await _guard_owner(interaction)
        if not ch:
            return
        ov = ch.overwrites_for(interaction.guild.default_role)
        hidden = ov.send_messages is False
        ov.send_messages = None if hidden else False
        await ch.set_permissions(interaction.guild.default_role, overwrite=ov)
        msg = "💬 チャットを有効にしました。" if hidden else "🤐 チャットを無効にしました。"
        await interaction.response.send_message(msg, ephemeral=True)

    # ── 行1 ──
    @discord.ui.button(emoji="✅", label="信頼", style=discord.ButtonStyle.success,
                       row=1, custom_id="tvc:trust")
    async def trust(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "trust")

    @discord.ui.button(emoji="🚫", label="信頼解除", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="tvc:untrust")
    async def untrust(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "untrust")

    @discord.ui.button(emoji="✉️", label="招待", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="tvc:invite")
    async def invite(self, interaction, button):
        ch = await _guard_owner(interaction)
        if not ch:
            return
        try:
            inv = await ch.create_invite(max_age=3600, max_uses=0, reason="自由部屋 招待")
            await interaction.response.send_message(
                f"✉️ 招待リンク（1時間有効）：\n{inv.url}", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("⚠️ 招待リンクを作れませんでした。", ephemeral=True)

    @discord.ui.button(emoji="👢", label="キック", style=discord.ButtonStyle.danger,
                       row=1, custom_id="tvc:kick")
    async def kick(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "kick")

    @discord.ui.button(emoji="🌐", label="地域", style=discord.ButtonStyle.secondary,
                       row=1, custom_id="tvc:region")
    async def region(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            v = discord.ui.View(timeout=60)
            v.add_item(RegionSelect(ch))
            await interaction.response.send_message("🌐 地域を選んでください：", view=v, ephemeral=True)

    # ── 行2 ──
    @discord.ui.button(emoji="⛔", label="ブロック", style=discord.ButtonStyle.danger,
                       row=2, custom_id="tvc:block")
    async def block(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "block")

    @discord.ui.button(emoji="♻️", label="ブロック解除", style=discord.ButtonStyle.secondary,
                       row=2, custom_id="tvc:unblock")
    async def unblock(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "unblock")

    @discord.ui.button(emoji="👑", label="権限取得", style=discord.ButtonStyle.primary,
                       row=2, custom_id="tvc:claim")
    async def claim(self, interaction, button):
        ch, owner = _owner_vc(interaction.user)
        if ch is None:
            await interaction.response.send_message(
                "❌ 自由部屋に入ってから操作してください。", ephemeral=True)
            return
        if owner == str(interaction.user.id):
            await interaction.response.send_message("もうあなたがオーナーです。", ephemeral=True)
            return
        # 現オーナーがVCにいなければ奪える
        owner_present = any(str(m.id) == owner for m in ch.members)
        if owner_present:
            await interaction.response.send_message(
                "❌ オーナーがまだ部屋にいます。", ephemeral=True)
            return
        db.set_temp_vc_owner(str(ch.id), str(interaction.user.id))
        await ch.set_permissions(interaction.user, overwrite=discord.PermissionOverwrite(
            connect=True, manage_channels=True, move_members=True,
            mute_members=True, deafen_members=True))
        await interaction.response.send_message("👑 オーナー権限を取得しました！", ephemeral=True)

    @discord.ui.button(emoji="🤝", label="権限譲渡", style=discord.ButtonStyle.primary,
                       row=2, custom_id="tvc:transfer")
    async def transfer(self, interaction, button):
        ch = await _guard_owner(interaction)
        if ch:
            await _send_user_picker(interaction, ch, "transfer")

    @discord.ui.button(emoji="🗑️", label="消去", style=discord.ButtonStyle.danger,
                       row=2, custom_id="tvc:delete")
    async def delete(self, interaction, button):
        ch = await _guard_owner(interaction)
        if not ch:
            return
        await interaction.response.send_message("🗑️ 部屋を消去します…", ephemeral=True)
        waiting = db.get_waiting_for(str(ch.id))
        if waiting:
            wc = interaction.guild.get_channel(int(waiting))
            if wc:
                try:
                    await wc.delete(reason="自由部屋 消去")
                except discord.HTTPException:
                    pass
            db.remove_temp_vc(waiting)
        db.remove_temp_vc(str(ch.id))
        try:
            await ch.delete(reason="オーナーが消去")
        except discord.HTTPException:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ サブUI ━━
class RenameModal(discord.ui.Modal, title="部屋の名前を変更"):
    new_name = discord.ui.TextInput(label="新しい名前", max_length=90)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction):
        try:
            await self.channel.edit(name=self.new_name.value)
            await interaction.response.send_message(
                f"🔤 名前を「{self.new_name.value}」に変更しました。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("⚠️ 変更できませんでした。", ephemeral=True)


class LimitModal(discord.ui.Modal, title="人数上限を設定"):
    limit = discord.ui.TextInput(label="人数上限（0で無制限・最大99）", placeholder="例: 5", max_length=2)

    def __init__(self, channel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction):
        try:
            n = max(0, min(99, int(self.limit.value)))
        except ValueError:
            await interaction.response.send_message("⚠️ 数字を入力してください。", ephemeral=True)
            return
        await self.channel.edit(user_limit=n)
        txt = "無制限" if n == 0 else f"{n}人"
        await interaction.response.send_message(f"👥 人数上限を {txt} にしました。", ephemeral=True)


class RegionSelect(discord.ui.Select):
    def __init__(self, channel):
        self.channel = channel
        opts = [discord.SelectOption(label=lbl, value=val) for lbl, val in REGIONS]
        super().__init__(placeholder="地域を選択…", options=opts)

    async def callback(self, interaction):
        val = self.values[0]
        region = None if val == "auto" else val
        try:
            await self.channel.edit(rtc_region=region)
            shown = "自動" if region is None else val
            await interaction.response.send_message(f"🌐 地域を「{shown}」にしました。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("⚠️ 変更できませんでした。", ephemeral=True)


async def _send_user_picker(interaction, channel, action):
    labels = {
        "trust": "✅ 信頼する人を選択", "untrust": "🚫 信頼解除する人を選択",
        "kick": "👢 キックする人を選択", "block": "⛔ ブロックする人を選択",
        "unblock": "♻️ ブロック解除する人を選択", "transfer": "🤝 新オーナーを選択",
    }
    v = discord.ui.View(timeout=60)
    v.add_item(TempVCUserSelect(channel, action))
    await interaction.response.send_message(labels.get(action, "ユーザーを選択"), view=v, ephemeral=True)


class TempVCUserSelect(discord.ui.UserSelect):
    def __init__(self, channel, action):
        self.channel = channel
        self.action = action
        super().__init__(placeholder="ユーザーを選択…", min_values=1, max_values=1)

    async def callback(self, interaction):
        target = self.values[0]
        ch = self.channel
        guild = interaction.guild
        try:
            if self.action == "trust":
                await ch.set_permissions(target, overwrite=discord.PermissionOverwrite(connect=True))
                # 待機室にいたら本体へ迎え入れる
                waiting = db.get_waiting_for(str(ch.id))
                if waiting and isinstance(target, discord.Member) and target.voice and \
                        target.voice.channel and str(target.voice.channel.id) == waiting:
                    try:
                        await target.move_to(ch)
                    except discord.HTTPException:
                        pass
                msg = f"✅ {target.display_name} を信頼しました。"
            elif self.action == "untrust":
                await ch.set_permissions(target, overwrite=None)
                msg = f"🚫 {target.display_name} の信頼を解除しました。"
            elif self.action == "kick":
                m = guild.get_member(target.id)
                if m and m.voice and m.voice.channel and m.voice.channel.id == ch.id:
                    await m.move_to(None)
                    msg = f"👢 {target.display_name} を退出させました。"
                else:
                    msg = "その人はこの部屋にいません。"
            elif self.action == "block":
                await ch.set_permissions(target, overwrite=discord.PermissionOverwrite(connect=False))
                m = guild.get_member(target.id)
                if m and m.voice and m.voice.channel and m.voice.channel.id == ch.id:
                    await m.move_to(None)
                msg = f"⛔ {target.display_name} をブロックしました。"
            elif self.action == "unblock":
                await ch.set_permissions(target, overwrite=None)
                msg = f"♻️ {target.display_name} のブロックを解除しました。"
            elif self.action == "transfer":
                db.set_temp_vc_owner(str(ch.id), str(target.id))
                await ch.set_permissions(target, overwrite=discord.PermissionOverwrite(
                    connect=True, manage_channels=True, move_members=True,
                    mute_members=True, deafen_members=True))
                msg = f"🤝 {target.display_name} にオーナーを譲渡しました。"
            else:
                msg = "不明な操作です。"
        except discord.Forbidden:
            msg = "⚠️ Botの権限が足りません（ロールの管理／メンバーの移動）。"
        await interaction.response.edit_message(content=msg, view=None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Cog ━━
class TempVC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._view_added = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._view_added:
            self.bot.add_view(TempVoicePanel())  # 永続View登録
            self._view_added = True

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        hub_id, cat_id, _ = _settings(str(guild.id))

        # 作成用VCに入った → 専用部屋を生成
        if after.channel and hub_id and str(after.channel.id) == hub_id:
            category = guild.get_channel(int(cat_id)) if cat_id else after.channel.category
            try:
                await _create_temp_vc(member, after.channel, category)
            except discord.Forbidden:
                pass

        # 抜けた部屋が空の自由部屋なら削除
        if before.channel:
            row = db.get_temp_vc_row(str(before.channel.id))
            if row is not None:
                remaining = [m for m in before.channel.members if not m.bot]
                if not remaining:
                    # main を消すときは紐づく待機室も消す
                    if row[1] == "main":
                        waiting = db.get_waiting_for(str(before.channel.id))
                        if waiting:
                            wc = guild.get_channel(int(waiting))
                            if wc:
                                try:
                                    await wc.delete(reason="親VC削除")
                                except discord.HTTPException:
                                    pass
                            db.remove_temp_vc(waiting)
                    db.remove_temp_vc(str(before.channel.id))
                    try:
                        await before.channel.delete(reason="自由部屋が空になった")
                    except discord.HTTPException:
                        pass


async def setup(bot):
    await bot.add_cog(TempVC(bot))
