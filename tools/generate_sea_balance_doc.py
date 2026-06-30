from pathlib import Path
import re
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import voyage_events as VE
import voyage_config as V
src = (ROOT / 'cogs' / 'voyage.py').read_text(encoding='utf-8')
coin = re.search(r'VOYAGE_COIN_REWARD_MULT\s*=\s*([0-9.]+)', src).group(1)
combat = re.search(r'NAVAL_COMBAT_REWARD_MULT\s*=\s*([0-9.]+)', src)
combat = combat.group(1) if combat else '1.0'
trade_mult = re.search(r'TRADE_UNIT\s*=\s*lambda\s*:\s*V\.FUEL_PRICE_PER\s*\*\s*([0-9.]+)', src)
trade_mult = float(trade_mult.group(1)) if trade_mult else 1.0

def event_weights(area):
    rows, total = [], 0
    for eid, d in VE.EVENT_DEFS.items():
        if area in d.get('areas', []):
            w = d.get('weight', {})
            val = w.get(area, 0) if isinstance(w, dict) else w
            if val > 0:
                total += val
                rows.append((eid, d.get('name', eid), val))
    return total, sorted(rows, key=lambda x: x[2], reverse=True)

def enemy_weights(area):
    rows = V.ENEMY_POOL_BY_AREA.get(area, [])
    return sum(w for _, w in rows), rows

md = []
md.append('# 航海バランス自動反映メモ\n\n')
md.append('このファイルは `python tools/generate_sea_balance_doc.py` で再生成できます。\n')
md.append('`voyage_config.py` / `voyage_events.py` / `cogs/voyage.py` の現在値を元にした、AI向け確認用の仕様書です。\n\n')
md.append('## 基本倍率\n\n')
md.append(f'- VOYAGE_COIN_REWARD_MULT: `{coin}`\n')
md.append(f'- NAVAL_COMBAT_REWARD_MULT: `{combat}`\n')
md.append('- 海戦/白兵戦EXP: `voyage_combat_xp(spec, win=True/False)` で敵の `crew_power` / `reward_mult` / `stars` / ボス補正から自動算出。勝利は満額、敗北は30%。\n')
md.append(f'- 商船燃料価格: 港単価 `{V.FUEL_PRICE_PER}` × `{trade_mult}` = `{V.FUEL_PRICE_PER * trade_mult:.2f}` / 燃料1\n')
md.append('\n## 魚の群れについて\n\n')
md.append('`魚の群れ`（`builtin_fish_cue`）は `EVENT_DEFS` 上の weight が 0 です。通常イベント抽選で二重に出さないためです。実際には `AREA_ENCOUNTERS` の `fish` 枠が当たった時に、選択式イベントとして表示されます。\n')
md.append('\n## エリア別探索カテゴリ重み（AREA_ENCOUNTERS）\n')
for area in range(1, 5):
    enc = V.AREA_ENCOUNTERS.get(area, {})
    total = sum(enc.values()) or 1
    md.append(f'\n### E{area} {V.AREA_NAMES.get(area, "")}\n\n')
    md.append('|カテゴリ|重み|割合|\n|---|---:|---:|\n')
    for k, w in sorted(enc.items(), key=lambda x: x[1], reverse=True):
        md.append(f'|{k}|{w}|{w / total * 100:.1f}%|\n')
md.append('\n## E1〜E4 イベント出現率（EVENT_DEFS内の重みベース）\n')
for area in range(1, 5):
    total, rows = event_weights(area)
    total = total or 1
    md.append(f'\n### E{area} イベント total weight={total}\n\n')
    md.append('|イベントID|イベント|重み|割合|\n|---|---|---:|---:|\n')
    for eid, name, w in rows:
        md.append(f'|`{eid}`|{name}|{w}|{w / total * 100:.1f}%|\n')
md.append('\n## E1〜E4 戦闘敵テーブル（戦闘発生時）\n')
for area in range(1, 5):
    total, rows = enemy_weights(area)
    total = total or 1
    md.append(f'\n### E{area}\n\n')
    md.append(f'- AREA_ENEMY_BASE: `{V.AREA_ENEMY_BASE.get(area)}`\n\n')
    md.append('|敵ID|敵名|重み|割合|ratio|hp_mult|atk_mult|reward|個性|勝利EXP目安|\n|---|---|---:|---:|---:|---:|---:|---:|---|---:|\n')
    for eid, w in rows:
        d = V.ENEMY_TYPES.get(eid, {})
        name = d.get('name', eid)
        
        spec = V.make_enemy_spec(eid, area) if hasattr(V, 'make_enemy_spec') else None
        xp = V.voyage_combat_xp(spec, True) if spec and hasattr(V, 'voyage_combat_xp') else ''
        note = d.get('note', '')
        md.append(f'|`{eid}`|{name}|{w}|{w / total * 100:.1f}%|{d.get("ratio", "")}|{d.get("hp_mult", "")}|{d.get("atk_mult", "")}|{d.get("reward", "")}|{note}|{xp}|\n')

out = ROOT / 'docs' / 'SEA_BALANCE_AUTO.md'
out.write_text(''.join(md), encoding='utf-8')
print(f'wrote {out}')
