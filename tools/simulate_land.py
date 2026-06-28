"""街道バランス確認用シミュレーター。

使い方:
  python tools/simulate_land.py --area plain --runs 1000 --seed 1
  python tools/simulate_land.py --area 1 --runs 100000 --start-level 1

前提:
- 遭遇した敵はすべて倒す想定
- HP/死亡/消耗品使用は簡略化（報酬量の期待値を見るため）
- メインイベントテーブル、ランダムイベント、イベント内サブ抽選、イベント戦闘、ストーリー選択肢の報酬、戦闘/アイテムドロップを含める
- 実ゲームのテーブル（land_config.py / voyage_config.py）を直接参照
"""
from __future__ import annotations
import argparse
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import land_config as L  # noqa: E402
import voyage_config as V  # noqa: E402

AREA_ALIASES = {
    "1": 1, "plain": 1, "heigen": 1, "平原": 1,
    "2": 2, "forest": 2, "mori": 2, "森": 2,
    "3": 3, "mountain": 3, "yama": 3, "山": 3,
}

def xp_to_next(level: int) -> int:
    return V.xp_to_next(level)

def add_xp(level: int, xp_pool: int, amount: int) -> tuple[int, int, int]:
    before = level
    xp_pool += int(amount)
    while level < V.LEVEL_MAX and xp_pool >= xp_to_next(level):
        xp_pool -= xp_to_next(level)
        level += 1
    return level, xp_pool, level - before

def land_xp_amount(level: int, area: int, raw_xp: int) -> int:
    mult = float(L.land_xp_scale(area, level)) if hasattr(L, "land_xp_scale") else 1.0
    amt = int(int(raw_xp) * mult)
    if raw_xp > 0 and mult > 0:
        return max(1, amt)
    return max(0, amt)

def weighted_pick(table: dict[str, float]) -> str:
    keys = list(table.keys())
    weights = list(table.values())
    return random.choices(keys, weights=weights)[0]

def roll_item_event() -> str:
    keys = [x[0] for x in L.LAND_ITEM_EVENT_DROPS]
    weights = [x[1] for x in L.LAND_ITEM_EVENT_DROPS]
    return random.choices(keys, weights=weights)[0]

def roll_item_drops(tier: str) -> list[str]:
    got = []
    for iid, rate in L.LAND_ITEM_DROP_RATES.get(tier, []):
        if random.random() < rate:
            got.append(iid)
    return got

def roll_equip_drop(area: int, tier: str) -> int | None:
    # 実ゲーム側は中ボス/大ボスはspecのdrop_tableを参照する。
    if tier == "zako":
        table = L.LAND_EQUIP_DROP.get(area, [])
    elif tier == "mid":
        table = random.choice(L.LAND_MIDRARES[area]).get("drop", [])
    else:
        table = L.RARE_BOSS.get("drop", [])
    for rank, rate in table:
        if random.random() < rate:
            return rank
    return None

def random_event_outcome(area: int) -> tuple[str, dict]:
    ev = L.pick_random_event(area)
    if not ev or not ev.get("choices"):
        return "nothing", {}
    ch = random.choice(ev["choices"])
    outs = ch.get("outcomes") or [("nothing", 1)]
    keys = [x[0] for x in outs]
    weights = [x[1] for x in outs]
    return random.choices(keys, weights=weights)[0], ch

def random_story_choice(area: int) -> dict:
    ev = L.pick_story(area)
    if not ev or not ev.get("choices"):
        return {}
    return random.choice(ev["choices"])

def simulate(area: int, runs: int, start_level: int, seed: int | None) -> dict:
    if seed is not None:
        random.seed(seed)
    a = L.LAND_AREAS[area]
    level = start_level
    xp_pool = 0
    total_xp = 0
    levelups = 0
    total_coin = 0
    events = Counter()
    items = Counter()
    equips = Counter()
    sub = Counter()

    for _ in range(runs):
        kind = weighted_pick(L.LAND_EVENT_TABLE[area])
        events[kind] += 1

        if kind == "combat":
            raw_xp = random.randint(*a["xp"])
            coin = random.randint(*a["coin"])
            tier = "zako"
        elif kind == "midrare":
            spec = random.choice(L.LAND_MIDRARES[area])
            raw_xp = random.randint(*spec["xp"])
            coin = random.randint(*spec["coin"])
            tier = "mid"
        elif kind == "rare":
            spec = random.choice(L.LAND_RARES[area])
            raw_xp = random.randint(*spec["xp"])
            coin = random.randint(*spec["coin"])
            tier = "rare"
        else:
            raw_xp = 0
            coin = 0
            tier = ""

        if tier:
            xp = land_xp_amount(level, area, raw_xp)
            total_xp += xp
            level, xp_pool, up = add_xp(level, xp_pool, xp)
            levelups += up
            total_coin += coin
            for iid in roll_item_drops(tier):
                items[iid] += 1
            eq = roll_equip_drop(area, tier)
            if eq:
                equips[f"☆{eq}"] += 1
            continue

        if kind == "item":
            items[roll_item_event()] += 1
        elif kind == "coin":
            total_coin += random.randint(*L.LAND_COIN_EVENT[area])
        elif kind == "gather":
            total_coin += random.randint(*L.LAND_GATHER_COIN[area])
        elif kind == "story":
            # 実ゲームのストーリー候補から1つ選び、さらに選択肢をランダムに選ぶ。
            ch = random_story_choice(area)
            if ch.get("xp"):
                xp = land_xp_amount(level, area, random.randint(*ch["xp"]))
                total_xp += xp
                level, xp_pool, up = add_xp(level, xp_pool, xp)
                levelups += up
            if ch.get("coin"):
                total_coin += random.randint(*ch["coin"])
            if ch.get("food") and ch["food"] in V.FOODS:
                items[f"food:{ch['food']}"] += 1
            if ch.get("outcomes"):
                keys = [x[0] for x in ch["outcomes"]]
                weights = [x[1] for x in ch["outcomes"]]
                outcome = random.choices(keys, weights=weights)[0]
                sub[f"story_{outcome}"] += 1
                if outcome == "item":
                    items[roll_item_event()] += 1
                elif outcome == "coin":
                    total_coin += random.randint(*L.LAND_COIN_EVENT[area])
                elif outcome == "xp":
                    raw = random.randint(1, 4) if area == 1 else random.randint(5, 12) if area == 2 else random.randint(8, 18)
                    xp = land_xp_amount(level, area, raw)
                    total_xp += xp
                    level, xp_pool, up = add_xp(level, xp_pool, xp)
                    levelups += up
                elif outcome == "combat":
                    raw_xp = random.randint(*a["xp"])
                    xp = land_xp_amount(level, area, raw_xp)
                    total_xp += xp
                    level, xp_pool, up = add_xp(level, xp_pool, xp)
                    levelups += up
                    total_coin += random.randint(*a["coin"])
                    events["story_combat"] += 1
                    for iid in roll_item_drops("zako"):
                        items[iid] += 1
        elif kind == "event":
            outcome, ch = random_event_outcome(area)
            sub[outcome] += 1
            if outcome == "item":
                items[roll_item_event()] += 1
            elif outcome == "coin":
                total_coin += random.randint(*L.LAND_COIN_EVENT[area])
            elif outcome == "xp":
                raw = random.randint(1, 4) if area == 1 else random.randint(5, 12) if area == 2 else random.randint(8, 18)
                xp = land_xp_amount(level, area, raw)
                total_xp += xp
                level, xp_pool, up = add_xp(level, xp_pool, xp)
                levelups += up
            elif outcome == "combat":
                # イベントから飛び出した敵は雑魚扱い。
                raw_xp = random.randint(*a["xp"])
                xp = land_xp_amount(level, area, raw_xp)
                total_xp += xp
                level, xp_pool, up = add_xp(level, xp_pool, xp)
                levelups += up
                total_coin += random.randint(*a["coin"])
                events["event_combat"] += 1
                for iid in roll_item_drops("zako"):
                    items[iid] += 1
                eq = roll_equip_drop(area, "zako")
                if eq:
                    equips[f"☆{eq}"] += 1

    return {
        "area": area, "area_name": a["name"], "runs": runs,
        "start_level": start_level, "final_level": level, "xp_pool": xp_pool,
        "total_xp": total_xp, "levelups": levelups, "total_coin": total_coin,
        "events": events, "items": items, "equips": equips, "sub": sub,
    }

def fmt_counter(c: Counter, name_map: dict[str, str] | None = None) -> str:
    if not c:
        return "なし"
    rows = []
    for k, v in c.most_common():
        label = name_map.get(k, k) if name_map else k
        rows.append(f"  {label}: {v}")
    return "\n".join(rows)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--area", default="plain", help="plain/forest/mountain または 1/2/3")
    ap.add_argument("--runs", type=int, default=1000)
    ap.add_argument("--start-level", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    area = AREA_ALIASES.get(str(args.area), None)
    if area is None:
        raise SystemExit("--area は plain/forest/mountain/1/2/3/平原/森/山 のどれか")
    r = simulate(area, args.runs, args.start_level, args.seed)
    item_names = {iid: f"{d['emoji']} {d['name']}" for iid, d in L.LAND_ITEMS.items()}
    item_names.update({f"food:{fid}": f"{f['emoji']} {f['name']}" for fid, f in V.FOODS.items()})
    print(f"====== 街道シミュレーション: {r['area_name']} {r['runs']:,}回 ======")
    print(f"開始Lv: {r['start_level']}  →  最終Lv: {r['final_level']} / 現在XP: {r['xp_pool']:,}/{xp_to_next(r['final_level']):,}")
    print(f"総XP: {r['total_xp']:,} / レベルアップ回数: {r['levelups']}")
    print(f"総コイン: {r['total_coin']:,}")
    print("\n[イベント]")
    print(fmt_counter(r["events"]))
    print("\n[イベント内サブ結果]")
    print(fmt_counter(r["sub"]))
    print("\n[消耗品]")
    print(fmt_counter(r["items"], item_names))
    print("\n[装備ドロップ]")
    print(fmt_counter(r["equips"]))

if __name__ == "__main__":
    main()
