import asyncio
import io
import os
import textwrap
import discord
from discord.ext import commands
from database import Database
from PIL import Image, ImageDraw, ImageFont, ImageOps

db = Database()

K_TEMP_ROLE = 'member_temp_role'
K_FULL_ROLE = 'member_full_role'
K_HOURS = 'member_required_hours'
K_PANEL_CHANNEL = 'member_panel_channel'
K_PANEL_MESSAGE = 'member_panel_message'
K_PROFILE_CHANNEL = 'member_profile_channel'
K_PROFILE_DISPLAY_MODE = 'member_profile_display_mode'
K_HOURS_ENABLED = 'member_hours_enabled'
K_STICKY_CHANNEL = 'sticky_channel'
K_STICKY_MESSAGE = 'sticky_message'
K_STICKY_CONTENT = 'sticky_content'

MBTIS = ['INTJ','INTP','ENTJ','ENTP','INFJ','INFP','ENFJ','ENFP','ISTJ','ISFJ','ESTJ','ESFJ','ISTP','ISFP','ESTP','ESFP','未診断']
GAMES = ['League of Legends','VALORANT','Apex Legends','Minecraft','Steamゲーム','雑談メイン']


def _kv(gid, key):
    return db.get_log_channel_id(str(gid), key)

def _set(gid, key, value):
    db.set_log_channel(str(gid), key, str(value))


def panel_embed():
    return discord.Embed(
        title='👥 サーバー参加登録',
        description=(
            'このパネルだけで参加登録が完了します。\n\n'
            '① **ルールを確認して同意**\n'
            '② **MBTIを選択**\n'
            '③ **遊ぶGAMEを選択**（複数可）\n'
            '④ **名前・趣味・一言を記入**\n\n'
            '登録内容は後からいつでも変更できます。必要項目を満たすと本メンバーロールが付与されます。'
        ), color=discord.Color.blurple())


class RuleConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
    @discord.ui.button(label='✅ ルールを読み、同意します', style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        db.set_member_rule(str(interaction.guild.id), str(interaction.user.id), 1)
        await interaction.response.edit_message(content='✅ ルール同意を記録しました。', embed=None, view=None)
        await report_promotion(interaction)


class MBTISelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='MBTIを選択…', options=[discord.SelectOption(label=x, value=x) for x in MBTIS])
    async def callback(self, interaction):
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), mbti=self.values[0])
        await interaction.response.send_message(f'✅ MBTIを **{self.values[0]}** に設定しました。', ephemeral=True)
        await publish_profile(interaction.user)
        await report_promotion(interaction)

class MBTIView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180); self.add_item(MBTISelect())

class GameSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder='遊ぶGAMEを選択（複数可）…', min_values=1, max_values=len(GAMES), options=[discord.SelectOption(label=x, value=x) for x in GAMES])
    async def callback(self, interaction):
        games = ','.join(self.values)
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), games=games)
        await interaction.response.send_message('✅ GAMEを設定しました：' + '・'.join(self.values), ephemeral=True)
        await publish_profile(interaction.user)
        await report_promotion(interaction)

class CustomGameModal(discord.ui.Modal, title='GAMEを自由入力'):
    games = discord.ui.TextInput(label='遊んでいるゲーム', placeholder='例：原神、Escape from Tarkov、雀魂', max_length=300)
    def __init__(self, current=''):
        super().__init__()
        self.games.default = current or ''
    async def on_submit(self, interaction):
        value = self.games.value.strip()
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), games=value)
        await interaction.response.send_message(f'✅ GAMEを **{value}** に設定しました。', ephemeral=True)
        await publish_profile(interaction.user)
        await report_promotion(interaction)

class GameView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180); self.add_item(GameSelect())
    @discord.ui.button(label='✍️ 自分で入力', style=discord.ButtonStyle.success, row=1)
    async def custom(self, interaction, button):
        p = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(CustomGameModal(p.get('games') or ''))

class ProfileModal(discord.ui.Modal, title='プロフィール入力・編集'):
    nickname = discord.ui.TextInput(label='名前・呼び方', max_length=50)
    hobby = discord.ui.TextInput(label='趣味', max_length=200)
    comment = discord.ui.TextInput(label='一言', style=discord.TextStyle.paragraph, max_length=300)
    def __init__(self, current=None):
        super().__init__()
        if current:
            self.nickname.default = current.get('nickname') or ''
            self.hobby.default = current.get('hobby') or ''
            self.comment.default = current.get('comment') or ''
    async def on_submit(self, interaction):
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), nickname=self.nickname.value, hobby=self.hobby.value, comment=self.comment.value)
        await interaction.response.send_message('✅ プロフィールを保存しました。', ephemeral=True)
        await publish_profile(interaction.user)
        await report_promotion(interaction)

class RegistrationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label='📖 ルール確認', style=discord.ButtonStyle.secondary, custom_id='member:rules', row=0)
    async def rules(self, interaction, button):
        await interaction.response.send_message('サーバーのルールを最後まで確認したうえで、下のボタンを押してください。', view=RuleConfirmView(), ephemeral=True)
    @discord.ui.button(label='🧠 MBTI', style=discord.ButtonStyle.primary, custom_id='member:mbti', row=0)
    async def mbti(self, interaction, button):
        await interaction.response.send_message('MBTIを選択してください。', view=MBTIView(), ephemeral=True)
    @discord.ui.button(label='🎮 GAME', style=discord.ButtonStyle.primary, custom_id='member:games', row=0)
    async def games(self, interaction, button):
        await interaction.response.send_message('遊ぶゲームを選択してください。', view=GameView(), ephemeral=True)
    @discord.ui.button(label='✏️ プロフィール', style=discord.ButtonStyle.success, custom_id='member:profile', row=1)
    async def profile(self, interaction, button):
        cur = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id))
        await interaction.response.send_modal(ProfileModal(cur))
    @discord.ui.button(label='✅ 登録状況', style=discord.ButtonStyle.secondary, custom_id='member:status', row=1)
    async def status(self, interaction, button):
        p = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        rule = db.get_member_rule(str(interaction.guild.id), str(interaction.user.id))
        secs = db.get_vc_seconds(interaction.user.id, interaction.guild.id)
        need = float(_kv(interaction.guild.id, K_HOURS) or 0)
        hours_on = (_kv(interaction.guild.id, K_HOURS_ENABLED) or 'OFF') == 'ON'
        lines = [
            f"ルール：{'✅' if rule else '❌'}",
            f"MBTI：{'✅ ' + p.get('mbti','') if p.get('mbti') else '❌'}",
            f"GAME：{'✅ ' + (p.get('games') or '').replace(',', '・') if p.get('games') else '❌'}",
            f"プロフィール：{'✅' if p.get('nickname') and p.get('hobby') and p.get('comment') else '❌'}",
            f"VC時間条件：{'ON' if hours_on else 'OFF'}" + (f"（{secs/3600:.1f} / {need:g}時間 {'✅' if secs >= need*3600 else '❌'}）" if hours_on else ''),
        ]
        full_id = _kv(interaction.guild.id, K_FULL_ROLE)
        full_role = interaction.guild.get_role(int(full_id)) if full_id and full_id != 'OFF' and str(full_id).isdigit() else None
        lines.append(f"正式ロール：{full_role.mention if full_role else '❌ 未設定または消失'}")
        await interaction.response.send_message('\n'.join(lines), ephemeral=True)
        await report_promotion(interaction)


def complete(member):
    gid, uid = str(member.guild.id), str(member.id)
    p = db.get_member_profile(gid, uid) or {}
    if not db.get_member_rule(gid, uid): return False
    if not p.get('mbti') or not p.get('games') or not p.get('nickname') or not p.get('hobby') or not p.get('comment'): return False
    if (_kv(gid, K_HOURS_ENABLED) or 'OFF') != 'ON':
        return True
    try: need = float(_kv(gid, K_HOURS) or 0) * 3600
    except ValueError: need = 0
    return db.get_vc_seconds(uid, gid) >= need

async def try_promote(member):
    """参加条件を確認し、正式メンバーロールを付与する。

    戻り値: (状態, メッセージ)
      incomplete: 条件未達
      already: 既に付与済み
      added: 付与成功
      error: 設定・権限・Discord APIエラー
    """
    if not isinstance(member, discord.Member):
        return 'error', 'メンバー情報を取得できませんでした。'
    if not complete(member):
        return 'incomplete', 'まだ登録条件を満たしていません。'

    guild = member.guild
    gid = str(guild.id)
    full_id = _kv(gid, K_FULL_ROLE)
    if not full_id or full_id == 'OFF':
        return 'error', '正式メンバーロールが管理者メニューで設定されていません。'

    try:
        full = guild.get_role(int(full_id))
    except (TypeError, ValueError):
        full = None
    if full is None:
        return 'error', '設定された正式メンバーロールが見つかりません。管理者メニューで設定し直してください。'
    if full in member.roles:
        return 'already', f'{full.mention} はすでに付与されています。'

    me = guild.me
    if me is None:
        return 'error', 'BOT自身のメンバー情報を取得できませんでした。'
    if not me.guild_permissions.manage_roles:
        return 'error', 'BOTに「ロールの管理」権限がありません。'
    if full >= me.top_role:
        return 'error', f'{full.mention} がBOTの一番上のロール以上にあります。サーバー設定でBOTロールを上へ移動してください。'

    try:
        await member.add_roles(full, reason='参加登録の全条件達成')
        return 'added', f'登録完了！ {full.mention} を付与しました。'
    except discord.Forbidden:
        return 'error', 'Discordにロール付与を拒否されました。BOTの権限とロール順を確認してください。'
    except discord.HTTPException as exc:
        return 'error', f'ロール付与中にDiscordエラーが発生しました：{exc}'


async def report_promotion(interaction):
    status, message = await try_promote(interaction.user)
    if status in {'added', 'error'}:
        try:
            await interaction.followup.send(('✅ ' if status == 'added' else '⚠️ ') + message, ephemeral=True)
        except (discord.HTTPException, discord.NotFound):
            pass
    return status, message


def _profile_card_text(member, p):
    nickname = p.get('nickname') or member.display_name
    games = (p.get('games') or '未設定').replace(',', '・')
    hobby = p.get('hobby') or '未設定'
    mbti = p.get('mbti') or '未設定'
    comment = p.get('comment') or '未設定'
    divider = '◾︎=========================◾︎'
    return (
        f'{divider}\n\n'
        f'**【名前】**  **{nickname}**  {member.mention}\n\n'
        f'**【趣味】**  {hobby}\n\n'
        f'**【ゲーム】**  {games}\n\n'
        f'**【MBTI】**  {mbti}\n\n'
        f'**【一言】**  {comment}\n\n'
        f'{divider}'
    )


def directory_profile_embed(member, p):
    nickname = p.get('nickname') or member.display_name
    e = discord.Embed(title=nickname, description=_profile_card_text(member, p), color=discord.Color.blurple())
    e.set_thumbnail(url=member.display_avatar.url)
    return e


def _profile_mode(guild_id):
    return (db.get_setting_text(str(guild_id), K_PROFILE_DISPLAY_MODE) or 'EMBED').upper()


def _find_japanese_font(size, bold=False):
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf' if bold else '/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc' if bold else '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        'C:/Windows/Fonts/YuGothB.ttc' if bold else 'C:/Windows/Fonts/YuGothR.ttc',
        'C:/Windows/Fonts/meiryob.ttc' if bold else 'C:/Windows/Fonts/meiryo.ttc',
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    raise RuntimeError('日本語フォントが見つかりません。Noto Sans CJKをインストールしてください。')


def _fit_text(draw, text, max_width, max_size, min_size=22, bold=False):
    for size in range(max_size, min_size - 1, -2):
        font = _find_japanese_font(size, bold=bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
    return _find_japanese_font(min_size, bold=bold)


def _wrap_by_width(draw, text, font, max_width, max_lines=2):
    text = (text or '').strip()
    if not text:
        return ['未設定']
    lines = []
    current = ''
    for ch in text:
        trial = current + ch
        if current and draw.textbbox((0, 0), trial, font=font)[2] > max_width:
            lines.append(current)
            current = ch
            if len(lines) >= max_lines - 1:
                break
        else:
            current = trial
    remaining_start = sum(len(x) for x in lines)
    if len(lines) < max_lines:
        remaining = text[remaining_start:]
        current = ''
        for ch in remaining:
            trial = current + ch
            if current and draw.textbbox((0, 0), trial + '…', font=font)[2] > max_width:
                current += '…'
                break
            current = trial
        if current:
            lines.append(current)
    return lines[:max_lines]


async def build_profile_card_file(member, p):
    width, height = 1200, 520
    img = Image.new('RGB', (width, height), '#10151f')
    draw = ImageDraw.Draw(img)

    # 無難な濃紺グラデーション背景
    top = (18, 28, 46)
    bottom = (10, 14, 23)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, width, y), fill=color)

    # 控えめな装飾
    draw.ellipse((820, -260, 1320, 240), fill=(24, 49, 91))
    draw.ellipse((930, -180, 1280, 170), fill=(18, 35, 64))
    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=30, outline=(70, 102, 165), width=3)
    draw.rounded_rectangle((360, 155, 1160, 460), radius=22, fill=(9, 14, 23), outline=(45, 62, 91), width=2)

    # アバター
    try:
        avatar_bytes = await member.display_avatar.with_size(256).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert('RGB')
        avatar = ImageOps.fit(avatar, (250, 250), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (250, 250), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 249, 249), fill=255)
        ring = Image.new('RGB', (270, 270), '#365eff')
        ring_mask = Image.new('L', (270, 270), 0)
        ImageDraw.Draw(ring_mask).ellipse((0, 0, 269, 269), fill=255)
        img.paste(ring, (55, 82), ring_mask)
        img.paste(avatar, (65, 92), mask)
    except Exception:
        draw.ellipse((55, 82, 325, 352), fill=(54, 94, 255))
        draw.ellipse((65, 92, 315, 342), fill=(36, 44, 61))

    label_font = _find_japanese_font(25, bold=True)
    value_font = _find_japanese_font(29)
    small_font = _find_japanese_font(21)
    name = p.get('nickname') or member.display_name
    name_font = _fit_text(draw, name, 710, 58, 34, bold=True)

    draw.text((365, 62), 'MEMBER PROFILE', font=small_font, fill=(116, 151, 255))
    draw.text((365, 92), name, font=name_font, fill='white')
    draw.text((368, 145), f'@{member.name}', font=small_font, fill=(145, 157, 181))

    fields = [
        ('【趣味】', p.get('hobby') or '未設定'),
        ('【ゲーム】', (p.get('games') or '未設定').replace(',', '・')),
        ('【MBTI】', p.get('mbti') or '未設定'),
        ('【一言】', p.get('comment') or '未設定'),
    ]
    positions = [(395, 190), (780, 190), (395, 300), (780, 300)]
    box_w = 330
    for (label, value), (x, y) in zip(fields, positions):
        draw.text((x, y), label, font=label_font, fill=(122, 158, 255))
        lines = _wrap_by_width(draw, str(value), value_font, box_w, max_lines=2)
        for i, line in enumerate(lines):
            draw.text((x, y + 42 + i * 37), line, font=value_font, fill=(238, 242, 250))

    draw.text((65, 402), 'プロフィールは本人がいつでも更新できます', font=small_font, fill=(121, 136, 160))
    draw.text((65, 446), member.guild.name[:35], font=small_font, fill=(98, 124, 190))

    out = io.BytesIO()
    img.save(out, format='PNG', optimize=True)
    out.seek(0)
    return discord.File(out, filename=f'profile_{member.id}.png')


class ProfileLinkView(discord.ui.View):
    def __init__(self, member_id):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label='プロフィールを開く', style=discord.ButtonStyle.link,
                                        url=f'https://discord.com/users/{member_id}'))


async def publish_profile(member):
    if not isinstance(member, discord.Member):
        return
    gid, uid = str(member.guild.id), str(member.id)
    cid = _kv(gid, K_PROFILE_CHANNEL)
    if not cid or cid == 'OFF':
        return
    channel = member.guild.get_channel(int(cid))
    if not isinstance(channel, discord.TextChannel):
        return
    p = db.get_member_profile(gid, uid) or {}
    if not (p.get('nickname') and p.get('hobby') and p.get('comment')):
        return

    key = f'member_profile_message:{uid}'
    oldid = db.get_setting_text(gid, key)
    mode = _profile_mode(gid)
    msg = None
    if oldid:
        try:
            msg = await channel.fetch_message(int(oldid))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
            msg = None

    try:
        if mode == 'IMAGE':
            file = await build_profile_card_file(member, p)
            if msg:
                await msg.edit(content=member.mention, embed=None, attachments=[file], view=ProfileLinkView(member.id))
            else:
                msg = await channel.send(content=member.mention, file=file, view=ProfileLinkView(member.id))
        else:
            embed = directory_profile_embed(member, p)
            if msg:
                await msg.edit(content=None, embed=embed, attachments=[], view=None)
            else:
                msg = await channel.send(embed=embed)
        db.set_setting_text(gid, key, str(msg.id))
    except (discord.Forbidden, discord.HTTPException, RuntimeError):
        raise

async def regenerate_all_profiles(guild):
    """プロフィール欄に登録済みプロフィールを新規投稿または既存メッセージ更新する。"""
    gid = str(guild.id)
    cid = _kv(gid, K_PROFILE_CHANNEL)
    if not cid or cid == 'OFF':
        return 0, 0, ['プロフィール欄チャンネルが未設定です。']
    channel = guild.get_channel(int(cid))
    if not isinstance(channel, discord.TextChannel):
        return 0, 0, ['設定されたプロフィール欄チャンネルが見つかりません。']

    updated = 0
    skipped = 0
    errors = []
    for user_id, p in db.get_all_member_profiles(gid):
        member = guild.get_member(int(user_id)) if user_id.isdigit() else None
        if member is None:
            skipped += 1
            continue
        if not (p.get('nickname') and p.get('hobby') and p.get('comment')):
            skipped += 1
            continue
        try:
            await publish_profile(member)
            updated += 1
        except Exception as exc:
            errors.append(f'{member.display_name}: {type(exc).__name__}')
        await asyncio.sleep(0.15)
    return updated, skipped, errors

def profile_embed(member, p):
    e = discord.Embed(
        title=f'{p.get("nickname") or member.display_name} さんがVCに参加しました',
        description=_profile_card_text(member, p),
        color=discord.Color.green(),
    )
    e.set_thumbnail(url=member.display_avatar.url)
    return e


class MemberOnboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.profile_messages = {}
        self.sticky_tasks = {}
        bot.add_view(RegistrationPanel())

    @commands.Cog.listener()
    async def on_member_join(self, member):
        rid = _kv(member.guild.id, K_TEMP_ROLE)
        if rid and rid != 'OFF':
            role = member.guild.get_role(int(rid))
            if role:
                try: await member.add_roles(role, reason='新規参加：仮メンバー')
                except (discord.Forbidden, discord.HTTPException): pass

    async def _delete_profile(self, guild_id, user_id):
        key=(guild_id,user_id); item=self.profile_messages.pop(key,None)
        if item:
            try: await item.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException): pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or before.channel == after.channel: return
        await self._delete_profile(member.guild.id, member.id)
        if after.channel is not None:
            p = db.get_member_profile(str(member.guild.id), str(member.id))
            if p:
                try:
                    msg = await after.channel.send(embed=profile_embed(member,p))
                    self.profile_messages[(member.guild.id,member.id)] = msg
                except (AttributeError, discord.Forbidden, discord.HTTPException): pass
        await try_promote(member)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot: return
        gid=str(message.guild.id); cid=_kv(gid,K_STICKY_CHANNEL)
        if not cid or str(message.channel.id)!=cid: return
        old=self.sticky_tasks.get(message.channel.id)
        if old and not old.done(): old.cancel()
        self.sticky_tasks[message.channel.id]=asyncio.create_task(self._bump_sticky(message.channel))

    async def _bump_sticky(self, channel):
        try:
            await asyncio.sleep(5)
            gid=str(channel.guild.id); oldid=_kv(gid,K_STICKY_MESSAGE); content=db.get_setting_text(gid,K_STICKY_CONTENT)
            if not content: return
            if oldid:
                try: await (await channel.fetch_message(int(oldid))).delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException): pass
            try:
                import json
                data=json.loads(content)
                embed=discord.Embed(title=data.get('title') or '📣 お知らせ', description=data.get('body') or '', color=0xC8A24B)
                msg=await channel.send(embed=embed)
            except Exception:
                msg=await channel.send(content)
            _set(gid,K_STICKY_MESSAGE,msg.id)
        except asyncio.CancelledError: pass

async def setup(bot):
    await bot.add_cog(MemberOnboarding(bot))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 管理者用設定UI

def admin_embed(guild):
    gid=str(guild.id)
    def role_text(key):
        rid=_kv(gid,key)
        if not rid or rid=='OFF': return '未設定'
        r=guild.get_role(int(rid)); return r.mention if r else '⚠️ 消失'
    panel=_kv(gid,K_PANEL_CHANNEL); profile_ch=_kv(gid,K_PROFILE_CHANNEL)
    pch=guild.get_channel(int(panel)) if panel and panel!='OFF' else None
    prof=guild.get_channel(int(profile_ch)) if profile_ch and profile_ch!='OFF' else None
    return discord.Embed(
        title='👥 メンバー管理', color=discord.Color.blurple(),
        description=(
            f'仮メンバー：{role_text(K_TEMP_ROLE)}\n'
            f'正式メンバー：{role_text(K_FULL_ROLE)}\n'
            f'VC時間条件：{_kv(gid,K_HOURS_ENABLED) or "OFF"}（{_kv(gid,K_HOURS) or "0"}時間）\n'
            f'登録パネル：{pch.mention if pch else "未設置"}\n'
            f'プロフィール欄：{prof.mention if prof else "未設定"}\n'
            f'プロフィール表示：{"画像カード" if _profile_mode(gid) == "IMAGE" else "通常Embed"}\n\n'
            '上から順に設定してください。登録パネルは1チャンネル・1パネルで完結します。'
        ))

class TempRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder='① 仮メンバーロールを選択', min_values=1, max_values=1, row=0)

    async def callback(self, interaction):
        role_id = self.values[0].id
        _set(interaction.guild.id, K_TEMP_ROLE, role_id)
        await interaction.response.edit_message(embed=admin_embed(interaction.guild), view=MemberAdminView())


class FullRoleSelect(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(placeholder='② 正式メンバーロールを選択', min_values=1, max_values=1, row=1)

    async def callback(self, interaction):
        role_id = self.values[0].id
        _set(interaction.guild.id, K_FULL_ROLE, role_id)
        await interaction.response.edit_message(embed=admin_embed(interaction.guild), view=MemberAdminView())


class PanelChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder='③ 登録パネルを設置するチャンネル', min_values=1, max_values=1,
                         channel_types=[discord.ChannelType.text], row=2)

    async def callback(self, interaction):
        # ChannelSelectの値が部分オブジェクトになる環境でも確実にGuildChannelへ解決する
        selected_id = self.values[0].id
        channel = interaction.guild.get_channel(selected_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message('⚠️ テキストチャンネルを取得できませんでした。', ephemeral=True)
            return

        await interaction.response.defer()
        try:
            old_channel_id = _kv(interaction.guild.id, K_PANEL_CHANNEL)
            old_message_id = _kv(interaction.guild.id, K_PANEL_MESSAGE)
            if old_channel_id and old_message_id and old_channel_id != 'OFF' and old_message_id != 'OFF':
                old_channel = interaction.guild.get_channel(int(old_channel_id))
                if old_channel:
                    try:
                        old_message = await old_channel.fetch_message(int(old_message_id))
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError):
                        pass

            message = await channel.send(embed=panel_embed(), view=RegistrationPanel())
            _set(interaction.guild.id, K_PANEL_CHANNEL, channel.id)
            _set(interaction.guild.id, K_PANEL_MESSAGE, message.id)
            await interaction.edit_original_response(embed=admin_embed(interaction.guild), view=MemberAdminView())
        except discord.Forbidden:
            await interaction.followup.send('⚠️ そのチャンネルで「メッセージを送信」「埋め込みリンク」の権限がありません。', ephemeral=True)
        except discord.HTTPException as exc:
            await interaction.followup.send(f'⚠️ 登録パネルの設置に失敗しました：{exc}', ephemeral=True)


class ProfileChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder='④ プロフィール欄チャンネルを選択', min_values=1, max_values=1,
                         channel_types=[discord.ChannelType.text], row=3)
    async def callback(self, interaction):
        channel = interaction.guild.get_channel(self.values[0].id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message('⚠️ テキストチャンネルを取得できませんでした。', ephemeral=True); return
        _set(interaction.guild.id, K_PROFILE_CHANNEL, channel.id)
        await interaction.response.edit_message(embed=admin_embed(interaction.guild), view=MemberAdminView())

class HoursModal(discord.ui.Modal,title='必要VC時間'):
    hours=discord.ui.TextInput(label='必要な累計VC時間',placeholder='例：3（不要なら0）',max_length=6)
    async def on_submit(self,interaction):
        try:
            h=float(self.hours.value)
            if h<0: raise ValueError
        except ValueError:
            await interaction.response.send_message('⚠️ 0以上の数字で入力してください。',ephemeral=True); return
        _set(interaction.guild.id,K_HOURS,h)
        await interaction.response.edit_message(embed=admin_embed(interaction.guild),view=MemberAdminView())

class MemberAdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)
        self.add_item(TempRoleSelect())
        self.add_item(FullRoleSelect())
        self.add_item(PanelChannelSelect())
        self.add_item(ProfileChannelSelect())

    async def interaction_check(self, interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message('⚠️ 管理者だけが操作できます。', ephemeral=True)
            return False
        return True
    @discord.ui.button(label='⏱️ 必要VC時間',style=discord.ButtonStyle.primary,row=4)
    async def hours(self,interaction,button): await interaction.response.send_modal(HoursModal())
    @discord.ui.button(label='VC時間条件：ON/OFF',style=discord.ButtonStyle.secondary,row=4)
    async def toggle_hours(self,interaction,button):
        gid=str(interaction.guild.id)
        now=(_kv(gid,K_HOURS_ENABLED) or 'OFF')
        _set(gid,K_HOURS_ENABLED,'OFF' if now=='ON' else 'ON')
        await interaction.response.edit_message(embed=admin_embed(interaction.guild),view=MemberAdminView())

    @discord.ui.button(label='表示切替：画像／通常', style=discord.ButtonStyle.primary, row=4)
    async def toggle_profile_display(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        gid = str(interaction.guild.id)
        new_mode = 'EMBED' if _profile_mode(gid) == 'IMAGE' else 'IMAGE'
        db.set_setting_text(gid, K_PROFILE_DISPLAY_MODE, new_mode)
        updated, skipped, errors = await regenerate_all_profiles(interaction.guild)
        await interaction.edit_original_response(embed=admin_embed(interaction.guild), view=MemberAdminView())
        message = f'✅ プロフィール表示を **{"画像カード" if new_mode == "IMAGE" else "通常Embed"}** に切り替え、{updated}件更新しました。'
        if skipped:
            message += f'\n未完成・退会済みなど {skipped}件はスキップしました。'
        if errors:
            message += '\n⚠️ 一部更新エラー：' + '、'.join(errors[:3])
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label='プロフィール一括更新', style=discord.ButtonStyle.success, row=4)
    async def regenerate_profiles(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        updated, skipped, errors = await regenerate_all_profiles(interaction.guild)
        text = f'✅ プロフィールを **{updated}件** 更新しました。'
        if skipped:
            text += f'\n未完了・退会済みなど **{skipped}件** はスキップしました。'
        if errors:
            text += '\n⚠️ エラー：' + '、'.join(errors[:5])
            if len(errors) > 5:
                text += f' ほか{len(errors)-5}件'
        await interaction.followup.send(text, ephemeral=True)
