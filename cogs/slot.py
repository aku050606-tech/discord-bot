import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
import asyncio
from datetime import datetime, timezone, timedelta

db = Database()
JST = timezone(timedelta(hours=9))

def get_machine_setting(machine_no: int) -> int:
    now = datetime.now(JST)
    month, day, weekday = now.month, now.day, now.weekday()
    if (month, day) in SLOT_NEWYEAR_DATES:
        machines = SLOT_MACHINES_NEWYEAR
    elif day in SLOT_BONUS_DAYS or weekday in SLOT_BONUS_WEEKDAYS:
        machines = SLOT_MACHINES_BONUS
    else:
        machines = SLOT_MACHINES_NORMAL
    return machines[machine_no - 1]

def get_reel_display(reel_key: str) -> str:
    symbols = REELS.get(reel_key, REELS["blank"])
    return f"┌─────────────────┐\n│ {symbols[0]} │ {symbols[1]} │ {symbols[2]} │\n└─────────────────┘"

def get_effect(yaku: str, has_bonus: bool, is_miss: bool) -> str:
    """毎回演出を返す"""
    if is_miss:
        # ハズレ演出（1%でボーナス当選あり）
        return random.choice(SLOT_EFFECTS["miss"])

    if has_bonus:
        r = random.random()
        if r < 0.10:
            # 矛盾演出チャンス
            if yaku in SLOT_EFFECTS["contradiction"]:
                return random.choice(SLOT_EFFECTS["contradiction"][yaku])
            return random.choice(SLOT_EFFECTS["weak"])
        elif r < 0.30:
            return random.choice(SLOT_EFFECTS["weak"])
        elif r < 0.55:
            return random.choice(SLOT_EFFECTS["medium"])
        elif r < 0.80:
            return random.choice(SLOT_EFFECTS["strong"])
        else:
            return random.choice(SLOT_EFFECTS["super"])
    else:
        r = random.random()
        if r < 0.40:
            return random.choice(SLOT_EFFECTS["miss"])
        elif r < 0.65:
            return random.choice(SLOT_EFFECTS["weak"])
        elif r < 0.85:
            return random.choice(SLOT_EFFECTS["medium"])
        else:
            return random.choice(SLOT_EFFECTS["strong"])

def spin_normal(setting: int) -> dict:
    s = SLOT_SETTINGS[setting]

    if random.random() < GOD_PROB:
        return {"type":"god_trigger","yaku":None,"bonus":"GOD","payout":0}
    if random.random() < LEGEND_PROB:
        return {"type":"legend_trigger","yaku":None,"bonus":"LEGEND","payout":0}

    yaku = None
    if random.random() < s["strong_chance_prob"]:
        yaku = "strong_chance"
    elif random.random() < s["strong_cherry_prob"]:
        yaku = "strong_cherry"
    elif random.random() < s["weak_chance_prob"]:
        yaku = "weak_chance"
    elif random.random() < s["suika_prob"]:
        yaku = "suika"
    elif random.random() < s["cherry_prob"]:
        yaku = "cherry"
    elif random.random() < s["bell_prob"]:
        yaku = "bell"
    elif random.random() < s["replay_prob"]:
        yaku = "replay"

    if yaku is None:
        return {"type":"blank","yaku":None,"bonus":None,"payout":0}

    rate_key = f"{yaku}_bonus_rate"
    bonus_rate = s.get(rate_key, 0)
    if random.random() < bonus_rate:
        ratio = BONUS_RATIO.get(yaku, {"regular":0.5,"big":0.5,"super":0.0})
        r2 = random.random()
        if r2 < ratio["regular"]:
            bonus = "REGULAR"
        elif r2 < ratio["regular"] + ratio["big"]:
            bonus = "BIG"
        else:
            bonus = "SUPER"
        return {"type":"yaku_bonus","yaku":yaku,"bonus":bonus,"payout":0}

    payout = NORMAL_PAYOUTS.get(yaku, 0)
    return {"type":"yaku","yaku":yaku,"bonus":None,"payout":payout}

def spin_freespin(fs_type: str) -> dict:
    probs = FREESPIN_YAKUS[fs_type]
    payout = FREESPIN_BASE_PAYOUT
    yaku_results = []
    for yaku, prob in probs.items():
        if random.random() < prob:
            yaku_results.append(yaku)
            payout += FREESPIN_PAYOUTS.get(yaku, 0)
    continue_bonus = None
    for yaku in yaku_results:
        rate = FREESPIN_BONUS_RATES.get(yaku, 0)
        if random.random() < rate:
            continue_bonus = fs_type
            break
    return {"yakus":yaku_results,"payout":payout,"continue":continue_bonus is not None}

active_slots: dict[str, dict] = {}

class SlotMachineButton(discord.ui.Button):
    def __init__(self, machine_no: int):
        row = (machine_no - 1) // 5
        super().__init__(label=f"{machine_no}番台", style=discord.ButtonStyle.primary, row=row)
        self.machine_no = machine_no

    async def callback(self, interaction: discord.Interaction):
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
            "machine":self.machine_no,"setting":setting,"guild_id":guild_id,
            "state":"normal","fs_type":None,"fs_remaining":0,
            "fs_total_payout":0,"pending_bonus":None,
        }
        embed = discord.Embed(
            title=f"🎰 スロット — {self.machine_no}番台",
            description=f"**{SLOT_BET}コイン**掛け\n設定は台を打って確かめよう！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="残高", value=f"{bal:,} コイン", inline=True)
        await interaction.response.edit_message(embed=embed, view=SlotGameView(uid))

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        for i in range(1, 11):
            self.add_item(SlotMachineButton(i))

    @discord.ui.button(label="🏠 戻る", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import MainMenuView, build_menu_embed
        await interaction.response.edit_message(embed=build_menu_embed(), view=MainMenuView())

class SlotGameView(discord.ui.View):
    def __init__(self, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label="回す", style=discord.ButtonStyle.primary, emoji="🎰")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_slots.get(self.user_id)
        if not game:
            await interaction.response.send_message("ゲームが見つかりません", ephemeral=True)
            return

        await interaction.response.defer()
        uid = self.user_id
        guild_id = game["guild_id"]

        # フリースピン中
        if game["state"] == "freespin":
            result = spin_freespin(game["fs_type"])
            game["fs_remaining"] -= 1
            game["fs_total_payout"] += result["payout"]
            db.update_balance(uid, guild_id, result["payout"])
            new_bal = db.get_balance(uid, guild_id)

            # 継続チェック
            if result["continue"]:
                game["fs_remaining"] += FREESPIN_GAMES
                is_revival = game["fs_remaining"] == FREESPIN_GAMES
                title = "🔥 復活！！！" if is_revival else "🌟 フリースピン継続！！"
                embed = discord.Embed(title=title, color=discord.Color.gold())
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
            elif game["fs_remaining"] <= 0:
                fs_label = FREESPIN_TYPES[game["fs_type"]]["label"]
                color = FREESPIN_TYPES[game["fs_type"]]["color"]
                embed = discord.Embed(title="💨 フリースピン終了", color=color)
                embed.add_field(name="種別", value=f"**{fs_label}**", inline=False)
                embed.add_field(name="💰 合計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=False)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                game["state"] = "normal"
                game["fs_type"] = None
                game["fs_remaining"] = 0
                game["fs_total_payout"] = 0
            else:
                embed = discord.Embed(title="🌟 フリースピン中", color=FREESPIN_TYPES[game["fs_type"]]["color"])
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)

            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            return

        # ボーナス告知ゲーム
        if game["state"] == "pending_bonus":
            bonus = game["pending_bonus"]
            reel_key = f"{bonus.lower()}_bonus"
            reel = get_reel_display(reel_key)
            fs_label = FREESPIN_TYPES[bonus]["label"]
            color = FREESPIN_TYPES[bonus]["color"]
            game["state"] = "freespin"
            game["fs_type"] = bonus
            game["fs_remaining"] = FREESPIN_GAMES
            game["fs_total_payout"] = 0
            game["pending_bonus"] = None

            embed = discord.Embed(
                title="✨ F R E E S P I N ✨",
                description=f"```\n{reel}\n```\n種別は...お楽しみに！",
                color=color
            )
            embed.add_field(name="回数", value=f"{FREESPIN_GAMES}回", inline=True)
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            return

        # 通常スピン
        bal = db.get_balance(uid, guild_id)
        if bal < SLOT_BET:
            await interaction.followup.send("❌ コインが足りません", ephemeral=True)
            return

        db.update_balance(uid, guild_id, -SLOT_BET)
        result = spin_normal(game["setting"])
        yaku = result.get("yaku")
        bonus = result.get("bonus")
        payout = result.get("payout", 0)

        is_miss = result["type"] == "blank"

        # ハズレ演出1%ボーナス
        if is_miss and random.random() < MISS_BONUS_CHANCE:
            bonus = random.choice(["REGULAR","BIG"])
            result["type"] = "yaku_bonus"
            is_miss = False

        if payout > 0:
            db.update_balance(uid, guild_id, payout)

        new_bal = db.get_balance(uid, guild_id)

        # GOD・レジェンド単独
        if result["type"] in ["god_trigger","legend_trigger"]:
            bonus_type = result["bonus"]
            effect = random.choice(SLOT_EFFECTS["god"] if bonus_type == "GOD" else SLOT_EFFECTS["legend"])

            # 演出表示
            embed1 = discord.Embed(title="🎰", description=effect, color=FREESPIN_TYPES[bonus_type]["color"])
            await interaction.followup.edit_message(interaction.message.id, embed=embed1, view=self)
            await asyncio.sleep(SLOT_WAIT)

            # ・・・
            embed2 = discord.Embed(title="🎰", description="・・・", color=FREESPIN_TYPES[bonus_type]["color"])
            await interaction.followup.edit_message(interaction.message.id, embed=embed2, view=self)
            await asyncio.sleep(SLOT_WAIT)

            # リール表示
            reel = get_reel_display(f"{bonus_type.lower()}_bonus")
            embed3 = discord.Embed(
                title=f"{'☯️' if bonus_type == 'GOD' else '🌐'} {FREESPIN_TYPES[bonus_type]['label']}",
                description=f"```\n{reel}\n```",
                color=FREESPIN_TYPES[bonus_type]["color"]
            )
            game["state"] = "freespin"
            game["fs_type"] = bonus_type
            game["fs_remaining"] = FREESPIN_GAMES
            game["fs_total_payout"] = 0
            await interaction.followup.edit_message(interaction.message.id, embed=embed3, view=self)
            return

        # 演出テキスト
        effect = get_effect(yaku, bonus is not None, is_miss)

        # 演出表示
        embed1 = discord.Embed(description=effect, color=discord.Color.dark_gray())
        await interaction.followup.edit_message(interaction.message.id, embed=embed1, view=self)
        await asyncio.sleep(SLOT_WAIT)

        # ・・・
        embed2 = discord.Embed(description="・・・", color=discord.Color.dark_gray())
        await interaction.followup.edit_message(interaction.message.id, embed=embed2, view=self)
        await asyncio.sleep(SLOT_WAIT)

        # リール表示
        reel_key = yaku if yaku else "blank"
        reel = get_reel_display(reel_key)

        yaku_label = {
            "cherry":"🍒 チェリー","strong_cherry":"🍒🍒🍒 強チェリー！！",
            "suika":"🍉🍉🍉 スイカ！","bell":"🔔🔔🔔 ベル！",
            "replay":"🔄🔄🔄 リプレイ！","weak_chance":"💥 チャンス目！",
            "strong_chance":"💥💥 強チャンス目！！",
        }.get(yaku, "")

        if bonus:
            game["state"] = "pending_bonus"
            game["pending_bonus"] = bonus
            embed3 = discord.Embed(
                title=yaku_label,
                description=f"```\n{reel}\n```",
                color=discord.Color.gold()
            )
            embed3.set_footer(text=f"残高: {new_bal:,} コイン | 次のゲームへ...")
        else:
            color = discord.Color.dark_gray() if not yaku else discord.Color.blue()
            embed3 = discord.Embed(title=yaku_label if yaku_label else "　", description=f"```\n{reel}\n```", color=color)
            if payout > 0:
                embed3.add_field(name="払い出し", value=f"+{payout:,} コイン", inline=True)
            embed3.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)

        await interaction.followup.edit_message(interaction.message.id, embed=embed3, view=self)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def quit_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        active_slots.pop(self.user_id, None)
        embed = discord.Embed(title="🚪 終了", description="またね！", color=discord.Color.dark_gray())
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        active_slots.pop(self.user_id, None)

class Slot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slot", description="スロットマシンで遊ぶ！台を選んで回そう")
    async def slot(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if uid in active_slots:
            await interaction.response.send_message("❌ すでにプレイ中です", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎰 スロット — 台選択",
            description=f"**{SLOT_BET}コイン**掛け\n1〜10番台から選んでください！",
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed, view=SlotSelectView(), ephemeral=True)

async def setup(bot):
    await bot.add_cog(Slot(bot))
