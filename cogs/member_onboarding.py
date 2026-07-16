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


BADGE_CATEGORIES = {
    'personality': {
        'title': '性格',
        'color': (245, 190, 70),
        'items': [
            ('bright', '明るい', '😄'), ('quiet', 'おとなしい', '🤫'), ('friendly', '話しかけやすい', '🤝'),
            ('shy', '人見知り', '🙈'), ('easygoing', 'マイペース', '😎'), ('cheerful', 'ノリがいい', '😂'),
            ('gentle', '優しい', '😊'), ('serious', '真面目', '🧠'), ('natural', '天然', '🌿'),
            ('calm', '落ち着いている', '☕'), ('competitive', '負けず嫌い', '🔥'), ('listener', '聞き上手', '👂'),
            ('caregiver', '面倒見がいい', '🤍'), ('moodmaker', '盛り上げ役', '🎉'), ('relaxed', 'のんびり', '🛋️'),
        ],
    },
    'communication': {
        'title': 'コミュニケーション',
        'color': (60, 165, 235),
        'items': [
            ('chat_love', '雑談好き', '💬'), ('vc_love', 'VC好き', '🎙️'), ('listen_only', '聞き専', '🎧'),
            ('invite_me', '誘ってほしい', '📞'), ('talk_ok', '話しかけ歓迎', '🙌'), ('dm_ok', 'DM歓迎', '📩'),
            ('rom', '見る専多め', '👀'), ('reply_fast', '返信早め', '⚡'), ('reply_slow', '返信ゆっくり', '🐢'),
            ('small_group', '少人数派', '👥'), ('large_group', '大人数OK', '📣'), ('late_vc', '深夜VC', '🌙'),
            ('day_vc', '昼VC', '☀️'), ('text_main', 'チャット中心', '⌨️'), ('voice_main', 'VC中心', '🔊'),
        ],
    },
    'hobby': {
        'title': '趣味',
        'color': (174, 105, 230),
        'items': [
            ('music', '音楽', '🎵'), ('karaoke', 'カラオケ', '🎤'), ('movie', '映画', '🎬'),
            ('anime', 'アニメ', '📺'), ('manga', '漫画', '📖'), ('reading', '読書', '📚'),
            ('cafe', 'カフェ', '☕'), ('gourmet', 'グルメ', '🍜'), ('cooking', '料理', '🍳'),
            ('drive', 'ドライブ', '🚗'), ('travel', '旅行', '✈️'), ('photo', '写真', '📷'),
            ('drawing', 'イラスト', '🎨'), ('fitness', '筋トレ', '💪'), ('sports', '運動', '🏃'),
            ('shopping', 'ショッピング', '🛍️'), ('dog', '犬派', '🐶'), ('cat', '猫派', '🐱'),
        ],
    },
    'game': {
        'title': 'ゲーム',
        'color': (235, 92, 104),
        'items': [
            ('game_love', 'ゲーム好き', '🎮'), ('no_game', 'ゲームはしない', '🚫'), ('fps', 'FPS', '🔫'),
            ('rpg', 'RPG', '⚔️'), ('craft', 'クラフト', '🏗️'), ('openworld', 'オープンワールド', '🌍'),
            ('survival', 'サバイバル', '🏕️'), ('horror', 'ホラー', '👻'), ('party', 'パーティーゲーム', '🎲'),
            ('mobile', 'スマホゲーム', '📱'), ('pc_game', 'PCゲーム', '💻'), ('console', '家庭用ゲーム', '🕹️'),
            ('casual', 'エンジョイ勢', '😆'), ('serious_game', 'ガチ勢', '🏆'), ('beginner_ok', '初心者歓迎', '🌱'),
            ('teach_me', '教えてほしい', '📚'), ('teach_you', '教えるの好き', '🎓'),
        ],
    },
    'purpose': {
        'title': '交流目的・生活',
        'color': (75, 200, 145),
        'items': [
            ('friends', '友達募集', '🤝'), ('hangout', '一緒に遊びたい', '🎉'), ('talking', '雑談したい', '☕'),
            ('game_friends', 'ゲーム仲間募集', '🎮'), ('hobby_friends', '趣味友募集', '📚'), ('casual_social', '気軽に交流', '🌈'),
            ('morning', '朝型', '🌞'), ('night', '夜型', '🌙'), ('indoor', 'インドア', '🏠'),
            ('outdoor', 'アウトドア', '🏕️'), ('weekend', '休日中心', '📅'), ('weekday', '平日中心', '🗓️'),
        ],
    },
}

BADGE_LOOKUP = {
    key: {'label': label, 'emoji': emoji, 'category': category, 'color': data['color']}
    for category, data in BADGE_CATEGORIES.items()
    for key, label, emoji in data['items']
}


def _badge_keys(profile):
    raw = (profile or {}).get('badges') or ''
    return [x for x in raw.split('|') if x in BADGE_LOOKUP]


def _badge_labels(profile):
    labels = [BADGE_LOOKUP[x]['label'] for x in _badge_keys(profile)]
    custom = ((profile or {}).get('custom_badge') or '').strip()
    if custom:
        labels.append(custom)
    return labels[:4]


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


class AboutSlotModal(discord.ui.Modal):
    question = discord.ui.TextInput(label='質問', placeholder='例：好きなアニメ', max_length=40)
    answer = discord.ui.TextInput(label='回答', placeholder='例：攻殻機動隊', style=discord.TextStyle.paragraph, max_length=160)

    def __init__(self, slot, current=None):
        super().__init__(title=f'ABOUT ME+ 項目{slot}')
        self.slot = int(slot)
        current = current or {}
        self.question.default = current.get(f'about_q{slot}') or ''
        self.answer.default = current.get(f'about_a{slot}') or ''

    async def on_submit(self, interaction):
        db.update_member_profile(
            str(interaction.guild.id), str(interaction.user.id),
            **{f'about_q{self.slot}': self.question.value.strip(),
               f'about_a{self.slot}': self.answer.value.strip()}
        )
        await interaction.response.send_message(f'✅ ABOUT ME+ の項目{self.slot}を保存しました。', ephemeral=True)
        await publish_profile(interaction.user)


class FreeTextModal(discord.ui.Modal, title='自由欄を編集'):
    free_text = discord.ui.TextInput(
        label='自由欄',
        placeholder='好きなこと、最近ハマっていること、誘ってほしいゲームなど自由にどうぞ',
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=300,
    )

    def __init__(self, current=None):
        super().__init__()
        self.free_text.default = (current or {}).get('free_text') or ''

    async def on_submit(self, interaction):
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), free_text=self.free_text.value.strip())
        await interaction.response.send_message('✅ 自由欄を保存しました。', ephemeral=True)
        await publish_profile(interaction.user)


class AboutMePlusView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=180)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('本人だけ編集できます。', ephemeral=True)
            return False
        return True

    async def _open(self, interaction, slot):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(AboutSlotModal(slot, current))

    @discord.ui.button(label='項目1', style=discord.ButtonStyle.primary)
    async def slot1(self, interaction, button): await self._open(interaction, 1)
    @discord.ui.button(label='項目2', style=discord.ButtonStyle.primary)
    async def slot2(self, interaction, button): await self._open(interaction, 2)
    @discord.ui.button(label='項目3', style=discord.ButtonStyle.primary)
    async def slot3(self, interaction, button): await self._open(interaction, 3)



class BadgeCategorySelect(discord.ui.Select):
    def __init__(self, category, owner_id, current):
        self.category = category
        self.owner_id = int(owner_id)
        data = BADGE_CATEGORIES[category]
        selected = set(_badge_keys(current))
        options = [
            discord.SelectOption(label=label, value=key, emoji=emoji, default=key in selected)
            for key, label, emoji in data['items']
        ]
        super().__init__(
            placeholder=f"{data['title']}から選択（合計4個まで）",
            min_values=0,
            max_values=min(4, len(options)),
            options=options,
        )

    async def callback(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('本人だけ変更できます。', ephemeral=True)
            return
        profile = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        existing = _badge_keys(profile)
        category_keys = {key for key, _, _ in BADGE_CATEGORIES[self.category]['items']}
        kept = [key for key in existing if key not in category_keys]
        custom = (profile.get('custom_badge') or '').strip()
        merged = kept + list(self.values)
        max_regular = 3 if custom else 4
        if len(merged) > max_regular:
            await interaction.response.send_message(
                f'バッジは自由枠を含めて4個までです。現在の自由バッジ：{custom or "なし"}',
                ephemeral=True,
            )
            return
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), badges='|'.join(merged))
        await interaction.response.send_message('バッジを更新しました：' + ('・'.join(_badge_labels({**profile, 'badges': '|'.join(merged)})) or '未選択'), ephemeral=True)
        await publish_profile(interaction.user)


class BadgeCategoryView(discord.ui.View):
    def __init__(self, category, owner_id, current):
        super().__init__(timeout=180)
        self.add_item(BadgeCategorySelect(category, owner_id, current))


class CustomBadgeModal(discord.ui.Modal, title='自由バッジを設定'):
    badge = discord.ui.TextInput(
        label='自由バッジ（1個）',
        placeholder='例：麻雀、競馬、釣り、Aimer好き',
        required=False,
        max_length=18,
    )
    def __init__(self, current=None):
        super().__init__()
        self.badge.default = ((current or {}).get('custom_badge') or '')

    async def on_submit(self, interaction):
        profile = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        value = self.badge.value.strip()
        if value and len(_badge_keys(profile)) >= 4:
            await interaction.response.send_message('すでに通常バッジを4個選んでいます。自由バッジを入れる場合は通常バッジを3個以下にしてください。', ephemeral=True)
            return
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), custom_badge=value)
        await interaction.response.send_message('自由バッジを保存しました。' if value else '自由バッジを削除しました。', ephemeral=True)
        await publish_profile(interaction.user)


class BadgeMenuView(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=180)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('本人だけ変更できます。', ephemeral=True)
            return False
        return True

    async def _open_category(self, interaction, category):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_message(
            f"【{BADGE_CATEGORIES[category]['title']}】から選んでください。選び直すと、このカテゴリの選択だけ更新されます。",
            view=BadgeCategoryView(category, interaction.user.id, current),
            ephemeral=True,
        )

    @discord.ui.button(label='性格', style=discord.ButtonStyle.primary, row=0)
    async def personality(self, interaction, button): await self._open_category(interaction, 'personality')
    @discord.ui.button(label='コミュニケーション', style=discord.ButtonStyle.primary, row=0)
    async def communication(self, interaction, button): await self._open_category(interaction, 'communication')
    @discord.ui.button(label='趣味', style=discord.ButtonStyle.primary, row=0)
    async def hobby(self, interaction, button): await self._open_category(interaction, 'hobby')
    @discord.ui.button(label='ゲーム', style=discord.ButtonStyle.primary, row=0)
    async def game(self, interaction, button): await self._open_category(interaction, 'game')
    @discord.ui.button(label='交流・生活', style=discord.ButtonStyle.primary, row=0)
    async def purpose(self, interaction, button): await self._open_category(interaction, 'purpose')

    @discord.ui.button(label='自由バッジ', style=discord.ButtonStyle.success, row=1)
    async def custom(self, interaction, button):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(CustomBadgeModal(current))

    @discord.ui.button(label='すべて解除', style=discord.ButtonStyle.danger, row=1)
    async def clear(self, interaction, button):
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), badges='', custom_badge='')
        await interaction.response.send_message('バッジをすべて解除しました。', ephemeral=True)
        await publish_profile(interaction.user)

class ProfileEditMenu(discord.ui.View):
    def __init__(self, owner_id):
        super().__init__(timeout=180)
        self.owner_id = int(owner_id)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('このプロフィールは本人だけ編集できます。', ephemeral=True)
            return False
        return True

    @discord.ui.button(label='基本プロフィール', style=discord.ButtonStyle.success, row=0)
    async def basic(self, interaction, button):
        cur = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(ProfileModal(cur))

    @discord.ui.button(label='MBTI', style=discord.ButtonStyle.primary, row=0)
    async def mbti(self, interaction, button):
        await interaction.response.send_message('MBTIを選択してください。', view=MBTIView(), ephemeral=True)

    @discord.ui.button(label='GAME', style=discord.ButtonStyle.primary, row=0)
    async def games(self, interaction, button):
        await interaction.response.send_message('遊ぶゲームを選択または自由入力してください。', view=GameView(), ephemeral=True)

    @discord.ui.button(label='ABOUT ME+', style=discord.ButtonStyle.secondary, row=1)
    async def about_plus(self, interaction, button):
        await interaction.response.send_message('編集する項目を選んでください。質問と回答を自由に設定できます。', view=AboutMePlusView(interaction.user.id), ephemeral=True)

    @discord.ui.button(label='BADGES', style=discord.ButtonStyle.secondary, row=1)
    async def badges(self, interaction, button):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        selected = '・'.join(_badge_labels(current)) or '未選択'
        await interaction.response.send_message(
            f'あなたを表すバッジを4個まで選べます。\n現在：{selected}',
            view=BadgeMenuView(interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label='自由欄', style=discord.ButtonStyle.secondary, row=1)
    async def free(self, interaction, button):
        cur = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(FreeTextModal(cur))


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
    @discord.ui.button(label='⭐ ABOUT ME+', style=discord.ButtonStyle.secondary, custom_id='member:about_plus', row=1)
    async def about_plus(self, interaction, button):
        await interaction.response.send_message('任意項目です。編集する枠を選んでください。', view=AboutMePlusView(interaction.user.id), ephemeral=True)
    @discord.ui.button(label='🏅 BADGES', style=discord.ButtonStyle.secondary, custom_id='member:badges', row=2)
    async def badges(self, interaction, button):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        selected = '・'.join(_badge_labels(current)) or '未選択'
        await interaction.response.send_message(
            f'任意項目です。あなたを表すバッジを4個まで選べます。\n現在：{selected}',
            view=BadgeMenuView(interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label='📄 自由欄', style=discord.ButtonStyle.secondary, custom_id='member:free_text', row=2)
    async def free_text(self, interaction, button):
        cur = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_modal(FreeTextModal(cur))
    @discord.ui.button(label='✅ 登録状況', style=discord.ButtonStyle.secondary, custom_id='member:status', row=2)
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


def _profile_weekly_stats(guild_id, user_id):
    """過去7日間のVC・チャット合計とサーバー内順位を返す。"""
    import time
    since_hour = int(time.time()) // 3600 - (24 * 7)
    result = {
        'vc_total': 0, 'vc_rank': None,
        'chat_total': 0, 'chat_rank': None,
    }
    conn = db.get_conn()
    try:
        cur = conn.cursor()
        for kind in ('vc', 'chat'):
            try:
                cur.execute(
                    """SELECT user_id, SUM(amount) AS total
                       FROM activity_log
                       WHERE guild_id=? AND kind=? AND ts_hour>=?
                       GROUP BY user_id
                       ORDER BY total DESC, user_id ASC""",
                    (str(guild_id), kind, int(since_hour)),
                )
            except Exception:
                continue
            rows = [(str(uid), int(total or 0)) for uid, total in cur.fetchall()]
            for index, (uid, total) in enumerate(rows, start=1):
                if uid == str(user_id):
                    result[f'{kind}_total'] = total
                    result[f'{kind}_rank'] = index
                    break
    finally:
        conn.close()
    return result


def _format_profile_vc(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rem = divmod(seconds, 3600)
    minutes = rem // 60
    if hours:
        return f'{hours}時間{minutes}分'
    if minutes:
        return f'{minutes}分'
    return '0分'


def _draw_centered_text(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    draw.text(((x1 + x2) / 2, (y1 + y2) / 2), text, font=font, fill=fill, anchor='mm')


async def build_profile_card_file(member, p):
    """BOTORI用の横長プロフィール画像カードを生成する。"""
    import random
    import re
    from datetime import datetime, timezone

    width, height = 1600, 860
    img = Image.new('RGB', (width, height), '#050b16')
    draw = ImageDraw.Draw(img)

    # 配色
    accent = (57, 122, 255)
    accent_soft = (27, 72, 145)
    text_main = (241, 246, 255)
    text_sub = (159, 180, 216)
    panel_fill = (5, 15, 29)
    panel_alt = (8, 21, 39)
    line = (31, 63, 101)

    # 全体背景グラデーション
    top = (5, 15, 34)
    bottom = (1, 7, 15)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line((0, y, width, y), fill=color)

    # 外枠・各パネル
    draw.rounded_rectangle((28, 28, width-28, height-28), radius=34, outline=accent, width=3)
    header_box = (48, 48, width-48, 352)
    content_box = (48, 370, width-48, 720)
    footer_box = (48, 735, width-48, 812)
    draw.rounded_rectangle(header_box, radius=26, fill=panel_alt, outline=(38, 79, 137), width=2)
    draw.rounded_rectangle(content_box, radius=24, fill=panel_fill, outline=line, width=2)
    draw.rounded_rectangle(footer_box, radius=20, fill=panel_fill, outline=line, width=2)

    # ヘッダー右側の夜景装飾（パネルの上に描く）
    rng = random.Random(int(member.id) % 999983)
    for _ in range(95):
        x = rng.randint(760, 1515)
        y = rng.randint(66, 250)
        r = rng.choice((1, 1, 1, 2))
        color = rng.choice(((115, 158, 222), (181, 207, 241), (78, 121, 193)))
        draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
    # 月と青い光
    draw.ellipse((1270, 74, 1374, 178), fill=(188, 216, 247))
    draw.ellipse((1297, 70, 1383, 157), fill=panel_alt)
    for radius, alpha_color in ((150, (13, 38, 77)), (110, (19, 53, 102)), (70, (25, 70, 137))):
        cx, cy = 1110, 212
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=alpha_color, width=2)
    # 城・山シルエット
    draw.polygon([(650, 352), (790, 280), (910, 352), (1050, 255), (1170, 352), (1310, 292), (1480, 352)], fill=(3, 10, 21))
    for bx, by, bw, bh in [(1060, 235, 35, 117), (1110, 270, 28, 82), (1150, 214, 40, 138), (1210, 265, 26, 87)]:
        draw.rectangle((bx, by, bx+bw, by+bh), fill=(2, 8, 18))
        draw.polygon([(bx-5, by), (bx+bw//2, by-30), (bx+bw+5, by)], fill=(2, 8, 18))
    draw.line((700, 338, 1485, 338), fill=(18, 55, 104), width=2)

    # フォント
    tiny = _find_japanese_font(19)
    small = _find_japanese_font(23)
    small_b = _find_japanese_font(23, bold=True)
    medium = _find_japanese_font(29)
    medium_b = _find_japanese_font(29, bold=True)
    section = _find_japanese_font(25, bold=True)
    name = (p.get('nickname') or member.display_name).strip()
    name_font = _fit_text(draw, name, 610, 70, 40, bold=True)

    # アバター
    avatar_box = (70, 72, 356, 358)
    try:
        avatar_bytes = await member.display_avatar.with_size(512).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert('RGB')
        avatar = ImageOps.fit(avatar, (260, 260), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (260, 260), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 259, 259), fill=255)
        ring_mask = Image.new('L', (286, 286), 0)
        ImageDraw.Draw(ring_mask).ellipse((0, 0, 285, 285), fill=255)
        ring = Image.new('RGB', (286, 286), accent)
        img.paste(ring, (70, 72), ring_mask)
        img.paste(avatar, (83, 85), mask)
        draw.ellipse((315, 300, 352, 337), fill=(35, 210, 115), outline=panel_alt, width=5)
    except Exception:
        draw.ellipse(avatar_box, fill=accent)
        draw.ellipse((83, 85, 343, 345), fill=(27, 39, 61))

    # ヘッダー文字（anchorで縦位置を統一）
    draw.text((405, 92), 'MEMBER PROFILE', font=small_b, fill=(81, 148, 255), anchor='lm')
    draw.text((405, 155), name, font=name_font, fill=text_main, anchor='lm')
    draw.text((410, 208), f'@{member.name}', font=small, fill=(139, 158, 190), anchor='lm')

    mbti = (p.get('mbti') or '').strip()
    badge_text = mbti or '未設定'
    badge_font = small_b
    badge_w = draw.textbbox((0, 0), badge_text, font=badge_font)[2] + 34
    badge_box = (410, 229, 410 + badge_w, 275)
    draw.rounded_rectangle(badge_box, radius=12, fill=(43, 31, 100), outline=(104, 78, 220), width=2)
    _draw_centered_text(draw, badge_box, badge_text, badge_font, (226, 220, 255))

    comment = (p.get('comment') or '').strip()
    quote = comment or '一言はまだ登録されていません'
    quote_font = _fit_text(draw, quote, 790, 31, 21)
    draw.text((405, 315), f'“ {quote} ”', font=quote_font, fill=(224, 232, 246), anchor='lm')

    # セクション座標
    col1_x, col2_x, col3_x, col4_x = 78, 545, 905, 1260
    top_y = 410
    for x, title in ((col1_x, 'ABOUT ME'), (col2_x, 'ABOUT ME+'), (col3_x, 'BADGES'), (col4_x, 'RANKING')):
        draw.text((x, top_y), title, font=section, fill=(78, 145, 255), anchor='lm')
    for x in (515, 875, 1235):
        draw.line((x, 392, x, 692), fill=line, width=2)

    # ABOUT ME：各行を同じ高さに揃える
    hobby = (p.get('hobby') or '').strip()
    about_rows = [('名前', name), ('MBTI', mbti or '—'), ('趣味', hobby or '—'), ('一言', comment or '—')]
    row_centers = [468, 528, 588, 648]
    for (label, value), cy in zip(about_rows, row_centers):
        draw.text((col1_x, cy), label, font=small_b, fill=text_sub, anchor='lm')
        value_font = _fit_text(draw, value, 285, 24, 18)
        value_display = value
        while value_display and draw.textbbox((0, 0), value_display, font=value_font)[2] > 285:
            value_display = value_display[:-1]
        if value_display != value:
            value_display = value_display.rstrip() + '…'
        draw.text((205, cy), value_display, font=value_font, fill=text_main, anchor='lm')

    # ABOUT ME+：本人が自由に設定できる3つの質問と回答
    plus_rows = []
    for index in (1, 2, 3):
        question = (p.get(f'about_q{index}') or '').strip()
        answer = (p.get(f'about_a{index}') or '').strip()
        plus_rows.append((question or f'自由項目{index}', answer or '—'))
    py_plus = 450
    for question, answer in plus_rows:
        q_font = _fit_text(draw, question, 285, 22, 17, bold=True)
        a_font = _fit_text(draw, answer, 285, 21, 16)
        draw.text((col2_x, py_plus), question, font=q_font, fill=text_sub, anchor='la')
        box = (col2_x, py_plus + 29, 835, py_plus + 73)
        draw.rounded_rectangle(box, radius=11, fill=(11, 22, 38), outline=(35, 58, 88), width=2)
        answer_display = answer
        while answer_display and draw.textbbox((0,0), answer_display, font=a_font)[2] > 255:
            answer_display = answer_display[:-1]
        if answer_display != answer:
            answer_display = answer_display.rstrip() + '…'
        draw.text((col2_x + 14, py_plus + 51), answer_display, font=a_font, fill=text_main, anchor='lm')
        py_plus += 86

    # 週間アクティビティを取得
    stats = _profile_weekly_stats(member.guild.id, member.id)
    vc_total = stats['vc_total']
    chat_total = stats['chat_total']
    vc_rank = stats['vc_rank']
    chat_rank = stats['chat_rank']

    # BADGES：本人が選んだ4つを2列×2段で表示
    selected_badges = []
    for key in _badge_keys(p):
        info = BADGE_LOOKUP[key]
        selected_badges.append((info['label'], info['color']))
    custom_badge = (p.get('custom_badge') or '').strip()
    if custom_badge:
        selected_badges.append((custom_badge, (130, 145, 170)))
    selected_badges = selected_badges[:4]
    while len(selected_badges) < 4:
        selected_badges.append(('未設定', (65, 78, 100)))

    badge_boxes = [
        (col3_x, 452, 1044, 528), (1055, 452, 1195, 528),
        (col3_x, 544, 1044, 620), (1055, 544, 1195, 620),
    ]
    for (label, color), box in zip(selected_badges, badge_boxes):
        fill = tuple(max(10, int(c * 0.22)) for c in color)
        draw.rounded_rectangle(box, radius=15, fill=fill, outline=color, width=2)
        dot_x = box[0] + 18
        dot_y = (box[1] + box[3]) // 2
        draw.ellipse((dot_x - 7, dot_y - 7, dot_x + 7, dot_y + 7), fill=color)
        max_w = box[2] - box[0] - 52
        badge_label_font = _fit_text(draw, label, max_w, 22, 16, bold=True)
        display = label
        while display and draw.textbbox((0, 0), display, font=badge_label_font)[2] > max_w:
            display = display[:-1]
        if display != label:
            display = display.rstrip() + '…'
        draw.text((box[0] + 38, dot_y), display, font=badge_label_font, fill=text_main, anchor='lm')

    # RANKING：既存activity_logから実数と順位を表示
    joined_days = 0
    if getattr(member, 'joined_at', None):
        now = datetime.now(timezone.utc)
        joined_days = max(1, (now - member.joined_at).days + 1)
    rank_rows = [
        ('VC時間（今週）', f'{vc_rank}位' if vc_rank else '—', _format_profile_vc(vc_total)),
        ('チャット数（今週）', f'{chat_rank}位' if chat_rank else '—', f'{chat_total:,}件'),
        ('サーバー参加日数', f'{joined_days}日' if joined_days else '—', ''),
    ]
    ry = 470
    for label, rank_value, detail in rank_rows:
        draw.text((col4_x, ry), label, font=small, fill=(219, 227, 242), anchor='lm')
        color = (68, 160, 255) if 'VC' in label else ((255, 91, 121) if 'チャット' in label else (81, 215, 145))
        draw.text((1510, ry), rank_value, font=small_b, fill=color, anchor='rm')
        if detail:
            draw.text((1510, ry + 30), detail, font=tiny, fill=text_sub, anchor='rm')
        ry += 83

    # 下部：好きなこと + BOTORIロゴ文字
    draw.text((78, 773), '好きなこと', font=section, fill=(78, 145, 255), anchor='lm')
    hobby_display = (p.get('free_text') or '').strip() or hobby or '—'
    hobby_font = _fit_text(draw, hobby_display, 1020, 28, 19)
    draw.text((260, 773), hobby_display, font=hobby_font, fill=text_main, anchor='lm')
    draw.text((1485, 773), 'BOTORI', font=small_b, fill=(91, 137, 220), anchor='rm')
    draw.text((1485, 797), 'MEMBER PROFILE', font=tiny, fill=(72, 101, 153), anchor='rm')

    out = io.BytesIO()
    img.save(out, format='PNG', optimize=True)
    out.seek(0)
    return discord.File(out, filename=f'profile_{member.id}.png')


class ProfileCardView(discord.ui.View):
    def __init__(self, member_id=None):
        super().__init__(timeout=None)
        if member_id:
            self.add_item(discord.ui.Button(label='プロフィールを開く', style=discord.ButtonStyle.link,
                                            url=f'https://discord.com/users/{member_id}', row=0))

    @discord.ui.button(label='編集', emoji='✏️', style=discord.ButtonStyle.secondary,
                       custom_id='member:profile_card_edit', row=0)
    async def edit_profile(self, interaction, button):
        target = interaction.message.mentions[0] if interaction.message and interaction.message.mentions else None
        if target is None:
            await interaction.response.send_message('プロフィールの所有者を確認できませんでした。', ephemeral=True)
            return
        if interaction.user.id != target.id:
            await interaction.response.send_message('このプロフィールは本人だけ編集できます。', ephemeral=True)
            return
        await interaction.response.send_message('編集する項目を選んでください。', view=ProfileEditMenu(target.id), ephemeral=True)


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
                await msg.edit(content=member.mention, embed=None, attachments=[file], view=ProfileCardView(member.id))
            else:
                msg = await channel.send(content=member.mention, file=file, view=ProfileCardView(member.id))
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
        bot.add_view(ProfileCardView())

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
