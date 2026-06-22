import discord
from discord.ext import commands
import random

# キーワード → 返答リスト（ランダムで返す）
AUTO_REPLIES = {
    "おはよう": ["おはようございます！☀️ 今日も一日頑張ろう！", "おはよう！✨ 良い一日を！", "おはようございます🌅"],
    "おやすみ": ["おやすみなさい🌙 ゆっくり休んでね", "おやすみ～💤", "おやすみなさい！良い夢を✨"],
    "ありがとう": ["どういたしまして！😊", "いえいえ～！", "役に立てて嬉しいです！✨"],
    "こんにちは": ["こんにちは！😄", "こんにちは～！元気？", "やあ！こんにちは！"],
    "こんばんは": ["こんばんは！🌙", "こんばんは～！今日はどうだった？", "こんばんは！✨"],
    "疲れた": ["お疲れ様！ゆっくり休んでね💪", "おつかれ～！今日も頑張ったね！", "お疲れさまでした！💙"],
    "ヒマ": ["じゃあ /fortune で運勢を見てみよう！🔮", "/slot でスロットを試してみない？🎰", "チャットでもしようよ！/chat で話しかけて✨"],
    "にゃ": ["にゃーん🐱", "ニャン！", "🐾 にゃ！"],
}

class AutoReply(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        content = message.content.lower()

        for keyword, replies in AUTO_REPLIES.items():
            if keyword in content:
                reply = random.choice(replies)
                await message.reply(reply, mention_author=False)
                return  # 1回だけ返信

        # BOTがメンションされたとき
        if self.bot.user in message.mentions:
            responses = [
                "呼んだ？😊 `/chat` で話しかけてみてね！",
                "なんですか～？✨ `/help` でコマンド一覧が見れるよ！",
                "はーい！🙋 何かお手伝いできることある？",
            ]
            await message.reply(random.choice(responses), mention_author=False)

async def setup(bot):
    await bot.add_cog(AutoReply(bot))
