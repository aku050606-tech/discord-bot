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

PROFILE_THEMES = {
    'devi': {'label': 'DEVI 悪魔', 'accent': (185,72,255), 'panel': (10,7,20), 'alt': (14,8,27), 'line': (105,45,145)},
    'sakura': {'label': 'SAKURA 桜', 'accent': (255,126,188), 'panel': (23,10,24), 'alt': (34,13,33), 'line': (127,52,91)},
    'cyber': {'label': 'CYBER サイバー', 'accent': (0,220,255), 'panel': (3,17,27), 'alt': (4,24,38), 'line': (0,102,135)},
    'space': {'label': 'SPACE 宇宙', 'accent': (156,95,255), 'panel': (12,8,30), 'alt': (19,10,43), 'line': (84,48,135)},
    'ocean': {'label': 'OCEAN 深海', 'accent': (45,161,255), 'panel': (2,18,36), 'alt': (4,29,52), 'line': (20,79,124)},
    'fantasy': {'label': 'FANTASY 幻想', 'accent': (239,184,87), 'panel': (20,17,14), 'alt': (31,24,16), 'line': (112,83,35)},
    'city': {'label': 'CITY 夜景', 'accent': (91,137,255), 'panel': (6,12,27), 'alt': (9,18,38), 'line': (39,66,121)},
    'hell': {'label': 'HELL 地獄', 'accent': (255,74,45), 'panel': (27,5,7), 'alt': (42,7,9), 'line': (132,35,29)},
    'snow': {'label': 'SNOW 雪国', 'accent': (126,211,255), 'panel': (6,20,35), 'alt': (10,31,51), 'line': (48,103,143)},
    'forest': {'label': 'FOREST 森', 'accent': (45,218,151), 'panel': (4,22,20), 'alt': (7,32,29), 'line': (24,94,75)},
}

THEME_ALIASES = {
    'night': 'city', 'purple': 'space', 'emerald': 'forest', 'sunset': 'hell',
    'mono': 'snow', 'gold': 'fantasy',
}



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


class FreeTextModal(discord.ui.Modal, title='好きなことを編集'):
    free_text = discord.ui.TextInput(
        label='好きなこと',
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
        await interaction.response.send_message('✅ 好きなことを保存しました。', ephemeral=True)
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

class ProfileThemeSelect(discord.ui.Select):
    def __init__(self, owner_id, current='night'):
        self.owner_id = int(owner_id)
        options = [discord.SelectOption(label=data['label'], value=key, default=(key == current)) for key, data in PROFILE_THEMES.items()]
        super().__init__(placeholder='背景テーマを選択…', min_values=1, max_values=1, options=options)

    async def callback(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message('本人だけ変更できます。', ephemeral=True)
            return
        value = self.values[0]
        db.update_member_profile(str(interaction.guild.id), str(interaction.user.id), profile_theme=value)
        await interaction.response.send_message(f"✅ 背景を **{PROFILE_THEMES[value]['label']}** に変更しました。", ephemeral=True)
        await publish_profile(interaction.user)


class ProfileThemeView(discord.ui.View):
    def __init__(self, owner_id, current='night'):
        super().__init__(timeout=180)
        self.add_item(ProfileThemeSelect(owner_id, current))


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

    @discord.ui.button(label='背景テーマ', style=discord.ButtonStyle.secondary, row=1)
    async def theme(self, interaction, button):
        current = db.get_member_profile(str(interaction.guild.id), str(interaction.user.id)) or {}
        await interaction.response.send_message('プロフィールカードの背景を選んでください。', view=ProfileThemeView(interaction.user.id, current.get('profile_theme') or 'night'), ephemeral=True)

    @discord.ui.button(label='好きなこと', style=discord.ButtonStyle.secondary, row=1)
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

    @discord.ui.button(label='💙 好きなこと', style=discord.ButtonStyle.secondary, custom_id='member:free_text', row=2)
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


async def _build_profile_card_file_legacy(member, p):
    """背景・ガラスUI・可変情報を完全分離してプロフィールカードを生成する。"""
    from datetime import datetime, timezone

    width, height = 1370, 1148
    root = os.path.dirname(os.path.dirname(__file__))
    raw_theme_key = (p.get('profile_theme') or 'devi').strip()
    theme_key = THEME_ALIASES.get(raw_theme_key, raw_theme_key)
    bg_path = os.path.join(root, 'assets', 'profile', 'backgrounds', f'{theme_key}.png')
    overlay_path = os.path.join(root, 'assets', 'profile', 'overlays', 'glass_overlay.png')

    try:
        src = Image.open(bg_path).convert('RGB')
        img = ImageOps.fit(src, (width, height), method=Image.Resampling.LANCZOS).convert('RGBA')
    except Exception:
        img = Image.new('RGBA', (width, height), '#20213f')

    try:
        overlay = Image.open(overlay_path).convert('RGBA')
        if overlay.size != (width, height):
            overlay = overlay.resize((width, height), Image.Resampling.LANCZOS)
        img.alpha_composite(overlay)
    except Exception:
        pass

    draw = ImageDraw.Draw(img)
    text_main = (246, 244, 252)
    text_sub = (196, 184, 220)
    input_fill = (20, 20, 48, 210)
    title_col = (211, 172, 240)

    small = _find_japanese_font(22)
    small_b = _find_japanese_font(22, bold=True)
    medium = _find_japanese_font(28)
    medium_b = _find_japanese_font(28, bold=True)

    name = (p.get('nickname') or member.display_name).strip()
    mbti = (p.get('mbti') or '').strip() or '未設定'
    hobby = (p.get('hobby') or '').strip() or '—'
    comment = (p.get('comment') or '').strip() or '—'

    # Header profile information
    draw.text((350, 92), 'MEMBER PROFILE', font=_find_japanese_font(25, bold=True), fill=title_col)
    nf = _fit_text(draw, name, 280, 64, 36, bold=True)
    draw.text((350, 140), name, font=nf, fill=text_main)
    draw.text((350, 220), f'@{member.name}', font=medium, fill=(174, 157, 201))
    badge_w = max(100, draw.textbbox((0, 0), mbti, font=medium_b)[2] + 38)
    badge_box = (350, 265, 350 + badge_w, 321)
    draw.rounded_rectangle(badge_box, radius=15, fill=(72, 53, 125, 230), outline=(168, 132, 220), width=2)
    _draw_centered_text(draw, badge_box, mbti, medium_b, text_main)
    qtext = comment.replace('☆', '★')
    qf = _fit_text(draw, qtext, 285, 30, 18)
    draw.text((350, 353), f'“ {qtext} ”', font=qf, fill=(235, 229, 244))

    # Avatar
    avatar_size = 250
    ax, ay = 58, 92
    try:
        avatar_bytes = await member.display_avatar.with_size(512).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert('RGB')
        avatar = ImageOps.fit(avatar, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
        draw.ellipse((ax - 10, ay - 10, ax + avatar_size + 10, ay + avatar_size + 10), fill=(174, 145, 220))
        img.paste(avatar, (ax, ay), mask)
        draw.ellipse((ax + 218, ay + 218, ax + 252, ay + 252), fill=(93, 212, 139), outline=(55, 50, 92), width=4)
    except Exception:
        pass

    # Section titles
    for text, pos in [('ABOUT ME',(50,477)),('ABOUT ME+',(378,477)),('BADGES',(694,477)),('RANKING',(1008,477))]:
        draw.text(pos, text, font=_find_japanese_font(28, bold=True), fill=title_col)

    # ABOUT ME
    rows = [('名前', name), ('MBTI', mbti), ('趣味', hobby), ('一言', comment)]
    ys = [590, 660, 730, 800]
    for (lab, val), yy in zip(rows, ys):
        draw.text((58, yy), lab, font=small_b, fill=(204, 188, 224), anchor='lm')
        vf = _fit_text(draw, val, 145, 25, 16)
        draw.text((180, yy), val, font=vf, fill=text_main, anchor='lm')

    # ABOUT ME+
    py = 560
    for i in (1, 2, 3):
        q = (p.get(f'about_q{i}') or '').strip() or f'自由項目{i}'
        a = (p.get(f'about_a{i}') or '').strip() or '—'
        qf = _fit_text(draw, q, 240, 22, 15, bold=True)
        draw.text((378, py), q, font=qf, fill=(214, 199, 230))
        box = (378, py + 31, 620, py + 82)
        draw.rounded_rectangle(box, radius=10, fill=input_fill, outline=(77, 69, 113), width=1)
        af = _fit_text(draw, a, 218, 21, 14)
        draw.text((392, py + 57), a, font=af, fill=text_main, anchor='lm')
        py += 112

    # BADGES
    selected = []
    for key in _badge_keys(p):
        info = BADGE_LOOKUP[key]
        selected.append((info['label'], info['color']))
    custom = (p.get('custom_badge') or '').strip()
    if custom:
        selected.append((custom, (130, 145, 170)))
    selected = selected[:4]
    while len(selected) < 4:
        selected.append(('未設定', (90, 90, 120)))
    boxes = [(688, 575, 806, 685), (820, 575, 940, 685), (688, 710, 806, 820), (820, 710, 940, 820)]
    for (label, color), box in zip(selected, boxes):
        fill = tuple(max(18, int(c * .22)) for c in color) + (235,)
        draw.rounded_rectangle(box, radius=18, fill=fill, outline=color, width=2)
        cx = (box[0] + box[2]) // 2
        draw.ellipse((cx - 10, box[1] + 17, cx + 10, box[1] + 37), fill=color)
        bf = _fit_text(draw, label, box[2] - box[0] - 16, 20, 13, bold=True)
        draw.text((cx, box[1] + 80), label, font=bf, fill=text_main, anchor='mm')

    # RANKING
    stats = _profile_weekly_stats(member.guild.id, member.id)
    joined_days = 0
    if getattr(member, 'joined_at', None):
        joined_days = max(1, (datetime.now(timezone.utc) - member.joined_at).days + 1)
    ranks = [
        ('VC時間（今週）', f"{stats['vc_rank']}位" if stats['vc_rank'] else '—', _format_profile_vc(stats['vc_total']), (105, 174, 255)),
        ('チャット数（今週）', f"{stats['chat_rank']}位" if stats['chat_rank'] else '—', f"{stats['chat_total']:,}件", (247, 106, 157)),
        ('サーバー参加日数', f'{joined_days}日' if joined_days else '—', '', (93, 211, 145)),
    ]
    ry = [590, 710, 820]
    for (lab, val, detail, col), yy in zip(ranks, ry):
        draw.text((1010, yy), lab, font=small, fill=text_main, anchor='lm')
        draw.text((1287, yy), val, font=medium_b, fill=col, anchor='rm')
        if detail:
            draw.text((1287, yy + 34), detail, font=small, fill=text_sub, anchor='rm')

    # Bottom panels
    free = ((p.get('free_text') or '').strip() or hobby or '—').replace('☆', '★')
    draw.text((250, 965), '好きなこと', font=_find_japanese_font(30, bold=True), fill=(238, 139, 193))
    ff = _fit_text(draw, free, 570, 30, 17)
    draw.text((250, 1040), free, font=ff, fill=text_main)
    draw.text((1114, 985), 'DEVI', font=_find_japanese_font(32, bold=True), fill=(235, 140, 194), anchor='ma')
    draw.text((1114, 1032), 'MEMBER PROFILE', font=small, fill=(170, 153, 199), anchor='ma')

    out = io.BytesIO()
    img.convert('RGB').save(out, format='PNG', optimize=True)
    out.seek(0)
    return discord.File(out, filename=f'profile_{member.id}.png')


async def build_profile_card_file(member, p):
    """DEVI専用の完成背景へ、可変文字とアバターだけを正確に描画する。"""
    from datetime import datetime, timezone

    raw_theme_key = (p.get('profile_theme') or 'devi').strip()
    theme_key = THEME_ALIASES.get(raw_theme_key, raw_theme_key)
    if theme_key != 'devi':
        return await _build_profile_card_file_legacy(member, p)

    root = os.path.dirname(os.path.dirname(__file__))
    bg_path = os.path.join(root, 'assets', 'profile', 'backgrounds', 'devi.png')
    width, height = 1402, 1122

    try:
        img = Image.open(bg_path).convert('RGBA')
        if img.size != (width, height):
            img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
    except Exception:
        img = Image.new('RGBA', (width, height), '#15133d')

    draw = ImageDraw.Draw(img)
    text_main = (250, 247, 255)
    text_sub = (205, 190, 224)
    title_col = (245, 157, 210)
    soft_line = (190, 146, 235)

    small = _find_japanese_font(21)
    small_b = _find_japanese_font(21, bold=True)
    medium = _find_japanese_font(27)
    medium_b = _find_japanese_font(27, bold=True)

    name = (p.get('nickname') or member.display_name).strip()
    mbti = (p.get('mbti') or '').strip() or '未設定'
    hobby = (p.get('hobby') or '').strip() or '—'
    comment = (p.get('comment') or '').strip() or '—'

    # ── 左上：プロフィール基本情報（枠 34,46 ～ 656,387） ──
    avatar_size = 238
    ax, ay = 58, 91
    try:
        avatar_bytes = await member.display_avatar.with_size(512).read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert('RGB')
        avatar = ImageOps.fit(avatar, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size - 1, avatar_size - 1), fill=255)
        draw.ellipse((ax - 6, ay - 6, ax + avatar_size + 6, ay + avatar_size + 6),
                     fill=(72, 43, 126, 225), outline=(223, 151, 234), width=3)
        img.paste(avatar, (ax, ay), mask)
        draw.ellipse((ax + 204, ay + 204, ax + 238, ay + 238),
                     fill=(93, 212, 139), outline=(42, 31, 82), width=4)
    except Exception:
        pass

    tx = 330
    draw.text((tx, 87), 'MEMBER PROFILE', font=_find_japanese_font(24, bold=True), fill=title_col)
    nf = _fit_text(draw, name, 292, 58, 34, bold=True)
    draw.text((tx, 132), name, font=nf, fill=text_main)
    draw.text((tx, 202), f'@{member.name}', font=medium, fill=text_sub)

    badge_w = min(280, max(104, draw.textbbox((0, 0), mbti, font=medium_b)[2] + 42))
    badge_box = (tx, 247, tx + badge_w, 302)
    draw.rounded_rectangle(badge_box, radius=15, fill=(58, 35, 104, 220), outline=soft_line, width=2)
    _draw_centered_text(draw, badge_box, mbti, medium_b, text_main)

    qtext = comment.replace('☆', '★')
    qf = _fit_text(draw, f'“ {qtext} ”', 292, 27, 16)
    draw.text((tx, 331), f'“ {qtext} ”', font=qf, fill=(240, 231, 248))

    # ── 中段：4つの透明枠 ──
    title_font = _find_japanese_font(27, bold=True)
    draw.text((55, 438), 'ABOUT ME', font=title_font, fill=title_col)
    draw.text((398, 438), 'ABOUT ME+', font=title_font, fill=title_col)
    draw.text((744, 438), 'BADGES', font=title_font, fill=title_col)
    draw.text((1085, 438), 'RANKING', font=title_font, fill=title_col)

    # ABOUT ME（枠 34,412 ～ 337,831）
    rows = [('名前', name), ('MBTI', mbti), ('趣味', hobby), ('一言', comment)]
    ys = [540, 620, 700, 780]
    for (lab, val), yy in zip(rows, ys):
        draw.text((55, yy), lab, font=small_b, fill=(220, 199, 235), anchor='lm')
        vf = _fit_text(draw, val, 154, 24, 15)
        draw.text((165, yy), val, font=vf, fill=text_main, anchor='lm')

    # ABOUT ME+（枠 356,412 ～ 677,831）
    py = 510
    for i in (1, 2, 3):
        q = (p.get(f'about_q{i}') or '').strip() or f'自由項目{i}'
        a = (p.get(f'about_a{i}') or '').strip() or '—'
        qf = _fit_text(draw, q, 270, 21, 14, bold=True)
        draw.text((398, py), q, font=qf, fill=(224, 205, 237))
        box = (398, py + 31, 673, py + 83)
        draw.rounded_rectangle(box, radius=10, fill=(18, 14, 54, 165), outline=(112, 83, 155, 210), width=1)
        af = _fit_text(draw, a, 246, 20, 13)
        draw.text((412, py + 58), a, font=af, fill=text_main, anchor='lm')
        py += 105

    # BADGES（枠 698,412 ～ 1016,831）
    selected = []
    for key in _badge_keys(p):
        info = BADGE_LOOKUP[key]
        selected.append((info['label'], info['color']))
    custom = (p.get('custom_badge') or '').strip()
    if custom:
        selected.append((custom, (150, 142, 180)))
    selected = selected[:4]
    while len(selected) < 4:
        selected.append(('未設定', (98, 88, 132)))

    boxes = [(745, 540, 865, 650), (883, 540, 1003, 650),
             (745, 682, 865, 792), (883, 682, 1003, 792)]
    for (label, color), box in zip(selected, boxes):
        fill = tuple(max(18, int(c * .20)) for c in color) + (215,)
        draw.rounded_rectangle(box, radius=17, fill=fill, outline=color, width=2)
        cx = (box[0] + box[2]) // 2
        draw.ellipse((cx - 10, box[1] + 18, cx + 10, box[1] + 38), fill=color)
        bf = _fit_text(draw, label, box[2] - box[0] - 14, 19, 12, bold=True)
        draw.text((cx, box[1] + 82), label, font=bf, fill=text_main, anchor='mm')

    # RANKING（枠 1034,412 ～ 1345,831）
    stats = _profile_weekly_stats(member.guild.id, member.id)
    joined_days = 0
    if getattr(member, 'joined_at', None):
        joined_days = max(1, (datetime.now(timezone.utc) - member.joined_at).days + 1)
    ranks = [
        ('VC時間（今週）', f"{stats['vc_rank']}位" if stats['vc_rank'] else '—', _format_profile_vc(stats['vc_total']), (118, 184, 255)),
        ('チャット数（今週）', f"{stats['chat_rank']}位" if stats['chat_rank'] else '—', f"{stats['chat_total']:,}件", (247, 125, 181)),
        ('サーバー参加日数', f'{joined_days}日' if joined_days else '—', '', (111, 220, 161)),
    ]
    ry = [548, 670, 786]
    for (lab, val, detail, col), yy in zip(ranks, ry):
        lf = _fit_text(draw, lab, 176, 20, 14)
        draw.text((1085, yy), lab, font=lf, fill=text_main, anchor='lm')
        vf = _fit_text(draw, val, 90, 27, 18, bold=True)
        draw.text((1328, yy), val, font=vf, fill=col, anchor='rm')
        if detail:
            df = _fit_text(draw, detail, 120, 19, 13)
            draw.text((1328, yy + 32), detail, font=df, fill=text_sub, anchor='rm')

    # ── 下段：好きなこと（枠 34,855 ～ 1147,1056） ──
    free = ((p.get('free_text') or '').strip() or hobby or '—').replace('☆', '★')
    draw.text((60, 885), '好きなこと', font=_find_japanese_font(29, bold=True), fill=title_col)
    # 長文は2行まで自動折返し
    max_width = 1010
    words = list(free)
    lines, current = [], ''
    body_font = _find_japanese_font(27)
    for ch in words:
        test = current + ch
        if draw.textbbox((0, 0), test, font=body_font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = ch
            if len(lines) == 1:
                break
    if current and len(lines) < 2:
        lines.append(current)
    if len(''.join(lines)) < len(free) and lines:
        while lines[-1] and draw.textbbox((0, 0), lines[-1] + '…', font=body_font)[2] > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] += '…'
    draw.multiline_text((60, 948), '\n'.join(lines or ['—']), font=body_font,
                        fill=text_main, spacing=13)

    out = io.BytesIO()
    img.convert('RGB').save(out, format='PNG', optimize=True)
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
