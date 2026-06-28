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
        c.execute("""CREATE TABLE IF NOT EXISTS temp_vc (
            channel_id TEXT PRIMARY KEY, guild_id TEXT, owner_id TEXT,
            kind TEXT DEFAULT 'main', parent_id TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS vc_activity (
            user_id TEXT, guild_id TEXT,
            vc_seconds INTEGER DEFAULT 0, last_active TEXT,
            PRIMARY KEY (user_id, guild_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS activity_log (
            guild_id TEXT, user_id TEXT, kind TEXT, ts_hour INTEGER,
            amount INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, kind, ts_hour)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS line_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT, from_id TEXT, to_id TEXT,
            body TEXT, ts TEXT, is_read INTEGER DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS menu_visit (
            user_id TEXT, guild_id TEXT, last_open TEXT,
            PRIMARY KEY (user_id, guild_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS line_settings (
            user_id TEXT, guild_id TEXT, dm_notify INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        )""")
        # ── 解放ファンド（コミュニティ募金で次コンテンツ解放）──
        c.execute("""CREATE TABLE IF NOT EXISTS community_fund (
            guild_id TEXT, goal_key TEXT, total INTEGER DEFAULT 0, unlocked INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, goal_key)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS fund_contrib (
            guild_id TEXT, goal_key TEXT, user_id TEXT, amount INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, goal_key, user_id)
        )""")
        # ── ⚓ 航海（船・装備・レベル・航海中状態を1つのJSONブロブで保持）──
        c.execute("""CREATE TABLE IF NOT EXISTS voyage (
            user_id TEXT PRIMARY KEY, data TEXT
        )""")
        # ── 魚名リネーム移行（冪等）──
        # 湖 super_rare「アリゲーターガー」→「アロワナ」。最初からアロワナだった扱いにする。
        # 川の「アリゲーターガー幼魚」は文字列が異なるため影響なし。
        for tbl in ("zukan", "zukan_crown"):
            c.execute(
                f"UPDATE OR IGNORE {tbl} SET fish_name = 'アロワナ' WHERE fish_name = 'アリゲーターガー'"
            )
            # OR IGNORE で衝突した残骸（万一アロワナ既存時）を掃除
            c.execute(f"DELETE FROM {tbl} WHERE fish_name = 'アリゲーターガー'")

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
        from config import jst_today_str
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "INSERT INTO send_log (user_id, guild_id, amount, sent_date) VALUES (?, ?, ?, ?)",
            (user_id, guild_id, amount, jst_today_str()),
        )
        conn.commit()
        conn.close()

    def get_today_sent(self, user_id, guild_id):
        from config import jst_today_str
        conn = self.get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM send_log WHERE user_id = ? AND guild_id = ? AND sent_date = ?",
            (user_id, guild_id, jst_today_str()),
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 自由部屋（一時VC）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def add_temp_vc(self, channel_id, guild_id, owner_id, kind="main", parent_id=None):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT OR REPLACE INTO temp_vc
                (channel_id, guild_id, owner_id, kind, parent_id)
                VALUES (?, ?, ?, ?, ?)""",
            (str(channel_id), str(guild_id), str(owner_id), kind,
             str(parent_id) if parent_id else None))
        conn.commit()
        conn.close()

    def remove_temp_vc(self, channel_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM temp_vc WHERE channel_id=?", (str(channel_id),))
        conn.commit()
        conn.close()

    def get_temp_vc(self, channel_id):
        """owner_id を返す（無ければ None）。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT owner_id FROM temp_vc WHERE channel_id=?", (str(channel_id),))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def get_temp_vc_row(self, channel_id):
        """(owner_id, kind, parent_id) を返す（無ければ None）。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT owner_id, kind, parent_id FROM temp_vc WHERE channel_id=?",
                  (str(channel_id),))
        row = c.fetchone()
        conn.close()
        return row if row else None

    def set_temp_vc_owner(self, channel_id, owner_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("UPDATE temp_vc SET owner_id=? WHERE channel_id=?",
                  (str(owner_id), str(channel_id)))
        conn.commit()
        conn.close()

    def get_waiting_for(self, parent_id):
        """親VCに紐づく待機VCの channel_id を返す（無ければ None）。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT channel_id FROM temp_vc WHERE kind='waiting' AND parent_id=?",
                  (str(parent_id),))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # VC活動量（累計VC秒・最終活動）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def add_vc_seconds(self, user_id, guild_id, secs, ts=None):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO vc_activity (user_id, guild_id, vc_seconds, last_active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id)
                DO UPDATE SET vc_seconds = vc_seconds + ?, last_active = ?""",
            (str(user_id), str(guild_id), int(secs), ts, int(secs), ts))
        conn.commit()
        conn.close()

    def touch_active(self, user_id, guild_id, ts):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO vc_activity (user_id, guild_id, vc_seconds, last_active)
                VALUES (?, ?, 0, ?)
                ON CONFLICT(user_id, guild_id)
                DO UPDATE SET last_active = ?""",
            (str(user_id), str(guild_id), ts, ts))
        conn.commit()
        conn.close()

    def get_vc_seconds(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT vc_seconds FROM vc_activity WHERE user_id=? AND guild_id=?",
                  (str(user_id), str(guild_id)))
        row = c.fetchone()
        conn.close()
        return row[0] if row else 0

    def get_all_vc_activity(self, guild_id):
        """{user_id: (vc_seconds, last_active)} を返す。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT user_id, vc_seconds, last_active FROM vc_activity WHERE guild_id=?",
                  (str(guild_id),))
        rows = c.fetchall()
        conn.close()
        return {u: (s, la) for u, s, la in rows}

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 時間帯別アクティビティ（VC秒・チャット数を1時間バケットで蓄積）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def log_activity(self, guild_id, user_id, kind, amount, epoch):
        ts_hour = int(epoch) // 3600
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO activity_log (guild_id, user_id, kind, ts_hour, amount)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, kind, ts_hour)
                DO UPDATE SET amount = amount + ?""",
            (str(guild_id), str(user_id), kind, ts_hour, int(amount), int(amount)))
        conn.commit()
        conn.close()

    def rank_activity(self, guild_id, kind, since_hour, limit=10):
        """(user_id, 合計) を多い順に返す。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""SELECT user_id, SUM(amount) AS total FROM activity_log
                WHERE guild_id=? AND kind=? AND ts_hour>=?
                GROUP BY user_id ORDER BY total DESC LIMIT ?""",
            (str(guild_id), kind, int(since_hour), int(limit)))
        rows = c.fetchall()
        conn.close()
        return [(u, t) for u, t in rows]

    def activity_buckets(self, guild_id, kind, since_hour):
        """(ts_hour, 合計) をサーバー全体で時間バケットごとに返す（グラフ用）。"""
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""SELECT ts_hour, SUM(amount) FROM activity_log
                WHERE guild_id=? AND kind=? AND ts_hour>=?
                GROUP BY ts_hour ORDER BY ts_hour ASC""",
            (str(guild_id), kind, int(since_hour)))
        rows = c.fetchall()
        conn.close()
        return [(int(h), int(a)) for h, a in rows]

    def prune_activity(self, before_hour):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM activity_log WHERE ts_hour < ?", (int(before_hour),))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LINE（bot内メッセージ）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def add_line_message(self, guild_id, from_id, to_id, body, ts):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO line_messages (guild_id, from_id, to_id, body, ts)
                VALUES (?, ?, ?, ?, ?)""",
            (str(guild_id), str(from_id), str(to_id), body, ts))
        conn.commit()
        conn.close()

    def get_line_inbox(self, guild_id, to_id, limit=15):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""SELECT id, from_id, body, ts, is_read FROM line_messages
                WHERE guild_id=? AND to_id=? ORDER BY id DESC LIMIT ?""",
            (str(guild_id), str(to_id), int(limit)))
        rows = c.fetchall()
        conn.close()
        return rows

    def line_unread_count(self, guild_id, to_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""SELECT COUNT(*) FROM line_messages
                WHERE guild_id=? AND to_id=? AND is_read=0""",
            (str(guild_id), str(to_id)))
        n = c.fetchone()[0]
        conn.close()
        return n

    def mark_line_all_read(self, guild_id, to_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""UPDATE line_messages SET is_read=1
                WHERE guild_id=? AND to_id=? AND is_read=0""",
            (str(guild_id), str(to_id)))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # メニュー来訪（今日初めて開いたか判定用）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def get_menu_seen(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT last_open FROM menu_visit WHERE user_id=? AND guild_id=?",
                  (str(user_id), str(guild_id)))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None

    def set_menu_seen(self, user_id, guild_id, day):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO menu_visit (user_id, guild_id, last_open)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET last_open=?""",
            (str(user_id), str(guild_id), day, day))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # LINE DM通知設定（個人ごと・デフォルトOFF）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def get_line_dm(self, user_id, guild_id):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("SELECT dm_notify FROM line_settings WHERE user_id=? AND guild_id=?",
                  (str(user_id), str(guild_id)))
        row = c.fetchone()
        conn.close()
        return bool(row[0]) if row else False

    def set_line_dm(self, user_id, guild_id, enabled):
        conn = self.get_conn()
        c = conn.cursor()
        c.execute("""INSERT INTO line_settings (user_id, guild_id, dm_notify)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET dm_notify=?""",
            (str(user_id), str(guild_id), 1 if enabled else 0, 1 if enabled else 0))
        conn.commit()
        conn.close()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 解放ファンド（コミュニティ募金）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def get_fund(self, guild_id, goal_key):
        """(total, unlocked) を返す。未作成なら (0, False)。"""
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT total, unlocked FROM community_fund WHERE guild_id=? AND goal_key=?",
                  (str(guild_id), goal_key))
        row = c.fetchone(); conn.close()
        return (row[0], bool(row[1])) if row else (0, False)

    def is_fund_unlocked(self, guild_id, goal_key):
        return self.get_fund(guild_id, goal_key)[1]

    def add_fund_contribution(self, guild_id, goal_key, user_id, amount):
        """募金を加算。新しい累積額を返す。"""
        conn = self.get_conn(); c = conn.cursor()
        c.execute("""INSERT INTO community_fund (guild_id, goal_key, total)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, goal_key) DO UPDATE SET total = total + ?""",
            (str(guild_id), goal_key, amount, amount))
        c.execute("""INSERT INTO fund_contrib (guild_id, goal_key, user_id, amount)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, goal_key, user_id) DO UPDATE SET amount = amount + ?""",
            (str(guild_id), goal_key, str(user_id), amount, amount))
        c.execute("SELECT total FROM community_fund WHERE guild_id=? AND goal_key=?",
                  (str(guild_id), goal_key))
        total = c.fetchone()[0]
        conn.commit(); conn.close()
        return total

    def set_fund_unlocked(self, guild_id, goal_key):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("""INSERT INTO community_fund (guild_id, goal_key, total, unlocked)
                VALUES (?, ?, 0, 1)
                ON CONFLICT(guild_id, goal_key) DO UPDATE SET unlocked = 1""",
            (str(guild_id), goal_key))
        conn.commit(); conn.close()

    def get_user_fund_contribution(self, guild_id, goal_key, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT amount FROM fund_contrib WHERE guild_id=? AND goal_key=? AND user_id=?",
                  (str(guild_id), goal_key, str(user_id)))
        row = c.fetchone(); conn.close()
        return row[0] if row else 0

    def get_fund_contributors(self, guild_id, goal_key, limit=10):
        """[(user_id, amount), ...] を多い順に返す。"""
        conn = self.get_conn(); c = conn.cursor()
        c.execute("""SELECT user_id, amount FROM fund_contrib
                WHERE guild_id=? AND goal_key=? AND amount > 0
                ORDER BY amount DESC LIMIT ?""",
            (str(guild_id), goal_key, limit))
        rows = c.fetchall(); conn.close()
        return [(r[0], r[1]) for r in rows]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ⚓ 航海プロフィール（船・装備・レベル・航海中状態をJSONで保持）
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    def _default_voyage(self):
        return {
            "has_ship": False,
            # ── 船本体＋部位スロット（個人装備と同じ思想）──
            "ship": None,              # 所持船ID（None=未所持・1隻のみ）
            "ship_skills": [],         # 船本体に刻んだ技
            "ship_hp_cur": 0,          # 現在の船HP（海戦用・港で全回復）
            "ship_parts": {            # 部位＝｛item,skills,dura｝ or None
                "cannon": None, "armor": None, "rigging": None,
            },
            # ── 個人インベントリ（部位別・枠上限：武器5/胴3/脚3）──
            "inventory": {"weapon": [], "torso": [], "legs": []},
            "equipped": {"weapon": None, "torso": None, "legs": None},
            "level": 1, "xp": 0, "cur_hp": 100,
            "learned_skills": {},
            "unequip_kits": 0,
            "gacha_medals": 0,         # 🎖️ 技ガチャ1回につき1枚。交換所で☆3技/ペットと交換
            "lottery_tickets": 0,      # 🎟️ 技ガチャのハズレ枠などで入手。所持品から使用
            "special_items": [],       # 全損しても持ち帰れる特殊アイテム（救済枠）
            "shards": 0,               # 🧭 羅針盤のカケラ（特殊ポーチ・永続・全損でもロストしない・航海をまたいで蓄積）
            "has_voyage_rod": False,    # 🎣 航海専用の釣り竿（ドックで10万・永久・これが無いと海で釣れない）
            "karma": 20,               # ⚖️ カルマ（20=やや善寄りスタート・永続・選択で±に振れる）
            "voyage": None,
        }

    def get_voyage(self, user_id):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("SELECT data FROM voyage WHERE user_id=?", (str(user_id),))
        row = c.fetchone(); conn.close()
        if row is None:
            d = self._default_voyage()
            self.save_voyage(user_id, d)
            return d
        d = json.loads(row[0])
        base = self._default_voyage()
        # 欠けたトップレベルキーを補完
        for k, v in base.items():
            if k not in d: d[k] = v
        # ── 旧構造（personal/slot_skills）→ 新インベントリ構造へ移行 ──
        if "inventory" not in d or "personal" in d or "slot_skills" in d:
            inv = {"weapon": [], "torso": [], "legs": []}
            eq = {"weapon": None, "torso": None, "legs": None}
            old_p = d.get("personal", {})
            old_ss = d.get("slot_skills", {}) if isinstance(d.get("slot_skills"), dict) else {}
            for part in ("weapon", "torso", "legs"):
                item = old_p.get(part)
                if isinstance(item, str):
                    sk = old_ss.get(part, [])
                    sk = sk if isinstance(sk, list) else []
                    inv[part].append({"item": item, "skills": list(sk)})
                    eq[part] = 0
            d["inventory"] = inv; d["equipped"] = eq
            d.pop("personal", None); d.pop("slot_skills", None)
        for part in ("weapon", "torso", "legs"):
            d.setdefault("inventory", {}).setdefault(part, [])
            d.setdefault("equipped", {}).setdefault(part, None)
        if "cur_hp" not in d: d["cur_hp"] = 100
        # ── 旧船構造（ship_equip/hull_dura）→ 新（ship本体＋部位）へ移行 ──
        if "ship_equip" in d or "ship_parts" not in d:
            had_ship = d.get("has_ship", False)
            d["ship"] = "frigate" if had_ship else None
            d["ship_skills"] = d.get("ship_skills", []) if isinstance(d.get("ship_skills"), list) else []
            d["ship_parts"] = {"cannon": None, "armor": None, "rigging": None}
            d["ship_hp_cur"] = 300 if had_ship else 0
            d.pop("ship_equip", None); d.pop("hull_dura", None)
        d.setdefault("ship_parts", {"cannon": None, "armor": None, "rigging": None})
        for p in ("cannon", "armor", "rigging"):
            d["ship_parts"].setdefault(p, None)
        d.setdefault("ship_skills", [])
        d.setdefault("ship_hp_cur", 0)
        d.setdefault("ship", None)
        d.setdefault("lottery_tickets", 0)
        d.setdefault("special_items", [])
        # ── 🧭 カケラを永続枠へ：旧 voyage内shards をトップレベル(特殊ポーチ)へ移行 ──
        d.setdefault("shards", 0)
        d.setdefault("karma", 20)  # ⚖️ カルマ（20=やや善寄りスタート・永続）
        vy = d.get("voyage")
        if isinstance(vy, dict) and "shards" in vy:
            d["shards"] = max(d.get("shards", 0), vy.pop("shards"))
        return d

    def save_voyage(self, user_id, data):
        conn = self.get_conn(); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO voyage (user_id, data) VALUES (?, ?)",
                  (str(user_id), json.dumps(data, ensure_ascii=False)))
        conn.commit(); conn.close()
