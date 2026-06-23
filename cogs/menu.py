import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from datetime import date
import random

db = Database()

DAILY_SEND_LIMIT = 3000  # 1日の送金上限

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 送金関連
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SendAmountModal(discord.ui.Modal, title="💸 送金額を入力"):
    amount_input = discord.ui.TextInput(
        label="送金額（コイン）",
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
                f"❌ 本日の送金上限を超えています（残り: {self.remaining:,} コイン）", ephemeral=True
            )
            return

        bal = db.get_balance(self.sender_id, self.guild_id)
        if bal < amount:
            await interaction.response.send_message(
                f"❌ コインが足りません（残高: {bal:,} コイン）", ephemeral=True
            )
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
            description=f"{interaction.user.mention} → **{self.target_name}**\n**{amount:,} コイン** を送りました！",
            color=discord.Color.green()
        )
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)
        embed.add_field(name="本日の残り送金枠", value=f"{remaining_after:,} / {DAILY_SEND_LIMIT:,} コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=SendBackView(self.sender_id))


class MemberSelect(discord.ui.Select):
    def __init__(self, sender_id: str, guild_id: str, members: list, remaining: int):
        self.sender_id = sender_id
        self.guild_id = guild_id
        self.remaining = remaining
        options = [
            discord.SelectOption(
                label=m.display_name[:25],
                value=str(m.id),
                description=f"ID: {m.id}"
            )
            for m in members
        ]
        super().__init__(
            placeholder="送り先のメンバーを選んでください...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.sender_id:
            await interaction.response.send_message("❌ これはあなたのメニューではありません", ephemeral=True)
            return
        target_id = self.values[0]
        target_member = interaction.guild.get_member(int(target_id))
        target_name = target_member.display_name if target_member else f"ID:{target_id}"
        modal = SendAmountModal(self.sender_id, self.guild_id, target_id, target_name, self.remaining)
        await interaction.response.send_modal(modal)


class SendSelectView(discord.ui.View):
    def __init__(self, sender_id: str, guild_id: str, all_members: list, remaining: int, page: int = 0):
        super().__init__(timeout=60)
        self.sender_id = sender_id
        self.guild_id = guild_id
        self.all_members = all_members
        self.remaining = remaining
        self.page = page
        self.per_page = 25
        self.total_pages = max(1, (len(all_members) + self.per_page - 1) // self.per_page)

        # 現在ページのメンバー
        start = page * self.per_page
        page_members = all_members[start:start + self.per_page]
        self.add_item(MemberSelect(sender_id, guild_id, page_members, remaining))

        # ページングボタン
        if self.total_pages > 1:
            prev_btn = discord.ui.Button(
                label=f"◀ 前へ",
                style=discord.ButtonStyle.secondary,
                disabled=(page == 0),
                row=1
            )
            next_btn = discord.ui.Button(
                label=f"次へ ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(page >= self.total_pages - 1),
                row=1
            )
            page_btn = discord.ui.Button(
                label=f"{page + 1} / {self.total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=1
            )
            prev_btn.callback = self.prev_page
            next_btn.callback = self.next_page
            self.add_item(prev_btn)
            self.add_item(page_btn)
            self.add_item(next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        if not await check_user(interaction, self.sender_id): return
        new_view = SendSelectView(self.sender_id, self.guild_id, self.all_members, self.remaining, self.page - 1)
        embed = discord.Embed(
            title="💸 送金",
            description=f"送り先を選んでください\n\n本日の残り送金枠: **{self.remaining:,} / {DAILY_SEND_LIMIT:,} コイン**",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=new_view)

    async def next_page(self, interaction: discord.Interaction):
        if not await check_user(interaction, self.sender_id): return
        new_view = SendSelectView(self.sender_id, self.guild_id, self.all_members, self.remaining, self.page + 1)
        embed = discord.Embed(
            title="💸 送金",
            description=f"送り先を選んでください\n\n本日の残り送金枠: **{self.remaining:,} / {DAILY_SEND_LIMIT:,} コイン**",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.sender_id): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.sender_id))


class SendBackView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ユーザー確認ヘルパー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def check_user(interaction: discord.Interaction, user_id: str) -> bool:
    """操作者が本人か確認。違う場合はepheralでエラーを送る"""
    if str(interaction.user.id) != user_id:
        await interaction.response.send_message("❌ これはあなたのメニューではありません", ephemeral=True)
        return False
    return True

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メインメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_menu_embed(user: discord.Member = None):
    embed = discord.Embed(
        title="🎮 BOTメニュー",
        description="ボタンを押して各機能を使ってね！",
        color=discord.Color.blurple()
    )
    embed.add_field(name="🎰 ゲーム", value="スロット・ブラックジャック・ポーカー・チンチロ・数字当て・コインフリップ", inline=False)
    embed.add_field(name="🎣 釣り", value="湖・川・海で釣りができる！図鑑もあるよ", inline=False)
    embed.add_field(name="💰 コイン", value="残高確認・デイリーボーナス・ランキング・送金", inline=False)
    embed.add_field(name="✨ その他", value="占い・チーム分け", inline=False)
    return embed

class MainMenuView(discord.ui.View):
    def __init__(self, user_id: str = None):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def _check(self, interaction):
        if self.user_id:
            return await check_user(interaction, self.user_id)
        return True

    @discord.ui.button(label="🎰 ゲーム", style=discord.ButtonStyle.primary, row=0)
    async def games(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        embed = discord.Embed(title="🎮 ゲームメニュー", description="遊びたいゲームを選んでください！", color=discord.Color.dark_green())
        await interaction.response.edit_message(embed=embed, view=GameMenuView(uid))

    @discord.ui.button(label="🎣 釣り", style=discord.ButtonStyle.success, row=0)
    async def fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        embed = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="10コイン", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=FishMenuView(uid))

    @discord.ui.button(label="💰 コイン", style=discord.ButtonStyle.secondary, row=0)
    async def coins(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        embed = discord.Embed(title="💰 コインメニュー", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinMenuView(uid))

    @discord.ui.button(label="✨ その他", style=discord.ButtonStyle.secondary, row=0)
    async def others(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = str(interaction.user.id)
        embed = discord.Embed(title="✨ その他メニュー", color=discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=OtherMenuView(uid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ゲームメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GameMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🎰 スロット", style=discord.ButtonStyle.primary, row=0)
    async def slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(
            title="🎰 スロット — 台選択",
            description="1〜10番台から選んでください！\n設定は台によって違います。高設定を探せ！\n1回 **60コイン**",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=SlotWithBackView(self.user_id))

    @discord.ui.button(label="🃏 ブラックジャック", style=discord.ButtonStyle.primary, row=0)
    async def blackjack(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🃏 ブラックジャック", description="賭け金を入力してください！\n**100〜2,000コイン**", color=discord.Color.dark_green())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "blackjack", "ブラックジャック — 賭け金入力"))

    @discord.ui.button(label="♠️ ポーカー", style=discord.ButtonStyle.primary, row=0)
    async def poker(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="♠️ ポーカー", description="アンティ（参加費）を入力してください！\n**100〜2,000コイン**", color=discord.Color.dark_green())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "poker", "ポーカー — アンティ入力"))

    @discord.ui.button(label="🎲 チンチロ", style=discord.ButtonStyle.primary, row=1)
    async def chinchiro(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🎲 チンチロ", description="賭け金を入力してください！\n**100〜2,000コイン**", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "chinchiro", "チンチロ — 賭け金入力"))

    @discord.ui.button(label="🎯 数字当て", style=discord.ButtonStyle.primary, row=1)
    async def numguess(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🎯 数字当てゲーム", description="賭け金を入力してください！\n**100〜2,000コイン**", color=discord.Color.blurple())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "numguess", "数字当て — 賭け金入力"))

    @discord.ui.button(label="🪙 コインフリップ", style=discord.ButtonStyle.primary, row=1)
    async def coinflip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        embed = discord.Embed(title="🪙 コインフリップ", description="賭け金を入力してください！\n**100〜2,000コイン**", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=make_bet_view(self.user_id, str(interaction.guild.id), "coinflip", "コインフリップ — 賭け金入力"))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スロット台選択
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlotWithBackView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        for i in range(1, 11):
            self.add_item(SlotMachineButton(i, user_id))

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

class SlotMachineButton(discord.ui.Button):
    def __init__(self, machine_no: int, user_id: str):
        row = (machine_no - 1) // 5
        super().__init__(label=f"{machine_no}番台", style=discord.ButtonStyle.primary, row=row)
        self.machine_no = machine_no
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if not await check_user(interaction, self.user_id): return
        from cogs.slot import active_slots, get_machine_setting, SLOT_BET, SlotGameView
        uid = self.user_id
        guild_id = str(interaction.guild.id)

        if uid in active_slots:
            await interaction.response.send_message("❌ すでにプレイ中です", ephemeral=True)
            return

        bal = db.get_balance(uid, guild_id)
        if bal < SLOT_BET:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        setting = get_machine_setting(self.machine_no)
        active_slots[uid] = {
            "machine": self.machine_no, "setting": setting, "guild_id": guild_id,
            "state": "normal", "fs_type": None, "fs_remaining": 0,
            "fs_total_payout": 0, "pending_bonus": None,
            "fs_continued": False, "fs_noticed": False,
            "spinning": False,
        }

        embed = discord.Embed(
            title=f"🎰 スロット — {self.machine_no}番台",
            description=f"**{SLOT_BET}コイン**掛け\n設定は台を打って確かめよう！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="残高", value=f"{bal:,} コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=SlotGameView(uid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 賭け金選択ビュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 賭け金入力モーダル（共通）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BetModal(discord.ui.Modal):
    bet_input = discord.ui.TextInput(
        label="賭け金（100〜2,000コイン）",
        placeholder="例: 1000",
        min_length=1,
        max_length=7,
    )

    def __init__(self, title: str, user_id: str, guild_id: str, game_type: str):
        super().__init__(title=title)
        self.user_id = user_id
        self.guild_id = guild_id  # Noneの場合はon_submit内でinteractionから取得
        self.game_type = game_type

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = self.guild_id or str(interaction.guild.id)
        try:
            bet = int(self.bet_input.value.replace(",", "").replace("，", ""))
        except ValueError:
            await interaction.response.send_message("❌ 数字を入力してください", ephemeral=True)
            return

        if bet < 100:
            await interaction.response.send_message("❌ 最低100コインから", ephemeral=True)
            return
        if bet > 2000:
            await interaction.response.send_message("❌ 最大2,000コインまで", ephemeral=True)
            return

        bal = db.get_balance(self.user_id, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        if self.game_type == "blackjack":
            from cogs.blackjack import BlackjackModeView
            embed = discord.Embed(
                title="🃏 ブラックジャック",
                description=f"賭け金: **{bet:,} コイン**\nモードを選んでください！",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=BlackjackModeView(bet))

        elif self.game_type == "poker":
            from cogs.poker import PokerModeView
            embed = discord.Embed(
                title="♠️ ポーカー",
                description=f"アンティ: **{bet:,} コイン**\nモードを選んでください！",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=PokerModeView(bet))

        elif self.game_type == "chinchiro":
            from cogs.chinchiro import ChinchiroModeView
            embed = discord.Embed(
                title="🎲 チンチロ",
                description=f"賭け金: **{bet:,} コイン**\nモードを選んでください！",
                color=discord.Color.blue()
            )
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
            await interaction.response.edit_message(embed=embed, view=NumguessPlayView(self.user_id, self.guild_id))

        elif self.game_type == "coinflip":
            embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(bet, self.user_id))


def make_bet_view(user_id: str, guild_id: str, game_type: str, title: str, back_label: str = "🏠 戻る"):
    """賭け金入力ボタン1つのViewを生成"""
    class BetView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
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
            await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self._user_id))

    return BetView()


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
        super().__init__(timeout=30)
        self.bet = bet
        self.user_id = user_id

    async def do_flip(self, interaction: discord.Interaction, choice: str):
        if not await check_user(interaction, self.user_id): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message("❌ コインが足りません", ephemeral=True)
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
        embed.add_field(name="判定", value=f"{'🎉 勝ち！' if won else '😢 負け...'} {net:+,} コイン", inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
        await interaction.response.edit_message(embed=embed, view=CoinflipAgainView(self.bet, self.user_id))

    @discord.ui.button(label="表 (Heads)", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "heads")

    @discord.ui.button(label="裏 (Tails)", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "tails")

class CoinflipAgainView(discord.ui.View):
    def __init__(self, bet: int, user_id: str):
        super().__init__(timeout=60)
        self.bet = bet
        self.user_id = user_id

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🪙")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(self.bet, self.user_id))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣りメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FishMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🏞️ 湖（10コイン）", style=discord.ButtonStyle.success, row=0)
    async def lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, "lake", edit=True)

    @discord.ui.button(label="🏔️ 川（50コイン）", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, "river", edit=True)

    @discord.ui.button(label="🌊 海（100コイン）", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.fishing import do_fish
        await do_fish(interaction, "sea", edit=True)

    @discord.ui.button(label="📖 図鑑", style=discord.ButtonStyle.secondary, row=1)
    async def zukan(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.zukan import ZukanAreaView
        uid = self.user_id
        from config import LAKE_FISH, RIVER_FISH, SEA_FISH
        FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}
        AREA_NAMES = {"lake": "🏞️ 湖", "river": "🏔️ 川", "sea": "🌊 海"}
        embed = discord.Embed(title="📖 釣り図鑑", description="エリアを選んで図鑑を見よう！", color=discord.Color.blue())
        for area in ["lake", "river", "sea"]:
            caught = db.get_zukan(uid, area)
            fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
            embed.add_field(name=AREA_NAMES[area], value=f"{len(caught)}/{len(fish_list)} 種類", inline=True)
        await interaction.response.edit_message(embed=embed, view=ZukanAreaView(uid))

    @discord.ui.button(label="🏪 釣具屋", style=discord.ButtonStyle.success, row=2)
    async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        from cogs.shop import ShopView
        embed = discord.Embed(title="🏪 釣具屋", description="カテゴリを選んでください！", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=ShopView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# コインメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CoinMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
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
        embed.add_field(name=interaction.user.display_name, value=f"**{bal:,} コイン**")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎁 デイリーボーナス", style=discord.ButtonStyle.success, row=0)
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)
        today = str(date.today())
        last = db.get_last_daily(uid)
        if last == today:
            await interaction.response.send_message("⏰ 今日はすでにデイリーボーナスを受け取っています！", ephemeral=True)
            return
        db.update_balance(uid, guild_id, 500)
        db.set_last_daily(uid, today)
        bal = db.get_balance(uid, guild_id)
        embed = discord.Embed(title="🎁 デイリーボーナス！", description=f"**+500 コイン** ゲット！\n残高: **{bal:,} コイン**", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏆 ランキング", style=discord.ButtonStyle.secondary, row=0)
    async def ranking(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        guild_id = str(interaction.guild.id)
        rows = db.get_ranking(guild_id, 10)
        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(title="🏆 コインランキング", color=discord.Color.gold())
        if not rows:
            embed.description = "まだデータがありません"
        else:
            lines = []
            for i, (uid, bal) in enumerate(rows):
                m = medals[i] if i < 3 else f"{i+1}."
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"ID:{uid}"
                lines.append(f"{m} **{name}** — {bal:,} コイン")
            embed.description = "\n".join(lines)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💸 送金", style=discord.ButtonStyle.primary, row=0)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        uid = self.user_id
        guild_id = str(interaction.guild.id)

        # 今日の残り送金枠
        today_sent = db.get_today_sent(uid, guild_id)
        remaining = max(0, DAILY_SEND_LIMIT - today_sent)

        if remaining <= 0:
            await interaction.response.send_message(
                f"❌ 本日の送金上限（{DAILY_SEND_LIMIT:,} コイン）に達しています。明日また試してね！",
                ephemeral=True
            )
            return

        # BOT・自分以外のメンバー一覧（全員）
        members = [
            m for m in interaction.guild.members
            if not m.bot and str(m.id) != uid
        ]

        if not members:
            await interaction.response.send_message("❌ 送金できるメンバーがいません", ephemeral=True)
            return

        embed = discord.Embed(
            title="💸 送金",
            description=f"送り先を選んでください\n\n本日の残り送金枠: **{remaining:,} / {DAILY_SEND_LIMIT:,} コイン**",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=SendSelectView(uid, guild_id, members, remaining))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# その他メニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

FORTUNES = [
    ("大吉", discord.Color.gold(), "最高の一日！何でも積極的に挑戦しよう！"),
    ("吉", discord.Color.green(), "良いことが起きる予感。前向きに過ごそう！"),
    ("中吉", discord.Color.blue(), "コツコツ努力が報われる日。"),
    ("小吉", discord.Color.teal(), "小さな幸せを大切に。"),
    ("末吉", discord.Color.blurple(), "慎重に行動すると吉。"),
    ("凶", discord.Color.orange(), "無理せず休息を取ろう。"),
    ("大凶", discord.Color.red(), "要注意！でも明日はきっと良くなる。"),
]
LUCKY_ITEMS = ["コーヒー", "青ペン", "ネコ", "古い本", "星形のもの", "音楽"]
LUCKY_COLORS = ["赤", "青", "緑", "金", "白", "紫"]

class OtherMenuView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id

    async def _check(self, interaction):
        return await check_user(interaction, self.user_id)

    @discord.ui.button(label="🔮 占い", style=discord.ButtonStyle.secondary, row=0)
    async def fortune(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        seed = int(str(interaction.user.id) + str(date.today()).replace("-", ""))
        rng = random.Random(seed)
        name, color, msg = rng.choice(FORTUNES)
        item = rng.choice(LUCKY_ITEMS)
        lucky_color = rng.choice(LUCKY_COLORS)
        lucky_num = rng.randint(1, 99)
        embed = discord.Embed(title=f"🔮 今日の運勢: {name}", description=msg, color=color)
        embed.add_field(name="🍀 ラッキーアイテム", value=item, inline=True)
        embed.add_field(name="🎨 ラッキーカラー", value=lucky_color, inline=True)
        embed.add_field(name="🔢 ラッキーナンバー", value=str(lucky_num), inline=True)
        embed.set_footer(text=f"{interaction.user.display_name} の運勢（{date.today()} 版）")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⚔️ チーム分け", style=discord.ButtonStyle.secondary, row=0)
    async def teamsplit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])
        embed = discord.Embed(title="⚔️ チーム分け結果", color=discord.Color.blue())
        embed.add_field(name="🔵 チーム1", value=" / ".join(f"**{p}番**" for p in team1), inline=False)
        embed.add_field(name="🔴 チーム2", value=" / ".join(f"**{p}番**" for p in team2), inline=False)
        await interaction.response.edit_message(embed=embed, view=TeamsplitAgainView(self.user_id))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

class TeamsplitAgainView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=120)
        self.user_id = user_id

    @discord.ui.button(label="🔀 もう一度シャッフル", style=discord.ButtonStyle.primary)
    async def resplit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])
        embed = discord.Embed(title="⚔️ チーム分け結果", color=discord.Color.blue())
        embed.add_field(name="🔵 チーム1", value=" / ".join(f"**{p}番**" for p in team1), inline=False)
        embed.add_field(name="🔴 チーム2", value=" / ".join(f"**{p}番**" for p in team2), inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await check_user(interaction, self.user_id): return
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView(self.user_id))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Menu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="menu", description="BOTのメニューを開く")
    async def menu(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await interaction.response.send_message(
            embed=build_menu_embed(),
            view=MainMenuView(uid),
        )

async def setup(bot):
    await bot.add_cog(Menu(bot))
