"""⚓ さびれた港 ＆ 解放ファンド（コミュニティ募金）。
未解放：伝説の釣り人が事情を（ぼかして）語り、支援を募る。累積・進捗・貢献者を可視化。
解放後：港が再興し、危険水域（遠征）と総合ショップへのメニューになる。
"""
import discord
from discord.ext import commands
from database import Database
from config import FUND_GOALS, ADMIN_USER_IDS
import voyage_config as V

db = Database()
DEFAULT_GOAL = "danger_zone"


def _has_port_access(guild, user, goal_key):
    """解放済み or admin（テストプレイ用の早期入場）なら港に入れる。"""
    if db.is_fund_unlocked(str(guild.id), goal_key):
        return True
    return str(user.id) in ADMIN_USER_IDS

# 伝説の釣り人（未解放時。海の名はぼかす）
LEGEND_FISHER_LINES = (
    "……おう、よく来たな、若いの。\n"
    "だが見ての通り、この港はすっかり寂れちまった。\n\n"
    "昔はここから、人の住まう海の遥か先――\n"
    "**凍てつく地獄** と **燃え盛る地獄**へ、遠洋に出られたもんだ。\n"
    "そりゃあ恐ろしい海よ……名を口にするのも憚られる。\n\n"
    "……すまん。今はその **資金も、道具も**、何もかも失っちまった。\n"
    "このままじゃ、お前さんを送り出してやることもできん。\n\n"
    "だが――みんなで力を合わせて資金を集めてくれるなら。\n"
    "この港、もう一度よみがえらせてみせる。……約束しよう。"
)


def _bar(cur, goal, width=12):
    ratio = min(cur / goal, 1.0) if goal > 0 else 0.0
    filled = int(round(width * ratio))
    return "🟦" * filled + "⬜" * (width - filled)


def _add_progress_fields(embed, guild, user, goal_key):
    g = FUND_GOALS[goal_key]; gid = str(guild.id)
    total, _ = db.get_fund(gid, goal_key); goal = g["goal"]
    pct = min(total / goal * 100, 100) if goal else 100
    embed.add_field(
        name=f"進捗　{pct:.1f}%",
        value=f"{_bar(total, goal)}\n**{total:,}** / {goal:,} ナトコイン"
              f"（あと **{max(goal - total, 0):,}**）",
        inline=False)
    contributors = db.get_fund_contributors(gid, goal_key, limit=10)
    if contributors:
        medals = ["🥇", "🥈", "🥉"]; lines = []
        for i, (uid, amt) in enumerate(contributors):
            m = guild.get_member(int(uid))
            name = m.display_name if m else "退出したメンバー"
            rank = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{rank} {name} … **{amt:,}**")
        embed.add_field(name="🏆 貢献ランキング", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="🏆 貢献ランキング",
                        value="まだ誰も支援していません。最初の出資者になろう！", inline=False)
    mine = db.get_user_fund_contribution(gid, goal_key, str(user.id))
    embed.add_field(name="あなたの貢献", value=f"💰 {mine:,} ナトコイン", inline=False)


def build_locked_port_embed(guild, user, goal_key=DEFAULT_GOAL):
    embed = discord.Embed(
        title="🎣 伝説の釣り人 ── さびれた港",
        description=LEGEND_FISHER_LINES, color=0x5d6d7e)
    _add_progress_fields(embed, guild, user, goal_key)
    embed.set_footer(text="⚓ さびれた港（閉鎖中）｜支援したナトコインは戻りません")
    return embed


def build_port_hub_embed(guild, goal_key=DEFAULT_GOAL):
    # ⚓ 再興ハブは廃止（解放済みは open_port → open_voyage で母港へ直行）。互換のため最小限残置。
    total, _ = db.get_fund(str(guild.id), goal_key)
    return discord.Embed(title="⚓ さびれた港", description="母港へ。", color=0x16a085)


# ── 未解放：支援するボタンのみ ──
class LockedPortView(discord.ui.View):
    def __init__(self, user_id, goal_key=DEFAULT_GOAL):
        super().__init__(timeout=900)
        self.user_id = str(user_id)
        self.goal_key = goal_key

    @discord.ui.button(label="💰 支援する", style=discord.ButtonStyle.success)
    async def contribute(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return
        if db.is_fund_unlocked(str(interaction.guild.id), self.goal_key):
            await interaction.response.send_message("✅ もう解放ずみです！", ephemeral=True)
            return
        await interaction.response.send_modal(ContributeModal(self.user_id, self.goal_key))

    @discord.ui.button(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return
        from cogs.menu import go_town
        await go_town(interaction, self.user_id)


# ── 解放後：港ハブ（危険水域 / ショップ）──
class PortHubView(discord.ui.View):
    def __init__(self, user_id, goal_key=DEFAULT_GOAL):
        super().__init__(timeout=900)
        self.user_id = str(user_id)
        self.goal_key = goal_key

    @discord.ui.button(label="🌊 危険水域（航海）", style=discord.ButtonStyle.danger, row=0)
    async def waters(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return
        from cogs.voyage import open_voyage
        await open_voyage(interaction, self.user_id)

    @discord.ui.button(label="🏪 総合ショップ", style=discord.ButtonStyle.success, row=0)
    async def shop(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return
        from cogs.voyage import open_voyage
        await open_voyage(interaction, self.user_id)

    @discord.ui.button(label="🚪 立ち去る", style=discord.ButtonStyle.secondary, row=1)
    async def leave(self, interaction, button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return
        await interaction.response.edit_message(content="港を後にした。", embed=None, view=None)



def _grant_port_pet(user_id: str, pet_id: str):
    """港復興トップ支援者へのペット付与。重複付与防止フラグも保存。"""
    vp = db.get_voyage(user_id)
    if vp.get("port_revival_pet_claimed"):
        return False, vp
    vp.setdefault("special_items", []).append(pet_id)
    vp["port_revival_pet_claimed"] = True
    db.add_zukan(user_id, "item_seen", pet_id)
    db.save_voyage(user_id, vp)
    return True, vp


class PortRevivalPetSelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        opts = [
            discord.SelectOption(label=V.PETS["pet_dog"]["name"], value="pet_dog", emoji=V.PETS["pet_dog"]["emoji"], description="港復興記念・オーグからの贈り物"),
            discord.SelectOption(label=V.PETS["pet_cat"]["name"], value="pet_cat", emoji=V.PETS["pet_cat"]["emoji"], description="港復興記念・オーグからの贈り物"),
        ]
        super().__init__(placeholder="🐾 オーグからの贈り物を選ぶ", min_values=1, max_values=1, options=opts)

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これは港復興の最大支援者への贈り物です。", ephemeral=True)
            return
        pet_id = self.values[0]
        ok, vp = _grant_port_pet(self.uid, pet_id)
        if not ok:
            await interaction.response.send_message("もう港復興記念の贈り物は受け取り済みです。", ephemeral=True)
            return
        pet = V.PETS[pet_id]
        e = discord.Embed(
            title="🎁 オーグからの贈り物",
            description=(
                "「……港が、戻ってきたな。」\n\n"
                "オーグは照れくさそうに鼻をかき、木箱の中から小さな相棒をそっと抱き上げた。\n\n"
                f"**{pet['emoji']} {pet['name']}** が、あなたの仲間になった。\n\n"
                "「一番この港に賭けてくれたやつに、俺からの礼だ。\n"
                "大事にしてやってくれ。……こいつも、きっとお前を気に入る。」"
            ),
            color=discord.Color.gold()
        )
        await interaction.response.edit_message(embed=e, view=None)


class PortRevivalPetGiftView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.add_item(PortRevivalPetSelect(uid, gid))


class ContributeModal(discord.ui.Modal):
    def __init__(self, user_id, goal_key):
        g = FUND_GOALS[goal_key]
        super().__init__(title=f"{g['emoji']} さびれた港に支援")
        self.user_id = user_id
        self.goal_key = goal_key
        self.amount = discord.ui.TextInput(
            label="支援するナトコイン", placeholder="例: 5000",
            required=True, max_length=12)
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id); gid = str(interaction.guild.id)
        raw = str(self.amount.value).replace(",", "").replace("，", "").strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ 数字で入力してください", ephemeral=True); return
        amt = int(raw)
        if amt <= 0:
            await interaction.response.send_message("❌ 1以上を入力してください", ephemeral=True); return
        bal = db.get_balance(uid, gid)
        if bal < amt:
            await interaction.response.send_message(
                f"❌ ナトコインが足りません（残高: {bal:,}）", ephemeral=True); return

        g = FUND_GOALS[self.goal_key]; goal = g["goal"]
        already = db.is_fund_unlocked(gid, self.goal_key)
        db.update_balance(uid, gid, -amt)
        new_total = db.add_fund_contribution(gid, self.goal_key, uid, amt)
        just_unlocked = (not already) and new_total >= goal
        if just_unlocked:
            db.set_fund_unlocked(gid, self.goal_key)

        if just_unlocked:
            done = discord.Embed(
                title="🎉 さびれた港 ── 再興！",
                description=("みんなの支援で港がよみがえった！\n"
                             "もう一度 **⚓ さびれた港** を開けば、母港から航海に出られる。"),
                color=discord.Color.gold())
            await interaction.response.edit_message(embed=done, view=None)
        else:
            embed = build_locked_port_embed(interaction.guild, interaction.user, self.goal_key)
            await interaction.response.edit_message(embed=embed, view=LockedPortView(uid, self.goal_key))
        await interaction.followup.send(
            f"💰 **{amt:,} ナトコイン** を港に投じた！ありがとう、相棒。", ephemeral=True)

        if just_unlocked:
            try:
                ann = discord.Embed(
                    title=g.get("unlock_title", "🎉 解放！"),
                    description=g.get("unlock_msg", ""), color=discord.Color.gold())
                ann.add_field(name="達成額", value=f"**{new_total:,}** ナトコイン", inline=True)
                ann.set_footer(text="支援してくれた全員に感謝を！")
                await interaction.channel.send(embed=ann)

                top = db.get_fund_contributors(gid, self.goal_key, limit=1)
                if top:
                    top_uid, top_amt = top[0]
                    m = interaction.guild.get_member(int(top_uid))
                    top_name = m.mention if m else f"<@{top_uid}>"
                    gift = discord.Embed(
                        title="🐾 港復興記念 ── オーグからの贈り物",
                        description=(
                            "波止場に、久しぶりの灯りがともった。\n\n"
                            "オーグが、少しだけ笑う。\n\n"
                            "「一番この港に金を入れてくれたやつに、俺から礼がある。\n"
                            "犬か猫、好きな方を選べ。こいつらも港の復興を見届けた仲間だ。」\n\n"
                            f"最大支援者：{top_name}\n"
                            f"支援額：**{top_amt:,}** ナトコイン"
                        ),
                        color=discord.Color.gold()
                    )
                    await interaction.channel.send(embed=gift, view=PortRevivalPetGiftView(top_uid, gid))
            except Exception:
                pass


async def open_port(interaction: discord.Interaction, user_id: str = None, goal_key=DEFAULT_GOAL):
    """さびれた港を開く。メニューと同じメッセージを編集して表示（別メッセージにしない）。
    解放済みは母港（航海中なら航海画面）へ直行。未解放は支援ページ。"""
    uid = user_id or str(interaction.user.id)
    gid = str(interaction.guild.id)
    if _has_port_access(interaction.guild, interaction.user, goal_key):
        from cogs.voyage import build_port_embed, build_voyage_embed, PortView, VoyageView
        vp = db.get_voyage(uid)
        if vp.get("voyage"):
            embed = build_voyage_embed(vp, "⛵ 航海の続きだ。"); view = VoyageView(uid, gid)
        else:
            embed = build_port_embed(vp); view = PortView(uid, gid)
    else:
        embed = build_locked_port_embed(interaction.guild, interaction.user, goal_key)
        view = LockedPortView(uid, goal_key)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.edit_message(embed=embed, view=view)


class Fund(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(Fund(bot))
