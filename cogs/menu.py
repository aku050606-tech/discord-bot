import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from datetime import date
import random

db = Database()

DAILY_AMOUNT = 500          # デイリーボーナス額
DAILY_SEND_LIMIT = 3000     # 1日の送金上限（ナトコイン）

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
    return db.get_last_daily(user_id, guild_id) != str(date.today())


async def go_home(interaction: discord.Interaction, user_id: str = None):
    """どこからでもホームへ戻る共通処理（残高付きで描画）"""
    uid = user_id or str(interaction.user.id)
    embed = build_menu_embed(interaction.user, str(interaction.guild.id))
    await interaction.response.edit_message(embed=embed, view=MainMenuView(uid))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ホーム画面
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_menu_embed(user: discord.abc.User = None, guild_id: str = None):
    """ホームのembed。user と guild_id があれば残高・デイリー状況を表示する。"""
    embed = discord.Embed(
        title="🎮 BOTメニュー",
        description="使いたいメニューを選んでください",
        color=discord.Color.blurple(),
    )

    if user is not None and guild_id is not None:
        uid = str(user.id)
        bal = db.get_balance(uid, guild_id)
        claimable = _daily_claimable(uid, guild_id)
        embed.add_field(name="💰 残高", value=f"**{bal:,}** ナトコイン", inline=True)
        embed.add_field(
            name="🎁 本日のデイリー",
            value="受け取り可能！" if claimable else "受け取り済み",
            inline=True,
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)

    embed.add_field(
        name="メニュー一覧",
        value=(
            "🎰 **スロット** — EVENT HORIZONを目指せ\n"
            "🎣 **釣り** — 湖・川・海／図鑑／釣具屋\n"
            "🃏 **カジノ** — BJ・ポーカー・チンチロ 等\n"
            "💰 **ウォレット** — 残高・デイリー・送金・ランキング"
        ),
        inline=False,
    )
    return embed


class MainMenuView(discord.ui.View):
    def __init__(self, user_id: str = None):
        super().__init__(timeout=900)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    # ── 1段目：力を入れている2大コンテンツを個別枠で ──
    @discord.ui.button(label="🎰 スロット", style=discord.ButtonStyle.primary, row=0)
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

    @discord.ui.button(label="🎣 釣り", style=discord.ButtonStyle.success, row=0)
    async def fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        from cogs.fishing import build_fish_menu_embed
        embed = build_fish_menu_embed()
        await interaction.response.edit_message(embed=embed, view=FishMenuView(uid))

    # ── 2段目：その他ゲーム & ウォレット ──
    @discord.ui.button(label="🃏 カジノ", style=discord.ButtonStyle.primary, row=1)
    async def casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        embed = discord.Embed(
            title="🃏 カジノ",
            description="遊ぶゲームを選んでください\nベット **100〜2,000** ナトコイン",
            color=discord.Color.dark_purple(),
        )
        await interaction.response.edit_message(embed=embed, view=CasinoMenuView(uid))

    @discord.ui.button(label="💰 ウォレット", style=discord.ButtonStyle.secondary, row=1)
    async def wallet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        embed = discord.Embed(title="💰 ウォレット", color=discord.Color.gold())
        embed.add_field(name="現在の残高", value=f"**{bal:,}** ナトコイン", inline=False)
        await interaction.response.edit_message(embed=embed, view=WalletMenuView(uid))

    # ── 3段目：ワンタップ・デイリー受取 ──
    @discord.ui.button(label="🎁 デイリー受取", style=discord.ButtonStyle.success, row=2)
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        if not _daily_claimable(uid, guild_id):
            await interaction.response.send_message(
                "⏰ 今日はすでにデイリーボーナスを受け取っています！", ephemeral=True)
            return
        db.update_balance(uid, guild_id, DAILY_AMOUNT)
        db.set_last_daily(uid, guild_id, str(date.today()))
        # ホームを最新残高で再描画
        await go_home(interaction, uid)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# カジノメニュー（スロット以外のゲーム）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def open_casino_menu(interaction, user_id=None):
    """カジノメニューを開く（各ゲームの『戻る』から共通で使う）。"""
    uid = user_id or str(interaction.user.id)
    embed = discord.Embed(
        title="🃏 カジノ",
        description="遊ぶゲームを選んでください\nベット **100〜2,000** ナトコイン",
        color=discord.Color.dark_purple(),
    )
    await interaction.response.edit_message(embed=embed, view=CasinoMenuView(uid))

class CasinoMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🃏 ブラックジャック", style=discord.ButtonStyle.primary, row=0)
    async def blackjack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🃏 ブラックジャック", description="賭け金を入力してください！\n**100〜2,000ナトコイン**", color=discord.Color.dark_green())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "blackjack", "ブラックジャック — 賭け金入力"))

    @discord.ui.button(label="♠️ ポーカー", style=discord.ButtonStyle.primary, row=0)
    async def poker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="♠️ ポーカー", description="アンティ（参加費）を入力してください！\n**100〜2,000ナトコイン**", color=discord.Color.dark_green())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "poker", "ポーカー — アンティ入力"))

    @discord.ui.button(label="🎲 チンチロ", style=discord.ButtonStyle.primary, row=0)
    async def chinchiro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🎲 チンチロ", description="賭け金を入力してください！\n**100〜2,000ナトコイン**", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "chinchiro", "チンチロ — 賭け金入力"))

    @discord.ui.button(label="🎯 数字当て", style=discord.ButtonStyle.primary, row=1)
    async def numguess(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🎯 数字当てゲーム", description="賭け金を入力してください！\n**100〜2,000ナトコイン**", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "numguess", "数字当て — 賭け金入力"))

    @discord.ui.button(label="🪙 コインフリップ", style=discord.ButtonStyle.primary, row=1)
    async def coinflip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🪙 コインフリップ", description="賭け金を入力してください！\n**100〜2,000ナトコイン**", color=discord.Color.gold())
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

        if self.game_type == "blackjack":
            from cogs.blackjack import BlackjackModeView
            embed = discord.Embed(title="🃏 ブラックジャック", description=f"賭け金: **{bet:,} ナトコイン**\nモードを選んでください！", color=discord.Color.dark_green())
            await interaction.response.edit_message(embed=embed, view=BlackjackModeView(bet))

        elif self.game_type == "poker":
            from cogs.poker import PokerModeView
            embed = discord.Embed(title="♠️ ポーカー", description=f"アンティ: **{bet:,} ナトコイン**\nモードを選んでください！", color=discord.Color.dark_green())
            await interaction.response.edit_message(embed=embed, view=PokerModeView(bet))

        elif self.game_type == "chinchiro":
            from cogs.chinchiro import ChinchiroModeView
            embed = discord.Embed(title="🎲 チンチロ", description=f"賭け金: **{bet:,} ナトコイン**\nモードを選んでください！", color=discord.Color.blue())
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
        from cogs.fishing import do_fish
        await do_fish(interaction, "lake", edit=True)

    @discord.ui.button(label="🏔️ 川（50ナトコイン）", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, "river", edit=True)

    @discord.ui.button(label="🌊 海（100ナトコイン）", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, "sea", edit=True)

    @discord.ui.button(label="📖 図鑑", style=discord.ButtonStyle.secondary, row=1)
    async def zukan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.zukan import ZukanCategoryView, build_category_embed
        await interaction.response.edit_message(
            embed=build_category_embed(self.user_id),
            view=ZukanCategoryView(self.user_id))

    @discord.ui.button(label="🗺️ 宝の地図を使う", style=discord.ButtonStyle.primary, row=1)
    async def treasure(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import use_treasure_map
        await use_treasure_map(interaction, edit=True)

    @discord.ui.button(label="🏪 釣具屋", style=discord.ButtonStyle.success, row=1)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.shop import ShopView
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())

    @discord.ui.button(label="🌤️ 天気予報士", style=discord.ButtonStyle.secondary, row=2)
    async def forecaster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import forecaster_embed, NPCView
        await interaction.response.edit_message(embed=forecaster_embed(), view=NPCView("forecaster", self.user_id))

    @discord.ui.button(label="🎣 怪しい釣り人", style=discord.ButtonStyle.secondary, row=2)
    async def angler(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import angler_embed, NPCView
        await interaction.response.edit_message(embed=angler_embed(), view=NPCView("angler", self.user_id))

    @discord.ui.button(label="⚓ 危険海域", style=discord.ButtonStyle.danger, row=2)
    async def danger_zone(self, interaction: discord.Interaction, button: discord.ui.Button):
        import random as _r
        lines = [
            "船がないとここには行けないぞ…どこまで泳ぐつもりだ？",
            "ここから先は船がなけりゃ話にならん。波に呑まれて魚の餌になりたいのか？",
            "危険海域…？　まだお前にゃ早い。第一、船はどうした。泳いで渡る気か？",
            "船も無しに来る奴があるか。命がいくつあっても足りんぞ、ここはな。",
        ]
        await interaction.response.send_message(_r.choice(lines), ephemeral=True)

    @discord.ui.button(label="🏠 ホームへ戻る", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await go_home(interaction, self.user_id)


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

    @discord.ui.button(label="🎁 デイリーボーナス", style=discord.ButtonStyle.success, row=0)
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        today = str(date.today())
        if db.get_last_daily(uid, guild_id) == today:
            await interaction.response.send_message("⏰ 今日はすでにデイリーボーナスを受け取っています！", ephemeral=True)
            return
        db.update_balance(uid, guild_id, DAILY_AMOUNT)
        db.set_last_daily(uid, guild_id, today)
        bal = db.get_balance(uid, guild_id)
        embed = discord.Embed(title="🎁 デイリーボーナス！", description=f"**+{DAILY_AMOUNT} ナトコイン** ゲット！\n残高: **{bal:,} ナトコイン**", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 ランキング", style=discord.ButtonStyle.secondary, row=0)
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        guild_id = str(interaction.guild.id)
        rows = db.get_ranking(guild_id, 10)
        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="🏆 ナトコインランキング", color=discord.Color.gold())
        if not rows:
            embed.description = "まだデータがありません"
        else:
            lines = []
            for i, (uid, bal) in enumerate(rows):
                m = medals[i] if i < 3 else f"{i+1}."
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"ID:{uid}"
                lines.append(f"{m} **{name}** — {bal:,} ナトコイン")
            embed.description = "\n".join(lines)
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

    @discord.ui.button(label="🏠 ホームへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await go_home(interaction, self.user_id)


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
        await interaction.response.send_message(embed=embed, view=MainMenuView(uid))


async def setup(bot):
    await bot.add_cog(Menu(bot))
