"""Discordに接続せず、独立した一時DBで起動・主要画面・保存互換性を確認する。"""
import ast
import importlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_TEMP = tempfile.TemporaryDirectory(prefix='nato-offline-')
os.environ['RAILWAY_VOLUME_MOUNT_PATH'] = _TEMP.name
import bot  # noqa: E402


class OfflineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        bot.db.initialize()

    async def test_all_extensions_and_commands(self):
        async with bot.bot:
            await bot.load_extensions()
            try:
                self.assertEqual(len(bot.bot.extensions), 27)
                expected = {
                    'balance', 'daily', 'send_coin', 'fortune', 'blackjack',
                    'poker', 'numguess', 'teamsplit', 'teamsplit_custom',
                    'logchannel', 'slot', 'fish', 'zukan', 'chinchiro', 'shop',
                    '募集パネル設置', '鍛冶屋', 'menu', 'admin', 'quest', 'ranking',
                }
                self.assertEqual({c.name for c in bot.bot.tree.get_commands()}, expected)
                self.assertIn('VC時間', bot.bot.tree.get_command('ranking').description)
            finally:
                for extension in reversed(list(bot.bot.extensions)):
                    await bot.bot.unload_extension(extension)

    async def test_main_panels(self):
        cases = {
            'menu': [('MainMenuView', ('1', '1')), ('ShoppingStreetView', ('1', '1')),
                     ('CasinoMenuView', ('1',)), ('WalletMenuView', ('1',)),
                     ('CoinflipChoiceView', (100, '1'))],
            'phone': [('PhoneHomeView', ('1',))],
            'land': [('LandHomeView', ('1', '1')), ('LandAreaView', ('1', '1', 1))],
            'voyage': [('PortView', ('1', '1')), ('EquipShopView', ('1', '1')),
                       ('InventoryView', ('1', '1')), ('ItemShopView', ('1', '1')),
                       ('SkillGachaView', ('1', '1')), ('GachaExchangeView', ('1', '1')),
                       ('ShopView', ('1', '1')), ('EnemyZukanView', ('1', '1'))],
            'blackjack': [('BlackjackModeView', (100,))],
            'poker': [('PokerModeView', (100,))],
            'chinchiro': [('ChinchiroModeView', (100,))],
            'blacksmith': [('BlacksmithView', ('1',))],
            'slot': [('SlotSelectView', ())],
            'juggler': [('KishuSelectView', ()), ('JugglerSelectView', ())],
            'member_onboarding': [('RegistrationPanel', ()), ('MemberAdminView', ()),
                                  ('ProfileEditMenu', (1,))],
            'activitystats': [('StatsView', ('1',)), ('PublicRankingView', (1,))],
            'tempvc': [('TempVoicePanel', ())],
            'admin': [('AdminMenuView', ('1',))],
        }
        for module, specs in cases.items():
            m = importlib.import_module('cogs.' + module)
            for name, args in specs:
                with self.subTest(panel=name):
                    view = getattr(m, name)(*args)
                    try:
                        self.assertLessEqual(len(view.children), 25)
                        view.to_components()
                    finally:
                        view.stop()

    async def test_database_round_trip(self):
        db = bot.db
        self.assertEqual(db.get_balance('db-user', 'one'), 3000)
        db.update_balance('db-user', 'one', 250)
        self.assertEqual(db.get_balance('db-user', 'one'), 3250)
        self.assertEqual(db.get_balance('db-user', 'two'), 3000)
        vp = db.get_voyage('db-user')
        vp['level'] = 7
        vp['ship_skills'] = ['old-skill']
        vp['legacy_extra'] = {'keep': True}
        db.save_voyage('db-user', vp)
        loaded = db.get_voyage('db-user')
        self.assertEqual(loaded['level'], 7)
        self.assertEqual(loaded['ship_skills'], ['old-skill'])
        self.assertEqual(loaded['legacy_extra'], {'keep': True})
        db.initialize()
        self.assertEqual(db.get_balance('db-user', 'one'), 3250)

    async def test_render_ranking_without_network(self):
        from cogs.activitystats import build_public_rank_card, _FONT_CANDIDATES
        if not any(Path(p).exists() for p in _FONT_CANDIDATES):
            self.skipTest("fonts-noto-cjk が未導入の環境では画像描画をスキップ")
        guild = SimpleNamespace(id=999, name='Offline test', get_member=lambda _: None)
        image = await build_public_rank_card(guild, 1, 'vc', '1w')
        try:
            self.assertEqual(image.fp.read(8), b'\x89PNG\r\n\x1a\n')
        finally:
            image.close()

    async def test_simulator_drop_distribution(self):
        from tools.simulate_land import roll_equip_drop
        for area in (1, 2, 3):
            for tier in ('zako', 'mid', 'rare'):
                with self.subTest(area=area, tier=tier):
                    with patch('tools.simulate_land.random.random', return_value=0):
                        self.assertIn(roll_equip_drop(area, tier), (1, 2, 3))

    async def test_direct_local_module_references(self):
        local_names = {'config', 'land_config', 'voyage_config', 'voyage_skills',
                       'voyage_combat', 'voyage_events', 'weather'}
        for file in ROOT.rglob('*.py'):
            if 'tests' in file.parts:
                continue
            tree = ast.parse(file.read_text(encoding='utf-8'))
            imports = {a.asname or a.name: a.name for n in ast.walk(tree)
                       if isinstance(n, ast.Import) for a in n.names if a.name in local_names}
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in imports:
                    m = importlib.import_module(imports[n.value.id])
                    with self.subTest(file=file.name, symbol=n.attr):
                        self.assertTrue(hasattr(m, n.attr))


if __name__ == '__main__':
    unittest.main()
