import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import *
import random
import asyncio
from datetime import datetime, timezone, timedelta
from cogs.embed_utils import pad_embed

db = Database()
JST = timezone(timedelta(hours=9))

def get_machine_setting(machine_no: int) -> int:
    """日付ベースで台ごとの設定をランダム決定（1日1回更新）"""
    from config import get_daily_machines
    machines = get_daily_machines()
    return machines[machine_no - 1]

def get_reel_display(reel_key: str) -> str:
    symbols = REELS.get(reel_key, REELS["blank"])
    return f"┌─────────────────┐\n│ {symbols[0]} │ {symbols[1]} │ {symbols[2]} │\n└─────────────────┘"

def get_effect(yaku: str, has_bonus: bool, is_miss: bool) -> str:
    """演出を返す。yakuの種類と結果に連動させる"""
    if is_miss:
        return random.choice(SLOT_EFFECTS["miss"])

    if has_bonus:
        # ボーナス当選時：役に応じた矛盾演出 or 強演出
        r = random.random()
        if r < 0.10 and yaku in SLOT_EFFECTS.get("contradiction", {}):
            # 矛盾演出（例：チェリーの気配でベルが来る）
            return random.choice(SLOT_EFFECTS["contradiction"][yaku])
        elif r < 0.35:
            return random.choice(SLOT_EFFECTS["weak"])
        elif r < 0.60:
            return random.choice(SLOT_EFFECTS["medium"])
        elif r < 0.82:
            return random.choice(SLOT_EFFECTS["strong"])
        else:
            return random.choice(SLOT_EFFECTS["super"])
    else:
        # ハズレ・通常役：役の強さに応じて演出を出し分け
        if yaku in ("strong_chance", "strong_cherry"):
            # 強役は強めの演出
            r = random.random()
            if r < 0.20:
                return random.choice(SLOT_EFFECTS["medium"])
            elif r < 0.65:
                return random.choice(SLOT_EFFECTS["strong"])
            else:
                return random.choice(SLOT_EFFECTS["super"])
        elif yaku in ("weak_chance", "suika"):
            r = random.random()
            if r < 0.30:
                return random.choice(SLOT_EFFECTS["weak"])
            elif r < 0.70:
                return random.choice(SLOT_EFFECTS["medium"])
            else:
                return random.choice(SLOT_EFFECTS["strong"])
        elif yaku in ("cherry",):
            r = random.random()
            if r < 0.50:
                return random.choice(SLOT_EFFECTS["miss"])
            else:
                return random.choice(SLOT_EFFECTS["weak"])
        elif yaku in ("bell", "replay"):
            r = random.random()
            if r < 0.60:
                return random.choice(SLOT_EFFECTS["miss"])
            else:
                return random.choice(SLOT_EFFECTS["weak"])
        else:
            # ハズレ
            r = random.random()
            if r < 0.60:
                return random.choice(SLOT_EFFECTS["miss"])
            elif r < 0.85:
                return random.choice(SLOT_EFFECTS["weak"])
            else:
                return random.choice(SLOT_EFFECTS["medium"])

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

    # 継続抽選：子役重複のみ（残り10ゲーム以下の時だけ抽選、それ以外は無抽選）
    # 呼び出し側でfs_remainingを確認してから抽選するため、ここではフラグだけ返す
    continued = False
    for yaku in yaku_results:
        rate = FREESPIN_BONUS_RATES.get(yaku, 0)
        if random.random() < rate:
            continued = True
            break

    return {
        "yakus": yaku_results,
        "payout": payout,
        "continued": continued,  # 継続当選フラグ（残り10以下の時のみ有効）
    }

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
            "fs_continued":False,  # 継続当選済みフラグ（未告知管理用）
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
        # 連打防止
        if game.get("spinning"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True)
            return
        game["spinning"] = True

        await interaction.response.defer()
        uid = self.user_id
        guild_id = game["guild_id"]

        # フリースピン中
        if game["state"] == "freespin":
            fs_remaining_before = game["fs_remaining"]
            result = spin_freespin(game["fs_type"])
            game["fs_remaining"] -= 1
            game["fs_total_payout"] += result["payout"]

            yaku_display = "、".join([{
                "replay":"🔄リプレイ","bell":"🔔ベル","cherry":"🍒チェリー",
                "suika":"🍉スイカ","weak_chance":"💥チャンス目",
                "strong_cherry":"🍒強チェリー","strong_chance":"💥強チャンス目",
            }.get(y, y) for y in result["yakus"]]) or "ハズレ"

            # 継続抽選：残り10ゲーム以下 かつ まだ当選していない時だけ
            if not game.get("fs_continued") and fs_remaining_before <= 10 and result["continued"]:
                game["fs_continued"] = True
                game["fs_remaining"] += FREESPIN_GAMES  # 内部確定：即加算

            # 告知判定（当選済みで未告知の場合のみ）
            is_last_game = game["fs_remaining"] <= 0
            show_notice = False
            if game.get("fs_continued") and not game.get("fs_noticed"):
                if is_last_game or random.random() < 0.5:
                    show_notice = True
                    game["fs_noticed"] = True

            # 通常時と同じ演出
            has_bonus = show_notice  # 告知タイミング＝ボーナス演出
            is_miss = len(result["yakus"]) == 0
            top_yaku = result["yakus"][0] if result["yakus"] else None
            effect = get_effect(top_yaku, has_bonus, is_miss)

            # 演出表示
            embed_effect = discord.Embed(
                title="🌟 フリースピン中",
                description=effect,
                color=FREESPIN_TYPES[game["fs_type"]]["color"]
            )
            embed_effect.add_field(name="残り", value=f"{game['fs_remaining'] + 1}回", inline=True)
            pad_embed(embed_effect, target_fields=4)
            await interaction.followup.edit_message(interaction.message.id, embed=embed_effect, view=self)
            await asyncio.sleep(SLOT_WAIT)

            db.update_balance(uid, guild_id, result["payout"])
            new_bal = db.get_balance(uid, guild_id)

            # 結果embed
            if show_notice and continued:
                # 継続告知
                fs_label = FREESPIN_TYPES[game["fs_type"]]["label"]
                color = FREESPIN_TYPES[game["fs_type"]]["color"]
                embed = discord.Embed(title="🔥 フリースピン継続！！", color=color)
                embed.add_field(name="今回の図柄", value=yaku_display, inline=False)
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                pad_embed(embed, target_fields=5)
            elif game["fs_remaining"] <= 0 and not continued:
                # 終了
                fs_label = FREESPIN_TYPES[game["fs_type"]]["label"]
                color = FREESPIN_TYPES[game["fs_type"]]["color"]
                embed = discord.Embed(title="💨 フリースピン終了", color=color)
                embed.add_field(name="種別", value=f"**{fs_label}**", inline=False)
                embed.add_field(name="今回の図柄", value=yaku_display, inline=True)
                embed.add_field(name="💰 合計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=False)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                pad_embed(embed, target_fields=5)
                game["state"] = "normal"
                game["fs_type"] = None
                game["fs_remaining"] = 0
                game["fs_total_payout"] = 0
                game["fs_continued"] = False
                game["fs_noticed"] = False
            else:
                # 通常進行（継続当選済みだが未告知の場合も含む）
                embed = discord.Embed(
                    title="🌟 フリースピン中",
                    color=FREESPIN_TYPES[game["fs_type"]]["color"]
                )
                embed.add_field(name="今回の図柄", value=yaku_display, inline=False)
                embed.add_field(name="今回の払い出し", value=f"{result['payout']:,} コイン", inline=True)
                embed.add_field(name="累計獲得", value=f"{game['fs_total_payout']:,} コイン", inline=True)
                embed.add_field(name="残り", value=f"{game['fs_remaining']}回", inline=True)
                embed.add_field(name="残高", value=f"{new_bal:,} コイン", inline=False)
                pad_embed(embed, target_fields=5)

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
            game["fs_continued"] = False
            game["fs_noticed"] = False

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
        pad_embed(embed1, target_fields=5)
        await interaction.followup.edit_message(interaction.message.id, embed=embed1, view=self)
        await asyncio.sleep(SLOT_WAIT)

        # ・・・
        embed2 = discord.Embed(description="・・・", color=discord.Color.dark_gray())
        pad_embed(embed2, target_fields=5)
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
            pad_embed(embed3, target_fields=5)
        else:
            color = discord.Color.dark_gray() if not yaku else discord.Color.blue()
            embed3 = discord.Embed(title=yaku_label if yaku_label else "　", description=f"```\n{reel}\n```", color=color)
            if payout > 0:
                embed3.add_field(name="払い出し", value=f"+{payout:,} コイン", inline=True)
            embed3.add_field(name="残高", value=f"{new_bal:,} コイン", inline=True)
            pad_embed(embed3, target_fields=5)

        await interaction.followup.edit_message(interaction.message.id, embed=embed3, view=self)
        if game:
            game["spinning"] = False

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
