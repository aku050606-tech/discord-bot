import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import random

db = Database()
_ping = discord.AllowedMentions(users=True)

SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

def make_deck():
    return [{"suit": s, "rank": r} for s in SUITS for r in RANKS]

def card_str(card):
    return f"{card['suit']}{card['rank']}"

def hand_value(hand):
    val, aces = 0, 0
    for card in hand:
        r = card["rank"]
        if r in ("J", "Q", "K"):
            val += 10
        elif r == "A":
            aces += 1
            val += 11
        else:
            val += int(r)
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

def hand_str(hand, hide_second=False):
    if hide_second:
        return f"{card_str(hand[0])} 🂠"
    return " ".join(card_str(c) for c in hand)

active_games: dict[str, dict] = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 対人戦（2人が交互にプレイ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

pvp_rooms: dict[str, dict] = {}

def build_pvp_embed(room: dict, phase_ended=False) -> discord.Embed:
    p1 = room["p1"]
    p2 = room["p2"]
    turn = room["turn"]
    embed = discord.Embed(title="🃏 ブラックジャック 対人戦", color=discord.Color.dark_green())
    v1 = hand_value(p1["hand"])
    v2 = hand_value(p2["hand"])

    if phase_ended:
        embed.add_field(name=f"{p1['name']} の手札（{v1}）", value=hand_str(p1["hand"]), inline=False)
        embed.add_field(name=f"{p2['name']} の手札（{v2}）", value=hand_str(p2["hand"]), inline=False)
    else:
        if turn == 1:
            embed.add_field(name=f"🎮 {p1['name']} の番（{v1}）", value=hand_str(p1["hand"]), inline=False)
            embed.add_field(name=f"{p2['name']} の手札", value="🂠 🂠（待機中）", inline=False)
        else:
            embed.add_field(name=f"{p1['name']} の手札", value=hand_str(p1["hand"]), inline=False)
            embed.add_field(name=f"🎮 {p2['name']} の番（{v2}）", value=hand_str(p2["hand"]), inline=False)

    embed.add_field(name="ポット", value=f"{room['pot']:,} ナトコイン", inline=True)
    return embed


def build_pvp_public_embed(room: dict) -> discord.Embed:
    """対人戦の共有メッセージ（手札は伏せる）。"""
    p1, p2 = room["p1"], room["p2"]
    turn = room["turn"]
    embed = discord.Embed(title="🃏 ブラックジャック 対人戦", color=discord.Color.dark_green())

    def line(p, key):
        n = len(p["hand"])
        mark = "✅ スタンド" if p.get("stood") else ("🎮 行動中" if (key == ("p1" if turn == 1 else "p2")) else "待機")
        return f"🂠 ×{n}（非公開）　{mark}"

    embed.add_field(name=f"{p1['name']}", value=line(p1, "p1"), inline=True)
    embed.add_field(name=f"{p2['name']}", value=line(p2, "p2"), inline=True)
    cur = p1 if turn == 1 else p2
    embed.add_field(name="現在の手番", value=f"🎮 **{cur['name']}**", inline=False)
    embed.add_field(name="ポット", value=f"{room['pot']:,} ナトコイン", inline=True)
    embed.set_footer(text="「自分の手札を見て行動する」を押すと、自分にだけ手札が表示されます")
    return embed


def resolve_pvp(room: dict) -> str:
    """決着処理：残高を精算して結果テキストを返す。"""
    p1, p2 = room["p1"], room["p2"]
    v1, v2 = hand_value(p1["hand"]), hand_value(p2["hand"])
    bust1, bust2 = v1 > 21, v2 > 21
    g = room["guild_id"]
    if bust1 and bust2:
        result = "🤝 両者バスト！引き分け"
        db.update_balance(p1["id"], g, room["pot"] // 2)
        db.update_balance(p2["id"], g, room["pot"] // 2)
    elif bust1:
        result = f"💥 {p1['name']} バスト！{p2['name']} の勝ち！"
        db.update_balance(p2["id"], g, room["pot"])
    elif bust2:
        result = f"💥 {p2['name']} バスト！{p1['name']} の勝ち！"
        db.update_balance(p1["id"], g, room["pot"])
    elif v1 > v2:
        result = f"🎉 {p1['name']} の勝ち！（{v1} vs {v2}）"
        db.update_balance(p1["id"], g, room["pot"])
    elif v2 > v1:
        result = f"🎉 {p2['name']} の勝ち！（{v2} vs {v1}）"
        db.update_balance(p2["id"], g, room["pot"])
    else:
        result = f"🤝 引き分け！（{v1} vs {v2}）"
        db.update_balance(p1["id"], g, room["pot"] // 2)
        db.update_balance(p2["id"], g, room["pot"] // 2)
    return result


class PvPPublicView(discord.ui.View):
    """共有メッセージに置く『手札を見て行動する』ボタン。"""
    def __init__(self, room_id: str):
        super().__init__(timeout=900)
        self.room_id = room_id

    @discord.ui.button(label="🃏 自分の手札を見て行動する", style=discord.ButtonStyle.primary)
    async def view_act(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room or not room.get("p2"):
            await interaction.response.send_message("この対戦は終了しています", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid == room["p1"]["id"]:
            pkey = "p1"
        elif uid == room["p2"]["id"]:
            pkey = "p2"
        else:
            await interaction.response.send_message("あなたはこの対戦の参加者ではありません", ephemeral=True)
            return
        me = room[pkey]
        turn_key = "p1" if room["turn"] == 1 else "p2"
        val = hand_value(me["hand"])
        my_turn = (pkey == turn_key) and (not me.get("stood")) and (val < 21)
        e = discord.Embed(
            title="🃏 あなたの手札",
            description=f"{hand_str(me['hand'])}\n**合計 {val}**",
            color=discord.Color.blurple(),
        )
        e.set_footer(text="この表示はあなたにだけ見えています")
        if my_turn:
            await interaction.response.send_message(
                embed=e, view=PvPPrivateActView(self.room_id, pkey), ephemeral=True)
        else:
            note = "いまは相手の番です。待っててね。" if pkey != turn_key else "あなたの番は終了しています。"
            e.description += f"\n\n{note}"
            await interaction.response.send_message(embed=e, ephemeral=True)


class PvPPrivateActView(discord.ui.View):
    """本人だけに見えるヒット/スタンド/ダブルダウン。"""
    def __init__(self, room_id: str, pkey: str):
        super().__init__(timeout=900)
        self.room_id = room_id
        self.pkey = pkey
        # ダブルダウンは「初手（2枚）かつ追加ベット分の残高がある」ときだけ表示
        room = pvp_rooms.get(room_id)
        allow_dd = False
        if room and room.get(pkey):
            me = room[pkey]
            if len(me["hand"]) == 2 and db.get_balance(me["id"], room["guild_id"]) >= room["bet"]:
                allow_dd = True
        if not allow_dd:
            for item in list(self.children):
                if getattr(item, "custom_id", None) == "bj_dd":
                    self.remove_item(item)

    def _guard(self, interaction):
        room = pvp_rooms.get(self.room_id)
        if not room or not room.get("p2"):
            return None
        me = room[self.pkey]
        if str(interaction.user.id) != me["id"]:
            return None
        turn_key = "p1" if room["turn"] == 1 else "p2"
        if self.pkey != turn_key or me.get("stood"):
            return None
        return room

    async def _refresh_public(self, room):
        msg = room.get("message")
        if msg:
            try:
                await msg.edit(embed=build_pvp_public_embed(room), view=PvPPublicView(self.room_id))
            except Exception:
                pass

    async def _end_my_turn(self, interaction, room):
        """自分の番を終える：相手が未行動ならターン交代、両者済みなら決着。"""
        other = "p2" if self.pkey == "p1" else "p1"
        if not room[other].get("stood") and hand_value(room[other]["hand"]) <= 21:
            room["turn"] = 1 if other == "p1" else 2
            e = discord.Embed(title="🃏 あなたの番は終了",
                              description="相手の番に移ります。結果をお待ちください。",
                              color=discord.Color.greyple())
            await interaction.response.edit_message(embed=e, view=None)
            msg = room.get("message")
            if msg:
                try:
                    mention = f"<@{room[other]['id']}>"
                    await msg.edit(content=f"{mention} の番です！", embed=build_pvp_public_embed(room),
                                   view=PvPPublicView(self.room_id), allowed_mentions=_ping)
                except Exception:
                    pass
        else:
            result = resolve_pvp(room)
            e = discord.Embed(title="🃏 決着しました",
                              description="共有メッセージで結果を確認してください。",
                              color=discord.Color.greyple())
            await interaction.response.edit_message(embed=e, view=None)
            reveal = build_pvp_embed(room, phase_ended=True)
            reveal.add_field(name="🏆 結果", value=result, inline=False)
            msg = room.get("message")
            if msg:
                try:
                    await msg.edit(content="", embed=reveal, view=None)
                except Exception:
                    pass
            pvp_rooms.pop(self.room_id, None)

    @discord.ui.button(label="ヒット", style=discord.ButtonStyle.primary, emoji="👆")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = self._guard(interaction)
        if not room:
            await interaction.response.send_message("いまは行動できません", ephemeral=True)
            return
        me = room[self.pkey]
        me["hand"].append(room["deck"].pop())
        val = hand_value(me["hand"])
        if val >= 21:
            await self._end_my_turn(interaction, room)
        else:
            e = discord.Embed(title="🃏 あなたの手札",
                              description=f"{hand_str(me['hand'])}\n**合計 {val}**",
                              color=discord.Color.blurple())
            e.set_footer(text="この表示はあなたにだけ見えています")
            await interaction.response.edit_message(embed=e, view=self)
            await self._refresh_public(room)

    @discord.ui.button(label="スタンド", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = self._guard(interaction)
        if not room:
            await interaction.response.send_message("いまは行動できません", ephemeral=True)
            return
        room[self.pkey]["stood"] = True
        await self._end_my_turn(interaction, room)

    @discord.ui.button(label="ダブルダウン", style=discord.ButtonStyle.danger, emoji="⚡", custom_id="bj_dd")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = self._guard(interaction)
        if not room:
            await interaction.response.send_message("いまは行動できません", ephemeral=True)
            return
        me = room[self.pkey]
        if len(me["hand"]) != 2:
            await interaction.response.send_message("ダブルダウンは最初の2枚のときだけです", ephemeral=True)
            return
        bal = db.get_balance(me["id"], room["guild_id"])
        if bal < room["bet"]:
            await interaction.response.send_message("ダブルダウンに必要なナトコインが足りません", ephemeral=True)
            return
        # 追加ベットをポットへ → 1枚だけ引いて自動スタンド
        db.update_balance(me["id"], room["guild_id"], -room["bet"])
        room["pot"] += room["bet"]
        me["hand"].append(room["deck"].pop())
        me["stood"] = True
        await self._end_my_turn(interaction, room)


class PvPWaitView(discord.ui.View):
    def __init__(self, room_id: str, host_id: str):
        super().__init__(timeout=900)
        self.room_id = room_id
        self.host_id = host_id

    @discord.ui.button(label="参加して対戦！", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room:
            await interaction.response.send_message("ルームが見つかりません", ephemeral=True)
            return
        uid = str(interaction.user.id)
        if uid == room["p1"]["id"]:
            await interaction.response.send_message("自分自身とは対戦できません", ephemeral=True)
            return

        bal = db.get_balance(uid, room["guild_id"])
        if bal < room["bet"]:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        db.update_balance(uid, room["guild_id"], -room["bet"])
        room["pot"] += room["bet"]

        deck = make_deck()
        random.shuffle(deck)
        room["deck"] = deck
        room["p1"]["hand"] = [deck.pop(), deck.pop()]
        room["p2"] = {
            "id": uid,
            "name": interaction.user.display_name,
            "hand": [deck.pop(), deck.pop()],
            "stood": False
        }
        room["turn"] = 1

        embed = build_pvp_public_embed(room)
        view = PvPPublicView(self.room_id)
        mention = f"<@{room['p1']['id']}>"
        await interaction.response.edit_message(content=f"{mention} の番です！", embed=embed,
                                                view=view, allowed_mentions=_ping)
        room["message"] = interaction.message

    @discord.ui.button(label="◀️ 中止（賭け金返却）", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        room = pvp_rooms.get(self.room_id)
        if not room:
            await interaction.response.send_message("ルームが見つかりません", ephemeral=True)
            return
        if str(interaction.user.id) != self.host_id:
            await interaction.response.send_message("募集者だけが中止できます", ephemeral=True)
            return
        if room.get("p2"):
            await interaction.response.send_message("すでに対戦相手が参加しています", ephemeral=True)
            return
        db.update_balance(self.host_id, room["guild_id"], room["bet"])
        pvp_rooms.pop(self.room_id, None)
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction, str(interaction.user.id))

    async def on_timeout(self):
        pvp_rooms.pop(self.room_id, None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI戦（ディーラーBOT）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BlackjackAIView(discord.ui.View):
    def __init__(self, user_id: str, guild_id: str):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id

    async def update_embed(self, interaction: discord.Interaction, ended=False):
        game = active_games.get(self.user_id)
        if not game:
            return
        p_val = hand_value(game["player"])
        d_val = hand_value(game["dealer"])
        bet = game["bet"]
        embed = discord.Embed(title="🤖 ブラックジャック vs AI", color=discord.Color.dark_green())
        embed.add_field(name=f"あなたの手札（{p_val}）", value=hand_str(game["player"]), inline=False)

        if ended:
            embed.add_field(name=f"ディーラーの手札（{d_val}）", value=hand_str(game["dealer"]), inline=False)
            # 賭け金はゲーム開始時に引き済み → 勝ちはbet*2返却、引き分けはbet返却、負けは0
            if p_val > 21:
                result, refund, color = f"💥 バスト！ -{bet:,} ナトコイン", 0, discord.Color.red()
            elif d_val > 21 or p_val > d_val:
                result, refund, color = f"🎉 勝ち！ +{bet:,} ナトコイン", bet * 2, discord.Color.gold()
            elif p_val == d_val:
                result, refund, color = "🤝 引き分け！ ±0", bet, discord.Color.blue()
            else:
                result, refund, color = f"😢 負け！ -{bet:,} ナトコイン", 0, discord.Color.red()
            embed.color = color
            if refund > 0:
                db.update_balance(self.user_id, self.guild_id, refund)
            new_bal = db.get_balance(self.user_id, self.guild_id)
            embed.add_field(name="結果", value=result, inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            active_games.pop(self.user_id, None)
            net = refund - bet
            end_view = _bj_post_view(self.user_id, self.guild_id, bet, net)
            if net > 0:
                from cogs.bigwin import announce_big_win
                await announce_big_win(interaction, interaction.user, "ブラックジャック",
                                       net, balance=new_bal)
        else:
            embed.add_field(name="ディーラーの手札", value=hand_str(game["dealer"], hide_second=True), inline=False)
            embed.set_footer(text=f"賭け: {bet:,} ナトコイン")
            end_view = self
        await interaction.response.edit_message(embed=embed, view=end_view)

    @discord.ui.button(label="ヒット", style=discord.ButtonStyle.primary, emoji="👆")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_games.get(self.user_id)
        if not game:
            return
        game["player"].append(game["deck"].pop())
        if hand_value(game["player"]) >= 21:
            await self.update_embed(interaction, ended=True)
        else:
            await self.update_embed(interaction)

    @discord.ui.button(label="スタンド", style=discord.ButtonStyle.secondary, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_games.get(self.user_id)
        if not game:
            return
        while hand_value(game["dealer"]) < 17:
            game["dealer"].append(game["deck"].pop())
        await self.update_embed(interaction, ended=True)

    @discord.ui.button(label="ダブルダウン", style=discord.ButtonStyle.danger, emoji="⚡")
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        game = active_games.get(self.user_id)
        if not game:
            return
        bal = db.get_balance(self.user_id, self.guild_id)
        if bal < game["bet"]:
            await interaction.response.send_message("ナトコインが足りません", ephemeral=True)
            return
        db.update_balance(self.user_id, self.guild_id, -game["bet"])
        game["bet"] *= 2
        game["player"].append(game["deck"].pop())
        while hand_value(game["dealer"]) < 17:
            game["dealer"].append(game["deck"].pop())
        await self.update_embed(interaction, ended=True)

    async def on_timeout(self):
        active_games.pop(self.user_id, None)


class BJAgainButton(discord.ui.Button):
    def __init__(self, bet: int, user_id: str, guild_id: str):
        super().__init__(label="もう一回！", style=discord.ButtonStyle.primary, emoji="🃏")
        self.bet = bet
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        bet = self.bet
        uid = self.user_id
        guild_id = self.guild_id
        bal = db.get_balance(uid, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return
        db.update_balance(uid, guild_id, -bet)
        deck = make_deck()
        random.shuffle(deck)
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        active_games[uid] = {"deck": deck, "player": player, "dealer": dealer, "bet": bet}
        p_val = hand_value(player)
        embed = discord.Embed(title="🤖 ブラックジャック vs AI", color=discord.Color.dark_green())
        embed.add_field(name=f"あなたの手札（{p_val}）", value=hand_str(player), inline=False)
        embed.add_field(name="ディーラーの手札", value=hand_str(dealer, hide_second=True), inline=False)
        embed.set_footer(text=f"賭け: {bet:,} ナトコイン")
        view = BlackjackAIView(uid, guild_id)
        if p_val == 21:
            winnings = int(bet * 1.5)
            db.update_balance(uid, guild_id, bet + winnings)
            new_bal = db.get_balance(uid, guild_id)
            embed.color = discord.Color.gold()
            embed.add_field(name="結果", value=f"🃏 ブラックジャック！ +{winnings:,} ナトコイン（1.5倍）", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            active_games.pop(uid, None)
            view = _bj_post_view(uid, guild_id, bet, winnings)
            await interaction.response.edit_message(embed=embed, view=view)
            from cogs.bigwin import announce_big_win
            await announce_big_win(interaction, interaction.user, "ブラックジャック",
                                   winnings, balance=new_bal, detail="🃏 ブラックジャック（1.5倍）")
            return
        await interaction.response.edit_message(embed=embed, view=view)

class BJBackButton(discord.ui.Button):
    def __init__(self, user_id: str):
        super().__init__(label="◀️ カジノへ戻る", style=discord.ButtonStyle.secondary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("あなたのゲームではありません", ephemeral=True)
            return
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction, self.user_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 勝利後のView（ダブルアップ or もう一回）共通
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _bj_again_view(bet, uid, guild_id):
    v = discord.ui.View(timeout=60)
    v.add_item(BJAgainButton(bet, uid, guild_id))
    v.add_item(BJBackButton(uid))
    return v


def _bj_post_view(uid, guild_id, bet, net):
    """net>0ならダブルアップ入口、それ以外は通常のもう一回View。"""
    if net > 0:
        from cogs.doubleup import build_entry_view
        return build_entry_view(uid, guild_id, net, "ブラックジャック",
                                lambda: _bj_again_view(bet, uid, guild_id))
    return _bj_again_view(bet, uid, guild_id)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# モード選択
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class BlackjackModeView(discord.ui.View):
    def __init__(self, bet: int):
        super().__init__(timeout=900)
        self.bet = bet

    @discord.ui.button(label="🤖 AIと対戦", style=discord.ButtonStyle.primary)
    async def vs_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = self.bet
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if user_id in active_games:
            await interaction.response.send_message("❌ すでにゲーム中です", ephemeral=True)
            return

        db.update_balance(user_id, guild_id, -bet)
        deck = make_deck()
        random.shuffle(deck)
        player = [deck.pop(), deck.pop()]
        dealer = [deck.pop(), deck.pop()]
        active_games[user_id] = {"deck": deck, "player": player, "dealer": dealer, "bet": bet}

        p_val = hand_value(player)
        embed = discord.Embed(title="🤖 ブラックジャック vs AI", color=discord.Color.dark_green())
        embed.add_field(name=f"あなたの手札（{p_val}）", value=hand_str(player), inline=False)
        embed.add_field(name="ディーラーの手札", value=hand_str(dealer, hide_second=True), inline=False)
        embed.set_footer(text=f"賭け: {bet:,} ナトコイン | ヒット / スタンド / ダブルダウン")

        view = BlackjackAIView(user_id, guild_id)
        if p_val == 21:
            winnings = int(bet * 1.5)
            db.update_balance(user_id, guild_id, bet + winnings)
            new_bal = db.get_balance(user_id, guild_id)
            embed.color = discord.Color.gold()
            embed.add_field(name="結果", value=f"🃏 ブラックジャック！ +{winnings:,} ナトコイン（1.5倍）", inline=False)
            embed.add_field(name="残高", value=f"{new_bal:,} ナトコイン", inline=False)
            active_games.pop(user_id, None)
            view = _bj_post_view(user_id, guild_id, bet, winnings)
            await interaction.response.edit_message(embed=embed, view=view)
            from cogs.bigwin import announce_big_win
            await announce_big_win(interaction, interaction.user, "ブラックジャック",
                                   winnings, balance=new_bal, detail="🃏 ブラックジャック（1.5倍）")
            return
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="⚔️ 人と対戦", style=discord.ButtonStyle.success)
    async def vs_human(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = self.bet
        uid = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        room_id = f"bj_{uid}"

        db.update_balance(uid, guild_id, -bet)
        pvp_rooms[room_id] = {
            "guild_id": guild_id,
            "bet": bet,
            "pot": bet,
            "deck": [],
            "p1": {"id": uid, "name": interaction.user.display_name, "hand": [], "stood": False},
            "p2": None,
            "turn": 1,
        }

        embed = discord.Embed(
            title="⚔️ ブラックジャック 対人戦",
            description=(
                f"**{interaction.user.display_name}** がブラックジャック対人戦を開始！\n"
                f"賭け金: **{bet:,} ナトコイン**\n\n"
                f"「参加して対戦！」ボタンを押して挑戦しよう！"
            ),
            color=discord.Color.blue()
        )
        view = PvPWaitView(room_id, uid)
        await interaction.response.edit_message(embed=embed, view=view)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @discord.ui.button(label="🔙 カジノへ戻る", style=discord.ButtonStyle.secondary, row=4)
    async def __back_casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.menu import open_casino_menu
        await open_casino_menu(interaction)

class Blackjack(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="ブラックジャック！AIと対戦 or 人と対戦を選べる")
    @app_commands.describe(bet="賭けるナトコイン数（最低10）")
    async def blackjack(self, interaction: discord.Interaction, bet: int):
        if bet < 10:
            await interaction.response.send_message("❌ 最低10ナトコインから", ephemeral=True)
            return
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        bal = db.get_balance(user_id, guild_id)
        if bal < bet:
            await interaction.response.send_message(f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True)
            return

        embed = discord.Embed(
            title="🃏 ブラックジャック",
            description=f"賭け金: **{bet:,} ナトコイン**\n\nモードを選んでください！",
            color=discord.Color.dark_green()
        )
        embed.add_field(name="🤖 AIと対戦", value="ディーラーBOTと1対1。いつでも即プレイ！", inline=True)
        embed.add_field(name="⚔️ 人と対戦", value="サーバーメンバーと対決。誰かが参加するのを待とう！", inline=True)
        await interaction.response.send_message(embed=embed, view=BlackjackModeView(bet))


async def setup(bot):
    await bot.add_cog(Blackjack(bot))
