"""共通ダブルアップ（対コンピューター・ハイ＆ロー）。
- 勝った『勝ち分(net)』だけを賭ける。外しても元の賭け金は戻る（マイルド方式）。
- 「自分のカード」がコンピューターのカードより高い/低いかを当てる。
  ⬆️高い/⬇️ローを先に宣言 → 両者のカードを同時にめくって勝負（引き分けは負け）。
  ※コンピューターのカードを見てから選べると必ず有利な方を選べてしまい勝率72%＝経済破壊になるため、
    宣言してからめくる方式にして勝率6/13≒46%（フェアな2倍配当）を保つ。
- チェーンは最大5連。各回「確定」できる。対人戦には付けない。
勝ち分(net)は呼び出し時点で既に残高に反映済みである前提。
"""
import discord
import random

try:
    from config import BIG_WIN_ANNOUNCE
except Exception:
    BIG_WIN_ANNOUNCE = 10000

MAX_CHAIN = 5
SUITS = ["♠️", "♥️", "♦️", "♣️"]
RANK_NAME = {1: "A", 11: "J", 12: "Q", 13: "K"}


def _rank_name(r: int) -> str:
    return RANK_NAME.get(r, str(r))


def draw_card():
    return random.randint(1, 13), random.choice(SUITS)


def card_str(r: int, s: str) -> str:
    return f"{s}{_rank_name(r)}"


async def _check(interaction, user_id) -> bool:
    if str(interaction.user.id) != user_id:
        await interaction.response.send_message("❌ あなたのゲームではありません", ephemeral=True)
        return False
    return True


def build_entry_view(user_id, guild_id, net, title, again_factory):
    """勝利画面に添える：ダブルアップ or 確定。netは現在の勝ち分(>0)。"""
    return DoubleUpEntryView(user_id, guild_id, net, title, again_factory, chain=0)


def _done_embed(title, desc, color, balance):
    e = discord.Embed(title=f"⏫ {title} — ダブルアップ", description=desc, color=color)
    e.add_field(name="残高", value=f"{balance:,} ナトコイン", inline=False)
    return e


class DoubleUpEntryView(discord.ui.View):
    def __init__(self, user_id, guild_id, stake, title, again_factory, chain=0):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id
        self.stake = stake          # いま賭けられる勝ち分（残高に反映済み）
        self.title = title
        self.again_factory = again_factory
        self.chain = chain          # 成功した連鎖回数

    @discord.ui.button(label="⏫ ダブルアップ", style=discord.ButtonStyle.danger)
    async def doubleup(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        e = discord.Embed(
            title=f"🎴 {self.title} — ダブルアップ（{self.chain + 1}/{MAX_CHAIN}連）",
            description=(f"コンピューターと1枚ずつ勝負！\n"
                        f"**あなたのカードはコンピューターより高い？低い？**\n"
                        f"先に宣言して、同時にめくります（同じ数字は負け）。\n\n"
                        f"賭け中の勝ち分: **{self.stake:,} ナトコイン**\n"
                        f"当たれば **{self.stake * 2:,}** に倍増、外すと勝ち分を失う（元の賭け金は戻る）"),
            color=discord.Color.dark_gold(),
        )
        await interaction.response.edit_message(
            embed=e, view=DoubleUpChoiceView(self.user_id, self.guild_id, self.stake,
                                             self.title, self.again_factory, self.chain))

    @discord.ui.button(label="✅ 確定する", style=discord.ButtonStyle.success)
    async def cashout(self, interaction, button):
        if not await _check(interaction, self.user_id): return
        from database import Database
        bal = Database().get_balance(self.user_id, self.guild_id)
        e = _done_embed(self.title, f"💰 **{self.stake:,} ナトコイン** を確定しました！", discord.Color.green(), bal)
        await interaction.response.edit_message(embed=e, view=self.again_factory())


class DoubleUpChoiceView(discord.ui.View):
    def __init__(self, user_id, guild_id, stake, title, again_factory, chain):
        super().__init__(timeout=900)
        self.user_id = user_id
        self.guild_id = guild_id
        self.stake = stake
        self.title = title
        self.again_factory = again_factory
        self.chain = chain

    async def _resolve(self, interaction, pick):
        if not await _check(interaction, self.user_id): return
        from database import Database
        db = Database()
        cr, cs = draw_card()   # コンピューターのカード
        pr, ps = draw_card()   # あなたのカード
        if pr == cr:
            win = False        # 同じ数字は負け
        elif pick == "high":
            win = pr > cr
        else:
            win = pr < cr

        comp = card_str(cr, cs)
        mine = card_str(pr, ps)
        pick_label = "⬆️高い" if pick == "high" else "⬇️低い"
        cards_line = f"🤖 コンピューター: **{comp}**\n🙋 あなた: **{mine}**（宣言: {pick_label}）"

        if win:
            db.update_balance(self.user_id, self.guild_id, self.stake)  # 勝ち分を倍に
            new_stake = self.stake * 2
            new_chain = self.chain + 1
            bal = db.get_balance(self.user_id, self.guild_id)
            # 勝ち分が初めて閾値を超えた瞬間だけBOT告知（連打スパム防止）
            if self.stake < BIG_WIN_ANNOUNCE <= new_stake:
                from cogs.bigwin import announce_big_win
                await announce_big_win(interaction, interaction.user,
                                       f"{self.title}のダブルアップ",
                                       new_stake, balance=bal,
                                       detail=f"{new_chain}連目で大勝ち！")
            if new_chain >= MAX_CHAIN:
                e = _done_embed(self.title,
                                f"{cards_line}\n→ ✅ **当たり！**\n"
                                f"🏆 {MAX_CHAIN}連達成！ **{new_stake:,} ナトコイン** を確定！",
                                discord.Color.gold(), bal)
                await interaction.response.edit_message(embed=e, view=self.again_factory())
            else:
                e = discord.Embed(
                    title=f"🎴 {self.title} — ダブルアップ成功（{new_chain}/{MAX_CHAIN}連）",
                    description=(f"{cards_line}\n→ ✅ **当たり！**\n"
                                f"勝ち分が **{new_stake:,} ナトコイン** に倍増！\n\n"
                                f"さらに挑戦する？ それとも確定する？"),
                    color=discord.Color.gold(),
                )
                e.add_field(name="残高", value=f"{bal:,} ナトコイン", inline=False)
                await interaction.response.edit_message(
                    embed=e, view=DoubleUpEntryView(self.user_id, self.guild_id, new_stake,
                                                    self.title, self.again_factory, new_chain))
        else:
            db.update_balance(self.user_id, self.guild_id, -self.stake)  # 勝ち分没収
            bal = db.get_balance(self.user_id, self.guild_id)
            reason = "同じ数字…！" if pr == cr else "外れ…！"
            e = _done_embed(self.title,
                            f"{cards_line}\n→ 💀 **ハズレ（{reason}）**\n"
                            f"勝ち分 **{self.stake:,} ナトコイン** を失った…（元の賭け金は戻っています）",
                            discord.Color.red(), bal)
            await interaction.response.edit_message(embed=e, view=self.again_factory())

    @discord.ui.button(label="⬆️ 高い", style=discord.ButtonStyle.primary)
    async def high(self, interaction, button):
        await self._resolve(interaction, "high")

    @discord.ui.button(label="⬇️ 低い", style=discord.ButtonStyle.primary)
    async def low(self, interaction, button):
        await self._resolve(interaction, "low")
