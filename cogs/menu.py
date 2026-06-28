import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from datetime import date, datetime, timezone, timedelta
import random
import time
from config import DAILY_AMOUNT, DAILY_SEND_LIMIT, jst_today_str, ADMIN_USER_IDS
from quest_tracker import record as quest_record
import quest_tracker as QT

db = Database()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 共通ヘルパー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def check_user(interaction: discord.Interaction, user_id: str) -> bool:
    """操作者が本人か確認。違う場合はephemeralでエラーを返す"""
    if user_id is not None and str(interaction.user.id) != user_id:
        await interaction.response.send_message("❌ これはあなたのメニューではありません", ephemeral=True)
        return False
    return True


def _daily_claimable(user_id: str, guild_id: str) -> bool:
    return db.get_last_daily(user_id, guild_id) != jst_today_str()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ホームのひとこと（時間帯 × 初回/再訪・丁寧な執事口調・お名前呼び）
#   {name} に「表示名さん」が入る。「おかえり」一辺倒にならないよう散らす。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_JST = timezone(timedelta(hours=9))

# 今日はじめて開いたとき（お出迎え）
WELCOME = {
    "earlymorning": [
        "{name}、おはようございます。ずいぶんとお早いのですね。",
        "{name}、まだ夜も明けきらぬうちに……ようこそお越しを。",
        "おはようございます、{name}。静かな早朝のお供をいたします。",
        "{name}、お早いお目覚めで。本日も良き一日になりますよう。",
        "{name}、夜明け前のひととき、ごゆるりとお過ごしを。",
        "ようこそ、{name}。朝靄の中、お待ち申し上げておりました。",
        "{name}、おはようございます。一番乗りでございますね。",
        "{name}、早起きは三文の徳と申します。よきことがありますよう。",
        "おはようございます、{name}。お茶でもご用意いたしましょうか。",
        "{name}、まだ街も眠っております。どうぞお静かに、お楽しみを。",
        "{name}、清々しい早朝でございます。お会いできて光栄です。",
        "{name}、お早うございます。本日も誠心誠意お供いたします。",
    ],
    "morning": [
        "{name}、おはようございます。本日も良き一日になりますよう。",
        "おはようございます、{name}。お会いできて光栄でございます。",
        "{name}、お目覚めですね。お越しをお待ちしておりました。",
        "{name}、よい朝でございます。本日もどうぞお楽しみを。",
        "{name}、おはようございます。今日も張り切ってまいりましょう。",
        "ようこそ、{name}。爽やかな朝のお供をいたします。",
        "{name}、おはようございます。朝食はお済みでしょうか。",
        "{name}、良き目覚めを。本日のご武運をお祈りいたします。",
        "おはようございます、{name}。今日はどんな一日になりましょうか。",
        "{name}、朝の光がよくお似合いです。ようこそお越しを。",
        "{name}、おはようございます。今日も一日、お供いたします。",
        "ごきげんよう、{name}。素晴らしい朝でございますね。",
    ],
    "noon": [
        "{name}、ようこそお越しくださいました。",
        "いらっしゃいませ、{name}。お昼のひととき、ごゆるりと。",
        "{name}、お待ち申し上げておりました。",
        "ごきげんよう、{name}。本日もお供いたします。",
        "{name}、お昼はお済みでしょうか。ごゆっくりどうぞ。",
        "ようこそ、{name}。日中のひととき、お楽しみを。",
        "{name}、いらっしゃいませ。よい午後になりますよう。",
        "{name}、お忙しい中、よくぞお越しを。",
        "いらっしゃいませ、{name}。少しの息抜きにどうぞ。",
        "{name}、お会いできて光栄です。本日もご一緒に。",
        "{name}、陽の高いうちのお越し、歓迎いたします。",
        "ごきげんよう、{name}。さあ、何から始めましょうか。",
    ],
    "evening": [
        "{name}、本日もお疲れ様でございます。",
        "いらっしゃいませ、{name}。夕暮れのひととき、おくつろぎを。",
        "{name}、お越しいただき光栄でございます。",
        "ごきげんよう、{name}。よい夕べになりますよう。",
        "{name}、一日のお勤め、お疲れ様でございました。",
        "ようこそ、{name}。茜色の空が美しゅうございます。",
        "{name}、夕刻のひととき、ゆるりとお過ごしを。",
        "いらっしゃいませ、{name}。日暮れと共にお迎えを。",
        "{name}、お疲れのところ、ようこそお越しを。",
        "{name}、夕陽に照らされて、ようこそ。お供いたします。",
        "ごきげんよう、{name}。ひと息つかれてはいかがです。",
        "{name}、本日もよくぞ。夕べのひととき、ご一緒に。",
    ],
    "night": [
        "{name}、こんばんは。よい夜をお過ごしくださいませ。",
        "いらっしゃいませ、{name}。夜のひととき、お供いたします。",
        "{name}、本日も一日お疲れ様でございました。",
        "ごきげんよう、{name}。静かな夜にようこそ。",
        "{name}、こんばんは。今宵はどう楽しまれますか。",
        "ようこそ、{name}。夜の帳が下りてまいりました。",
        "{name}、よい夜分でございます。ごゆるりとどうぞ。",
        "いらっしゃいませ、{name}。灯りを灯してお待ちを。",
        "{name}、こんばんは。本日の締めくくりにどうぞ。",
        "{name}、夜のしじまにようこそ。お供いたします。",
        "ごきげんよう、{name}。今宵のご武運をお祈りして。",
        "{name}、こんばんは。月も美しい夜でございます。",
    ],
    "midnight": [
        "{name}、こんな夜更けに……ようこそお越しを。",
        "{name}、夜分遅くにお目覚めですか。お供いたします。",
        "いらっしゃいませ、{name}。深夜のひととき、おしのびで。",
        "{name}、お夜食でもご用意いたしましょうか。",
        "{name}、丑三つ時のお越し、お待ちしておりました。",
        "ようこそ、{name}。静寂の中、そっとお迎えを。",
        "{name}、夜更かしのお供、喜んでいたします。",
        "{name}、こんばんは。くれぐれもお体にはお気をつけて。",
        "{name}、月明かりだけのお出迎えで失礼を。ようこそ。",
        "{name}、眠れぬ夜でございますか。私がお供を。",
        "{name}、深夜にようこそ。どうか、ほどほどに。",
        "{name}、静かな夜更けでございます。ごゆるりと。",
    ],
}

# 同じ日にまた戻ってきたとき（お戻り・表現を散らす）
RETURN = {
    "earlymorning": [
        "{name}、お戻りでしたか。まだ朝も早うございます。",
        "おや、{name}。早々にお戻りとは。お待ちしておりました。",
        "{name}、またお越しで。早朝のひととき、続けてまいりましょう。",
        "お戻りですね、{name}。ご無理は……と申し上げたいところですが。",
        "{name}、お早いお戻りで。何かお忘れ物でも？",
        "{name}、まだ夜明け前。お付き合いいたしますとも。",
        "ふふ、{name}。よほど待ちきれなかったのですね。",
        "{name}、お戻りをお待ちしておりました。さあ、続きを。",
        "{name}、朝の空気は格別でございましょう。お帰りなさいませ。",
        "お戻りで、{name}。一番星もまだ瞬いております。",
        "{name}、またお会いできて。早朝も悪くないものでしょう。",
        "{name}、ご機嫌うるわしゅう。今しばらくお供いたします。",
    ],
    "morning": [
        "{name}、おかえりなさいませ。",
        "お戻りでしたか、{name}。お待ちしておりました。",
        "{name}、またお会いできて嬉しゅうございます。",
        "{name}、ご機嫌うるわしゅう。続けてまいりましょう。",
        "お戻りですね、{name}。次は何をなさいますか。",
        "{name}、朝のうちにもうひと勝負で。頼もしい限りです。",
        "{name}がお戻りになると、朝も華やぎます。",
        "{name}、お帰りで。コーヒーのおかわりはいかがです。",
        "お戻りを、{name}。まだ午前は始まったばかり。",
        "{name}、またのお越し、心より歓迎いたします。",
        "ふふ、{name}。お好きですねえ。さあ、参りましょう。",
        "{name}、お戻りでございますね。本日もご一緒に。",
    ],
    "noon": [
        "{name}、おかえりなさいませ。ご機嫌いかがですか。",
        "お戻りですね、{name}。次は何をなさいますか。",
        "{name}、お待ち申し上げておりました。",
        "{name}がいらっしゃると、華やぎますね。",
        "お戻りで、{name}。お昼休みでございますか。",
        "{name}、またのお越し、嬉しゅうございます。",
        "ふふ、{name}。離れがたいご様子で。",
        "{name}、お帰りなさいませ。続きをご一緒に。",
        "お戻りですね、{name}。午後も頼りにしております。",
        "{name}、よくお戻りで。さあ、参りましょう。",
        "{name}、ちょうどお待ちしていたところでございます。",
        "{name}、おかえりなさいませ。お茶を淹れ直しましょうか。",
    ],
    "evening": [
        "{name}、おかえりなさいませ。",
        "お戻りでしたか、{name}。ちょうどお噂をしておりました。",
        "{name}、よくお戻りで。引き続きお供いたします。",
        "ごきげんよう、{name}。今宵も楽しんでまいりましょう。",
        "お戻りですね、{name}。夕餉の前にもうひと遊び。",
        "{name}、お帰りなさいませ。茜空がお待ちかねです。",
        "ふふ、{name}。まだまだ宵の口でございますよ。",
        "{name}、またお会いできて。夕暮れも華やぎます。",
        "お戻りで、{name}。今日もよくお励みで。",
        "{name}、おかえりなさいませ。続きをご一緒に。",
        "{name}、よくぞお戻りを。さあ、参りましょう。",
        "{name}、お戻りでございますね。日が沈むまでお供を。",
    ],
    "night": [
        "{name}、おかえりなさいませ。",
        "お戻りでしたか、{name}。今宵もご一緒に。",
        "{name}、またお会いできて光栄でございます。",
        "{name}、よい夜を。最後までお供いたします。",
        "お戻りですね、{name}。夜はこれからでございます。",
        "{name}、お帰りなさいませ。灯りを灯してお待ちを。",
        "ふふ、{name}。夜更けのお戻り、嬉しゅうございます。",
        "{name}、よくお戻りで。今宵も心ゆくまで。",
        "お戻りで、{name}。月も見守っております。",
        "{name}、おかえりなさいませ。続きをまいりましょう。",
        "{name}、またのお越し。夜の静けさもご一緒に。",
        "{name}、お戻りでございますね。よい夜をご一緒に。",
    ],
    "midnight": [
        "{name}、おかえりなさいませ。夜更かしもほどほどに。",
        "お戻りですね、{name}。ご無理はなさいませんよう。",
        "{name}、またお会いできて光栄でございます。",
        "{name}、こんな時間に……お戻り、お待ちしておりました。",
        "ふふ、{name}。眠れぬご様子で。お供いたします。",
        "{name}、お帰りなさいませ。そろそろお休みも。",
        "お戻りで、{name}。夜はもうこんなに更けて。",
        "{name}、よくお戻りを。最後の一勝負でございますか。",
        "{name}、深夜のお戻り、嬉しくも心配でございます。",
        "{name}、おかえりなさいませ。お体だけはご大切に。",
        "{name}、また月の下でお会いするとは。お供を。",
        "{name}、お戻りでございますね。どうか、お早めにお休みを。",
    ],
}


def _time_band(hour: int) -> str:
    if hour >= 23 or hour < 4:
        return "midnight"      # 23〜3時
    if 4 <= hour < 7:
        return "earlymorning"  # 4〜6時（早朝）
    if 7 <= hour < 11:
        return "morning"       # 7〜10時（朝）
    if 11 <= hour < 16:
        return "noon"          # 11〜15時（昼）
    if 16 <= hour < 19:
        return "evening"       # 16〜18時（夕方）
    return "night"             # 19〜22時（夜）


def _pick_footer(user, guild_id: str) -> str:
    now = datetime.now(_JST)
    today = str(now.date())
    uid = str(user.id)
    first_today = db.get_menu_seen(uid, guild_id) != today
    db.set_menu_seen(uid, guild_id, today)
    band = _time_band(now.hour)
    pool = WELCOME[band] if first_today else RETURN[band]
    name = f"{user.display_name}さん"
    return random.choice(pool).format(name=name)


async def go_home(interaction: discord.Interaction, user_id: str = None):
    """どこからでもホームへ戻る共通処理（残高付きで描画）"""
    uid = user_id or str(interaction.user.id)
    embed = build_menu_embed(interaction.user, str(interaction.guild.id))
    await interaction.response.edit_message(embed=embed, view=MainMenuView(uid, str(interaction.guild.id)))


async def go_town(interaction: discord.Interaction, user_id: str = None):
    """ナトタウン（=ホーム本体）へ戻る。go_home と同義。"""
    await go_home(interaction, user_id)


async def _coming_soon(interaction, title):
    """未実装の棚：準備中アナウンス（本人だけにephemeral）。"""
    embed = discord.Embed(
        title=f"🔧 {title} ── 準備中",
        description="この施設は近日オープン予定。お楽しみに！",
        color=0x7F8C8D)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ホーム画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_menu_embed(user: discord.abc.User = None, guild_id: str = None):
    """ホームのembed。user と guild_id があれば残高・デイリー・クエスト状況を表示する。"""
    E = "\u001b"  # ANSIエスケープ
    embed = discord.Embed(
        title="🏙️　Ｎ Ａ Ｔ Ｏ　Ｔ Ｏ Ｗ Ｎ　🏙️",
        color=0xC8A24B,  # 上質なゴールド
    )

    if user is not None and guild_id is not None:
        uid = str(user.id)
        bal = db.get_balance(uid, guild_id)
        claimable_daily = _daily_claimable(uid, guild_id)
        try:
            qs = QT.get_status(uid, guild_id)
            q_done = sum(1 for s in qs if s["completed"])
            q_total = len(qs)
            q_claim = sum(1 for s in qs if s["completed"] and not s["claimed"])
        except Exception:
            q_done = q_total = q_claim = 0

        daily_txt = (f"{E}[1;32m受取可能 ●{E}[0m" if claimable_daily
                     else f"{E}[1;30m受取済み{E}[0m")
        try:
            import voyage_config as _V
            _vp = db.get_voyage(uid)
            _lv = _vp.get("level", 1); _xp = _vp.get("xp", 0); _nxt = _V.xp_to_next(_lv)
            adv_txt = f"{E}[1;36mLv.{_lv}（XP {_xp}/{_nxt}）{E}[0m"
        except Exception:
            adv_txt = f"{E}[1;36mLv.1{E}[0m"
        quest_txt = f"{E}[1;36m{q_done} / {q_total} 達成{E}[0m"
        if q_claim:
            quest_txt += f"  {E}[1;33m🎁 受取可能{E}[0m"

        embed.description = (
            "```ansi\n"
            f"{E}[1;30m──────────  WALLET  ──────────{E}[0m\n"
            f"{E}[0;33m💰 残高　　{E}[1;37m {bal:,} ナトコイン{E}[0m\n"
            f"{E}[0;33m🎁 デイリー{E}[0m {daily_txt}\n"
            f"{E}[0;33m📜 クエスト{E}[0m {quest_txt}\n"
            f"{E}[0;33m🗺️ 冒険者　{E}[0m {adv_txt}\n"
            f"{E}[1;30m──────────────────────────────{E}[0m\n"
            "```"
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    else:
        embed.description = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n下のボタンから選んでね"

    embed.add_field(
        name="〔　Ｍ Ｅ Ｎ Ｕ　〕",
        value=(
            "🎣　**釣り**　　　── 湖・川・海で大物を狙う\n"
            "⚓　**さびれた港**── 船で大海原へ。航海・白兵戦・財宝\n"
            "🛒　**商店街**　　── 船・道具・装備・ガチャ\n"
            "🏛️　**ギルド**　　── 討伐クエストで稼ぐ（準備中）\n"
            "🛤️　**街道**　　　── 平原・森・山を徒歩で冒険\n"
            "🃏　**カジノ**　　── スロット＆テーブルで一攫千金\n"
            "📱　**スマホ**　　── 銀行・デイリー・クエスト・募集\n"
            "🏠　**家**　　　　── 休んでHPを全快（5分ごと）"
        ),
        inline=False,
    )
    if user is not None and guild_id is not None:
        embed.set_footer(text=_pick_footer(user, guild_id))
    return embed


class MainMenuView(discord.ui.View):
    def __init__(self, user_id: str = None, guild_id: str = None):
        super().__init__(timeout=900)
        self.user_id = user_id
        # スマホボタンにLINE未読バッジを付ける（通知設定OFFでも表示）
        if user_id and guild_id:
            try:
                n = db.line_unread_count(guild_id, user_id)
            except Exception:
                n = 0
            if n > 0:
                for c in self.children:
                    if isinstance(c, discord.ui.Button) and c.label and c.label.startswith("📱"):
                        c.label = f"📱 スマホ 🔴{n}"
                        break

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    # ── 1段目：今あそべる2大コンテンツ ──
    @discord.ui.button(label="🎣 釣り", style=discord.ButtonStyle.primary, row=0)
    async def fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import build_fish_menu_embed
        await interaction.response.edit_message(
            embed=build_fish_menu_embed(), view=FishMenuView(str(interaction.user.id)))

    @discord.ui.button(label="⚓ さびれた港", style=discord.ButtonStyle.primary, row=0)
    async def port(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fund import open_port
        await open_port(interaction, str(interaction.user.id), "danger_zone")

    # ── 2段目：商店街（船・道具・装備・ガチャ）──
    @discord.ui.button(label="🚢 船屋", style=discord.ButtonStyle.secondary, row=1)
    async def shipwright(self, interaction, button):
        if not await self._check(interaction): return
        await _coming_soon(interaction, "船屋")

    @discord.ui.button(label="🛒 道具屋", style=discord.ButtonStyle.secondary, row=1)
    async def item_shop(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.voyage import open_item_shop
        await open_item_shop(interaction, str(interaction.user.id))

    @discord.ui.button(label="⚔️ 装備屋", style=discord.ButtonStyle.secondary, row=1)
    async def equip_shop(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.voyage import open_equip_shop
        await open_equip_shop(interaction, str(interaction.user.id))

    @discord.ui.button(label="🎰 ガチャ屋", style=discord.ButtonStyle.secondary, row=1)
    async def gacha(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.voyage import open_skill_gacha
        await open_skill_gacha(interaction, str(interaction.user.id))

    # ── 3段目：冒険（ギルド・街道）──
    @discord.ui.button(label="🏛️ ギルド", style=discord.ButtonStyle.secondary, row=2)
    async def guild(self, interaction, button):
        if not await self._check(interaction): return
        await _coming_soon(interaction, "ギルド")

    @discord.ui.button(label="🛤️ 街道", style=discord.ButtonStyle.secondary, row=2)
    async def road(self, interaction, button):
        if not await self._check(interaction): return
        from cogs.land import open_land
        await open_land(interaction, str(interaction.user.id))

    @discord.ui.button(label="🏠", style=discord.ButtonStyle.secondary, row=2)
    async def house(self, interaction, button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        gid = str(interaction.guild.id)
        vp = db.get_voyage(uid)
        HOME_HEAL_CD = 300  # 5分
        last = vp.get("last_home_heal", 0)
        left = HOME_HEAL_CD - (time.time() - last)
        mh = 100 + (vp.get("level", 1) - 1) * 10
        if left > 0:
            m, s = divmod(int(left) + 1, 60)
            await interaction.response.send_message(
                f"🏠 まだ休めない。次に休めるまで **あと {m}分{s}秒**。", ephemeral=True); return
        if vp.get("cur_hp", mh) >= mh:
            # 満タンでもCDは消費しない（無駄打ち防止）。一応知らせる。
            await interaction.response.send_message(
                "🏠 もうHPは満タンだ。よく休めている。", ephemeral=True); return
        vp["cur_hp"] = mh
        vp["last_home_heal"] = time.time()
        db.save_voyage(uid, vp)
        await interaction.response.send_message(
            f"🏠 家でゆっくり休んだ。**HPが全快した！**（{mh}/{mh}）\n"
            f"次に休めるのは5分後。", ephemeral=True)

    # ── 4段目：カジノ・スマホ ──
    @discord.ui.button(label="🃏 カジノ", style=discord.ButtonStyle.success, row=3)
    async def casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        await interaction.response.edit_message(embed=build_casino_embed(), view=CasinoMenuView(uid))

    @discord.ui.button(label="📱 スマホ", style=discord.ButtonStyle.success, row=3)
    async def wallet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        from cogs.phone import build_phone_embed, PhoneHomeView
        await interaction.response.send_message(
            embed=build_phone_embed(interaction.user, interaction.guild),
            view=PhoneHomeView(uid), ephemeral=True)

    @discord.ui.button(label="📦 インベントリ", style=discord.ButtonStyle.primary, row=3)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.voyage import open_inventory
        await open_inventory(interaction, str(interaction.user.id), back="town")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# カジノメニュー（スロット以外のゲーム）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_GAME_ENTRY = {
    "blackjack": ("♠️　Ｂ Ｌ Ａ Ｃ Ｋ Ｊ Ａ Ｃ Ｋ", "21 を超えず、ディーラーを上回れ", "賭け金"),
    "poker":     ("♠️　Ｐ Ｏ Ｋ Ｅ Ｒ", "役で魅せる心理戦。最後に笑うのは誰か", "アンティ"),
    "chinchiro": ("🎲　Ｃ Ｈ Ｉ Ｎ Ｃ Ｈ Ｉ Ｒ Ｏ", "天運のサイコロ、振るは己の度胸", "賭け金"),
    "numguess":  ("🎯　Ｎ Ｕ Ｍ Ｂ Ｅ Ｒ", "一点を読み切る、その美学", "賭け金"),
    "coinflip":  ("🪙　Ｃ Ｏ Ｉ Ｎ　Ｆ Ｌ Ｉ Ｐ", "表か、裏か。運命は一瞬で決まる", "賭け金"),
}


def build_game_entry_embed(game: str) -> discord.Embed:
    title, catch, betword = _GAME_ENTRY[game]
    E = "\u001b"
    G = f"{E}[1;33m"; R = f"{E}[1;31m"; W = f"{E}[1;37m"; K = f"{E}[1;30m"; g = f"{E}[0;33m"; X = f"{E}[0m"
    desc = (
        "```ansi\n"
        f"{R}╔══════════════════════════════╗{X}\n"
        f"{W}   {catch}{X}\n"
        f"{R}╚══════════════════════════════╝{X}\n"
        "\n"
        f"{R}━━━━━━━━━━━━━━━━━━━━━━━━━━━━{X}\n"
        f"{g}   {betword}　{W}100 〜 2,000{g} ナトコイン{X}\n"
        f"{K}   下の「✏️ 入力」からどうぞ{X}\n"
        "```"
    )
    return discord.Embed(title=title, description=desc, color=0xA31621)


def build_mode_select_embed(game: str, bet: int) -> discord.Embed:
    title, _catch, betword = _GAME_ENTRY[game]
    E = "\u001b"
    G = f"{E}[1;33m"; R = f"{E}[1;31m"; W = f"{E}[1;37m"; K = f"{E}[1;30m"; g = f"{E}[0;33m"; X = f"{E}[0m"
    desc = (
        "```ansi\n"
        f"{R}╔══════════════════════════════╗{X}\n"
        f"{g}   {betword}　{W}{bet:,}{g} ナトコイン{X}\n"
        f"{R}╚══════════════════════════════╝{X}\n"
        "\n"
        f"{K}   遊ぶモードをお選びください{X}\n"
        "```"
    )
    return discord.Embed(title=title, description=desc, color=0xA31621)


def build_casino_embed() -> discord.Embed:
    """深紅×ゴールドの高級カジノ風メニュー。"""
    E = "\u001b"
    G = f"{E}[1;33m"   # ゴールド（太字黄）
    g = f"{E}[0;33m"   # 淡ゴールド
    R = f"{E}[1;31m"   # 深紅
    W = f"{E}[1;37m"   # 白
    K = f"{E}[1;30m"   # グレー
    X = f"{E}[0m"
    desc = (
        "```ansi\n"
        f"{R}╔══════════════════════════════╗{X}\n"
        f"{G}     ✦  Ｇ Ｒ Ａ Ｎ Ｄ  Ｃ Ａ Ｓ Ｉ Ｎ Ｏ  ✦{X}\n"
        f"{K}        ようこそ、今宵のテーブルへ{X}\n"
        f"{R}╚══════════════════════════════╝{X}\n"
        "\n"
        f"{G}🃏 ブラックジャック {K}…… {W}ディーラーとの一騎打ち{X}\n"
        f"{G}♠️ ポーカー        {K}…… {W}役で魅せる心理戦{X}\n"
        f"{G}🎲 チンチロ        {K}…… {W}運命のサイコロ勝負{X}\n"
        f"{G}🎯 数字当て        {K}…… {W}一点読みの美学{X}\n"
        f"{G}🪙 コインフリップ  {K}…… {W}表か、裏か{X}\n"
        "\n"
        f"{R}━━━━━━━━━━━━━━━━━━━━━━━━━━━━{X}\n"
        f"{g}   ベット {W}100 〜 2,000{g} ナトコイン{X}\n"
        "```"
    )
    embed = discord.Embed(
        title="♠️ ♥️　Ｃ Ａ Ｓ Ｉ Ｎ Ｏ　♦️ ♣️",
        description=desc,
        color=0xA31621,  # 深紅
    )
    embed.set_footer(text="♣ ♦ ♥ ♠　ごゆるりとお楽しみを")
    return embed


async def open_casino_menu(interaction, user_id=None):
    """カジノメニューを開く（各ゲームの『戻る』から共通で使う）。"""
    uid = user_id or str(interaction.user.id)
    await interaction.response.edit_message(embed=build_casino_embed(), view=CasinoMenuView(uid))

class CasinoMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🎰 スロット", style=discord.ButtonStyle.danger, row=0)
    async def slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.slot import active_slots
        from cogs.juggler import active_jug, build_kishu_embed, KishuSelectView
        uid = str(interaction.user.id)
        g = active_slots.get(uid)
        jg = active_jug.get(uid)
        if (g and g.get("spinning")) or (jg and jg.get("spinning")):
            await interaction.response.send_message(
                "⏳ 演出の途中です。数秒待ってからもう一度お試しください。", ephemeral=True)
            return
        active_slots.pop(uid, None)
        active_jug.pop(uid, None)
        await interaction.response.edit_message(embed=build_kishu_embed(), view=KishuSelectView())

    @discord.ui.button(label="🃏 ブラックジャック", style=discord.ButtonStyle.primary, row=0)
    async def blackjack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = build_game_entry_embed("blackjack")
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "blackjack", "ブラックジャック — 賭け金入力"))

    @discord.ui.button(label="♠️ ポーカー", style=discord.ButtonStyle.primary, row=0)
    async def poker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = build_game_entry_embed("poker")
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "poker", "ポーカー — アンティ入力"))

    @discord.ui.button(label="🎲 チンチロ", style=discord.ButtonStyle.primary, row=0)
    async def chinchiro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = build_game_entry_embed("chinchiro")
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "chinchiro", "チンチロ — 賭け金入力"))

    @discord.ui.button(label="🎯 数字当て", style=discord.ButtonStyle.primary, row=1)
    async def numguess(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = build_game_entry_embed("numguess")
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "numguess", "数字当て — 賭け金入力"))

    @discord.ui.button(label="🪙 コインフリップ", style=discord.ButtonStyle.primary, row=1)
    async def coinflip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = build_game_entry_embed("coinflip")
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "coinflip", "コインフリップ — 賭け金入力"))

    @discord.ui.button(label="🏠 ホームへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await go_home(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 賭け金入力（カジノ各ゲーム共通）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BetModal(discord.ui.Modal):
    bet_input = discord.ui.TextInput(
        label="賭け金（100〜2,000ナトコイン）",
        placeholder="例: 1000",
        min_length=1,
        max_length=7,
    )

    def __init__(self, title: str, user_id: str, guild_id: str, game_type: str):
        super().__init__(title=title)
        self.user_id = user_id
        self.guild_id = guild_id
        self.game_type = game_type

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = self.guild_id or str(interaction.guild.id)
        try:
            bet = int(self.bet_input.value.replace(",", "").replace("，", ""))
        except ValueError:
            await interaction.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return

        if bet < 100:
            await interaction.response.send_message("❌ 最低100ナトコインから", ephemeral=True)
            return
        if bet > 2000:
            await interaction.response.send_message("❌ 最大2,000ナトコインまで", ephemeral=True)
            return

        bal = db.get_balance(self.user_id, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        # デイリークエスト: カジノを1プレイ（チンチロは専用クエストも加算）
        quest_record(self.user_id, guild_id, "casino")
        if self.game_type == "chinchiro":
            quest_record(self.user_id, guild_id, "chinchiro")

        if self.game_type == "blackjack":
            from cogs.blackjack import BlackjackModeView
            embed = build_mode_select_embed("blackjack", bet)
            await interaction.response.edit_message(embed=embed, view=BlackjackModeView(bet))

        elif self.game_type == "poker":
            from cogs.poker import PokerModeView
            embed = build_mode_select_embed("poker", bet)
            await interaction.response.edit_message(embed=embed, view=PokerModeView(bet))

        elif self.game_type == "chinchiro":
            from cogs.chinchiro import ChinchiroModeView
            embed = build_mode_select_embed("chinchiro", bet)
            await interaction.response.edit_message(embed=embed, view=ChinchiroModeView(bet))

        elif self.game_type == "numguess":
            from cogs.numguess import active_games, NumguessPlayView, build_game_embed
            if self.user_id in active_games:
                await interaction.response.send_message("❌ すでにゲーム中です", ephemeral=True)
                return
            db.update_balance(self.user_id, guild_id, -bet)
            answer = random.randint(1, 100)
            active_games[self.user_id] = {"answer": answer, "tries": 0, "bet": bet, "guild_id": guild_id}
            embed = build_game_embed(active_games[self.user_id], "1〜100の数字を当ててください！")
            await interaction.response.edit_message(embed=embed, view=NumguessPlayView(self.user_id, guild_id))

        elif self.game_type == "coinflip":
            embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(bet, self.user_id))


def make_bet_view(user_id: str, guild_id: str, game_type: str, title: str, back_label: str = "◀️ カジノへ戻る"):
    """賭け金入力ボタン1つのViewを生成"""
    class BetView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=900)
            self._user_id = user_id
            self._guild_id = guild_id
            self._game_type = game_type
            self._modal_title = title

        @discord.ui.button(label="💰 賭け金を入力する", style=discord.ButtonStyle.primary, emoji="✏️")
        async def enter_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await check_user(interaction, self._user_id): return
            modal = BetModal(self._modal_title, self._user_id, self._guild_id, self._game_type)
            await interaction.response.send_modal(modal)

        @discord.ui.button(label=back_label, style=discord.ButtonStyle.secondary)
        async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not await check_user(interaction, self._user_id): return
            await open_casino_menu(interaction, self._user_id)

    return BetView()


# 後方互換（他から呼ばれても動くように残す）
def BlackjackBetView(user_id: str):
    return make_bet_view(user_id, None, "blackjack", "ブラックジャック — 賭け金入力")

def PokerBetView(user_id: str):
    return make_bet_view(user_id, None, "poker", "ポーカー — アンティ入力")

def ChinchiroBetView(user_id: str):
    return make_bet_view(user_id, None, "chinchiro", "チンチロ — 賭け金入力")

def NumguessBetView(user_id: str):
    return make_bet_view(user_id, None, "numguess", "数字当て — 賭け金入力")

def CoinflipBetView(user_id: str):
    return make_bet_view(user_id, None, "coinflip", "コインフリップ — 賭け金入力")


class CoinflipChoiceView(discord.ui.View):
    def __init__(self, bet: int, user_id: str):
        super().__init__(timeout=900)
        self.bet = bet
        self.user_id = user_id

    async def do_flip(self, interaction: discord.Interaction, choice: str):
        if not await check_user(interaction, self.user_id): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message("❌ ナトコインが足りません", ephemeral=True)
            return
        result = random.choice(["heads", "tails"])
        won = choice == result
        if won:
            db.update_balance(uid, guild_id, self.bet)
            net = self.bet
        else:
            db.update_balance(uid, guild_id, -self.bet)
            net = -self.bet
        new_bal = db.get_balance(uid, guild_id)
        result_emoji = "🪙 表" if result == "heads" else "🪙 裏"
        embed = discord.Embed(title="🪙 コインフリップ", color=discord.Color.green() if won else discord.Color.red())
        embed.add_field(name="結果", value=result_emoji, inline=True)
        embed.add_field(name="あなた", value="表" if choice == "heads" else "裏", inline=True)
        embed.add_field(name="判定", value=f"{'🎉 勝ち！' if won else '😢 負け...'} {net:+,} ナトコイン", inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
        if won and net > 0:
            from cogs.doubleup import build_entry_view
            view = build_entry_view(uid, guild_id, net, "コインフリップ",
                                    lambda: CoinflipAgainView(self.bet, self.user_id))
        else:
            view = CoinflipAgainView(self.bet, self.user_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="表 (Heads)", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "heads")

    @discord.ui.button(label="裏 (Tails)", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "tails")

    @discord.ui.button(label="◀️ 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await open_casino_menu(interaction, self.user_id)


class CoinflipAgainView(discord.ui.View):
    def __init__(self, bet: int, user_id: str):
        super().__init__(timeout=900)
        self.bet = bet
        self.user_id = user_id

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🪙")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(self.bet, self.user_id))

    @discord.ui.button(label="◀️ カジノへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await open_casino_menu(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣りメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FishMenuView(discord.ui.View):
    def __init__(self, user_id: str = None):
        super().__init__(timeout=900)
        self.user_id = user_id

    async def _check(self, interaction):
        if self.user_id is None:
            self.user_id = str(interaction.user.id)
            return True
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🏞️ 湖（10ナトコイン）", style=discord.ButtonStyle.success, row=0)
    async def lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._enter_area(interaction, "lake")

    @discord.ui.button(label="🏔️ 川（50ナトコイン）", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._enter_area(interaction, "river")

    @discord.ui.button(label="🌊 海（100ナトコイン）", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await self._enter_area(interaction, "sea")

    async def _enter_area(self, interaction: discord.Interaction, area: str):
        """エリア選択 → (装備の相性で)警告 → 3つの釣り場(①②③)を表示。"""
        from cogs.fishing import build_spot_menu_embed
        from config import FISHING_RODS, rod_warns_here
        gear = db.get_gear(self.user_id)
        rod = FISHING_RODS[gear["rod_id"]]
        # 入場自体は妨げない。竿が不適なら実際に釣ろうとした時(do_fish)に
        # 「この竿だと釣れない」とアナウンスが出る方針。
        # 得意エリア外なら「得しない」警告を挟む
        if rod_warns_here(gear["rod_id"], area):
            await interaction.response.edit_message(
                embed=_build_warn_embed(rod, area),
                view=AreaWarnView(area, self.user_id))
            return
        await interaction.response.edit_message(
            embed=build_spot_menu_embed(area), view=SpotMenuView(area, self.user_id))

    @discord.ui.button(label="🌤️ 天気予報士", style=discord.ButtonStyle.secondary, row=1)
    async def forecaster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import forecaster_embed, NPCView
        await interaction.response.edit_message(embed=forecaster_embed(), view=NPCView("forecaster", self.user_id))

    @discord.ui.button(label="🎣 怪しい釣り人", style=discord.ButtonStyle.secondary, row=1)
    async def angler(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import angler_embed, NPCView
        await interaction.response.edit_message(embed=angler_embed(), view=NPCView("angler", self.user_id))

    @discord.ui.button(label="🏪 釣具屋", style=discord.ButtonStyle.success, row=2)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.shop import ShopView
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())

    @discord.ui.button(label="🗺️ 宝の地図を使う", style=discord.ButtonStyle.primary, row=2)
    async def treasure(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import use_treasure_map
        await use_treasure_map(interaction, edit=True)

    @discord.ui.button(label="◀ ナトタウンへ戻る", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await go_town(interaction, self.user_id)


class SpotMenuView(discord.ui.View):
    """エリア内の3つの釣り場(①②③)。中身は同じ・時間帯と天候だけ異なる。"""
    def __init__(self, area, user_id: str = None):
        super().__init__(timeout=900)
        self.area = area
        self.user_id = user_id

    async def _check(self, interaction):
        if self.user_id is None:
            self.user_id = str(interaction.user.id)
            return True
        return await check_user(interaction, self.user_id)

    async def _go(self, interaction, spot):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, self.area, spot, edit=True)

    @discord.ui.button(label="①", style=discord.ButtonStyle.success, row=0)
    async def s1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, 1)

    @discord.ui.button(label="②", style=discord.ButtonStyle.primary, row=0)
    async def s2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, 2)

    @discord.ui.button(label="③", style=discord.ButtonStyle.danger, row=0)
    async def s3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._go(interaction, 3)

    @discord.ui.button(label="◀️ エリア選択へ", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import build_fish_menu_embed
        await interaction.response.edit_message(embed=build_fish_menu_embed(), view=FishMenuView(self.user_id))


_AREA_LABEL = {"lake": "🏞️湖", "river": "🏔️川", "sea": "🌊海"}

def _build_warn_embed(rod, area):
    """得意エリア外で釣ろうとした時の『得しない』注意。"""
    area_lbl = _AREA_LABEL.get(area, area)
    if rod is not None and rod.get("home") == "sea" and rod.get("name", "").startswith("伝説"):
        body = (f"{area_lbl}は「{rod['name']}」の本領（🌊海）ではありません。\n"
                f"ここでも**レジェンド級の魚は釣れます**が、竿の消耗が増えて**収支はトントン**（大きくは稼げません）。\n\n"
                f"それでもこの場所で釣りますか？")
    else:
        home_lbl = _AREA_LABEL.get(rod.get("home"), "得意エリア") if rod else "得意エリア"
        body = (f"{area_lbl}は「{rod['name']}」の得意な場所ではありません。\n"
                f"釣れますが消耗が増えて**収支はトントン**（あまり得しません）。\n"
                f"しっかり稼ぐなら **{home_lbl}** がおすすめです。\n\n"
                f"それでもこの場所で釣りますか？")
    return discord.Embed(title="⚠️ ここは得意エリアじゃないよ", description=body, color=0xE67E22)


class AreaWarnView(discord.ui.View):
    """得意エリア外の確認。続行で釣り場(①②③)へ、やめるでエリア選択へ。"""
    def __init__(self, area, user_id: str = None):
        super().__init__(timeout=900)
        self.area = area
        self.user_id = user_id

    async def _check(self, interaction):
        if self.user_id is None:
            self.user_id = str(interaction.user.id)
            return True
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="それでも釣る", style=discord.ButtonStyle.danger, emoji="🎣", row=0)
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import build_spot_menu_embed
        await interaction.response.edit_message(
            embed=build_spot_menu_embed(self.area), view=SpotMenuView(self.area, self.user_id))

    @discord.ui.button(label="エリア選択へ戻る", style=discord.ButtonStyle.secondary, emoji="◀️", row=0)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import build_fish_menu_embed
        await interaction.response.edit_message(embed=build_fish_menu_embed(), view=FishMenuView(self.user_id))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ウォレットメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WalletMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="💰 残高確認", style=discord.ButtonStyle.secondary, row=0)
    async def balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        embed = discord.Embed(title="💰 残高確認", color=discord.Color.gold())
        embed.add_field(name=interaction.user.display_name, value=f"**{bal:,} ナトコイン**")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💸 送金", style=discord.ButtonStyle.primary, row=0)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        today_sent = db.get_today_sent(uid, guild_id)
        remaining = max(0, DAILY_SEND_LIMIT - today_sent)
        if remaining <= 0:
            await interaction.response.send_message(
                f"❌ 本日の送金上限（{DAILY_SEND_LIMIT:,} ナトコイン）に達しています。明日また試してね！",
                ephemeral=True)
            return
        embed = discord.Embed(
            title="💸 送金",
            description=f"送り先を選んでください\n\n本日の残り送金枠: **{remaining:,} / {DAILY_SEND_LIMIT:,} ナトコイン**",
            color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=SendSelectView(uid, guild_id, remaining))

    @discord.ui.button(label="◀️ スマホに戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.phone import open_phone
        await open_phone(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 送金フロー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SendAmountModal(discord.ui.Modal, title="💸 送金額を入力"):
    amount_input = discord.ui.TextInput(
        label="送金額（ナトコイン）",
        placeholder="例: 500",
        min_length=1,
        max_length=7,
    )

    def __init__(self, sender_id: str, guild_id: str, target_id: str, target_name: str, remaining: int):
        super().__init__()
        self.sender_id = sender_id
        self.guild_id = guild_id
        self.target_id = target_id
        self.target_name = target_name
        self.remaining = remaining

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value.replace(",", "").replace("，", ""))
        except ValueError:
            await interaction.response.send_message("❌ 金額は数字で入力してください", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("❌ 1以上の金額を入力してください", ephemeral=True)
            return
        if amount > self.remaining:
            await interaction.response.send_message(
                f"❌ 本日の送金上限を超えています（残り: {self.remaining:,} ナトコイン）", ephemeral=True)
            return
        bal = db.get_balance(self.sender_id, self.guild_id)
        if bal < amount:
            await interaction.response.send_message(
                f"❌ ナトコインが足りません（残高: {bal:,} ナトコイン）", ephemeral=True)
            return

        # 送金実行
        db.update_balance(self.sender_id, self.guild_id, -amount)
        db.update_balance(self.target_id, self.guild_id, amount)
        db.add_send_log(self.sender_id, self.guild_id, amount)
        quest_record(self.sender_id, self.guild_id, "send")   # 送金クエスト

        new_bal = db.get_balance(self.sender_id, self.guild_id)
        today_sent = db.get_today_sent(self.sender_id, self.guild_id)
        remaining_after = max(0, DAILY_SEND_LIMIT - today_sent)

        embed = discord.Embed(
            title="💸 送金完了！",
            description=f"{interaction.user.mention} → **{self.target_name}**\n**{amount:,} ナトコイン** を送りました！",
            color=discord.Color.green())
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
        embed.add_field(name="本日の残り送金枠", value=f"{remaining_after:,} / {DAILY_SEND_LIMIT:,} ナトコイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=SendBackView(self.sender_id))


class UserPicker(discord.ui.UserSelect):
    def __init__(self, sender_id: str, guild_id: str, remaining: int):
        super().__init__(placeholder="送り先のメンバーを選んでください...", min_values=1, max_values=1)
        self.sender_id = sender_id
        self.guild_id = guild_id
        self.remaining = remaining

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.sender_id:
            await interaction.response.send_message("❌ これはあなたのメニューではありません", ephemeral=True)
            return
        target = self.values[0]
        if getattr(target, "bot", False):
            await interaction.response.send_message("❌ BOTには送れません", ephemeral=True)
            return
        if str(target.id) == self.sender_id:
            await interaction.response.send_message("❌ 自分自身には送れません", ephemeral=True)
            return
        modal = SendAmountModal(self.sender_id, self.guild_id, str(target.id), target.display_name, self.remaining)
        await interaction.response.send_modal(modal)


class SendSelectView(discord.ui.View):
    def __init__(self, sender_id: str, guild_id: str, remaining: int):
        super().__init__(timeout=900)
        self.sender_id = sender_id
        self.guild_id = guild_id
        self.remaining = remaining
        self.add_item(UserPicker(sender_id, guild_id, remaining))

    @discord.ui.button(label="🏠 ホームへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.sender_id): return
        await go_home(interaction, self.sender_id)


class SendBackView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id

    @discord.ui.button(label="🏠 ホームへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await go_home(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Menu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="menu", description="BOTのメニューを開く")
    async def menu(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        embed = build_menu_embed(interaction.user, str(interaction.guild.id))
        await interaction.response.send_message(embed=embed, view=MainMenuView(uid, str(interaction.guild.id)))


async def setup(bot):
    await bot.add_cog(Menu(bot))
