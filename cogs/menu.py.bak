import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from datetime import date
import random

db = Database()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メインメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_menu_embed():
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
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🎰 ゲーム", style=discord.ButtonStyle.primary, row=0)
    async def games(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🎮 ゲームメニュー", color=discord.Color.dark_green())
        embed.description = "遊びたいゲームを選んでください！"
        await interaction.response.edit_message(embed=embed, view=GameMenuView())

    @discord.ui.button(label="🎣 釣り", style=discord.ButtonStyle.success, row=0)
    async def fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🎣 釣りメニュー", color=discord.Color.blue())
        embed.add_field(name="🏞️ 湖", value="無料", inline=True)
        embed.add_field(name="🏔️ 川", value="50コイン", inline=True)
        embed.add_field(name="🌊 海", value="100コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=FishMenuView())

    @discord.ui.button(label="💰 コイン", style=discord.ButtonStyle.secondary, row=0)
    async def coins(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="💰 コインメニュー", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinMenuView())

    @discord.ui.button(label="✨ その他", style=discord.ButtonStyle.secondary, row=0)
    async def others(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="✨ その他メニュー", color=discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=OtherMenuView())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ゲームメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class GameMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="🎰 スロット", style=discord.ButtonStyle.primary, row=0)
    async def slot(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.slot import SlotSelectView
        embed = discord.Embed(
            title="🎰 スロット — 台選択",
            description="1〜10番台から選んでください！\n設定は台によって違います。高設定を探せ！\n1回 **60コイン**",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=SlotWithBackView())

    @discord.ui.button(label="🃏 ブラックジャック", style=discord.ButtonStyle.primary, row=0)
    async def blackjack(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description="賭け金を選んでください！",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=BlackjackBetView())

    @discord.ui.button(label="♠️ ポーカー", style=discord.ButtonStyle.primary, row=0)
    async def poker(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="♠️ ポーカー",
            description="アンティ（参加費）を選んでください！",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=PokerBetView())

    @discord.ui.button(label="🎲 チンチロ", style=discord.ButtonStyle.primary, row=1)
    async def chinchiro(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎲 チンチロ",
            description="賭け金を選んでください！",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=ChinchiroBetView())

    @discord.ui.button(label="🎯 数字当て", style=discord.ButtonStyle.primary, row=1)
    async def numguess(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎯 数字当てゲーム",
            description="賭け金を選んでください！",
            color=discord.Color.blurple()
        )
        await interaction.response.edit_message(embed=embed, view=NumguessBetView())

    @discord.ui.button(label="🪙 コインフリップ", style=discord.ButtonStyle.primary, row=1)
    async def coinflip(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🪙 コインフリップ",
            description="賭け金を選んでください！",
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=embed, view=CoinflipBetView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# スロット台選択（メニューから）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlotWithBackView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        # 台選択ボタンを追加
        for i in range(1, 11):
            self.add_item(SlotMachineButton(i))

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class SlotMachineButton(discord.ui.Button):
    def __init__(self, machine_no: int):
        row = (machine_no - 1) // 5
        super().__init__(
            label=f"{machine_no}番台",
            style=discord.ButtonStyle.primary,
            row=row
        )
        self.machine_no = machine_no

    async def callback(self, interaction: discord.Interaction):
        from cogs.slot import active_slots, get_machine_setting, SLOT_BET, SlotGameView
        uid = str(interaction.user.id)
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
            "machine": self.machine_no,
            "setting": setting,
            "guild_id": guild_id,
            "state": "normal",
            "fs_type": None,
            "fs_remaining": 0,
            "fs_total_payout": 0,
            "pending_bonus": None,
            "total_in": 0,
            "total_out": 0,
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

class BlackjackBetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def start(self, interaction: discord.Interaction, bet: int):
        from cogs.blackjack import BlackjackModeView
        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=f"賭け金: **{bet:,} コイン**\nモードを選んでください！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="🤖 AIと対戦", value="ディーラーBOTと1対1", inline=True)
        embed.add_field(name="⚔️ 人と対戦", value="メンバーと対決！", inline=True)
        await interaction.response.edit_message(embed=embed, view=BlackjackModeView(bet))

    @discord.ui.button(label="100コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 100)

    @discord.ui.button(label="500コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 500)

    @discord.ui.button(label="1000コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 1000)

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class PokerBetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def start(self, interaction: discord.Interaction, ante: int):
        from cogs.poker import PokerModeView
        embed = discord.Embed(
            title="♠️ ポーカー",
            description=f"アンティ: **{ante:,} コイン**\nモードを選んでください！",
            color=discord.Color.dark_green()
        )
        await interaction.response.edit_message(embed=embed, view=PokerModeView(ante))

    @discord.ui.button(label="100コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 100)

    @discord.ui.button(label="500コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 500)

    @discord.ui.button(label="1000コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 1000)

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class ChinchiroBetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def start(self, interaction: discord.Interaction, bet: int):
        from cogs.chinchiro import ChinchiroModeView
        embed = discord.Embed(
            title="🎲 チンチロ",
            description=f"賭け金: **{bet:,} コイン**\nモードを選んでください！",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=ChinchiroModeView(bet))

    @discord.ui.button(label="100コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 100)

    @discord.ui.button(label="500コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 500)

    @discord.ui.button(label="1000コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 1000)

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class NumguessBetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def start(self, interaction: discord.Interaction, bet: int):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        from cogs.numguess import active_games, MAX_TRIES
        if uid in active_games:
            await interaction.response.send_message("❌ すでにゲーム中です。`/guess` で続けてください", ephemeral=True)
            return
        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -bet)
        answer = random.randint(1, 100)
        active_games[uid] = {"answer": answer, "tries": 0, "bet": bet, "guild_id": guild_id}
        embed = discord.Embed(
            title="🎯 数字当てゲーム",
            description=f"1〜100の数字を当ててください！\n最大 **{MAX_TRIES}回** まで挑戦できます。\n`/guess [数字]` で答えを入力してね",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"賭け: {bet:,} コイン")
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="100コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 100)

    @discord.ui.button(label="500コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 500)

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class CoinflipBetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    async def start(self, interaction: discord.Interaction, bet: int):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(bet))

    @discord.ui.button(label="100コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet100(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 100)

    @discord.ui.button(label="500コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet500(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 500)

    @discord.ui.button(label="1000コイン", style=discord.ButtonStyle.primary, row=0)
    async def bet1000(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.start(interaction, 1000)

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class CoinflipChoiceView(discord.ui.View):
    def __init__(self, bet: int):
        super().__init__(timeout=30)
        self.bet = bet

    async def do_flip(self, interaction: discord.Interaction, choice: str):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません", ephemeral=True)
            return
        result = random.choice(["heads", "tails"])
        won = choice == result
        net = self.bet if won else -self.bet
        db.update_balance(uid, guild_id, net)
        new_bal = db.get_balance(uid, guild_id)
        result_emoji = "🪙 表" if result == "heads" else "🪙 裏"
        embed = discord.Embed(
            title="🪙 コインフリップ",
            color=discord.Color.green() if won else discord.Color.red()
        )
        embed.add_field(name="結果", value=result_emoji, inline=True)
        embed.add_field(name="あなた", value="表" if choice == "heads" else "裏", inline=True)
        embed.add_field(name="判定", value=f"{'🎉 勝ち！' if won else '😢 負け...'} {net:+,} コイン", inline=False)
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
        await interaction.response.edit_message(embed=embed, view=CoinflipAgainView(self.bet, choice))

    @discord.ui.button(label="表 (Heads)", style=discord.ButtonStyle.primary)
    async def heads(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "heads")

    @discord.ui.button(label="裏 (Tails)", style=discord.ButtonStyle.secondary)
    async def tails(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.do_flip(interaction, "tails")

class CoinflipAgainView(discord.ui.View):
    def __init__(self, bet: int, last_choice: str):
        super().__init__(timeout=60)
        self.bet = bet
        self.last_choice = last_choice

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🪙")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🪙 コインフリップ", description="表・裏どちらに賭けますか？", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=CoinflipChoiceView(self.bet))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 釣りメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FishMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🏞️ 湖（無料）", style=discord.ButtonStyle.success, row=0)
    async def lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.fishing import do_fish
        await do_fish(interaction, "lake", edit=True)

    @discord.ui.button(label="🏔️ 川（50コイン）", style=discord.ButtonStyle.primary, row=0)
    async def river(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.fishing import do_fish
        await do_fish(interaction, "river", edit=True)

    @discord.ui.button(label="🌊 海（100コイン）", style=discord.ButtonStyle.danger, row=0)
    async def sea(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.fishing import do_fish
        await do_fish(interaction, "sea", edit=True)

    @discord.ui.button(label="📖 図鑑", style=discord.ButtonStyle.secondary, row=1)
    async def zukan(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.zukan import ZukanAreaView
        uid = str(interaction.user.id)
        from config import LAKE_FISH, RIVER_FISH, SEA_FISH
        FISH_BY_AREA = {"lake": LAKE_FISH, "river": RIVER_FISH, "sea": SEA_FISH}
        AREA_NAMES = {"lake": "🏞️ 湖", "river": "🏔️ 川", "sea": "🌊 海"}
        embed = discord.Embed(title="📖 釣り図鑑", description="エリアを選んで図鑑を見よう！", color=discord.Color.blue())
        for area in ["lake", "river", "sea"]:
            caught = db.get_zukan(uid, area)
            fish_list = [f for f in FISH_BY_AREA[area] if f["rarity"] != "trash"]
            embed.add_field(name=AREA_NAMES[area], value=f"{len(caught)}/{len(fish_list)} 種類", inline=True)
        await interaction.response.edit_message(embed=embed, view=ZukanAreaView(uid))

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# コインメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CoinMenuView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="💰 残高確認", style=discord.ButtonStyle.secondary, row=0)
    async def balance(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        embed = discord.Embed(title="💰 残高確認", color=discord.Color.gold())
        embed.add_field(name=interaction.user.display_name, value=f"**{bal:,} コイン**")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎁 デイリーボーナス", style=discord.ButtonStyle.success, row=0)
    async def daily(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
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

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

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
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="🔮 占い", style=discord.ButtonStyle.secondary, row=0)
    async def fortune(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        players = list(range(1, 11))
        random.shuffle(players)
        team1 = sorted(players[:5])
        team2 = sorted(players[5:])
        embed = discord.Embed(title="⚔️ チーム分け結果", color=discord.Color.blue())
        embed.add_field(name="🔵 チーム1", value=" / ".join(f"**{p}番**" for p in team1), inline=False)
        embed.add_field(name="🔴 チーム2", value=" / ".join(f"**{p}番**" for p in team2), inline=False)
        await interaction.response.edit_message(embed=embed, view=TeamsplitAgainView())

    @discord.ui.button(label="🏠 メニューへ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class TeamsplitAgainView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="🔀 もう一度シャッフル", style=discord.ButtonStyle.primary)
    async def resplit(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Menu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="menu", description="BOTのメニューを開く")
    async def menu(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=build_menu_embed(), view=MainMenuView())

async def setup(bot):
    await bot.add_cog(Menu(bot))
