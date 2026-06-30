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

try:
    from database import Database
    _db = Database()
except Exception:
    _db = None


def _resolve_channel(interaction):
    """告知先チャンネルを決める。優先順位：
    ① ログ設定の『🎣 釣果・大勝利アナウンス』(bigwin) で指定したch
    ② bigwin が 'OFF' なら告知しない（None）
    ③ 未設定なら config.BIG_WIN_ANNOUNCE_CHANNEL_ID（従来の固定ID）
    ④ それも無ければ、遊んだチャンネルにフォールバック
    """
    play_channel = getattr(interaction, "channel", None)
    guild = getattr(interaction, "guild", None)
    client = getattr(interaction, "client", None)

    def _get(cid):
        ch = None
        if client is not None:
            ch = client.get_channel(cid)
        if ch is None and guild is not None:
            ch = guild.get_channel(cid)
        return ch

    # ① / ② ログ設定（DB）
    if _db is not None and guild is not None:
        try:
            cid = _db.get_log_channel_id(str(guild.id), "bigwin")
        except Exception:
            cid = None
        if cid == "OFF":
            return None
        if cid:
            ch = _get(int(cid))
            if ch is not None:
                return ch

    # ③ 従来の固定ID
    if BIG_WIN_ANNOUNCE_CHANNEL_ID:
        ch = _get(BIG_WIN_ANNOUNCE_CHANNEL_ID)
        if ch is not None:
            return ch

    # ④ 遊んだチャンネル
    return play_channel


# ━━━ ゲーム別の告知閾値 ━━━
# 告知を出すのは3種だけ：スロット(3万+)・釣り(5万+)・航海(10万+)。これ以外は告知しない。
_ANNOUNCE_RULES = [
    ("航海",     100000),   # 1回の航海で10万コイン以上持ち帰ったとき
    ("スロット",  30000),   # スロットのAT/一撃が3万コイン超
    ("釣り",      50000),   # 釣り（嵐の宝箱・ヌシ含む）が5万コイン超
    ("宝の地図",  50000),   # 宝の地図の報酬も釣り扱いで5万超
]

def _announce_threshold(game: str):
    """ゲーム名から告知閾値を返す。対象外なら None（＝告知しない）。"""
    g = game or ""
    for key, thr in _ANNOUNCE_RULES:
        if g.startswith(key) or key in g:
            return thr
    return None


async def announce_big_win(interaction, member, game: str, amount: int,
                           balance=None, detail: str | None = None,
                           force: bool = False):
    """大勝利アナウンスは一旦廃止。

    各ゲーム側からこの関数が呼ばれても何もしない。
    呼び出し元を大量に触らず、告知だけ安全に止めるための no-op。
    """
    return
    try:
        if amount is None:
            return
        # 📣 告知対象は高額勝利だけ。通常の勝ちでは静かにする。
        thr = _announce_threshold(game)
        if thr is None:
            return
        if amount < thr:
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
