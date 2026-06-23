import sqlite3

DB_PATH = "bot_data.db"

class Database:
    def __init__(self):
        self.path = DB_PATH

    def get_conn(self):
        return sqlite3.connect(self.path)

    def initialize(self):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS economy (
            user_id TEXT PRIMARY KEY, guild_id TEXT,
            balance INTEGER DEFAULT 1000, total_earned INTEGER DEFAULT 0,
            last_daily TEXT
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
        conn.commit()
        conn.close()
        print("✅ データベース初期化完了")

    def get_balance(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT balance FROM economy WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row is None:
            c.execute("INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, 1000)", (user_id, guild_id))
            conn.commit()
            conn.close()
            return 1000
        conn.close()
        return row[0]

    def update_balance(self, user_id, guild_id, amount):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("UPDATE economy SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)", (user_id, guild_id, 1000 + amount))
        conn.commit()
        conn.close()

    def set_balance(self, user_id, guild_id, amount):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("UPDATE economy SET balance = ? WHERE user_id = ?", (amount, user_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO economy (user_id, guild_id, balance) VALUES (?, ?, ?)", (user_id, guild_id, amount))
        conn.commit()
        conn.close()

    def get_ranking(self, guild_id, limit=10):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT user_id, balance FROM economy WHERE guild_id = ? ORDER BY balance DESC LIMIT ?", (guild_id, limit))
        rows = c.fetchall()
        conn.close()
        return rows

    def get_last_daily(self, user_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT last_daily FROM economy WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_last_daily(self, user_id, date_str):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("UPDATE economy SET last_daily = ? WHERE user_id = ?", (date_str, user_id))
        conn.commit()
        conn.close()

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

    def get_all_zukan_stats(self, guild_id):
        """全ユーザーの図鑑統計を返す（ランキング用）"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT DISTINCT user_id FROM economy WHERE guild_id = ?", (guild_id,))
        users = [r[0] for r in c.fetchall()]
        conn.close()
        return users
