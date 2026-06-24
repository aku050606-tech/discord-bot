import discord
from discord.ext import commands
from discord import app_commands
from database import Database
from config import ADMIN_USER_IDS, ADMIN_MAX_AMOUNT

db = Database()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 権限チェック
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def is_admin(user: discord.abc.User) -> bool:
    return str(user.id) in ADMIN_USER_IDS


async def deny(interaction: discord.Interaction):
    """権限なしを伝える（あらゆる入口で使う）"""
    msg = "⛔ このメニューはあなたには使用できません。"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


def parse_amount(raw: str):
    """金額文字列を正の整数にして返す。失敗時は (None, エラー文)"""
    try:
        n = int(raw.replace(",", "").replace("，", "").strip())
    except ValueError:
        return None, "❌ 金額は数字で入力してください"
    if n <= 0:
        return None, "❌ 1以上の金額を入力してください"
    if n > ADMIN_MAX_AMOUNT:
        return None, f"❌ 一度に動かせるのは {ADMIN_MAX_AMOUNT:,} までです"
    return n, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 操作ログ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def write_admin_log(interaction: discord.Interaction, action: str,
                          target_name: str, detail: str):
    """管理操作を bot-log チャンネルへ記録（logger.py の機構を流用）"""
    try:
        from cogs.logger import get_log_channel, jst_now
        ch = await get_log_channel(interaction.guild)
        embed = discord.Embed(title=f"🛠 管理操作: {action}", color=discord.Color.orange())
        embed.add_field(name="実行者", value=f"{interaction.user.mention}", inline=True)
        embed.add_field(name="対象", value=target_name, inline=True)
        embed.add_field(name="内容", value=detail, inline=False)
        embed.set_footer(text=jst_now())
        await ch.send(embed=embed)
    except Exception as e:
        # ログ失敗は本処理を止めない
        print(f"⚠️ 管理操作ログの記録に失敗: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# トップメニュー
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_admin_embed(interaction: discord.Interaction = None) -> discord.Embed:
    embed = discord.Embed(
        title="🛠 管理者メニュー",
        description="操作を選んでください（あなただけに表示されています）",
        color=discord.Color.dark_red(),
    )
    embed.add_field(
        name="できること",
        value=(
            "👤 **残高を見る** — メンバーの所持金を確認\n"
            "➕ **補填** — 指定メンバーに加算\n"
            "➖ **没収** — 指定メンバーから減算（0未満にはならない）\n"
            "🎯 **残高を設定** — ちょうどその額に上書き\n"
            "📢 **全員に配布** — このサーバーの全員に加算\n"
            "🧪 **テスト台** — すぐ GRAVITAS GAME に入れるスロットでAT演出を確認"
        ),
        inline=False,
    )
    embed.set_footer(text="すべての変更は bot-log に記録されます")
    return embed


class AdminMenuView(discord.ui.View):
    def __init__(self, admin_id: str):
        super().__init__(timeout=300)
        self.admin_id = admin_id

    async def _guard(self, interaction) -> bool:
        if not is_admin(interaction.user):
            await deny(interaction)
            return False
        return True

    @discord.ui.button(label="👤 残高を見る", style=discord.ButtonStyle.secondary, row=0)
    async def view_balance(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            embed=_pick_user_embed("👤 残高を見る", "確認したいメンバーを選んでください"),
            view=AdminUserSelectView(self.admin_id, "view"))

    @discord.ui.button(label="➕ 補填", style=discord.ButtonStyle.success, row=0)
    async def add(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            embed=_pick_user_embed("➕ 補填", "加算するメンバーを選んでください"),
            view=AdminUserSelectView(self.admin_id, "add"))

    @discord.ui.button(label="➖ 没収", style=discord.ButtonStyle.danger, row=0)
    async def sub(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            embed=_pick_user_embed("➖ 没収", "減算するメンバーを選んでください"),
            view=AdminUserSelectView(self.admin_id, "sub"))

    @discord.ui.button(label="🎯 残高を設定", style=discord.ButtonStyle.primary, row=1)
    async def setbal(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            embed=_pick_user_embed("🎯 残高を設定", "上書きするメンバーを選んでください"),
            view=AdminUserSelectView(self.admin_id, "set"))

    @discord.ui.button(label="📢 全員に配布", style=discord.ButtonStyle.success, row=1)
    async def distribute(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.send_modal(AdminDistributeModal(self.admin_id))

    @discord.ui.button(label="🧪 テスト台（スロット）", style=discord.ButtonStyle.primary, row=2)
    async def test_slot(self, interaction, button):
        if not await self._guard(interaction): return
        from cogs.slot import start_test_slot
        await start_test_slot(interaction)

    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.secondary, row=3)
    async def close(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            content="メニューを閉じました。", embed=None, view=None)


def _pick_user_embed(title: str, desc: str) -> discord.Embed:
    return discord.Embed(title=title, description=desc, color=discord.Color.dark_red())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# メンバー選択
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AdminUserSelect(discord.ui.UserSelect):
    def __init__(self, admin_id: str, action: str):
        super().__init__(placeholder="メンバーを選択...", min_values=1, max_values=1)
        self.admin_id = admin_id
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        target = self.values[0]
        guild_id = str(interaction.guild.id)

        if self.action == "view":
            bal = db.get_balance(str(target.id), guild_id)
            embed = discord.Embed(title="👤 残高確認", color=discord.Color.gold())
            embed.add_field(name=target.display_name, value=f"**{bal:,} ナトコイン**")
            await interaction.response.edit_message(embed=embed, view=AdminBackView(self.admin_id))
            return

        # add / sub / set は金額入力モーダルへ
        await interaction.response.send_modal(
            AdminAmountModal(self.admin_id, self.action, str(target.id), target.display_name))


class AdminUserSelectView(discord.ui.View):
    def __init__(self, admin_id: str, action: str):
        super().__init__(timeout=120)
        self.admin_id = admin_id
        self.add_item(AdminUserSelect(admin_id, action))

    @discord.ui.button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(
            embed=build_admin_embed(interaction), view=AdminMenuView(self.admin_id))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 金額入力（補填 / 没収 / 設定）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AdminAmountModal(discord.ui.Modal):
    amount_input = discord.ui.TextInput(label="金額（ナトコイン）", placeholder="例: 5000",
                                        min_length=1, max_length=13)

    def __init__(self, admin_id: str, action: str, target_id: str, target_name: str):
        titles = {"add": "➕ 補填する額", "sub": "➖ 没収する額", "set": "🎯 設定する残高"}
        super().__init__(title=titles.get(action, "金額入力"))
        self.admin_id = admin_id
        self.action = action
        self.target_id = target_id
        self.target_name = target_name

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return

        # set は0を許可（リセット用）、add/subは正の数のみ
        raw = self.amount_input.value
        if self.action == "set":
            try:
                amount = int(raw.replace(",", "").replace("，", "").strip())
            except ValueError:
                await interaction.response.send_message("❌ 金額は数字で入力してください", ephemeral=True); return
            if amount < 0:
                await interaction.response.send_message("❌ 0以上で入力してください", ephemeral=True); return
            if amount > ADMIN_MAX_AMOUNT:
                await interaction.response.send_message(f"❌ 上限は {ADMIN_MAX_AMOUNT:,} です", ephemeral=True); return
        else:
            amount, err = parse_amount(raw)
            if err:
                await interaction.response.send_message(err, ephemeral=True); return

        guild_id = str(interaction.guild.id)
        before = db.get_balance(self.target_id, guild_id)

        if self.action == "add":
            db.update_balance(self.target_id, guild_id, amount)
            action_name = "補填"
        elif self.action == "sub":
            after_calc = max(0, before - amount)   # マイナス残高を防ぐ
            db.set_balance(self.target_id, guild_id, after_calc)
            action_name = "没収"
        else:  # set
            db.set_balance(self.target_id, guild_id, amount)
            action_name = "残高設定"

        after = db.get_balance(self.target_id, guild_id)
        detail = f"{before:,} → **{after:,}** ナトコイン"

        embed = discord.Embed(title=f"✅ {action_name} 完了", color=discord.Color.green())
        embed.add_field(name="対象", value=self.target_name, inline=True)
        embed.add_field(name="変更", value=detail, inline=False)
        await interaction.response.edit_message(embed=embed, view=AdminBackView(self.admin_id))

        await write_admin_log(interaction, action_name, self.target_name, detail)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 全員に配布
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AdminDistributeModal(discord.ui.Modal, title="📢 全員に配布する額"):
    amount_input = discord.ui.TextInput(label="配布額（ナトコイン）", placeholder="例: 1000",
                                        min_length=1, max_length=13)

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = admin_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        amount, err = parse_amount(self.amount_input.value)
        if err:
            await interaction.response.send_message(err, ephemeral=True); return

        guild_id = str(interaction.guild.id)
        users = db.get_guild_users(guild_id)
        for uid in users:
            db.update_balance(uid, guild_id, amount)

        detail = f"{len(users)}人 に **+{amount:,}** ナトコイン"
        embed = discord.Embed(title="✅ 全員配布 完了", description=detail, color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=AdminBackView(self.admin_id))

        await write_admin_log(interaction, "全員配布", f"{len(users)}人", f"+{amount:,} ナトコイン")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 戻る
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AdminBackView(discord.ui.View):
    def __init__(self, admin_id: str):
        super().__init__(timeout=120)
        self.admin_id = admin_id

    @discord.ui.button(label="◀ メニューへ戻る", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(
            embed=build_admin_embed(interaction), view=AdminMenuView(self.admin_id))

    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.secondary)
    async def close(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(content="メニューを閉じました。", embed=None, view=None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin", description="管理者メニューを開く（管理者専用）")
    async def admin(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message("⛔ このコマンドは管理者専用です。", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=build_admin_embed(interaction),
            view=AdminMenuView(str(interaction.user.id)),
            ephemeral=True,   # 自分だけに見える
        )


async def setup(bot):
    await bot.add_cog(Admin(bot))
