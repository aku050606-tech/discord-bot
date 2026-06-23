"""
embed高さ統一ユーティリティ
全ゲームのembedをこの関数でパディングして高さを揃える
基準：フィールド4行 + description1行 = 5行相当
"""
import discord

# 空白文字（Discordで非表示になる幅ゼロスペース）
_BLANK = "\u200b"

def pad_embed(embed: discord.Embed, target_fields: int = 4) -> discord.Embed:
    """
    embedのフィールド数をtarget_fieldsに揃える
    足りない分は空白フィールドで埋める
    """
    current = len(embed.fields)
    for _ in range(max(0, target_fields - current)):
        embed.add_field(name=_BLANK, value=_BLANK, inline=False)
    return embed
