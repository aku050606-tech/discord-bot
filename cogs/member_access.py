"""参加区分による自由部屋権限。ロールIDだけ参照し、ロール名には依存しない。"""
import discord
from database import Database

db = Database()
K_TEMP = 'member_temp_role'
K_FULL = 'member_full_role'


def _role(guild, key):
    value = db.get_log_channel_id(str(guild.id), key)
    return guild.get_role(int(value)) if value and str(value).isdigit() else None


def allowed_roles(guild, tier):
    temp = _role(guild, K_TEMP)
    full = _role(guild, K_FULL)
    if tier not in ('temp', 'full') or temp is None or (full and temp.id == full.id):
        raise ValueError('仮メンバー／正式メンバーのロール設定が不正です。')
    if tier == 'full':
        if full is None:
            raise ValueError('正式メンバーロールが未設定です。')
        return [full]
    return [temp] + ([full] if full else [])


def has_access(member, tier):
    if not isinstance(member, discord.Member) or member.bot:
        return False
    if db.get_member_registration(member.guild.id, member.id).get('blocked'):
        return False
    if member.guild_permissions.administrator:
        return True  # Discordの管理者はチャンネル権限を超越する
    try:
        allowed = allowed_roles(member.guild, tier)
    except ValueError:
        return False
    return any(role in member.roles for role in allowed)


def base_overwrites(guild, tier, *, open_connect=True, bot_member=None):
    """他ロールの許可を前提にせず、デフォルト拒否から作成。"""
    out = {guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False)}
    for role in allowed_roles(guild, tier):
        out[role] = discord.PermissionOverwrite(view_channel=True, connect=bool(open_connect))
    me = bot_member or guild.me
    if me is not None:
        out[me] = discord.PermissionOverwrite(view_channel=True, connect=True,
                                               manage_channels=True, move_members=True)
    return out


def sanitize_overwrites(channel, tier, *, open_connect=True):
    """BOT管理の一時VCの危険なロール/個人許可を除いて再構築する。"""
    guild = channel.guild
    secure = base_overwrites(guild, tier, open_connect=open_connect)
    permitted = {r.id for r in allowed_roles(guild, tier)}
    for subject, overwrite in channel.overwrites.items():
        if isinstance(subject, discord.Role):
            if subject.id not in permitted and subject != guild.default_role:
                # 無関係の称号ロールに許可があると@everyone拒否を上書きできる
                if (overwrite.view_channel is True or overwrite.connect is True
                        or overwrite.manage_channels is True):
                    continue
                secure[subject] = overwrite
        elif isinstance(subject, discord.Member):
            if subject == guild.me:
                continue
            if not has_access(subject, tier):
                continue
            # 旧BOTが付けていた manage_channels / move_members 等を除去する。
            # 本人の入室許可・拒否だけ残し、公開範囲の変更権限は渡さない。
            secure[subject] = discord.PermissionOverwrite(
                view_channel=overwrite.view_channel,
                connect=overwrite.connect, send_messages=overwrite.send_messages)
    return secure
