"""参加登録v1のDB互換テスト。Discordへのネットワーク接続不要。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import database


class RegistrationDBTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='onboarding-')
        self.addCleanup(self.temporary.cleanup)
        self.path = str(Path(self.temporary.name) / 'bot_data.db')
        # 古い最小限の構造を再現して、追加列のマイグレーションを検査する。
        with sqlite3.connect(self.path) as conn:
            conn.execute('CREATE TABLE member_registration (guild_id TEXT, user_id TEXT, rule_ok INTEGER DEFAULT 0, PRIMARY KEY(guild_id,user_id))')
            conn.execute('INSERT INTO member_registration VALUES ("g","u",1)')
            conn.execute('CREATE TABLE member_profiles (guild_id TEXT, user_id TEXT, nickname TEXT, hobby TEXT, comment TEXT, mbti TEXT, games TEXT, PRIMARY KEY(guild_id,user_id))')
            conn.execute('CREATE TABLE temp_vc (channel_id TEXT PRIMARY KEY, guild_id TEXT, owner_id TEXT, kind TEXT DEFAULT "main", parent_id TEXT)')
        self.dir_patch = patch.object(database, 'DB_DIR', self.temporary.name)
        self.dir_patch.start()
        self.addCleanup(self.dir_patch.stop)
        self.db = database.Database()
        self.db.path = self.path
        self.db.initialize()

    def test_legacy_consent_requires_version(self):
        old = self.db.get_member_registration('g','u')
        self.assertTrue(old['rule_ok'])
        self.assertIsNone(old['consent_version'])
        self.db.accept_member_rules('g','u','v1')
        new = self.db.get_member_registration('g','u')
        self.assertEqual(new['consent_version'],'v1')
        self.assertEqual(new['age_confirmed'],1)
        self.assertTrue(new['consent_at'])

    def test_profile_save_retry_and_block(self):
        self.db.update_member_profile('g','u',nickname='例',gender='回答しない',comment='よろしく')
        self.assertEqual(self.db.get_member_profile('g','u')['gender'],'回答しない')
        self.db.accept_member_rules('g','u','v1')
        self.assertTrue(self.db.mark_member_registered('g','u'))
        first = self.db.get_member_registration('g','u')['registered_at']
        self.assertTrue(self.db.mark_member_registered('g','u'))
        self.assertEqual(first, self.db.get_member_registration('g','u')['registered_at'])
        self.db.set_member_blocked('g','u',True)
        self.assertFalse(self.db.mark_member_registered('g','u'))
        self.db.initialize()
        self.assertEqual(self.db.get_member_profile('g','u')['nickname'],'例')

    def test_tier_storage_old_rows(self):
        self.db.add_temp_vc('vc1','g','u',access_tier='full')
        rows = self.db.list_temp_vcs('g')
        self.assertEqual(rows[0][-1],'full')


if __name__ == '__main__':
    unittest.main()
