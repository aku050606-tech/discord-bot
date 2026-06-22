import discord
from discord.ext import commands
from discord import app_commands
import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# 会話履歴（メモリ内・再起動でリセット）
conversation_history: dict[str, list] = {}

class AIChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="chat", description="Claude AIと会話する")
    @app_commands.describe(message="Claudeへのメッセージ")
    async def chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()

        user_id = str(interaction.user.id)
        if user_id not in conversation_history:
            conversation_history[user_id] = []

        # 履歴に追加（最大20件）
        conversation_history[user_id].append({"role": "user", "content": message})
        if len(conversation_history[user_id]) > 20:
            conversation_history[user_id] = conversation_history[user_id][-20:]

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=(
                    "あなたはDiscordサーバーの陽気なアシスタントBOTです。"
                    "フレンドリーで親切に、絵文字を適度に使って返答してください。"
                    "長すぎず、Discordで読みやすい形式にしてください。"
                ),
                messages=conversation_history[user_id]
            )
            reply = response.content[0].text

            # 履歴にアシスタント返答を追加
            conversation_history[user_id].append({"role": "assistant", "content": reply})

            embed = discord.Embed(
                description=reply,
                color=discord.Color.blurple()
            )
            embed.set_author(name="Claude AI", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text=f"💬 {interaction.user.display_name}への返答")
            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {e}")

    @app_commands.command(name="reset_chat", description="AIとの会話履歴をリセットする")
    async def reset_chat(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        conversation_history.pop(user_id, None)
        await interaction.response.send_message("🔄 会話履歴をリセットしました！", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AIChat(bot))
