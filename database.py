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
        import json
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
        import json
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
        import json
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
