# 🤖 Discord BOT

Claude AI連携・サーバー内通貨・ゲーム・占い機能付きの多機能Discordボット

---

## 📦 ファイル構成

```
discord-bot/
├── bot.py              # メインファイル
├── database.py         # SQLiteデータベース管理
├── requirements.txt    # 依存パッケージ
├── railway.toml        # Railwayデプロイ設定
└── cogs/
    ├── ai_chat.py      # Claude AI会話
    ├── economy.py      # コイン・経済システム
    ├── games.py        # スロット・コインフリップ
    ├── fortune.py      # 占い・タロット
    └── auto_reply.py   # 自動返信
```

---

## 🚀 Railwayへのデプロイ手順

### 1. GitHubリポジトリを作成
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/あなたのGitHubユーザー名/discord-bot.git
git push -u origin main
```

### 2. Railwayでデプロイ
1. [railway.app](https://railway.app) にログイン
2. 「New Project」→「Deploy from GitHub repo」
3. 上記リポジトリを選択

### 3. 環境変数を設定
Railwayの「Variables」タブで以下を追加:

| 変数名 | 値 |
|--------|-----|
| `DISCORD_TOKEN` | Discordボットのトークン |
| `ANTHROPIC_API_KEY` | AnthropicのAPIキー |

### 4. デプロイ完了！
環境変数を保存すると自動的に再起動・24時間稼働します。

---

## 🎮 コマンド一覧

### 🤖 AI会話
| コマンド | 説明 |
|---------|------|
| `/chat [message]` | Claude AIと会話する |
| `/reset_chat` | 会話履歴をリセット |

### 💰 経済システム
| コマンド | 説明 |
|---------|------|
| `/balance` | 所持コインを確認 |
| `/daily` | 毎日500コインのボーナス |
| `/send_coin [ユーザー] [枚数]` | コインを送る |
| `/ranking` | コインランキング表示 |

### 🎰 ゲーム
| コマンド | 説明 |
|---------|------|
| `/slot [bet]` | スロットマシン（最低10コイン）|
| `/coinflip [表/裏] [bet]` | コインフリップ |

### 🔮 占い
| コマンド | 説明 |
|---------|------|
| `/fortune` | 今日の運勢（1日固定）|
| `/tarot` | タロットカードを引く |

### 💬 自動返信キーワード
「おはよう」「おやすみ」「ありがとう」「こんにちは」「こんばんは」「疲れた」「ヒマ」「にゃ」

---

## ⚙️ ローカルでのテスト
```bash
pip install -r requirements.txt
export DISCORD_TOKEN="あなたのトークン"
export ANTHROPIC_API_KEY="あなたのAPIキー"
python bot.py
```
