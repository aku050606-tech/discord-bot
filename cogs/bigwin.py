"""大勝利アナウンス（BOT告知）の共通ヘルパー。

各ゲームの「勝ちが確定した地点」から announce_big_win() を呼ぶだけでよい。
勝ち額が config.BIG_WIN_ANNOUNCE 以上のときだけ、プレイ中のチャンネルに
BOTが祝いの告知メッセージを投稿する（ゲーム本体のembedとは別メッセージ）。

告知に失敗してもゲーム進行には絶対に影響させない（例外は握りつぶす）。
"""
import discord

try:
    from config import BIG_WIN_ANNOUNCE
except Exception:
    BIG_WIN_ANNOUNCE = 10000

try:
    from config import BIG_WIN_ANNOUNCE_CHANNEL_ID
except Exception:
    BIG_WIN_ANNOUNCE_CHANNEL_ID = 0


def _resolve_channel(interaction):
    """告知先チャンネルを決める。固定IDが設定されていればそこ、無ければ
    ゲームを遊んだチャンネルにフォールバックする。"""
    play_channel = getattr(interaction, "channel", None)
    if not BIG_WIN_ANNOUNCE_CHANNEL_ID:
        return play_channel
    ch = None
    client = getattr(interaction, "client", None)
    if client is not None:
        ch = client.get_channel(BIG_WIN_ANNOUNCE_CHANNEL_ID)
    if ch is None:
        guild = getattr(interaction, "guild", None)
        if guild is not None:
            ch = guild.get_channel(BIG_WIN_ANNOUNCE_CHANNEL_ID)
    # 固定チャンネルが見つからなければ、遊んだチャンネルに出す
    return ch or play_channel


async def announce_big_win(interaction, member, game: str, amount: int,
                           balance=None, detail: str | None = None,
                           force: bool = False):
    """勝ち額が閾値以上、または force=True のとき告知チャンネルにBOT告知を出す。

    interaction : discord.Interaction（チャンネル/Bot取得に使う）
    member      : 勝ったユーザー（interaction.user を渡せばよい）
    game        : ゲーム名（例 "スロット" "釣り" "チンチロ"）
    amount      : 今回の勝ち額（ナトコイン）
    balance     : 任意。現在残高を併記する場合に渡す
    detail      : 任意。補足の一行（※ネタバレになる魚名などは入れない）
    force       : Trueなら閾値未満でも必ず告知（例: レジェンドの魚）
    """
    try:
        if amount is None:
            return
        if not force and amount < BIG_WIN_ANNOUNCE:
            return
        channel = _resolve_channel(interaction)
        if channel is None:
            return

        # 額に応じて少し演出を変える（盛り上げ用）
        if amount >= 100000:
            head = "🌟💰 超・大勝利アナウンス 💰🌟"
            flavor = "伝説級の一撃が飛び出した…！！"
        elif amount >= 50000:
            head = "🎊💰 特大勝利アナウンス 💰🎊"
            flavor = "とんでもない大勝ち！！"
        else:
            head = "🎉✨ 大勝利アナウンス ✨🎉"
            flavor = "大きな勝ちが出ました！"

        embed = discord.Embed(
            title=head,
            description=(f"{flavor}\n\n"
                         f"{member.mention} が **{game}** で\n"
                         f"## 💰 +{amount:,} ナトコイン"),
            color=discord.Color.gold(),
        )
        if detail:
            embed.add_field(name="内訳", value=detail, inline=False)
        if balance is not None:
            embed.add_field(name="現在の残高", value=f"{balance:,} ナトコイン", inline=False)
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        embed.set_footer(text="🎉 おめでとうございます！")

        await channel.send(embed=embed)
    except Exception:
        # 告知はおまけ。失敗してもゲームは止めない。
        pass
