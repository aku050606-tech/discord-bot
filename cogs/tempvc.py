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
from cogs.member_access import allowed_roles, has_access, base_overwrites, sanitize_overwrites
from database import Database

db = Database()

K_HUB = "tempvc_hub"
K_CATEGORY = "tempvc_category"
K_PANEL = "tempvc_panel"
K_ACCESS_TIER = "tempvc_access_tier"

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


def _tier(channel):
    rows = db.list_temp_vcs(channel.guild.id)
    for channel_id, _, _, _, tier in rows:
        if channel_id == str(channel.id):
            return tier if tier in ('temp', 'full') else 'temp'
    return 'temp'


def _privacy_locked(channel):
    roles = allowed_roles(channel.guild, _tier(channel))
    flags = [channel.overwrites_for(role).connect for role in roles]
    if any(flag is False for flag in flags):
        return True
    if any(flag is True for flag in flags):
        return False
    # 旧BOTの部屋は参加区分ロール上書き自体がなかった
    return channel.overwrites_for(channel.guild.default_role).connect is False


async def _set_privacy(channel, locked):
    # @everyone は必ず拒否のまま。参加ロールの接続だけを切り替える。
    await channel.edit(overwrites=sanitize_overwrites(channel, _tier(channel),
                                                       open_connect=not locked),
                       reason='自由部屋：登録者限定の公開切替')


def _still_owner(interaction, channel):
    current, owner_id = _owner_vc(interaction.user)
    return (current == channel and owner_id == str(interaction.user.id)
            and has_access(interaction.user, _tier(channel)))


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
    if ch is not None and not has_access(interaction.user, _tier(ch)):
        await interaction.response.send_message('参加資格がないため操作できません。', ephemeral=True)
        return None
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
    tier = db.get_log_channel_id(str(guild.id), K_ACCESS_TIER)
    if tier not in ('temp', 'full') or not has_access(member, tier):
        raise ValueError('自由部屋の区分が未設定か、参加資格がありません。')
    overwrites = base_overwrites(guild, tier)
    # ユーザーにチャンネル管理権限を渡すと閲覧許可を変更できてしまう。
    # オーナー権限はDBで管理し、操作はBOT経由に限定する。
    overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True)
    ch = await guild.create_voice_channel(
        name=f"{member.display_name}の部屋",
        category=category, overwrites=overwrites,
        user_limit=hub.user_limit or 0)
    db.add_temp_vc(str(ch.id), str(guild.id), str(member.id), kind="main", access_tier=tier)
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
        try:
            locked = _privacy_locked(ch)
            await _set_privacy(ch, not locked)
        except (discord.HTTPException, ValueError) as exc:
            await interaction.response.send_message(f'⚠️ 公開範囲を変更できません：{exc}', ephemeral=True)
            return
        msg = ('🔓 この参加区分の登録者に公開しました。'
               if locked else '🔒 参加区分の登録者にも接続を禁止しました（信頼した人は入室可）。')
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
            try:
                await _set_privacy(ch, False)
                await interaction.response.send_message('🕓 待機室をOFFにしました。', ephemeral=True)
            except (discord.HTTPException, ValueError) as exc:
                await interaction.response.send_message(f'⚠️ 本体の公開設定に失敗しました：{exc}', ephemeral=True)
            return
        try:
            tier = _tier(ch)
            wov = base_overwrites(interaction.guild, tier)
            # 先に待機室を作り、成功時だけ本体の接続を閉じる。
            wc = await interaction.guild.create_voice_channel(
                name=f'🕓待機-{interaction.user.display_name}',
                category=ch.category, overwrites=wov)
            try:
                await _set_privacy(ch, True)
            except Exception:
                await wc.delete(reason='本体の施錠に失敗したため待機室を取り消し')
                raise
            db.add_temp_vc(str(wc.id), str(interaction.guild.id),
                           str(interaction.user.id), kind='waiting',
                           parent_id=str(ch.id), access_tier=tier)
            await interaction.response.send_message(
                f'🕓 待機室を作りました：{wc.mention}\n「✅ 信頼」で迎え入れられます。', ephemeral=True)
        except (discord.HTTPException, ValueError) as exc:
            await interaction.response.send_message(f'⚠️ 待機室を作れません：{exc}', ephemeral=True)

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
        if not has_access(interaction.user, _tier(ch)):
            await interaction.response.send_message('参加資格がないため権限を取得できません。', ephemeral=True)
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
            view_channel=True, connect=True))
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
        if not _still_owner(interaction, self.channel):
            await interaction.response.send_message('オーナー権限がありません。', ephemeral=True)
            return
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
        if not _still_owner(interaction, self.channel):
            await interaction.response.send_message('オーナー権限がありません。', ephemeral=True)
            return
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
        if not _still_owner(interaction, self.channel):
            await interaction.response.send_message('オーナー権限がありません。', ephemeral=True)
            return
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
        if not _still_owner(interaction, ch):
            await interaction.response.edit_message(content='オーナー権限がありません。', view=None)
            return
        if db.get_temp_vc_row(ch.id) is None:
            await interaction.response.edit_message(content='部屋がすでに削除されています。', view=None)
            return
        # discord.ui.UserSelect は User を返すことがあるので Guild 内メンバーに解決する
        resolved = guild.get_member(target.id)
        if resolved is None:
            try:
                resolved = await guild.fetch_member(target.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                resolved = None
        if self.action in ('trust', 'transfer') and not has_access(resolved, _tier(ch)):
            await interaction.response.edit_message(
                content='⚠️ この部屋の参加資格がない相手は信頼・権限譲渡できません。', view=None)
            return
        if resolved is not None:
            target = resolved
        try:
            if self.action == "trust":
                await ch.set_permissions(target, overwrite=discord.PermissionOverwrite(view_channel=True, connect=True))
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
                    view_channel=True, connect=True))
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
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return
        # 参加区分を失った人の例外許可を削除し、VCからも退室させる。
        for cid, _, _, _, tier in db.list_temp_vcs(after.guild.id):
            ch = after.guild.get_channel(int(cid))
            if not isinstance(ch, discord.VoiceChannel):
                continue
            if has_access(after, tier):
                continue
            if after in ch.overwrites:
                try:
                    await ch.set_permissions(after, overwrite=None,
                                             reason='参加区分の権限が解除されたため')
                except (discord.Forbidden, discord.HTTPException):
                    pass
            if after.voice and after.voice.channel == ch:
                try:
                    await after.move_to(None, reason='参加資格を失ったため')
                except (discord.Forbidden, discord.HTTPException):
                    pass

    @app_commands.command(name='自由部屋権限修復', description='既存の自由部屋と待機室を参加ロール限定に修正します')
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def secure_rooms(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, errors = 0, []
        for cid, _, _, _, tier in db.list_temp_vcs(interaction.guild.id):
            ch = interaction.guild.get_channel(int(cid))
            if not isinstance(ch, discord.VoiceChannel):
                continue
            try:
                locked = _privacy_locked(ch)
                await ch.edit(overwrites=sanitize_overwrites(ch, tier, open_connect=not locked),
                              reason='BOT管理の自由部屋を参加ロール限定に移行')
                ok += 1
            except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
                errors.append(f'{cid}: {exc}')
        msg = f'修復した自由部屋・待機室：{ok}件'
        if errors:
            msg += '\n⚠️ 失敗：' + '; '.join(errors[:5])
        await interaction.followup.send(msg, ephemeral=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        hub_id, cat_id, _ = _settings(str(guild.id))

        # 作成用VCに入った → 専用部屋を生成
        if after.channel and hub_id and str(after.channel.id) == hub_id:
            category = guild.get_channel(int(cat_id)) if cat_id and cat_id.isdigit() else None
            tier = db.get_log_channel_id(str(guild.id), K_ACCESS_TIER)
            if isinstance(category, discord.CategoryChannel) and tier in ('temp', 'full') \
                    and has_access(member, tier):
                try:
                    await _create_temp_vc(member, after.channel, category)
                except (discord.Forbidden, discord.HTTPException, ValueError):
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
