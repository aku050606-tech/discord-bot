import os
import sqlite3
import json

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 保存先パス
#   Railwayで永続ボリュームをマウントすると RAILWAY_VOLUME_MOUNT_PATH が
#   自動でセットされる（例: /data）。そこに bot_data.db を置くことで
#   再デプロイ・再起動してもデータが残る。
#   ローカル実行時は環境変数が無いのでカレントに bot_data.db を作る。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DB_DIR = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", ".")
DB_PATH = os.path.join(DB_DIR, "bot_data.db")

# スタート所持金（新規ユーザーの初期残高）
STARTING_BALANCE = 3000


class Database:
    def __init__(self):
        self.path = DB_PATH

    def get_conn(self):
        return sqlite3.connect(self.path)

    def initialize(self):
        # 保存先ディレクトリが無ければ作る（ボリューム未マウント時の保険）
        os.makedirs(DB_DIR, exist_ok=True)

        conn = self.get_conn()
        c = conn.cursor()
        # economy は (user_id, guild_id) を主キーにして、サーバーごとに残高を分離する
        c.execute("""CREATE TABLE IF NOT EXISTS economy (
            user_id TEXT, guild_id TEXT,
            balance INTEGER DEFAULT {start}, total_earned INTEGER DEFAULT 0,
            last_daily TEXT,
            PRIMARY KEY (user_id, guild_id)
        )""".format(start=STARTING_BALANCE))
        c.execute("""CREATE TABLE IF NOT EXISTS send_log (
            user_id TEXT, guild_id TEXT, amount INTEGER,
            sent_date TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS info_dealer (
            user_id TEXT, guild_id TEXT, dealer TEXT, used_date TEXT,
            PRIMARY KEY (user_id, guild_id, dealer)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS zukan (
            user_id TEXT, area TEXT, fish_name TEXT,
            caught_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, area, fish_name)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS zukan_crown (
            user_id TEXT, area TEXT, fish_name TEXT,
            PRIMARY KEY (user_id, area, fish_name)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS zukan_bonus (
            user_id TEXT, bonus_type TEXT,
            PRIMARY KEY (user_id, bonus_type)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS vc_tracking (
            user_id TEXT, guild_id TEXT, joined_at TEXT,
            PRIMARY KEY (user_id, guild_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS fishing_gear (
            user_id TEXT PRIMARY KEY,
            rod_id TEXT DEFAULT 'bamboo',
            rod_uses INTEGER DEFAULT 999999,
            reel_id TEXT DEFAULT 'spinning',
            reel_uses INTEGER DEFAULT 999999,
            line_id TEXT DEFAULT 'nylon',
            line_uses INTEGER DEFAULT 999999,
            rod_inventory TEXT DEFAULT '{}',
            reel_inventory TEXT DEFAULT '{}',
            line_inventory TEXT DEFAULT '{}'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS player_state (
            user_id TEXT PRIMARY KEY,
            treasure_maps INTEGER DEFAULT 0,
            last_area TEXT DEFAULT 'lake'
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS chinchiro_ban (
            user_id TEXT, guild_id TEXT, ban_date TEXT,
            PRIMARY KEY (user_id, guild_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS quest_progress (
            user_id TEXT, guild_id TEXT, quest_date TEXT, quest_key TEXT,
            progress INTEGER DEFAULT 0, claimed INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id, quest_date, quest_key)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS log_config (
            guild_id TEXT, category TEXT, channel_id TEXT,
            PRIMARY KEY (guild_id, category)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id TEXT, message_id TEXT, emoji_key TEXT,
            role_id TEXT, emoji_display TEXT,
            PRIMARY KEY (message_id, emoji_key)
        )""")
        conn.commit()
        conn.close()
        print(f"✅ データベース初期化完了（保存先: {self.path}）")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 残高（サーバーごとに分離）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_balance(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT balance FROM economy WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        row = c.fetchone()
        if row is None:
            c.execute(
                "INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
                (user_id, guild_id, STARTING_BALANCE),
            )
            conn.commit()
            conn.close()
            return STARTING_BALANCE
        conn.close()
        return row[0]

    def update_balance(self, user_id, guild_id, amount):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "UPDATE economy SET balance = balance + ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id),
        )
        if c.rowcount == 0:
            c.execute(
                "INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
                (user_id, guild_id, STARTING_BALANCE + amount),
            )
        conn.commit()
        conn.close()

    def set_balance(self, user_id, guild_id, amount):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "UPDATE economy SET balance = ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id),
        )
        if c.rowcount == 0:
            c.execute(
                "INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)",
                (user_id, guild_id, amount),
            )
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # チンチロ 本日出禁（払えず追い出された人。日付が変われば自動解除）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def ban_chinchiro_today(self, user_id, guild_id, today):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "UPDATE chinchiro_ban SET ban_date = ? WHERE user_id = ? AND guild_id = ?",
            (today, user_id, guild_id),
        )
        if c.rowcount == 0:
            c.execute(
                "INSERT INTO chinchiro_ban (user_id, guild_id, ban_date) VALUES (?, ?, ?)",
                (user_id, guild_id, today),
            )
        conn.commit()
        conn.close()

    def is_chinchiro_banned(self, user_id, guild_id, today):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT ban_date FROM chinchiro_ban WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = c.fetchone()
        conn.close()
        return bool(row and row[0] == today)

    def get_ranking(self, guild_id, limit=10):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT user_id, balance FROM economy WHERE guild_id = ? ORDER BY balance DESC LIMIT ?",
            (guild_id, limit),
        )
        rows = c.fetchall()
        conn.close()
        return rows

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # デイリー（サーバーごと）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_last_daily(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT last_daily FROM economy WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_last_daily(self, user_id, guild_id, date_str):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "UPDATE economy SET last_daily = ? WHERE user_id = ? AND guild_id = ?",
            (date_str, user_id, guild_id),
        )
        if c.rowcount == 0:
            c.execute(
                "INSERT INTO economy (user_id, guild_id, balance, last_daily) VALUES (?, ?, ?, ?)",
                (user_id, guild_id, STARTING_BALANCE, date_str),
            )
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 送金ログ（1日の送金上限の判定に使う）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def add_send_log(self, user_id, guild_id, amount):
        from datetime import date
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO send_log (user_id, guild_id, amount, sent_date) VALUES (?, ?, ?, ?)",
            (user_id, guild_id, amount, str(date.today())),
        )
        conn.commit()
        conn.close()

    def get_today_sent(self, user_id, guild_id):
        from datetime import date
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM send_log WHERE user_id = ? AND guild_id = ? AND sent_date = ?",
            (user_id, guild_id, str(date.today())),
        )
        total = c.fetchone()[0]
        conn.close()
        return total or 0

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 情報屋（1日1回の利用管理）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_info_used_date(self, user_id, guild_id, dealer):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT used_date FROM info_dealer WHERE user_id=? AND guild_id=? AND dealer=?",
                  (user_id, guild_id, dealer))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_info_used_date(self, user_id, guild_id, dealer, date_str):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO info_dealer (user_id, guild_id, dealer, used_date) VALUES (?, ?, ?, ?)",
                  (user_id, guild_id, dealer, date_str))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 図鑑
    def get_treasure_maps(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT treasure_maps FROM player_state WHERE user_id = ?", (user_id,))
        row = c.fetchone(); conn.close()
        return row[0] if row else 0

    def add_treasure_map(self, user_id, n=1):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("""INSERT INTO player_state (user_id, treasure_maps) VALUES (?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET treasure_maps = treasure_maps + ?""",
                  (user_id, n, n))
        conn.commit(); conn.close()

    def use_treasure_map(self, user_id):
        """地図を1枚消費。成功でTrue、0枚ならFalse。"""
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT treasure_maps FROM player_state WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row or row[0] <= 0:
            conn.close(); return False
        c.execute("UPDATE player_state SET treasure_maps = treasure_maps - 1 WHERE user_id = ?", (user_id,))
        conn.commit(); conn.close(); return True

    def get_last_area(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT last_area FROM player_state WHERE user_id = ?", (user_id,))
        row = c.fetchone(); conn.close()
        return row[0] if row and row[0] else "lake"

    def set_last_area(self, user_id, area):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("""INSERT INTO player_state (user_id, last_area) VALUES (?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET last_area = ?""",
                  (user_id, area, area))
        conn.commit(); conn.close()

    def add_zukan(self, user_id, area, fish_name):
        conn = self.get_conn()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO zukan (user_id, area, fish_name) VALUES (?, ?, ?)", (user_id, area, fish_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_zukan(self, user_id, area):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT fish_name FROM zukan WHERE user_id = ? AND area = ?", (user_id, area))
        rows = [r[0] for r in c.fetchall()]
        conn.close()
        return rows

    def add_crown(self, user_id, area, fish_name):
        conn = self.get_conn()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO zukan_crown (user_id, area, fish_name) VALUES (?, ?, ?)", (user_id, area, fish_name))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def get_crowns(self, user_id, area):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT fish_name FROM zukan_crown WHERE user_id = ? AND area = ?", (user_id, area))
        rows = [r[0] for r in c.fetchall()]
        conn.close()
        return rows

    def get_crown_count(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM zukan_crown WHERE user_id = ?", (user_id,))
        count = c.fetchone()[0]
        conn.close()
        return count

    def check_zukan_bonus(self, user_id, bonus_type):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT 1 FROM zukan_bonus WHERE user_id = ? AND bonus_type = ?", (user_id, bonus_type))
        exists = c.fetchone() is not None
        conn.close()
        return exists

    def set_zukan_bonus(self, user_id, bonus_type):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO zukan_bonus (user_id, bonus_type) VALUES (?, ?)", (user_id, bonus_type))
        conn.commit()
        conn.close()

    def set_vc_join(self, user_id, guild_id, joined_at):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO vc_tracking (user_id, guild_id, joined_at) VALUES (?, ?, ?)", (user_id, guild_id, joined_at))
        conn.commit()
        conn.close()

    def get_vc_join(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT joined_at FROM vc_tracking WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def remove_vc_join(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM vc_tracking WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
        conn.commit()
        conn.close()

    def get_guild_users(self, guild_id):
        """そのサーバーに残高レコードを持つ全ユーザーIDを返す（全員配布用）"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT user_id FROM economy WHERE guild_id = ?", (guild_id,))
        users = [r[0] for r in c.fetchall()]
        conn.close()
        return users

    def get_all_zukan_stats(self, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT user_id FROM economy WHERE guild_id = ?", (guild_id,))
        users = [r[0] for r in c.fetchall()]
        conn.close()
        return users

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 釣り装備管理
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def get_gear(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM fishing_gear WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row is None:
            self._init_gear(user_id)
            return {
                "rod_id":"bamboo","rod_uses":999999,
                "reel_id":"spinning","reel_uses":999999,
                "line_id":"nylon","line_uses":999999,
                "rod_inventory":{"bamboo":999999},
                "reel_inventory":{"spinning":999999},
                "line_inventory":{"nylon":999999},
            }
        return {
            "rod_id":row[1],"rod_uses":row[2],
            "reel_id":row[3],"reel_uses":row[4],
            "line_id":row[5],"line_uses":row[6],
            "rod_inventory":json.loads(row[7]),
            "reel_inventory":json.loads(row[8]),
            "line_inventory":json.loads(row[9]),
        }

    def _init_gear(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR IGNORE INTO fishing_gear
            (user_id, rod_id, rod_uses, reel_id, reel_uses, line_id, line_uses,
             rod_inventory, reel_inventory, line_inventory)
            VALUES (?, 'bamboo', 999999, 'spinning', 999999, 'nylon', 999999, ?, ?, ?)""",
            (user_id,
             json.dumps({"bamboo":999999}),
             json.dumps({"spinning":999999}),
             json.dumps({"nylon":999999})))
        conn.commit()
        conn.close()

    def save_gear(self, user_id, gear):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO fishing_gear
            (user_id, rod_id, rod_uses, reel_id, reel_uses, line_id, line_uses,
             rod_inventory, reel_inventory, line_inventory)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, gear["rod_id"], gear["rod_uses"],
             gear["reel_id"], gear["reel_uses"],
             gear["line_id"], gear["line_uses"],
             json.dumps(gear["rod_inventory"]),
             json.dumps(gear["reel_inventory"]),
             json.dumps(gear["line_inventory"])))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # デイリークエスト進捗（quest_date は JST の日付。0時リセット）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def add_quest_progress(self, user_id, guild_id, quest_date, quest_key, n, target):
        """進捗を n 加算（target で頭打ち）。無ければ作成。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO quest_progress
                (user_id, guild_id, quest_date, quest_key, progress)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id, quest_date, quest_key)
                DO UPDATE SET progress = MIN(progress + ?, ?)""",
            (user_id, guild_id, quest_date, quest_key, min(n, target), n, target))
        conn.commit()
        conn.close()

    def get_quest_progress(self, user_id, guild_id, quest_date):
        """{quest_key: (progress, claimed)} を返す。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""SELECT quest_key, progress, claimed FROM quest_progress
                     WHERE user_id=? AND guild_id=? AND quest_date=?""",
                  (user_id, guild_id, quest_date))
        rows = c.fetchall()
        conn.close()
        return {k: (p, cl) for k, p, cl in rows}

    def set_quest_claimed(self, user_id, guild_id, quest_date, quest_key):
        """受取済みフラグを立てる（無ければ作成）。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO quest_progress
                (user_id, guild_id, quest_date, quest_key, progress, claimed)
                VALUES (?, ?, ?, ?, 0, 1)
                ON CONFLICT(user_id, guild_id, quest_date, quest_key)
                DO UPDATE SET claimed = 1""",
            (user_id, guild_id, quest_date, quest_key))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ログ設定（カテゴリ別の送信先チャンネル。channel_id='OFF'で送らない）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def set_log_channel(self, guild_id, category, channel_id):
        """カテゴリの送信先を保存。channel_id にはチャンネルID文字列か 'OFF'。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO log_config (guild_id, category, channel_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, category)
                DO UPDATE SET channel_id = ?""",
            (str(guild_id), category, str(channel_id), str(channel_id)))
        conn.commit()
        conn.close()

    def get_log_channel_id(self, guild_id, category):
        """設定された channel_id（'OFF' 含む）を返す。未設定なら None。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT channel_id FROM log_config WHERE guild_id=? AND category=?",
                  (str(guild_id), category))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def get_all_log_config(self, guild_id):
        """{category: channel_id} を返す。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT category, channel_id FROM log_config WHERE guild_id=?",
                  (str(guild_id),))
        rows = c.fetchall()
        conn.close()
        return {cat: cid for cat, cid in rows}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # リアクションロール（メッセージ×絵文字 → 役職）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def add_reaction_role(self, guild_id, message_id, emoji_key, role_id, emoji_display):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO reaction_roles
                (guild_id, message_id, emoji_key, role_id, emoji_display)
                VALUES (?, ?, ?, ?, ?)""",
            (str(guild_id), str(message_id), str(emoji_key), str(role_id), str(emoji_display)))
        conn.commit()
        conn.close()

    def get_reaction_role_id(self, message_id, emoji_key):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT role_id FROM reaction_roles WHERE message_id=? AND emoji_key=?",
                  (str(message_id), str(emoji_key)))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
