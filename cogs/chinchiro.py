import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import CHINCHIRO_MULT, CHINCHIRO_MIN_BET, CHINCHIRO_MAX_BET
import random
import asyncio
from datetime import date

db = Database()

def today_str() -> str:
    return date.today().isoformat()

# 払えず追い出されたときの演出（怖い人）
KICKED_LINES = (
    "🚪💢 ……奥から、人相のよくない男がのっそりと現れた。\n"
    "「兄ちゃん……ツケは、キッチリ払うてもらわなぁ？」\n"
    "有り金を根こそぎ巻き上げられ、表へ放り出された。\n\n"
    "💸 **所持ナトコインは 0 になった。**\n"
    "🈲 今日はもう、この店の暖簾はくぐれない……。"
)
# 出禁中に入ろうとしたとき
BANNED_LINES = (
    "🚪 入口で用心棒に肩をつかまれた。\n"
    "「兄ちゃん、今日はもう帰りな。……顔、覚えてるで」\n"
    "🈲 本日のチンチロは出入り禁止。日を改めて出直そう。"
)

def roll_dice():
    return [random.randint(1, 6) for _ in range(3)]

def evaluate(dice: list) -> tuple[int, str, str]:
    """役を判定。返り値は (強さスコア, 役名, 役キー)。
    スコア順: ピンゾロ100 > ゾロ目51〜56 > シゴロ49 > 目1〜6 > 目なし0 > ヒフミ-1"""
    d = sorted(dice)
    counts = {n: dice.count(n) for n in set(dice)}

    # ピンゾロ
    if d == [1, 1, 1]:
        return (100, "👑 ピンゾロ！！", "pinzoro")

    # ゾロ目
    if len(set(d)) == 1:
        return (50 + d[0], f"🎲 {d[0]}のゾロ目！", "zorome")

    # シゴロ
    if d == [4, 5, 6]:
        return (49, "🔥 シゴロ！！", "shigoro")

    # ヒフミ
    if d == [1, 2, 3]:
        return (-1, "💀 ヒフミ...", "hifumi")

    # 目
    for num, count in counts.items():
        if count == 2:
            remaining = [n for n in dice if n != num]
            return (remaining[0], f"🎯 目：{remaining[0]}", "me")

    return (-2, "💧 ションベン（目なし）", "menashi")

def decide(p_score: int, a_score: int) -> str:
    """左(p)視点の勝敗。バスト(score<0=ヒフミ/ションベン)同士は引き分け＝バスト役は勝たない。"""
    p_bust, a_bust = p_score < 0, a_score < 0
    if p_bust and a_bust:
        return "draw"
    if p_bust:
        return "lose"
    if a_bust:
        return "win"
    if p_score > a_score:
        return "win"
    if p_score < a_score:
        return "lose"
    return "draw"

def roll_with_reroll() -> tuple[list, int, str, str]:
    """目なしは最大3回まで自動で振り直し。最後の結果を返す。"""
    dice, score, label, kind = [], 0, "", "menashi"
    for _ in range(3):
        dice = roll_dice()
        score, label, kind = evaluate(dice)
        if kind != "menashi":
            break
    return dice, score, label, kind

def settle_multiplier(win_kind: str, lose_kind: str) -> int:
    """配当倍率。勝者の役の倍率に、敗者がヒフミなら2倍ペナルティを乗算。
    例: ピンゾロ(5)×ヒフミ(2) = 最大10倍付。"""
    mult = CHINCHIRO_MULT.get(win_kind, 1)
    if lose_kind == "hifumi":
        mult *= 2
    return mult

DICE_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣", 6: "6️⃣"}

def dice_str(dice: list) -> str:
    return " ".join(DICE_EMOJI[d] for d in dice)

def dice_reveal(dice: list, shown: int) -> str:
    """先頭 shown 個だけ出目を見せ、残りは 🎲（振っている最中）にする。"""
    return " ".join(DICE_EMOJI[d] if i < shown else "🎲" for i, d in enumerate(dice))

# 壺振り（ドキドキ感の溜め）演出フレーム
SHAKE_FRAMES = (
    "🥣 …カラ…",
    "🥣 …カラカラ…",
    "🥣 カラカラカラッ…！",
    "🥣 …シャッ、シャッ…",
    "🥣 …いくぞ…！",
)

async def animate_reveal(interaction, title, l_name, l_dice, l_label, r_name, r_dice, r_label, delay=0.62):
    """壺振り → 溜め → 左→右の順にサイコロを1個ずつめくる演出。ボタンは消した状態で進める。"""
    def emb(ls, rs, l_done=False, r_done=False, note=None):
        e = discord.Embed(title=title, color=discord.Color.blue())
        if note:
            e.description = note
        lv = dice_reveal(l_dice, ls) + (f"\n{l_label}" if l_done else "")
        rv = dice_reveal(r_dice, rs) + (f"\n{r_label}" if r_done else "　")
        e.add_field(name=l_name, value=lv, inline=True)
        e.add_field(name=r_name, value=rv, inline=True)
        return e

    # ── ① 壺を振る（両者まだ伏せたまま。ドキドキの溜め）──
    for frame in random.sample(SHAKE_FRAMES, 3):
        await interaction.edit_original_response(embed=emb(0, 0, note=f"**{frame}**"), view=None)
        await asyncio.sleep(delay * 0.7)
    # ② ためる一拍
    await interaction.edit_original_response(embed=emb(0, 0, note="**…せーのっ！**"), view=None)
    await asyncio.sleep(delay)

    # ── ③ 左（先攻）を1個ずつドキドキ開示 ──
    for i in range(1, 4):
        await interaction.edit_original_response(
            embed=emb(i, 0, note=f"🎲 **{l_name}** の出目…！"), view=None)
        await asyncio.sleep(delay)
    await interaction.edit_original_response(embed=emb(3, 0, l_done=True), view=None)
    await asyncio.sleep(delay)
    # ── ④ 右（後攻）を1個ずつ ──
    for i in range(1, 4):
        await interaction.edit_original_response(
            embed=emb(3, i, l_done=True, note=f"🎲 **{r_name}** の出目…！"), view=None)
        await asyncio.sleep(delay)
    await interaction.edit_original_response(embed=emb(3, 3, l_done=True, r_done=True), view=None)
    await asyncio.sleep(delay * 0.7)

# AI対戦
class ChinchiroAIView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str, bet: int):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet
        self.rolling = False

    @discord.ui.button(label="サイコロを振る！", style=discord.ButtonStyle.primary, emoji="🎲")
    async def roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        if self.rolling:
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True)
            return
        self.rolling = True
        await interaction.response.defer()
        try:
            await self._play(interaction)
        finally:
            self.rolling = False

    async def _play(self, interaction: discord.Interaction):
        uid, gid, bet = self.user_id, self.guild_id, self.bet

        # プレイヤー（目なしは最大3回振り直し。3回でも目なし＝ションベンで負け扱い）
        p_dice, p_score, p_label, p_kind = roll_with_reroll()
        # AI
        a_dice, a_score, a_label, a_kind = roll_with_reroll()

        # ── サイコロを1個ずつめくる演出（あなた → AI）──
        await animate_reveal(interaction, "🎲 チンチロ vs AI",
                             "あなた", p_dice, p_label, "AI", a_dice, a_label)

        # ── 決着（出目どおりに判定。改ざんは一切しない）──
        embed = discord.Embed(title="🎲 チンチロ vs AI", color=discord.Color.blue())
        embed.add_field(name="あなた", value=f"{dice_str(p_dice)}\n{p_label}", inline=True)
        embed.add_field(name="AI", value=f"{dice_str(a_dice)}\n{a_label}", inline=True)

        outcome = decide(p_score, a_score)
        bankrupt = False

        if outcome == "win":
            mult = settle_multiplier(p_kind, a_kind)
            winnings = bet * mult                                 # 役倍率を反映（テラ銭なし）
            db.update_balance(uid, gid, bet + winnings)           # 賭け金返却＋丸取り
            net = winnings
            mtxt = f"　{p_label}　**×{mult}倍**" if mult > 1 else f"　{p_label}（等倍）"
            result = f"🎉 勝ち！{mtxt}\n内訳: {bet:,} × {mult} = +{winnings:,} ナトコイン"
        elif outcome == "lose":
            mult = settle_multiplier(a_kind, p_kind)
            owed = bet * (mult - 1)                               # 賭け金は開始時に消費済み。追加で払う分
            bal = db.get_balance(uid, gid)                        # 賭け金を引いた後の残高
            if owed > bal:
                # ── 払えない → 怖い人。残高0＆本日出禁 ──
                lost_all = bet + bal
                db.set_balance(uid, gid, 0)
                db.ban_chinchiro_today(uid, gid, today_str())
                net = -lost_all
                bankrupt = True
                mtxt = f" ×{mult}倍" if mult > 1 else ""
                result = f"😱 AIの勝ち{mtxt} ── 払えない！"
            else:
                if owed > 0:
                    db.update_balance(uid, gid, -owed)
                net = -(bet + owed)
                mtxt = f" ×{mult}倍" if mult > 1 else ""
                result = f"😢 負け... AIの勝ち{mtxt}"
        else:
            db.update_balance(uid, gid, bet)                      # 引き分けは賭け金返却
            net = 0
            result = "🤝 引き分け！"

        new_bal = db.get_balance(uid, gid)

        if bankrupt:
            # 追い出し演出（リプレイ不可）
            embed.color = discord.Color.dark_red()
            embed.add_field(name="結果", value=f"{result}\n{net:,} ナトコイン", inline=False)
            embed.add_field(name="\u200b", value=KICKED_LINES, inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            await interaction.edit_original_response(embed=embed, view=_KickedView())
            return

        embed.color = discord.Color.gold() if net > 0 else discord.Color.red() if net < 0 else discord.Color.blue()
        embed.add_field(
            name="結果",
            value=f"{result}\n{'+' if net >= 0 else ''}{net:,} ナトコイン",
            inline=False
        )
        embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)

        view = ChinchiroAgainView(uid, gid, bet)
        if net > 0:
            from cogs.doubleup import build_entry_view
            view = build_entry_view(uid, gid, net, "チンチロ",
                                    lambda: ChinchiroAgainView(uid, gid, bet))
        await interaction.edit_original_response(embed=embed, view=view)

        # 勝ち額が大きければBOT告知
        if net > 0:
            from cogs.bigwin import announce_big_win
            await announce_big_win(interaction, interaction.user, "チンチロ",
                                   net, balance=new_bal, detail=p_label)

class ChinchiroAgainView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str, bet: int):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet

    @discord.ui.button(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🎲")
    async def again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        if db.is_chinchiro_banned(self.user_id, self.guild_id, today_str()):
            await interaction.response.edit_message(
                embed=discord.Embed(title="🚪 出入り禁止", description=BANNED_LINES,
                                    color=discord.Color.dark_red()),
                view=_KickedView())
            return
        bal = db.get_balance(self.user_id, self.guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(self.user_id, self.guild_id, -self.bet)
        embed = discord.Embed(title="🎲 チンチロ vs AI", description="サイコロを振ってください！", color=discord.Color.blue())
        embed.set_footer(text=f"賭け: {self.bet:,} ナトコイン")
        view = ChinchiroAIView(self.user_id, self.guild_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

class _KickedView(discord.ui.View):
    """払えず追い出された後／出禁中のナビ（リプレイ不可）。"""
    def __init__(self):
        super().__init__(timeout=900)

    @discord.ui.button(label="🔙 カジノへ戻る", style=discord.ButtonStyle.secondary)
    async def back_casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction)

# 対人戦
pvp_rooms: dict[str, dict] = {}

class ChinchiroPvPView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=900)
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

        if db.is_chinchiro_banned(uid, room["guild_id"], today_str()):
            await interaction.response.send_message(BANNED_LINES, ephemeral=True)
            return

        bal = db.get_balance(uid, room["guild_id"])
        if bal < room["bet"]:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, room["guild_id"], -room["bet"])
        room["guest_id"] = uid
        room["guest_name"] = interaction.user.display_name
        room["pot"] += room["bet"]

        embed = discord.Embed(
            title="🎲 チンチロ 対人戦",
            description=f"**{room['host_name']}** vs **{room['guest_name']}**\nポット: {room['pot']:,} ナトコイン",
            color=discord.Color.blue()
        )
        view = ChinchiroPvPGameView(self.room_id)
        await interaction.response.edit_message(embed=embed, view=view)

class ChinchiroPvPGameView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=900)
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
        if room.get("rolling"):
            await interaction.response.send_message("⏳ 処理中です...", ephemeral=True)
            return
        room["rolling"] = True
        await interaction.response.defer()
        try:
            await self._play(interaction, room)
        finally:
            if pvp_rooms.get(self.room_id):
                pvp_rooms[self.room_id]["rolling"] = False

    async def _play(self, interaction: discord.Interaction, room: dict):
        gid = room["guild_id"]
        bet = room["bet"]

        # 両者振る（目なしは最大3回振り直し）
        host_dice, host_score, host_label, host_kind = roll_with_reroll()
        guest_dice, guest_score, guest_label, guest_kind = roll_with_reroll()

        # ── サイコロを1個ずつめくる演出（ホスト → ゲスト）──
        await animate_reveal(interaction, "🎲 チンチロ 対人戦",
                             room["host_name"], host_dice, host_label,
                             room["guest_name"], guest_dice, guest_label)

        embed = discord.Embed(title="🎲 チンチロ 対人戦", color=discord.Color.gold())
        embed.add_field(name=room["host_name"], value=f"{dice_str(host_dice)}\n{host_label}", inline=True)
        embed.add_field(name=room["guest_name"], value=f"{dice_str(guest_dice)}\n{guest_label}", inline=True)

        # 勝敗（出目どおり。バスト同士は引き分け）
        oc = decide(host_score, guest_score)
        if oc == "win":
            winner, loser = "host", "guest"
            win_kind, lose_kind = host_kind, guest_kind
        elif oc == "lose":
            winner, loser = "guest", "host"
            win_kind, lose_kind = guest_kind, host_kind
        else:
            winner = None

        if winner is None:
            # 引き分け：両者の賭け金を返却
            db.update_balance(room["host_id"], gid, bet)
            db.update_balance(room["guest_id"], gid, bet)
            result = "🤝 引き分け！（賭け金返却）"
        else:
            mult = settle_multiplier(win_kind, lose_kind)
            winnings = bet * mult                                  # テラ銭なし
            win_id = room[f"{winner}_id"]
            lose_id = room[f"{loser}_id"]
            win_name = room[f"{winner}_name"]
            lose_name = room[f"{loser}_name"]
            # 敗者：賭け金を超える分(M-1倍)を追加で徴収
            owed = bet * (mult - 1)
            lbal = db.get_balance(lose_id, gid)
            if owed > lbal:
                # ── 敗者が払えない → 怖い人。残高0＆本日出禁。勝者は回収できた分だけ ──
                paid_extra = lbal
                db.set_balance(lose_id, gid, 0)
                db.ban_chinchiro_today(lose_id, gid, today_str())
                db.update_balance(win_id, gid, bet + bet + paid_extra)  # 自分の賭け金＋敗者の賭け金＋回収分
                mtxt = f" ×{mult}倍" if mult > 1 else ""
                result = (f"😱 {win_name} の勝ち！{mtxt}\n"
                          f"だが **{lose_name}** はツケを払えず…用心棒に身ぐるみ剥がされ追放された。\n"
                          f"🈲 {lose_name} は本日出入り禁止。\n"
                          f"{win_name} の獲得: {bet + paid_extra:,} ナトコイン（取り立てられた分まで）")
            else:
                if owed > 0:
                    db.update_balance(lose_id, gid, -owed)
                db.update_balance(win_id, gid, bet + winnings)         # 自分の賭け金＋丸取り
                win_label = host_label if winner == "host" else guest_label
                mtxt = f"　{win_label}　**×{mult}倍**" if mult > 1 else f"　{win_label}（等倍）"
                result = (f"🎉 {win_name} の勝ち！{mtxt}\n"
                          f"内訳: {bet:,} × {mult} = +{winnings:,} ナトコイン")

        embed.add_field(name="結果", value=result, inline=False)

        view = ChinchiroPvPContinueView(self.room_id)
        await interaction.edit_original_response(embed=embed, view=view)

        # 勝ち額が大きければBOT告知（勝者をメンションするため Member を取得）
        if winner is not None:
            try:
                from cogs.bigwin import announce_big_win
                win_id_for_ping = room[f"{winner}_id"]
                win_member = interaction.guild.get_member(int(win_id_for_ping))
                if win_member is not None:
                    win_label = host_label if winner == "host" else guest_label
                    await announce_big_win(interaction, win_member, "チンチロ対人戦",
                                           winnings, detail=win_label)
            except Exception:
                pass

class ChinchiroPvPContinueView(discord.ui.View):
    def __init__(self, room_id: str):
        super().__init__(timeout=900)
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
            await interaction.response.send_message("❌ どちらかのナトコインが足りません", ephemeral=True)
            pvp_rooms.pop(self.room_id, None)
            return

        db.update_balance(room["host_id"], room["guild_id"], -bet)
        db.update_balance(room["guest_id"], room["guild_id"], -bet)
        room["pot"] = bet * 2

        embed = discord.Embed(
            title="🎲 チンチロ 対人戦",
            description=f"**{room['host_name']}** vs **{room['guest_name']}**\nポット: {room['pot']:,} ナトコイン",
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
        super().__init__(timeout=900)
        self.bet = bet

    @discord.ui.button(label="🤖 AIと対戦", style=discord.ButtonStyle.primary)
    async def vs_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -self.bet)
        embed = discord.Embed(
            title="🎲 チンチロ vs AI",
            description="サイコロを振ってください！",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"賭け: {self.bet:,} ナトコイン")
        view = ChinchiroAIView(uid, guild_id, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚔️ 人と対戦", style=discord.ButtonStyle.success)
    async def vs_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        room_id = f"chinchiro_{uid}"
        bal = db.get_balance(uid, guild_id)
        if bal < self.bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
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
            description=f"**{interaction.user.display_name}** がチンチロ対人戦を開始！\n賭け金: **{self.bet:,} ナトコイン**\n\n参加ボタンを押して挑戦しよう！",
            color=discord.Color.blue()
        )
        view = ChinchiroPvPView(room_id)
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="🔙 カジノへ戻る", style=discord.ButtonStyle.secondary, row=4)
    async def __back_casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction)

class Chinchiro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="chinchiro", description="チンチロで勝負！AIと対戦 or 人と対戦")
    @app_commands.describe(bet="賭けるナトコイン数（10〜1000）")
    async def chinchiro(self, interaction: discord.Interaction, bet: int = 100):
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        # 本日出禁チェック（払えず追い出された人）
        if db.is_chinchiro_banned(uid, guild_id, today_str()):
            await interaction.response.send_message(
                embed=discord.Embed(title="🚪 出入り禁止", description=BANNED_LINES,
                                    color=discord.Color.dark_red()),
                ephemeral=True)
            return
        if bet < CHINCHIRO_MIN_BET:
            await interaction.response.send_message(f"❌ 最低{CHINCHIRO_MIN_BET}ナトコインから", ephemeral=True)
            return
        if bet > CHINCHIRO_MAX_BET:
            await interaction.response.send_message(f"❌ 賭け金は最大{CHINCHIRO_MAX_BET:,}ナトコインまで", ephemeral=True)
            return
        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）所持金以上は賭けられません", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎲 チンチロ",
            description=f"賭け金: **{bet:,} ナトコイン**\n\nモードを選んでください！",
            color=discord.Color.blue()
        )
        embed.add_field(name="🤖 AIと対戦", value="AIディーラーと公平勝負（テラ銭なし）", inline=True)
        embed.add_field(name="⚔️ 人と対戦", value="サーバーメンバーと対決（テラ銭なし）", inline=True)
        embed.add_field(name="役の倍率",
                        value="👑ピンゾロ×5 / 🎲ゾロ目×3 / 🔥シゴロ×2 / 🎯目×1\n💀ヒフミに勝つと倍率×2（最大ピンゾロで10倍付）",
                        inline=False)
        embed.set_footer(text="⚠️ 払えない額を負けると…身ぐるみ剥がされ、その日は出入り禁止")
        await interaction.response.send_message(embed=embed, view=ChinchiroModeView(bet))

async def setup(bot):
    await bot.add_cog(Chinchiro(bot))
