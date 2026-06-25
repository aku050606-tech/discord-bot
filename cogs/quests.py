import discord
from discord.ext import commands
from discord import app_commands
from database import Database
import quest_tracker as QT

db = Database()


def _bar(p, target, width=10):
    if target <= 0:
        return "█" * width
    filled = int(width * p / target)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def build_quest_embed(uid: str, gid: str) -> discord.Embed:
    status = QT.get_status(uid, gid)
    e = discord.Embed(
        title="📜 デイリークエスト",
        description="毎日 0時（JST）に更新。達成したら「受取」でナトコインGET！",
        color=discord.Color.gold(),
    )
    claimable = 0
    for s in status:
        q = s["q"]
        if s["claimed"]:
            state = "✅ 受取済み"
        elif s["completed"]:
            state = "🎁 **受取可能！**"
            claimable += q["reward"]
        else:
            state = f"`{_bar(s['progress'], q['target'])}` {s['progress']}/{q['target']}"
        e.add_field(
            name=f"{q['emoji']} {q['name']} （+{q['reward']:,}）",
            value=f"{q['desc']}\n{state}",
            inline=False,
        )
    if claimable:
        e.set_footer(text=f"受取可能: 合計 +{claimable:,} ナトコイン")
    else:
        e.set_footer(text="固定2つは毎日同じ／残り3つは毎日変わる")
    return e


class QuestView(discord.ui.View):
    def __init__(self, uid: str):
        super().__init__(timeout=300)
        self.uid = uid

    async def _check(self, interaction) -> bool:
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("あなたのクエストではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🎁 達成分を受取", style=discord.ButtonStyle.success, row=0)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        gid = str(interaction.guild.id)
        total, names = QT.claim_all(self.uid, gid)
        if total <= 0:
            await interaction.response.send_message(
                "受取できるクエストがまだありません！", ephemeral=True)
            return
        bal = db.get_balance(self.uid, gid)
        # 画面を最新化（受取済みに変わる）
        await interaction.response.edit_message(
            embed=build_quest_embed(self.uid, gid), view=self)
        # 受取結果をポップアップで通知
        result = discord.Embed(
            title="🎁 クエスト報酬を受け取った！",
            description="\n".join(names) + f"\n\n**合計 +{total:,} ナトコイン**\n残高: **{bal:,}**",
            color=discord.Color.green(),
        )
        await interaction.followup.send(embed=result, ephemeral=True)


async def open_quests(interaction: discord.Interaction, uid: str = None):
    """メニュー等から開く用。既存メッセージを差し替える。"""
    uid = uid or str(interaction.user.id)
    gid = str(interaction.guild.id)
    embed = build_quest_embed(uid, gid)
    view = QuestView(uid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class Quests(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quest", description="今日のデイリークエストを確認する")
    async def quest(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await interaction.response.send_message(
            embed=build_quest_embed(uid, str(interaction.guild.id)),
            view=QuestView(uid),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Quests(bot))
