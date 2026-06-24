import discord
import random
from datetime import date
from database import Database
from config import *   # get_daily_machines, is_high_setting_day など

db = Database()

INFO_PRO_COST = 1000   # スロプロの情報料（ナトコイン）

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セリフ集（ここを書き換えれば文言調整できます）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🧑‍💼 店長（無料・何回でも）── 通常日は景気のいいことだけ
MANAGER_NORMAL = [
    "いらっしゃい！今日もよ〜く回っとるよ！",
    "さっきデカいの出たばっかり、流れ来てる来てる！",
    "キミ、運のよさそうな顔しとるねぇ！",
    "今日はね……ぜ〜んぶアツい！（笑）",
    "負ける気がしない顔だよ、それ！座ってきな！",
    "ウチに悪い台は置いてないよ〜（ニッコリ）",
    "おっ、勝負師の目だ。今日は期待できるよ！",
    "さあさあ、台が温まってるうちに打ってきな！",
    "ツキってのは呼び込むもんだよ、キミならいける！",
    "今日のキミ、何か持ってる気がするねぇ〜",
    "景気よくいこう！笑って打てば運も寄ってくる！",
]
# 🧑‍💼 店長 ── イベント日（末尾1/3/7）は「設定6入れてる」とだけ言う（台数等は言わない）
MANAGER_EVENT = [
    "ここだけの話…今日は設定6、ちゃ〜んと入れてあるよ。探してみな！",
    "キミだから言うけど、本日は設定6アリ！気合い入れていきな！",
    "今日は祭りだよ！6を入れてある、悪いこた言わん、打ってきな！",
    "シーッ…今日は設定6が紛れてるよ。当てられるかい？",
    "本日は特別だ。設定6、入ってる。あとはキミの運次第さ！",
    "今日来たのは正解だよ。6、仕込んであるからね〜！",
]

# 👴 常連のじいさん（1日1回・ふわっと／やや当たる）── 属性ヒント
OJII_PHRASES = {
    "odd":  ["ふぉっふぉ…今日は奇数の台に縁を感じるのう",
             "わしの勘じゃが、奇数の番号がアツい気がするわい"],
    "even": ["今日は偶数の台が呼んどる気がするのう",
             "うーむ、偶数の番号に何かありそうじゃ"],
    "edge": ["端っこの台が気になるのう…ほっほ",
             "今日は隅っこの台に、縁を感じるわい"],
    "mid":  ["真ん中あたりに、何かありそうじゃ",
             "中ほどの台が呼んどる気がするのう"],
    "low":  ["若い番号がアツい気がするわい",
             "小さい番号に縁を感じるのう、ふぉっふぉ"],
    "high": ["番号の大きい台に、縁を感じるのう",
             "後ろの方の番号がアツい気がするわい"],
}
OJII_NOIDEA = [
    "うーむ、今日はピンと来んな。まあ、そういう日もあるわい",
    "ふぉっふぉ…今日は勘が鈍っとる。すまんのう",
    "今日は…なんとも言えんのう。自分の運を信じなされ",
]

# 🕶️ スロプロ（1日1回・1000ナトコイン・常に正確）
PRO_HIT = [
    "{n}番台か…悪くない。高設定の挙動だ、座る価値はある。",
    "{n}番台、アタリだ。今日はそこを回しときな。",
    "{n}番台は本物だ。データは嘘をつかねえ。",
    "{n}番台…いい数字だ。打って損はしねえよ。",
]
PRO_MISS = [
    "{n}番台はやめとけ。今日は伸びん。",
    "{n}番台…ハズレだ。別を当たった方がいい。",
    "{n}番台は薄い。俺なら座らねえな。",
    "{n}番台、期待するだけ無駄だ。よしときな。",
]


def _today():
    return str(date.today())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# セリフ生成ロジック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def manager_line() -> str:
    return random.choice(MANAGER_EVENT if is_high_setting_day() else MANAGER_NORMAL)


def ojii_line() -> str:
    """やや当たる：50%は高設定台の属性を本当に示し、30%は外れ台、20%はノーヒント。
    どれが本当かはプレイヤーには分からない（＝じいさんの味）。"""
    settings = get_daily_machines()
    hot = [i + 1 for i, s in enumerate(settings) if s >= 4]
    cold = [i + 1 for i, s in enumerate(settings) if s <= 3]
    r = random.random()
    if r < 0.5 and hot:
        target = random.choice(hot)
    elif r < 0.8 and cold:
        target = random.choice(cold)
    else:
        return random.choice(OJII_NOIDEA)
    attrs = ["odd" if target % 2 == 1 else "even",
             "edge" if target in (1, 5) else "mid"]
    if target in (1, 2):
        attrs.append("low")
    elif target in (4, 5):
        attrs.append("high")
    return random.choice(OJII_PHRASES[random.choice(attrs)])


def pro_result(machine_no: int):
    """常に正確：その台が高設定(4〜6)かどうか。 (is_high, セリフ) を返す。"""
    settings = get_daily_machines()
    s = settings[machine_no - 1]
    is_high = s >= 4
    line = random.choice(PRO_HIT if is_high else PRO_MISS).format(n=machine_no)
    return is_high, line


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 画面（サブ画面：3人が並ぶ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_info_embed() -> discord.Embed:
    e = discord.Embed(
        title="🕵️ 情報屋",
        description=("薄暗い一角に、見知った顔が三人。\n"
                     "気になるやつに、声をかけてみな。"),
        color=discord.Color.dark_gold(),
    )
    return e


async def _check(interaction, user_id) -> bool:
    if str(interaction.user.id) != user_id:
        await interaction.response.send_message("❌ これはあなたが呼んだ情報屋だよ", ephemeral=True)
        return False
    return True


class InfoResultView(discord.ui.View):
    """各キャラのセリフ表示後に出す戻り導線"""
    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="◀ 情報屋に戻る", style=discord.ButtonStyle.secondary)
    async def back_info(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        await interaction.response.edit_message(embed=build_info_embed(), view=InfoDealerView(self.user_id))

    @discord.ui.button(label="🎰 台選択へ", style=discord.ButtonStyle.primary)
    async def to_select(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        from cogs.slot import build_select_embed, SlotSelectView
        await interaction.response.edit_message(embed=build_select_embed(), view=SlotSelectView())


class InfoDealerView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="🧑‍💼 店長", style=discord.ButtonStyle.success, row=0)
    async def manager(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        e = discord.Embed(title="🧑‍💼 店長", description=manager_line(), color=discord.Color.green())
        await interaction.response.edit_message(embed=e, view=InfoResultView(self.user_id))

    @discord.ui.button(label="👴 常連のじいさん", style=discord.ButtonStyle.secondary, row=0)
    async def ojii(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        if db.get_info_used_date(uid, guild_id, "ojii") == _today():
            e = discord.Embed(title="👴 常連のじいさん",
                              description="ふぉっふぉ…今日はもう話したろ？また明日来なされ。",
                              color=discord.Color.dark_gray())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        db.set_info_used_date(uid, guild_id, "ojii", _today())
        e = discord.Embed(title="👴 常連のじいさん", description=ojii_line(), color=discord.Color.orange())
        e.set_footer(text="※じいさんの勘は…当たるも八卦、当たらぬも八卦（あなたにだけ見えています）")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @discord.ui.button(label="🕶️ スロプロ", style=discord.ButtonStyle.primary, row=0)
    async def pro(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        if db.get_info_used_date(uid, guild_id, "pro") == _today():
            e = discord.Embed(title="🕶️ スロプロ",
                              description="今日はもう教えたろ。明日また来な。",
                              color=discord.Color.dark_gray())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        bal = db.get_balance(uid, guild_id)
        if bal < INFO_PRO_COST:
            e = discord.Embed(title="🕶️ スロプロ",
                              description=f"金が足りねえな。情報料は **{INFO_PRO_COST:,}ナトコイン** だ。出直しな。",
                              color=discord.Color.red())
            await interaction.response.send_message(embed=e, ephemeral=True)
            return
        e = discord.Embed(title="🕶️ スロプロ",
                          description=("なんだ？……こっちもタダで教えるわけにはいかねえんだ。\n"
                                       f"**{INFO_PRO_COST:,}ナトコイン** 払ってくれりゃ、その台が当たりかどうか教えてやるよ。\n\n"
                                       "どの台を見る？番号を選びな。\n"
                                       "（教えられるのは1日1台だけ・あなたにだけ見えています）"),
                          color=discord.Color.dark_purple())
        await interaction.response.send_message(embed=e, view=ProPickView(uid), ephemeral=True)

    @discord.ui.button(label="◀ 台選択に戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back_select(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        from cogs.slot import build_select_embed, SlotSelectView
        await interaction.response.edit_message(embed=build_select_embed(), view=SlotSelectView())


class ProPickButton(discord.ui.Button):
    def __init__(self, machine_no: int, user_id: str):
        super().__init__(label=f"{machine_no}番台", style=discord.ButtonStyle.primary, row=0)
        self.machine_no = machine_no
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if not await _check(interaction, self.user_id): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        # 念のため二重チェック（連打対策）
        if db.get_info_used_date(uid, guild_id, "pro") == _today():
            e = discord.Embed(title="🕶️ スロプロ", description="今日はもう教えたろ。明日な。",
                              color=discord.Color.dark_gray())
            await interaction.response.edit_message(embed=e, view=None); return
        bal = db.get_balance(uid, guild_id)
        if bal < INFO_PRO_COST:
            e = discord.Embed(title="🕶️ スロプロ", description=f"金が足りねえな（{INFO_PRO_COST:,}必要）。",
                              color=discord.Color.red())
            await interaction.response.edit_message(embed=e, view=None); return
        # 課金 → 使用済み記録 → 開示
        db.update_balance(uid, guild_id, -INFO_PRO_COST)
        db.set_info_used_date(uid, guild_id, "pro", _today())
        is_high, line = pro_result(self.machine_no)
        new_bal = db.get_balance(uid, guild_id)
        e = discord.Embed(title="🕶️ スロプロ", description=line,
                          color=discord.Color.green() if is_high else discord.Color.red())
        e.add_field(name="情報料", value=f"-{INFO_PRO_COST:,} ナトコイン", inline=True)
        e.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=True)
        e.set_footer(text="この情報はあなたにだけ見えています")
        await interaction.response.edit_message(embed=e, view=None)


class ProPickView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = user_id
        for i in range(1, 6):
            self.add_item(ProPickButton(i, user_id))

    @discord.ui.button(label="◀ やめる", style=discord.ButtonStyle.secondary, row=1)
    async def cancel(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        e = discord.Embed(title="🕶️ スロプロ", description="今日はやめとくか。気が向いたらまた来な。",
                          color=discord.Color.dark_gray())
        await interaction.response.edit_message(embed=e, view=None)
