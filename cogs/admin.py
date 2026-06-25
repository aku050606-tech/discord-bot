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
    """管理操作を『🛠 管理操作』ログchへ記録（ログ設定で送信先を指定。未設定なら出さない）"""
    try:
        from cogs.logger import resolve_log_channel, jst_now
        ch = await resolve_log_channel(interaction.guild, "admin")
        if ch is None:
            return
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
            "📋 **ログ設定** — カテゴリ別にログchを指定／OFF\n"
            "📣 **アナウンス** — 設定したchへお知らせを投稿"
        ),
        inline=False,
    )
    embed.set_footer(text="残高操作は『🛠 管理操作』ログに記録されます（ログ設定で送信先を指定）")
    return embed


class AdminMenuView(discord.ui.View):
    def __init__(self, admin_id: str):
        super().__init__(timeout=900)
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

    @discord.ui.button(label="📋 ログ設定", style=discord.ButtonStyle.primary, row=2)
    async def log_settings(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.edit_message(
            embed=build_log_config_embed(interaction.guild),
            view=LogConfigView(self.admin_id))

    @discord.ui.button(label="📣 アナウンス", style=discord.ButtonStyle.primary, row=2)
    async def announce(self, interaction, button):
        if not await self._guard(interaction): return
        await interaction.response.send_modal(AnnounceModal(self.admin_id))

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
        super().__init__(timeout=900)
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
        super().__init__(timeout=900)
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ログ設定（カテゴリ別の送信先チャンネル指定 / OFF）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from cogs.logger import LOG_CATEGORIES


def build_log_config_embed(guild: discord.Guild) -> discord.Embed:
    cfg = db.get_all_log_config(str(guild.id))
    lines = []
    for key, name in LOG_CATEGORIES.items():
        cid = cfg.get(key)
        if cid and cid != "OFF":
            ch = guild.get_channel(int(cid))
            state = ch.mention if ch else "⚠️ ch消失"
        else:
            state = "🔕 OFF"
        lines.append(f"**{name}**　{state}")
    embed = discord.Embed(
        title="📋 ログ設定",
        description="カテゴリを選んで、送信先チャンネルを指定できます（デフォルトは全部OFF）。\n\n"
                    + "\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="未設定＝OFF（送らない）。設定したカテゴリだけログが出ます")
    return embed


class LogCategorySelect(discord.ui.Select):
    """編集するログカテゴリを選ぶ。"""
    def __init__(self, admin_id: str):
        self.admin_id = admin_id
        options = [discord.SelectOption(label=name, value=key)
                   for key, name in LOG_CATEGORIES.items()]
        super().__init__(placeholder="設定するカテゴリを選択…", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        category = self.values[0]
        await interaction.response.edit_message(
            embed=_category_edit_embed(interaction.guild, category),
            view=LogCategoryEditView(self.admin_id, category))


class LogConfigView(discord.ui.View):
    def __init__(self, admin_id: str):
        super().__init__(timeout=600)
        self.admin_id = admin_id
        self.add_item(LogCategorySelect(admin_id))

    @discord.ui.button(label="◀ 管理メニューへ", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(
            embed=build_admin_embed(interaction), view=AdminMenuView(self.admin_id))


def _category_edit_embed(guild, category) -> discord.Embed:
    name = LOG_CATEGORIES.get(category, category)
    cid = db.get_log_channel_id(str(guild.id), category)
    if cid and cid != "OFF":
        ch = guild.get_channel(int(cid))
        cur = ch.mention if ch else "⚠️ ch消失"
    else:
        cur = "🔕 OFF"
    return discord.Embed(
        title=f"設定中：{name}",
        description=f"現在： {cur}\n\n下で送信先チャンネルを選ぶか、「🔕 OFF」を押してください。",
        color=discord.Color.blurple(),
    )


class LogChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, admin_id: str, category: str):
        self.admin_id = admin_id
        self.category = category
        super().__init__(placeholder="送信先チャンネルを選択…",
                         channel_types=[discord.ChannelType.text], row=0)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        ch = self.values[0]
        db.set_log_channel(str(interaction.guild.id), self.category, str(ch.id))
        await interaction.response.edit_message(
            embed=build_log_config_embed(interaction.guild),
            view=LogConfigView(self.admin_id))


class LogCategoryEditView(discord.ui.View):
    def __init__(self, admin_id: str, category: str):
        super().__init__(timeout=600)
        self.admin_id = admin_id
        self.category = category
        self.add_item(LogChannelSelect(admin_id, category))

    @discord.ui.button(label="🔕 OFF（送らない）", style=discord.ButtonStyle.danger, row=1)
    async def turn_off(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        db.set_log_channel(str(interaction.guild.id), self.category, "OFF")
        await interaction.response.edit_message(
            embed=build_log_config_embed(interaction.guild),
            view=LogConfigView(self.admin_id))

    @discord.ui.button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(
            embed=build_log_config_embed(interaction.guild),
            view=LogConfigView(self.admin_id))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# アナウンス（設定したアナウンスchへBotが整形投稿）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class AnnounceModal(discord.ui.Modal, title="📣 アナウンス作成"):
    a_title = discord.ui.TextInput(
        label="タイトル（任意）", required=False, max_length=256,
        placeholder="例: メンテナンスのお知らせ")
    a_body = discord.ui.TextInput(
        label="本文", style=discord.TextStyle.paragraph, max_length=2000,
        placeholder="ここに本文を入力…")

    def __init__(self, admin_id: str):
        super().__init__()
        self.admin_id = admin_id

    async def on_submit(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        cid = db.get_log_channel_id(str(interaction.guild.id), "announce")
        if not cid or cid == "OFF":
            await interaction.response.send_message(
                "⚠️ アナウンスの送信先が未設定です。/admin の「📋 ログ設定」→「📣 手動アナウンス送信先」で先にchを設定してください。",
                ephemeral=True)
            return
        ch = interaction.guild.get_channel(int(cid))
        if ch is None:
            await interaction.response.send_message(
                "⚠️ 設定されたアナウンスchが見つかりません。再設定してください。", ephemeral=True)
            return
        # ビルダーへ（任意でリアクションロールを足してから投稿）
        view = AnnounceBuilderView(self.admin_id, str(ch.id),
                                   self.a_title.value, self.a_body.value)
        await interaction.response.send_message(
            embed=view.preview_embed(interaction.guild), view=view, ephemeral=True)


# ── アナウンス・ビルダー（リアクションロールを任意で付けて投稿）──
class AnnounceBuilderView(discord.ui.View):
    def __init__(self, admin_id: str, channel_id: str, title: str, body: str):
        super().__init__(timeout=600)
        self.admin_id = admin_id
        self.channel_id = channel_id
        self.title_text = title
        self.body_text = body
        self.pairs = []  # [{key, role_id, raw}]
        self.add_item(AnnounceRoleSelect(self))

    def _rr_lines(self):
        return "\n".join(f"{p['raw']} → <@&{p['role_id']}>" for p in self.pairs)

    def preview_embed(self, guild) -> discord.Embed:
        e = discord.Embed(title="📣 アナウンス作成（プレビュー）", color=0xC8A24B)
        e.add_field(name="タイトル", value=self.title_text or "（なし）", inline=False)
        body = self.body_text or "（なし）"
        e.add_field(name="本文", value=body[:600], inline=False)
        if self.pairs:
            e.add_field(name="🎭 リアクションロール", value=self._rr_lines(), inline=False)
        else:
            e.add_field(name="🎭 リアクションロール",
                        value="（なし）役職を選び絵文字を割り当てると追加されます。無しでも投稿OK。",
                        inline=False)
        ch = guild.get_channel(int(self.channel_id))
        e.set_footer(text=f"送信先: #{ch.name if ch else '不明'} ／ 「投稿する」で確定")
        return e

    @discord.ui.button(label="📤 投稿する", style=discord.ButtonStyle.success, row=2)
    async def post(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        ch = interaction.guild.get_channel(int(self.channel_id))
        if ch is None:
            await interaction.response.send_message("⚠️ 送信先chが見つかりません。", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"📣 {self.title_text}" if self.title_text else "📣 お知らせ",
            description=self.body_text,
            color=0xC8A24B,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text=f"{interaction.guild.name}")
        if self.pairs:
            embed.add_field(name="🎭 リアクションで役職GET", value=self._rr_lines(), inline=False)
        try:
            msg = await ch.send(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ そのchに投稿する権限がありません。", ephemeral=True)
            return
        # リアクション付与＋DB登録
        ok = 0
        for p in self.pairs:
            try:
                pe = discord.PartialEmoji.from_str(p["raw"])
                await msg.add_reaction(pe)
                db.add_reaction_role(str(interaction.guild.id), str(msg.id),
                                     p["key"], str(p["role_id"]), p["raw"])
                ok += 1
            except Exception:
                pass
        note = f"（リアクションロール {ok} 件設定）" if self.pairs else ""
        await interaction.response.edit_message(
            content=f"✅ {ch.mention} に投稿しました。{note}", embed=None, view=None)

    @discord.ui.button(label="❌ やめる", style=discord.ButtonStyle.secondary, row=2)
    async def cancel(self, interaction, button):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.edit_message(content="キャンセルしました。", embed=None, view=None)


class AnnounceRoleSelect(discord.ui.RoleSelect):
    def __init__(self, builder: "AnnounceBuilderView"):
        self.builder = builder
        super().__init__(placeholder="役職を選ぶ（→次に絵文字を入力）", row=0,
                         min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await deny(interaction); return
        await interaction.response.send_modal(
            AnnounceEmojiModal(self.builder, self.values[0]))


class AnnounceEmojiModal(discord.ui.Modal, title="絵文字を割り当て"):
    emoji_input = discord.ui.TextInput(
        label="この役職に付ける絵文字", placeholder="例: 🔴（カスタム絵文字もOK）", max_length=64)

    def __init__(self, builder: "AnnounceBuilderView", role: discord.Role):
        super().__init__()
        self.builder = builder
        self.role = role

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.emoji_input.value.strip()
        try:
            pe = discord.PartialEmoji.from_str(raw)
            key = str(pe.id) if pe.id else pe.name
        except Exception:
            await interaction.response.send_message("⚠️ 絵文字を認識できませんでした。", ephemeral=True)
            return
        if not key:
            await interaction.response.send_message("⚠️ 絵文字を認識できませんでした。", ephemeral=True)
            return
        # 同じ絵文字・同じ役職の重複を整理
        self.builder.pairs = [p for p in self.builder.pairs
                              if p["key"] != key and p["role_id"] != self.role.id]
        self.builder.pairs.append({"key": key, "role_id": self.role.id, "raw": raw})
        await interaction.response.edit_message(
            embed=self.builder.preview_embed(interaction.guild), view=self.builder)


async def setup(bot):
    await bot.add_cog(Admin(bot))
