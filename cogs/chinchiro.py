import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import CHINCHIRO_AI_PAYOUT, PVP_FEE_RATE
import random

db = Database()

def roll_dice():
    return [random.randint(1, 6) for _ in range(3)]

def evaluate(dice: list) -> tuple[int, str]:
    """役を判定。返り値は (強さスコア, 役名)"""
    d = sorted(dice)
    counts = {n: dice.count(n) for n in set(dice)}

    # ピンゾロ
    if d == [1, 1, 1]:
        return (100, "👑 ピンゾロ！！")

    # ゾロ目
    if len(set(d)) == 1:
        return (50 + d[0], f"🎲 {d[0]}のゾロ目！")

    # シゴロ
    if d == [4, 5, 6]:
        return (49, "🔥 シゴロ！！")

    # ヒフミ
    if d == [1, 2, 3]:
        return (-1, "💀 ヒフミ...")

    # 目
    for num, count in counts.items():
        if count == 2:
            remaining = [n for n in dice if n != num]
            return (remaining[0], f"🎯 目：{remaining[0]}")

    return (0, "❓ 目なし（振り直し）")

def dice_str(dice: list) -> str:
    emoji = {1:"1️⃣", 2:"2️⃣", 3:"3️⃣", 4:"4️⃣", 5:"5️⃣", 6:"6️⃣"}
    return " ".join(emoji[d] for d in dice)

# AI対戦
class ChinchiroAIView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str, bet: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet
        self.player_score = None
        self.player_label = None
        self.round = 0

    @discord.ui.button(label="サイコロを振る！", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return

        # プレイヤーの振り直しループ
        for _ in range(3):
            dice = roll_dice()
            score, label = evaluate(dice)
            if score != 0:
                break

        if score == 0:
            embed = discord.Embed(title="🎲 チンチロ vs AI", color=discord.Color.blue())
            embed.add_field(name="あなた", value=f"{dice_str(dice)}\n{label}", inline=False)
            embed.set_footer(text="3回振っても目なし...もう一度振ってください")
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # AIの振り直しループ
        for _ in range(3):
            ai_dice = roll_dice()
            ai_score, ai_label = evaluate(ai_dice)
            if ai_score != 0:
                break

        embed = discord.Embed(title="🎲 チンチロ vs AI", color=discord.Color.blue())
        embed.add_field(name="あなた", value=f"{dice_str(dice)}\n{label}", inline=True)
        embed.add_field(name="AI", value=f"{dice_str(ai_dice)}\n{ai_label}", inline=True)

        if score < 0:
            result = "負け"
            net = -self.bet
        elif ai_score < 0:
            result = "勝ち"
            net = self.bet
        elif score > ai_score:
            result = "勝ち"
            net = self.bet
        elif score < ai_score:
            result = "負け"
            net = -self.bet
        else:
            result = "引き分け"
            net = 0

        # AI出率90%調整
        if result == "勝ち" and random.random() > CHINCHIRO_AI_PAYOUT:
            net = -self.bet
            result = "負け（運が悪かった...）"

        db.update_balance(self.user_id, self.guild_id, net)
        new_bal = db.get_balance(self.user_id, self.guild_id)

        color = discord.Color.gold() if net > 0 else discord.Color.red() if net < 0 else discord.Color.blue()
        embed.color = color
        embed.add_field(
            name="結果",
            value=f"{'🎉 ' if net > 0 else '😢 ' if net < 0 else '🤝 '}{result}！ {'+' if net >= 0 else ''}{net:,} コイン",
            inline=False
        )
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)

        view = ChinchiroAgainView(self.user_id, self.guild_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

class ChinchiroAgainView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎲")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        bal = db.get_balance(self.user_id, self.guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(self.user_id, self.guild_id, -self.bet)
        embed = discord.Embed(title="🎲 チンチロ vs AI", description="サイコロを振ってください！", color=discord.Color.blue())
        embed.set_footer(text=f"賭け: {self.bet:,} コイン")
        view = ChinchiroAIView(self.user_id, self.guild_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

# 対人戦
pvp_rooms: dict[str, dict] = {}

class ChinchiroPvPView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=300)
        self.room_id = room_id

    @discord.ui.button(label="参加する", style=discord.ButtonStyle.success, emoji="✋")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room:
            await interaction.response.send_message("ルームが見つかりません", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid == room["host_id"]:
            await interaction.response.send_message("自分自身とは対戦できません", ephemeral=True)
            return
        if room.get("guest_id"):
            await interaction.response.send_message("すでに対戦中です", ephemeral=True)
            return

        bal = db.get_balance(uid, room["guild_id"])
        if bal < room["bet"]:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, room["guild_id"], -room["bet"])
        room["guest_id"] = uid
        room["guest_name"] = interaction.user.display_name
        room["pot"] += room["bet"]

        embed = discord.Embed(
            title="🎲 チンチロ 対人戦",
            description=f"**{room['host_name']}** vs **{room['guest_name']}**\nポット: {room['pot']:,} コイン",
            color=discord.Color.blue()
        )
        view = ChinchiroPvPGameView(self.room_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ChinchiroPvPGameView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=300)
        self.room_id = room_id

    @discord.ui.button(label="サイコロを振る！", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room:
            return
        uid = str(interaction.user.id)
        if uid not in [room["host_id"], room["guest_id"]]:
            await interaction.response.send_message("参加者ではありません", ephemeral=True)
            return

        # 両者振る
        for _ in range(3):
            host_dice = roll_dice()
            host_score, host_label = evaluate(host_dice)
            if host_score != 0:
                break

        for _ in range(3):
            guest_dice = roll_dice()
            guest_score, guest_label = evaluate(guest_dice)
            if guest_score != 0:
                break

        embed = discord.Embed(title="🎲 チンチロ 対人戦", color=discord.Color.blue())
        embed.add_field(name=room["host_name"], value=f"{dice_str(host_dice)}\n{host_label}", inline=True)
        embed.add_field(name=room["guest_name"], value=f"{dice_str(guest_dice)}\n{guest_label}", inline=True)

        pot = room["pot"]
        fee = int(pot * PVP_FEE_RATE)
        prize = pot - fee

        if host_score < 0 and guest_score < 0:
            result = "🤝 両者ヒフミ！引き分け"
            db.update_balance(room["host_id"], room["guild_id"], pot // 2)
            db.update_balance(room["guest_id"], room["guild_id"], pot // 2)
        elif host_score < 0:
            result = f"🎉 {room['guest_name']} の勝ち！"
            db.update_balance(room["guest_id"], room["guild_id"], prize)
        elif guest_score < 0:
            result = f"🎉 {room['host_name']} の勝ち！"
            db.update_balance(room["host_id"], room["guild_id"], prize)
        elif host_score > guest_score:
            result = f"🎉 {room['host_name']} の勝ち！"
            db.update_balance(room["host_id"], room["guild_id"], prize)
        elif guest_score > host_score:
            result = f"🎉 {room['guest_name']} の勝ち！"
            db.update_balance(room["guest_id"], room["guild_id"], prize)
        else:
            result = "🤝 引き分け！"
            db.update_balance(room["host_id"], room["guild_id"], pot // 2)
            db.update_balance(room["guest_id"], room["guild_id"], pot // 2)

        embed.add_field(name="結果", value=f"{result}\nポット: {prize:,} コイン（手数料{fee:,}コイン）", inline=False)
        embed.color = discord.Color.gold()

        view = ChinchiroPvPContinueView(self.room_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ChinchiroPvPContinueView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=60)
        self.room_id = room_id

    @discord.ui.button(label="続ける", style=discord.ButtonStyle.primary, emoji="🎲")
    async def continue_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room:
            return
        uid = str(interaction.user.id)
        if uid not in [room["host_id"], room["guest_id"]]:
            await interaction.response.send_message("参加者ではありません", ephemeral=True)
            return

        bet = room["bet"]
        host_bal = db.get_balance(room["host_id"], room["guild_id"])
        guest_bal = db.get_balance(room["guest_id"], room["guild_id"])

        if host_bal < bet or guest_bal < bet:
            await interaction.response.send_message("❌ どちらかのコインが足りません", ephemeral=True)
            pvp_rooms.pop(self.room_id, None)
            return

        db.update_balance(room["host_id"], room["guild_id"], -bet)
        db.update_balance(room["guest_id"], room["guild_id"], -bet)
        room["pot"] = bet * 2

        embed = discord.Embed(
            title="🎲 チンチロ 対人戦",
            description=f"**{room['host_name']}** vs **{room['guest_name']}**\nポット: {room['pot']:,} コイン",
            color=discord.Color.blue()
        )
        view = ChinchiroPvPGameView(self.room_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def quit_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        pvp_rooms.pop(self.room_id, None)
        self.clear_items()
        await interaction.response.edit_message(content="対戦終了！", embed=None, view=self)

# モード選択
class ChinchiroModeView(discord.ui.View):
    def __init__(self, bet: int):
        super().__init__(timeout=30)
        self.bet = bet

    @discord.ui.button(label="🤖 AIと対戦", style=discord.ButtonStyle.primary)
    async def vs_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -self.bet)
        embed = discord.Embed(
            title="🎲 チンチロ vs AI",
            description="サイコロを振ってください！",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"賭け: {self.bet:,} コイン")
        view = ChinchiroAIView(uid, guild_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚔️ 人と対戦", style=discord.ButtonStyle.success)
    async def vs_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        room_id = f"chinchiro_{uid}"
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -self.bet)
        pvp_rooms[room_id] = {
            "host_id": uid,
            "host_name": interaction.user.display_name,
            "guest_id": None,
            "guest_name": None,
            "guild_id": guild_id,
            "bet": self.bet,
            "pot": self.bet,
        }
        embed = discord.Embed(
            title="🎲 チンチロ 対人戦 — 募集中",
            description=f"**{interaction.user.display_name}** がチンチロ対人戦を開始！\n賭け金: **{self.bet:,} コイン**\n\n参加ボタンを押して挑戦しよう！",
            color=discord.Color.blue()
        )
        view = ChinchiroPvPView(room_id)
        await interaction.response.edit_message(embed=embed, view=view)

class Chinchiro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="chinchiro", description="チンチロで勝負！AIと対戦 or 人と対戦")
    @app_commands.describe(bet="賭けるコイン数（最低10）")
    async def chinchiro(self, interaction: discord.Interaction, bet: int = 100):
        if bet < 10:
            await interaction.response.send_message("❌ 最低10コインから", ephemeral=True)
            return
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎲 チンチロ",
            description=f"賭け金: **{bet:,} コイン**\n\nモードを選んでください！",
            color=discord.Color.blue()
        )
        embed.add_field(name="🤖 AIと対戦", value="出率90%のAIディーラーと勝負！", inline=True)
        embed.add_field(name="⚔️ 人と対戦", value="サーバーメンバーと対決！手数料10%", inline=True)
        await interaction.response.send_message(embed=embed, view=ChinchiroModeView(bet))

async def setup(bot):
    await bot.add_cog(Chinchiro(bot))
