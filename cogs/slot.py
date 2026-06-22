import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
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

def spin_normal(setting: int) -> dict:
    """通常時のスピン結果を返す"""
    s = SLOT_SETTINGS[setting]
    r = random.random()

    # レジェンド・GOD単独当選チェック
    if random.random() < GOD_PROB:
        return {"type": "god_trigger", "yaku": None, "bonus": "GOD"}
    if random.random() < LEGEND_PROB:
        return {"type": "legend_trigger", "yaku": None, "bonus": "LEGEND"}

    # 子役抽選
    yaku = None
    if random.random() < s["strong_chance_prob"]:
        yaku = "strong_chance"
    elif random.random() < s["strong_cherry_prob"]:
        yaku = "strong_cherry"
    elif random.random() < s["weak_chance_prob"]:
        yaku = "weak_chance"
    elif random.random() < 1/s["suika_prob"]:
        yaku = "suika"
    elif random.random() < 1/s["cherry_prob"]:
        yaku = "cherry"
    elif random.random() < 1/s["bell_prob"]:
        yaku = "bell"
    elif random.random() < 1/s["replay_prob"]:
        yaku = "replay"

    if yaku is None:
        return {"type": "blank", "yaku": None, "bonus": None, "payout": 0}

    # ボーナス重複チェック
    rate_key = f"{yaku}_bonus_rate"
    bonus_rate = s.get(rate_key, 0)
    if random.random() < bonus_rate:
        ratio = BONUS_RATIO.get(yaku, {"regular": 0.5, "big": 0.5, "super": 0.0})
        r2 = random.random()
        if r2 < ratio["regular"]:
            bonus = "REGULAR"
        elif r2 < ratio["regular"] + ratio["big"]:
            bonus = "BIG"
        else:
            bonus = "SUPER"
        return {"type": "yaku_bonus", "yaku": yaku, "bonus": bonus}

    # 子役のみ
    payout = NORMAL_PAYOUTS.get(yaku, 0)
    return {"type": "yaku", "yaku": yaku, "bonus": None, "payout": payout}

def get_effect(yaku: str, has_bonus: bool, setting: int) -> tuple[str, bool]:
    """演出テキストと矛盾フラグを返す（EFFECT_CHANCEで発生）"""
    if random.random() > EFFECT_CHANCE:
        return None, False

    if has_bonus:
        r = random.random()
        if r < 0.10:
            effect = random.choice(SLOT_EFFECTS["weak"])
            contradiction = yaku not in effect_to_yaku(effect)
            return effect, contradiction
        elif r < 0.35:
            return random.choice(SLOT_EFFECTS["medium"]), False
        elif r < 0.65:
            return random.choice(SLOT_EFFECTS["strong"]), False
        else:
            return random.choice(SLOT_EFFECTS["super"]), False
    else:
        r = random.random()
        if r < 0.70:
            effect = random.choice(SLOT_EFFECTS["weak"])
            contradiction = yaku not in effect_to_yaku(effect) and yaku in ["cherry","suika","strong_cherry","strong_chance","weak_chance"]
            return effect, contradiction
        elif r < 0.90:
            return random.choice(SLOT_EFFECTS["medium"]), False
        else:
            return random.choice(SLOT_EFFECTS["strong"]), False

def effect_to_yaku(effect: str) -> list:
    if "チェリー" in effect:
        return ["cherry", "strong_cherry"]
    if "スイカ" in effect or "緑" in effect:
        return ["suika"]
    if "ベル" in effect or "鐘" in effect:
        return ["bell"]
    return []

def spin_freespin(fs_type: str) -> dict:
    """フリースピン中のスピン結果"""
    probs = FREESPIN_YAKUS[fs_type]
    payout = FREESPIN_BASE_PAYOUT

    yaku_results = []
    for yaku, prob in probs.items():
        if random.random() < prob:
            yaku_results.append(yaku)
            payout += FREESPIN_PAYOUTS.get(yaku, 0)

    # 継続抽選
    continue_bonus = None
    for yaku in yaku_results:
        rate = FREESPIN_BONUS_RATES.get(yaku, 0)
        if random.random() < rate:
            continue_bonus = fs_type
            break

    return {
        "yakus": yaku_results,
        "payout": payout,
        "continue": continue_bonus is not None,
    }

# アクティブゲーム管理
active_slots: dict[str, dict] = {}

class SlotMachineSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=f"{i}番台", value=str(i))
            for i in range(1, 11)
        ]
        super().__init__(placeholder="台を選んでください（1〜10番）", options=options)

    async def callback(self, interaction: discord.Interaction):
        machine_no = int(self.values[0])
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if uid in active_slots:
            await interaction.response.send_message("❌ すでにプレイ中です", ephemeral=True)
            return

        bal = db.get_balance(uid, guild_id)
        if bal < SLOT_BET:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        setting = get_machine_setting(machine_no)
        active_slots[uid] = {
            "machine": machine_no,
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
            title=f"🎰 スロット — {machine_no}番台",
            description=f"**{SLOT_BET}コイン**掛け\n設定は台を打って確かめよう！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="残高", value=f"{bal:,} コイン", inline=True)
        view = SlotGameView(uid)
        await interaction.response.edit_message(embed=embed, view=view)

class SlotSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(SlotMachineSelect())

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

        uid = self.user_id
        guild_id = game["guild_id"]
        bal = db.get_balance(uid, guild_id)

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
                embed = discord.Embed(
                    title=f"🌟 フリースピン継続！！",
                    color=discord.Color.gold()
                )
                # 最終ゲームで継続なら復活演出
                if game["fs_remaining"] == FREESPIN_GAMES:
                    embed.title = "🔥 復活！！！"
                    embed.description = ".\n..\n..."

                yaku_display = " ".join([f"`{y}`" for y in result["yakus"]]) if result["yakus"] else "なし"
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)

            elif game["fs_remaining"] <= 0:
                # フリースピン終了
                fs_label = FREESPIN_TYPES[game["fs_type"]]["label"]
                color = FREESPIN_TYPES[game["fs_type"]]["color"]
                embed = discord.Embed(
                    title="💨 フリースピン終了",
                    color=color
                )
                embed.add_field(name="種別", value=f"**{fs_label}**", inline=False)
                embed.add_field(name="💰 合計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=False)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                game["state"] = "normal"
                game["fs_type"] = None
                game["fs_remaining"] = 0
                game["fs_total_payout"] = 0

            else:
                # 通常継続
                yaku_display = " ".join([f"`{y}`" for y in result["yakus"]]) if result["yakus"] else ""
                embed = discord.Embed(
                    title=f"🌟 フリースピン中",
                    color=FREESPIN_TYPES[game["fs_type"]]["color"]
                )
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                if yaku_display:
                    embed.set_footer(text=yaku_display)

            await interaction.response.edit_message(embed=embed, view=self)
            return

        # ボーナス告知ゲーム（子役当選の次スピン）
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
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # 通常スピン
        if bal < SLOT_BET:
            await interaction.response.send_message(f"❌ コインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, guild_id, -SLOT_BET)
        game["total_in"] += SLOT_BET
        new_bal = db.get_balance(uid, guild_id)

        result = spin_normal(game["setting"])
        yaku = result.get("yaku")
        bonus = result.get("bonus")
        payout = result.get("payout", 0)

        # 子役払い出し
        if payout > 0:
            db.update_balance(uid, guild_id, payout)
            new_bal = db.get_balance(uid, guild_id)
            game["total_out"] += payout

        reel_key = yaku if yaku else "blank"
        reel = get_reel_display(reel_key)

        # 演出（テンポ重視で一部のみ）
        effect_text = ""
        if yaku and yaku not in ["replay", "bell"]:
            effect, contradiction = get_effect(yaku, bonus is not None, game["setting"])
            if effect:
                if contradiction:
                    effect_text = f"{effect}\n💥 矛盾...！"
                else:
                    effect_text = effect

        # GOD・レジェンド単独
        if result["type"] in ["god_trigger", "legend_trigger"]:
            bonus_type = result["bonus"]
            god_effect = random.choice(SLOT_EFFECTS["god"] if bonus_type == "GOD" else SLOT_EFFECTS["legend"])
            embed = discord.Embed(
                title=f"{'☯️' if bonus_type == 'GOD' else '🌐'} {FREESPIN_TYPES[bonus_type]['label']}",
                description=f"{god_effect}\n\n```\n{get_reel_display(f'{bonus_type.lower()}_bonus')}\n```",
                color=FREESPIN_TYPES[bonus_type]["color"]
            )
            game["state"] = "freespin"
            game["fs_type"] = bonus_type
            game["fs_remaining"] = FREESPIN_GAMES
            game["fs_total_payout"] = 0
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # ボーナス当選→次ゲーム告知
        if bonus:
            game["state"] = "pending_bonus"
            game["pending_bonus"] = bonus
            desc = f"{effect_text}\n```\n{reel}\n```" if effect_text else f"```\n{reel}\n```"
            yaku_label = {
                "cherry": "🍒 チェリー！", "strong_cherry": "🍒🍒🍒 強チェリー！！",
                "suika": "🍉🍉🍉 スイカ！", "bell": "🔔🔔🔔 ベル！",
                "replay": "🔄🔄🔄 リプレイ！", "weak_chance": "💥 チャンス目！",
                "strong_chance": "💥💥 強チャンス目！！",
            }.get(yaku, "")
            embed = discord.Embed(
                title=yaku_label,
                description=desc,
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"残高: {new_bal:,} コイン | 次のゲームへ...")
            await interaction.response.edit_message(embed=embed, view=self)
            return

        # ハズレ・子役のみ
        yaku_label = {
            "cherry": "🍒 チェリー", "strong_cherry": "🍒🍒🍒 強チェリー",
            "suika": "🍉🍉🍉 スイカ", "bell": "🔔🔔🔔 ベル",
            "replay": "🔄🔄🔄 リプレイ", "weak_chance": "💥 チャンス目",
            "strong_chance": "💥💥 強チャンス目",
        }.get(yaku, "")

        desc = f"{effect_text}\n```\n{reel}\n```" if effect_text else f"```\n{reel}\n```"
        title = yaku_label if yaku_label else "　"

        color = discord.Color.dark_gray() if not yaku else discord.Color.blue()
        embed = discord.Embed(title=title, description=desc, color=color)

        if payout > 0:
            embed.add_field(name="払い出し", value=f"+{payout:,} コイン", inline=True)
        embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)

        if yaku in ["replay", "weak_chance", "strong_chance"]:
            embed.set_footer(text="次回無料！")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="やめる", style=discord.ButtonStyle.secondary, emoji="🚪")
    async def quit_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_slots.pop(self.user_id, None)
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
            await interaction.response.send_message("❌ すでにプレイ中です。やめるボタンを押してください", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎰 スロット — 台選択",
            description=(
                f"**{SLOT_BET}コイン**掛け\n"
                "1〜10番台から選んでください。\n"
                "設定は台によって異なります。高設定を探せ！"
            ),
            color=discord.Color.dark_green()
        )
        await interaction.response.send_message(embed=embed, view=SlotSelectView())

async def setup(bot):
    await bot.add_cog(Slot(bot))
