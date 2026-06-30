"""⚓ 航海システム（さびれた港 再興後コンテンツ）── Phase 1: 単独航海コア。
船購入 → 装備 → 出航 → 進む/引き返す → 釣り/上陸/海賊戦(2層) → 船倉を銀行入金。
敗北で失うのは航海中の船倉のみ。船戦は勝敗問わず船装備の耐久がガッツリ減る＝修理代シンク。
ネット≈105%（voyage_config の数値で制御・モンテカルロ検算済み）。
※ ガチャ/マーケット/協力航海は Phase2+ で実装予定。
"""
import random
import asyncio
import time
import discord
from discord.ext import commands
from database import Database
import voyage_config as V
import voyage_events as VE
import land_config as L
from config import ADMIN_USER_IDS

db = Database()

# 🍖 まとめ買いの個数ステップ（ドック食料店／商船取引で共用）
FOOD_QTY_STEPS = [1, 10, 50]
# ⛽ 商船での給油ステップ（航海中の緊急補給。港より割高）
TRADE_FUEL_STEPS = [500, 1000, 2000, 5000]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 計算ヘルパ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ── 船：本体＋部位スロットから 攻撃/防御/HP を算出 ──
def ship_def_of(vp):
    """所持船の定義 dict（未所持=None）。"""
    return V.SHIPS.get(vp.get("ship")) if vp.get("ship") else None

def ship_part_inst(vp, part):
    """部位に挿した船装備インスタンス {item,skills,dura} or None。"""
    return vp["ship_parts"].get(part)

def ship_part_def(vp, part):
    inst = ship_part_inst(vp, part)
    if not inst:
        return None
    return V.SHIP_PARTS[part]["items"].get(inst["item"])

def ship_attack(vp):
    d = ship_part_def(vp, "cannon")
    return d["power"] if d else 0

def ship_defense(vp):
    sd = ship_def_of(vp)
    base = sd["base_def"] if sd else 0
    a = ship_part_def(vp, "armor")
    return base + (a["power"] if a else 0)

def ship_max_hp(vp):
    sd = ship_def_of(vp)
    return sd["base_hp"] if sd else 0

def ship_max_fuel(vp):
    """⛽ 船のタンク容量。出航時の満タン値。船未所持なら0。"""
    sd = ship_def_of(vp)
    return sd.get("max_fuel", 0) if sd else 0

def ship_power(vp):
    """互換：海戦の総合戦闘力（攻＋防）。"""
    return ship_attack(vp) + ship_defense(vp)

# インベントリ枠上限
INV_CAP = {"weapon": 5, "torso": 3, "legs": 3}
SKILL_CAP = 5

def max_hp(vp):
    return 100 + (vp.get("level", 1) - 1) * 10



def _pet_counts(vp):
    """所持ペット数。special_itemsに同じペットが複数あれば複数効果として数える。"""
    counts = {}
    for pid in vp.get("special_items", []) or []:
        if pid in getattr(V, "PETS", {}):
            counts[pid] = counts.get(pid, 0) + 1
    return counts

def _pet_line(vp):
    counts = _pet_counts(vp)
    if not counts:
        return "なし"
    parts = []
    for pid, n in counts.items():
        p = V.PETS.get(pid, {})
        parts.append(f"{p.get('emoji','🐾')} {p.get('name', pid)}" + (f"×{n}" if n > 1 else ""))
    return " / ".join(parts) if parts else "なし"

def _pet_effect_line(vp):
    counts = _pet_counts(vp)
    effects = []
    h = counts.get("pet_hamster", 0)
    if h:
        effects.append(f"🐹 探索ごとHP{3*h}%回復")
    pairs = min(counts.get("pet_dog", 0), counts.get("pet_cat", 0))
    if pairs:
        effects.append(f"🐶🐱 2探索ごとHP{3*pairs}%回復")
    return " / ".join(effects) if effects else "なし"

def _active_voyage_buffs_line(vp):
    buffs = vp.get("voyage_buffs", {}) or {}
    bmeta = {
        "smoke_bomb": "💨煙玉",
        "lucky_charm": "🍀幸運",
        "old_map": "🗺️地図",
        "lantern": "🔦ランタン",
        "gold_compass": "🧭羅針盤",
    }
    lines = []
    for k in ("smoke_bomb", "lucky_charm", "old_map", "lantern", "gold_compass"):
        v = int(buffs.get(k, 0) or 0)
        if v > 0:
            unit = "回避" if k == "smoke_bomb" else "探索"
            lines.append(f"{bmeta.get(k,k)} 残り{v}{unit}")
    return " / ".join(lines)

def _apply_voyage_pet_effects(vp):
    """航海探索開始ごとのペット効果。複数所持は複数ぶん発動する。"""
    notes = []
    counts = _pet_counts(vp)
    mh = max_hp(vp)

    hamster_count = counts.get("pet_hamster", 0)
    if hamster_count > 0:
        cur = max(0, min(mh, vp.get("cur_hp", mh)))
        if cur < mh:
            heal = max(1, int(mh * 0.03)) * hamster_count
            before = cur
            vp["cur_hp"] = min(mh, cur + heal)
            suffix = f"×{hamster_count}" if hamster_count > 1 else ""
            notes.append(f"🐹 ハムスター{suffix}が癒してくれた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）")

    pair_count = min(counts.get("pet_dog", 0), counts.get("pet_cat", 0))
    if pair_count > 0:
        step = int(vp.get("voyage_pet_steps", 0)) + 1
        vp["voyage_pet_steps"] = step
        if step % 2 == 0:
            cur = max(0, min(mh, vp.get("cur_hp", mh)))
            if cur < mh:
                heal = max(1, int(mh * 0.03)) * pair_count
                before = cur
                vp["cur_hp"] = min(mh, cur + heal)
                suffix = f"×{pair_count}" if pair_count > 1 else ""
                notes.append(f"🐶🐱 犬と猫{suffix}が寄り添ってくれた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）")
    return "\n".join(notes) if notes else None

def _apply_hamster_voyage_heal(vp):
    """互換用。現在は全ペット効果をここで処理する。"""
    return _apply_voyage_pet_effects(vp)

def equipped_inst(vp, part):
    """装備中インスタンス {"item":id,"skills":[...]} を返す（未装備=None）。"""
    idx = vp["equipped"].get(part)
    lst = vp["inventory"].get(part, [])
    if idx is None or not (0 <= idx < len(lst)):
        return None
    return lst[idx]

def _level_stat_bonus(level):
    """Lv10以降は成長を緩やかにして、装備更新の価値を上げる。
    Lv1〜9: +2/Lv、Lv10以降: +1/Lv。
    """
    lv = max(1, int(level or 1))
    return 2 * lv if lv <= 9 else 18 + (lv - 9)

def attack_power(vp):
    w = equipped_inst(vp, "weapon")
    base = V.WEAPONS[w["item"]]["power"] if (w and w["item"] in V.WEAPONS) else 0
    return _level_stat_bonus(vp.get("level", 1)) + base

def defense_power(vp):
    d = _level_stat_bonus(vp.get("level", 1))
    for part in ("torso", "legs"):
        it = equipped_inst(vp, part)
        if it and it["item"] in V.ARMOR_PARTS[part]["items"]:
            d += V.ARMOR_PARTS[part]["items"][it["item"]]["power"]
    return d

def personal_power(vp):
    return attack_power(vp) + defense_power(vp)

def win_prob(me, foe):
    k = V.COMBAT_K
    p = (me ** k) / ((me ** k) + (foe ** k)) if (me + foe) > 0 else 0.5
    lo, hi = V.COMBAT_WIN_CLAMP
    return max(lo, min(hi, p))

def can_enter_sea(vp, sea):
    sd = ship_def_of(vp)
    if not sd:
        return False
    return sd.get("sea_unlock", 1) >= V.SEAS[sea]["unlock_hull"]

def add_xp(vp, amount):
    """XPを加算しレベルアップ処理。レベルアップしたら True を返す。"""
    leveled = False
    vp["xp"] += amount
    while vp["level"] < V.LEVEL_MAX and vp["xp"] >= V.xp_to_next(vp["level"]):
        vp["xp"] -= V.xp_to_next(vp["level"])
        vp["level"] += 1
        leveled = True
    return leveled

def dura_bar(cur, mx, width=8):
    if mx <= 0:
        return "—"
    ratio = max(0.0, min(1.0, cur / mx))
    filled = round(width * ratio)
    mark = "🟩" if ratio > 0.5 else ("🟨" if ratio > 0.2 else "🟥")
    return mark * filled + "⬛" * (width - filled)

def repair_cost(vp):
    """全船装備を満タンに戻すのに必要なコイン。"""
    cost = 0
    for part in ("cannon", "armor", "rigging"):
        inst = ship_part_inst(vp, part)
        pdef = ship_part_def(vp, part)
        if inst and pdef:
            mx = pdef.get("dura", 0)
            cost += max(0, mx - inst.get("dura", mx)) * V.SHIP_REPAIR_PER_DURA
    return cost

def any_part_broken(vp):
    """船装備のどれかが耐久0なら True（出航不可）。"""
    for part in ("cannon", "armor", "rigging"):
        inst = ship_part_inst(vp, part)
        if inst and inst.get("dura", 1) <= 0:
            return True
    return False

# ⛵ 航海報酬のナトコイン倍率。
# 以前は 1/3 でかなり渋く、初期船の満タン給油（約19,800）に対して
# E1周回の期待値が低すぎたため、入口海域でも燃料代を回収しやすい水準へ補正。
VOYAGE_COIN_REWARD_MULT = 0.70

def _scaled(rng, vm):
    return int(random.uniform(rng["base_min"], rng["base_max"]) * vm * VOYAGE_COIN_REWARD_MULT)

def _coin_bonus_from_vm(vp, vm):
    """報酬用vmから、海域/エリア倍率を除いた探索アイテム等のコイン倍率だけを取り出す。
    例: 黄金の羅針盤中なら 1.6。魚の売値など、エリア別に値付け済みの報酬へ使う。
    """
    try:
        v = vp.get("voyage") or {}
        sea = v.get("sea")
        area = area_of(v)
        base_vm = float(V.SEAS[sea]["val_mult"] * V.AREA_MULT[area])
        if base_vm <= 0:
            return 1.0
        return max(0.0, float(vm) / base_vm)
    except Exception:
        return 1.0

def _apply_voyage_coin_bonus_to_roll(roll, coin_bonus):
    """航海釣りなどの個別売値に、羅針盤などのコイン倍率を反映する。
    roll は表示にも使うため value をここで更新しておく。
    """
    try:
        bonus = float(coin_bonus)
    except Exception:
        bonus = 1.0
    if bonus and abs(bonus - 1.0) > 0.001 and int(roll.get("value", 0)) > 0:
        roll["value"] = max(1, int(int(roll.get("value", 0)) * bonus))
        roll["coin_bonus"] = bonus
    return roll

# ⚔️ 海戦・白兵戦の撃破報酬倍率。E1の燃料代負けを緩和しつつ、E2〜E4も同じ比率で底上げ。
NAVAL_COMBAT_REWARD_MULT = 1.25

# ━━━ 🎣 海の釣り（航海専用の竿のみ／演出＝魚影の時だけ／回数制限）━━━
#   レア度＝エリア依存（VOYAGE_FISH_RARITY）。リール/ラインは無効だが金冠（基礎確率）は健在。竿は永久。
def roll_voyage_fish(uid, area, mode="normal"):
    """エリアでレア度→エリアで魚種&売値→金冠（基礎確率のみ）。結果dictを返す。
    mode='rumor' で伝説が出やすい特別テーブルを使う。"""
    from config import RARITY_COLORS, GOLDEN_CROWN_CHANCE
    from cogs.fishing import pick_effect_by_rarity
    rarity = V.voyage_fish_rarity_pick(area, mode)
    pool = V.voyage_fish_pool(area, rarity)
    fish = random.choice(pool)
    value = int(fish["value"] * VOYAGE_COIN_REWARD_MULT)
    # 👑 金冠（基礎確率のみ＝リール/ラインは海の釣りでは効かない）。trash対象外・売値2倍
    is_golden = (rarity != "trash" and value > 0) and (random.random() < GOLDEN_CROWN_CHANCE)
    if is_golden:
        value *= 2
    eff_key, eff_text = pick_effect_by_rarity(rarity)
    return {"fish": fish, "rarity": rarity, "value": value, "is_golden": is_golden,
            "effect_key": eff_key, "effect_text": eff_text,
            "color": RARITY_COLORS.get(rarity, 0x1abc9c)}

VOYAGE_RARITY_LABEL = {
    "trash":"🗑️ ごみ", "common":"🐟 コモン", "uncommon":"🐠 アンコモン",
    "rare":"✨ レア", "super_rare":"💎 スーパーレア", "legend":"🌈 レジェンド",
}

def record_voyage_catch(uid, area, roll):
    """釣果を図鑑に記録。戻り値: (is_new, new_crown)。
    魚=voyage_fish_{area} / ごみ=voyage_fish_{area}_trash / 金冠=同キーのcrown表。"""
    fish = roll["fish"]
    if roll["rarity"] == "trash":
        return db.add_zukan(uid, f"voyage_fish_{area}_trash", fish["name"]), False
    is_new = db.add_zukan(uid, f"voyage_fish_{area}", fish["name"])
    new_crown = db.add_crown(uid, f"voyage_fish_{area}", fish["name"]) if roll["is_golden"] else False
    return is_new, new_crown

def check_voyage_fish_complete(uid, gid, area):
    """エリアの非ごみ魚を全種そろえたら、一度だけコンプ報酬を銀行に入金。
    戻り値: 報酬額（0=未コンプ or 受領済み）。"""
    need = V.voyage_fish_names(area)
    if not need:
        return 0
    got = set(db.get_zukan(uid, f"voyage_fish_{area}"))
    if not need <= got:
        return 0
    # 受領済みフラグ（zukanの一意制約を流用）
    first = db.add_zukan(uid, "voyage_fish_complete", f"area{area}")
    if not first:
        return 0
    reward = int(V.VOYAGE_FISH_COMPLETE_REWARD.get(area, 0) * VOYAGE_COIN_REWARD_MULT)
    if reward > 0:
        db.update_balance(uid, gid, reward)
    return reward

def voyage_catch_body(roll, is_new, new_crown, complete_reward=0):
    """釣果の結果テキスト（フレーバー＋魚名＋売値＋金冠＋NEW＋コンプ報酬）を組む。"""
    fish = roll["fish"]; rar = roll["rarity"]
    if rar == "trash":
        if roll["value"] > 0:
            body = (f"{fish['emoji']} **{fish['name']}** を引き上げた…サルベージ価値あり\n"
                    f"船倉に **+{roll['value']:,}**")
        else:
            body = f"{fish['emoji']} **{fish['name']}**…ハズレだ。船倉に入れるものは無かった。"
    else:
        crown = "👑 **金冠！** " if roll["is_golden"] else ""
        body = (f"{crown}{fish['emoji']} **{fish['name']}**（{VOYAGE_RARITY_LABEL[rar]}）\n"
                f"船倉に **+{roll['value']:,}**")
    if is_new and rar != "trash":
        body += "\n🏆 **海洋図鑑に新規登録！**"
    if new_crown:
        body += "\n✨ **金冠コンプに新規登録！**"
    if complete_reward > 0:
        body += f"\n✨🏆 **このエリアの魚をコンプリート！ 報酬 +{complete_reward:,} ナトコイン（銀行へ）**"
    return body

# ── エリア進行ヘルパ ──
def area_of(v):
    return v.get("area", 1)

def explores_done(v):
    return v.get("explores", 0)

def shards_of(vp):
    """🧭 特殊ポーチのカケラ数（永続・全損でも残る）。"""
    return vp.get("shards", 0)

# ━━━ ⚖️ カルマ（Phase2・基盤）━━━
def karma_of(vp):
    return vp.get("karma", 0)

def adjust_karma(vp, delta):
    """カルマを増減（上下限クランプ）。イベントの選択結果から呼ぶ窓口。戻り値=新カルマ。"""
    k = max(V.KARMA_MIN, min(V.KARMA_MAX, vp.get("karma", 0) + delta))
    vp["karma"] = k
    return k

def karma_tier_of(vp):
    return V.karma_tier(karma_of(vp))

def karma_badge(vp):
    """表示用バッジ：😇 善 (+45) のような文字列。"""
    k = karma_of(vp); m = V.KARMA_TIER_META[V.karma_tier(k)]
    sign = f"+{k}" if k > 0 else f"{k}"
    return f"{m['emoji']} {m['label']} ({sign})"

def apply_event_effects(vp, effects, vm=1.0):
    """イベント選択の effects を vp に適用。戻り値=(結果テキスト, combatキー or None)。"""
    # カルマ帯で結果分岐（karma_branch があれば上書きマージ）
    if "karma_branch" in effects:
        tier = karma_tier_of(vp)
        branch = effects["karma_branch"].get(tier, {})
        base = {k: val for k, val in effects.items() if k != "karma_branch"}
        effects = {**base, **branch}
    v = vp.get("voyage") or {}
    if effects.get("text_pool"):
        parts = [random.choice(effects["text_pool"])]
    elif effects.get("text"):
        parts = [effects["text"]]
    else:
        parts = []
    extra = []
    if effects.get("karma"):
        adjust_karma(vp, effects["karma"]); d = effects["karma"]
        extra.append(f"⚖️ カルマ {'+' if d > 0 else ''}{d}")
    if "coins" in effects:
        lo, hi = effects["coins"]
        if lo >= 0 and hi >= 0:
            amt = int(random.uniform(lo, hi) * vm * VOYAGE_COIN_REWARD_MULT); v["hold"] = v.get("hold", 0) + amt
            if amt: extra.append(f"📦 船倉 +{amt:,}")
        else:
            amt = int(random.uniform(lo, hi)); v["hold"] = max(0, v.get("hold", 0) + amt)
            if amt: extra.append(f"💸 {amt:,}")
    if effects.get("hp"):
        mh = max_hp(vp); floor = effects.get("hp_min", 0)
        vp["cur_hp"] = max(floor, min(mh, vp.get("cur_hp", mh) + effects["hp"]))
        extra.append(f"❤️ HP {'+' if effects['hp'] > 0 else ''}{effects['hp']}")
    if effects.get("ship_hp"):
        mh = max_hp(vp); vp["cur_hp"] = max(0, min(mh, vp.get("cur_hp", mh) + effects["ship_hp"]))
        extra.append(f"🚢 船体 {'+' if effects['ship_hp'] > 0 else ''}{effects['ship_hp']}")
    if effects.get("fuel"):
        before_fuel = v.get("fuel", 0)
        maxf = ship_max_fuel(vp)
        v["fuel"] = max(0, min(maxf, before_fuel + effects["fuel"]))
        delta_fuel = v["fuel"] - before_fuel
        if delta_fuel:
            extra.append(f"⛽ {'+' if delta_fuel > 0 else ''}{delta_fuel:,}")
    if effects.get("flag"):
        v.setdefault("flags", []).append(effects["flag"])
    if effects.get("shard"):
        if vp.get("shards", 0) < V.SHARD_NEEDED:
            vp["shards"] = vp.get("shards", 0) + 1
            got = vp["shards"]
            if got >= V.SHARD_NEEDED:
                extra.append(f"🧭 カケラ {got}/{V.SHARD_NEEDED} ✨ **最深部への道が開いた！**")
            else:
                extra.append(f"🧭 カケラ {got}/{V.SHARD_NEEDED}")
    # ⚒️ 選択肢イベント専用の素材入手機会。
    # 通常探索・敵ドロップ・発見系の全体供給率は触らず、
    # 「選択した時だけ素材が混じる」体感を増やすための別枠。
    craft = effects.get("craft")
    if craft and hasattr(V, "roll_craft_material"):
        area = int((v or {}).get("area", 1) or 1)
        chance = float(craft.get("chance", 1.0))
        rolls = int(craft.get("rolls", 1))
        bonus = float(craft.get("bonus", 1.0))
        amount = craft.get("amount", 1)
        got_lines = []
        for _ in range(max(0, rolls)):
            if random.random() <= chance:
                cmid = V.roll_craft_material("voyage", area, bonus=bonus)
                if cmid:
                    n = random.randint(int(amount[0]), int(amount[1])) if isinstance(amount, (list, tuple)) else int(amount)
                    got = _add_craft_material(None, vp, cmid, n)
                    if got:
                        got_lines.append(got + (f" ×{n}" if n > 1 else ""))
        if got_lines:
            extra.append("⚒️ " + " / ".join(got_lines))
    txt = "\n".join(parts)
    if extra:
        txt += "\n\n" + "　".join(extra)
    return txt, effects.get("combat"), effects.get("fish_school")

def can_advance(v, shards=0):
    """次エリアへ進めるか（探索10回＋エリア3→4はカケラ条件）。shards=特殊ポーチの永続カケラ数。"""
    if explores_done(v) < V.EXPLORE_TO_ADVANCE:
        return False
    if area_of(v) >= V.AREA_MAX:
        return False
    if area_of(v) == 3 and shards < V.SHARD_NEEDED:
        return False
    return True

def _try_shard(vp, key):
    """エリア3でのみ薄い確率でカケラ発見。特殊ポーチ(vp['shards']・永続)へ加算。"""
    v = vp.get("voyage") or {}
    if area_of(v) != 3:
        return ""
    # 3個揃ったら以降は拾わない（無限蓄積を防ぐ）
    if vp.get("shards", 0) >= V.SHARD_NEEDED:
        return ""
    if random.random() < V.SHARD_DROP.get(key, 0):
        vp["shards"] = vp.get("shards", 0) + 1
        got = vp["shards"]
        if got >= V.SHARD_NEEDED:
            return f"\n　{V.SHARD_NAME} 発見！（{got}/{V.SHARD_NEEDED}）✨ **最深部への道が開いた！**"
        return f"\n　{V.SHARD_NAME} 発見！（{got}/{V.SHARD_NEEDED}）"
    return ""

# ━━━ 🔍 探索の演出テキスト（ウェイト＆平穏）━━━
# 探索中のウェイト文（結果が出る前なので中立。何種類かをランダムに）
EXPLORE_WAITS = [
    "🔭 望遠鏡で水平線をなぞる……何が出る？",
    "🧭 羅針盤を片手に、波間へ目を凝らす……",
    "👀 見張り台から、海の先を探っていく……",
    "🪶 海鳥の行方を追って、静かに舵を切る……",
    "🌫️ 潮の匂いが、少し変わった気がする……",
    "🌊 帆をたわませる風に乗って、舳先を進める……",
    "🗺️ 海図にない海域へ、ゆっくりと分け入っていく……",
]
def explore_wait_text():
    return random.choice(EXPLORE_WAITS)

# ━━━ 🔍 探索（そのエリアを探る＝遭遇抽選）━━━
# 戦闘以外は vp を直接更新して ("text", msg) を返す。
# 海賊/ボスは ("combat", spec, scale, vm, is_boss) を返し、呼び出し側が
# NavalEncounter で実コマンド戦に入る（船倉の増減は戦闘側で精算）。
def roll_explore(vp):
    """探索を1回。探索カウント+1・航海消耗を適用し、遭遇を抽選して結果を返す。"""
    v = vp["voyage"]
    sea = v["sea"]; s = V.SEAS[sea]
    area = area_of(v); amult = V.AREA_MULT[area]
    vm = s["val_mult"] * amult            # 報酬は海×エリア
    scale = s["danger"] * amult           # 敵強さ/危険度は海×エリア
    v["explores"] = v.get("explores", 0) + 1
    buffs = vp.setdefault("voyage_buffs", {})
    active_lucky = buffs.get("lucky_charm", 0) > 0
    active_map = buffs.get("old_map", 0) > 0
    active_lantern = buffs.get("lantern", 0) > 0
    active_gold = buffs.get("gold_compass", 0) > 0
    # 🧭 黄金の羅針盤：海探索でも「船倉コイン系報酬」に反映する。
    # choiceイベント/敵撃破報酬は vm を通じて精算されるため、ここで報酬用倍率を分ける。
    reward_vm = vm * (1.6 if active_gold else 1.0)
    for _bk in ("lucky_charm", "old_map", "lantern", "gold_compass"):
        if buffs.get(_bk, 0) > 0:
            buffs[_bk] -= 1
            if buffs[_bk] <= 0:
                del buffs[_bk]
    for part in ("cannon", "armor"):
        inst = vp["ship_parts"].get(part)
        if inst:
            inst["dura"] = max(0, inst.get("dura", 0) - V.SAIL_DURA_COST)

    # 🗺️ 宝の地図の「次の探索で必ずあたり」フラグを消化：島の財宝を確定で出す
    flags = v.setdefault("flags", [])
    if "treasure_lead" in flags:
        flags.remove("treasure_lead")
        val = _scaled(V.ISLAND_TREASURE, reward_vm)
        return ("discover", {
            "kind": "island", "emoji": "🗺️", "title": "地図の×印",
            "flavor": "海図の×印の場所に着いた。波の下に、何かが沈んでいる――潜ってみるか？",
            "take_label": "🤿 引き上げる", "skip_label": "⛵ 見送る",
            "reward": val, "xp": V.XP_PER_ISLAND, "shard": "island",
            "take_text": f"泥にまみれた箱を引き上げ、こじ開けた。**地図は、本物だった！** 船倉に **+{val:,}**",
            "skip_text": "せっかくの印だが…見送って、先を急いだ。",
        })

    # 🎲 統合抽選：既存エンカウント(fish/island/pirate/boss/maelstrom/abyss)と
    #   イベント(choice/auto)を1つのプールにまとめて1回で抽選。
    base = V.AREA_ENCOUNTERS[area]
    pool_keys = list(base.keys()); pool_wts = list(base.values())
    for i, k in enumerate(pool_keys):
        if active_lantern and k == "calm":
            pool_wts[i] = max(0.1, pool_wts[i] * 0.25)
        if active_lucky and k in ("fish", "island", "maelstrom", "abyss", "boss"):
            pool_wts[i] *= 1.35
        if active_map and k in ("island", "maelstrom", "abyss"):
            pool_wts[i] *= 1.6
    for eid, w in VE.events_for_area(area):
        if active_map:
            w *= 1.8
        if active_lucky:
            w *= 1.15
        pool_keys.append(eid); pool_wts.append(w)
    enc = random.choices(pool_keys, weights=pool_wts)[0]
    BUILTIN = {"calm", "fish", "island", "maelstrom", "abyss", "boss", "pirate"}
    if enc not in BUILTIN:
        return ("choice", enc, reward_vm)

    if enc == "fish":
        # 🎣 魚影も平原式に「狙う/見送る」を選ばせる
        return ("choice", "builtin_fish_cue", reward_vm)
    if enc == "island":
        # 上陸後の中身はボタンを押した瞬間に抽選。
        # 無人島の出現率自体は変えず、「宝だけでなく伏兵/罠もある」設計にする。
        return ("discover", {
            "kind": "island", "emoji": "🏝️", "title": "無人島",
            "flavor": "水平線に、ぽつんと無人島が見えてきた。寄ってみるか？\n宝の匂いもするが、木陰の奥が妙に静かだ。",
            "take_label": "🏝️ 上陸する", "skip_label": "⛵ 通り過ぎる",
            "reward": 0, "xp": 0, "shard": "island",
            "island_landing_roll": True,
            "area": area, "scale": scale, "reward_vm": reward_vm,
            "skip_text": "島には寄らず、先を急いだ。",
        })
    if enc == "maelstrom":
        val = _scaled(V.MAELSTROM_REWARD, reward_vm)
        return ("discover", {
            "kind": "maelstrom", "emoji": "🌀", "title": "渦潮",
            "flavor": "前方に渦潮。中心に、何か漂流物が巻かれて光っている…突っ込むか？",
            "take_label": "🌀 突っ込む", "skip_label": "⚓ 避ける",
            "reward": val, "xp": 0, "shard": "maelstrom",
            "take_text": f"渦をうまく乗り切り、漂流物を回収！ 船倉に **+{val:,}**",
            "skip_text": "無理せず、渦を大きく迂回した。",
        })
    if enc == "abyss":
        val = _scaled(V.ABYSS_TREASURE, reward_vm)
        return ("discover", {
            "kind": "abyss", "emoji": "🕳️", "title": "光る海淵",
            "flavor": "海面の下に、ぼんやりと光る深い淵。何かが沈んでいる気配がする…覗くか？",
            "take_label": "🕳️ 覗き込む", "skip_label": "🚢 そっと離れる",
            "reward": val, "xp": 0, "shard": None,
            "take_text": f"吸い寄せられるように手を伸ばす…財宝を掴んだ！ 船倉に **+{val:,}**",
            "skip_text": "深淵から、そっと目を逸らした。何も起きなかった。",
        })
    if enc == "boss":
        spec = V.pick_boss(area)
        if spec is None:   # フォールバック（旧AREA_BOSS）
            spec = dict(V.AREA_BOSS[area]); spec["is_boss"] = True; spec["tier"] = V.BOSS_TIER.get(area, 4)
        return ("combat", spec, scale, reward_vm, True)
    # pirate枠＝エリアの敵プールから抽選（海賊・海獣・アンデッド・軍船・激レア）
    if vp.setdefault("voyage_buffs", {}).get("smoke_bomb", 0) > 0:
        vp["voyage_buffs"]["smoke_bomb"] -= 1
        if vp["voyage_buffs"]["smoke_bomb"] <= 0:
            del vp["voyage_buffs"]["smoke_bomb"]
        return ("text", "💨 煙玉の煙が海霧に紛れた。敵影をやり過ごした。")
    spec = V.pick_enemy(area)
    if spec is None:   # フォールバック（旧PIRATE_RANKS）
        spec = dict(random.choices(V.PIRATE_RANKS, weights=V.pirate_weights(sea, area))[0])
    return ("combat", spec, scale, reward_vm, spec.get("is_boss", False))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Embed ビルダー

# ── 🔍 発見→選択→結果 の演出フロー ──
VOYAGE_COL_NORMAL = 0x0f766e   # 通常航海（青緑）
VOYAGE_COL_CALM   = 0x4b5563   # 何もない・静か（鈍い灰）
VOYAGE_COL_EVENT  = 0xd4a017   # 発見・イベント（金）
VOYAGE_COL_FISH   = 0x1f6f8b   # 魚影（水色）
VOYAGE_COL_COMBAT = 0xd97706   # 戦闘気配（橙）
VOYAGE_COL_RARE   = 0xb91c1c   # ボス・危険（赤）
VOYAGE_COL_STORY  = 0x7c3aed   # 不穏・物語（紫）
VOYAGE_COL_MOVE   = 0x1e3a8a   # 海域移動（深青）

def _pad_voyage_note(note, min_lines=5):
    """航海UIの高さブレを抑えるため、本文行数をだいたい固定する。"""
    text = str(note or "")
    lines = text.splitlines() if text else []
    while len(lines) < min_lines:
        lines.append("\u200b")
    return "\n".join(lines)

def _emph(text):
    """航海の演出テキストを目立たせる：先頭行を見出し（大きい字）にする。"""
    if not text:
        return text
    parts = str(text).split("\n", 1)
    head = parts[0]
    if not head.startswith("## "):
        head = f"## {head}"
    return head + ("\n" + parts[1] if len(parts) > 1 else "")

def _voyage_theater_note(kind):
    table = {
        "calm":   (VOYAGE_COL_CALM,   "… 静かな海", "波は低く、帆だけが小さく鳴っている。\n今のところ、異変はない。"),
        "event":  (VOYAGE_COL_EVENT,  "## ✦ 何かを見つけた……", "水平線の向こうに、妙な影が見える。\n船を寄せるか、通り過ぎるか。"),
        "fish":   (VOYAGE_COL_FISH,   "## 🎣 水面がざわめく……", "船の下を、いくつもの魚影が横切った。\n竿先がかすかに震える。"),
        "combat": (VOYAGE_COL_COMBAT, "## ⚔️ 何かが近づいている……", "波音に紛れて、別の音が混じった。\n甲板に、緊張が走る。"),
        "rare":   (VOYAGE_COL_RARE,   "## ⚠️ 海が、重い。", "風が止んだ。\n水面の奥で、巨大な影が向きを変える。\n逃げるなら、今しかない。"),
        "story":  (VOYAGE_COL_STORY,  "## 🌑 不穏な気配", "海の匂いが、少し変わった。\nこの先に、ただの漂流物ではない何かがある。"),
        "move":   (VOYAGE_COL_MOVE,   "## ⛵ 船は進む……", "帆が風を孕み、船首が深い海へ向く。\n戻る海の色が、少しずつ遠ざかっていく。"),
        "reveal": (VOYAGE_COL_COMBAT, "## 🌊 息を殺す……", "揺れる影の輪郭を、じっと見極める。\n次の波で、正体が見える。"),
    }
    col, head, body = table.get(kind, table["event"])
    return col, _pad_voyage_note(f"{head}\n{body}", 5)

def _voyage_kind_for_result(res):
    try:
        if not res:
            return "event"
        if res[0] == "combat":
            spec = res[1]
            return "rare" if spec.get("is_boss") or int(spec.get("stars", 1)) >= 4 else "combat"
        if res[0] == "fish_cue":
            return "fish"
        if res[0] in ("choice", "discover"):
            return "event"
        return "calm"
    except Exception:
        return "event"

def build_discover_embed(vp, payload):
    """『何かを見つけた』段階。航海中と同じ固定情報枠で見せる。"""
    return build_voyage_embed(
        vp, _emph(payload["flavor"]),
        title=f"{payload['emoji']} {payload['title']}",
        color=VOYAGE_COL_EVENT,
        footer="さあ、どうする？")

def build_result_embed(vp, body, title="🌊 結果"):
    """報酬確定の『結果』段階。航海中と同じ固定情報枠で見せる。
    釣り/探索/結果のEmbed高さがガタつかないよう、結果本文は少し大きめに固定する。
    """
    return build_voyage_embed(vp, _pad_voyage_note(_emph(body), 8), title=title, color=0xf1c40f)

def build_voyage_theater_embed(vp, kind):
    col, note = _voyage_theater_note(kind)
    return build_voyage_embed(vp, note, color=col)

class DiscoverView(discord.ui.View):
    """発見に対して『漁る／無視』を選ばせる。選んで初めて報酬が確定。"""
    def __init__(self, uid, gid, payload):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.payload = payload
        tb = discord.ui.Button(label=payload["take_label"], style=discord.ButtonStyle.success)
        sb = discord.ui.Button(label=payload["skip_label"], style=discord.ButtonStyle.secondary)
        tb.callback = self._take; sb.callback = self._skip
        self.add_item(tb); self.add_item(sb)
    async def _take(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid); v = vp["voyage"]; p = self.payload

        # 🏝️ 無人島：上陸してから宝/空振り/伏兵/罠を抽選する。
        # 出現率は変えず、良イベント一辺倒にならないようにする。
        if p.get("island_landing_roll"):
            outcome = V.roll_island_landing()
            area = int(p.get("area") or v.get("area") or 1)
            scale = p.get("scale", 1.0)
            vm = p.get("reward_vm", 1.0)
            if outcome == "treasure":
                val = _scaled(V.ISLAND_TREASURE, vm)
                v["hold"] += val
                add_xp(vp, V.XP_PER_ISLAND)
                stxt = _try_shard(vp, "island")
                drop = _discover_drop(self.uid, vp, "island")
                db.save_voyage(self.uid, vp)
                await it.response.edit_message(
                    embed=build_result_embed(vp, f"🏝️ 島を歩き回ると…**お宝発見！** 船倉に **+{val:,}**{stxt}{drop}"),
                    view=ContinueVoyageView(self.uid, self.gid, ""))
                return
            if outcome == "empty":
                db.save_voyage(self.uid, vp)
                await it.response.edit_message(
                    embed=build_result_embed(vp, "🏝️ 島を歩き回ったが…めぼしい物は無かった。波の音だけが妙に大きい。"),
                    view=ContinueVoyageView(self.uid, self.gid, ""))
                return
            if outcome == "penalty":
                mh = max_hp(vp)
                hp_before = vp.get("cur_hp", mh)
                fuel_before = vp.get("fuel_tank", 0)
                hp_loss = max(1, int(max(1, hp_before) * V.ISLAND_PENALTY_HP_PCT))
                fuel_loss = max(100, int(max(0, fuel_before) * V.ISLAND_PENALTY_FUEL_PCT))
                vp["cur_hp"] = max(1, hp_before - hp_loss)
                vp["fuel_tank"] = max(0, fuel_before - fuel_loss)
                db.save_voyage(self.uid, vp)
                await it.response.edit_message(
                    embed=build_result_embed(
                        vp,
                        f"🏝️ 茂みの奥で古い罠が弾けた！\n❤️ HP **-{hp_before - vp['cur_hp']}** ／ ⛽ 燃料 **-{fuel_before - vp['fuel_tank']:,}**"),
                    view=ContinueVoyageView(self.uid, self.gid, ""))
                return
            # ambush
            spec = V.pick_enemy(area)
            if spec is None:
                spec = dict(random.choice(V.PIRATE_RANKS))
            spec = dict(spec)
            spec["name"] = "島影の伏兵・" + spec.get("name", "海賊")
            spec["flavor"] = "無人島に潜んでいた伏兵。宝を漁る獲物を待っていた。"
            db.save_voyage(self.uid, vp)
            await it.response.edit_message(
                embed=build_result_embed(vp, f"🏝️ 宝箱に手を伸ばした瞬間、木陰から殺気。\n⚔️ **{spec['name']}** が飛び出してきた！", title="⚠️ 伏兵！"),
                view=ProceedCombatView(self.uid, self.gid, spec, scale, vm, spec.get("is_boss", False)))
            return

        v["hold"] += p["reward"]
        if p.get("xp"): add_xp(vp, p["xp"])
        stxt = _try_shard(vp, p["shard"]) if p.get("shard") else ""
        drop = _discover_drop(self.uid, vp, p["kind"])   # 🍖⛽ 発見ドロップ
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_result_embed(vp, f"{p['emoji']} {p['take_text']}{stxt}{drop}"),
            view=ContinueVoyageView(self.uid, self.gid, ""))
    async def _skip(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        p = self.payload
        await it.response.edit_message(
            embed=build_result_embed(db.get_voyage(self.uid), f"{p['emoji']} {p['skip_text']}"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

# ━━━ 🎣 海の釣り（演出＝魚影。伝説の釣り竿のみ／演出ごとに回数制限）━━━
# 🎣 魚影が現れた時の導入演出（バリエーション）。深い海域(E3+)はえぐみのある変種も混ぜる。
FISH_CUE_INTROS = [
    "🐟 海面に、魚の群れが現れた――航海の竿が、かすかに震える。\n群れが去る前に、糸を垂らせ。",
    "🌊 水面が、無数の背びれでざわめいた。大きな群れだ。\n今だ、糸を垂らせ。",
    "🐟 きらめく魚影が、船の周りを回遊しはじめた。\n竿が手に馴染む――やるなら今。",
    "🎣 凪いだ海に、ふいに当たりの気配。群れが寄ってきている。\n逃がすな。",
    "🌊 海中を、ぼんやりとした群れの影が、ゆっくり船の下を横切っていく。\n糸を垂らせ。",
    "🐟 ぱしゃり、と魚が跳ねた。続いて、もう一匹。……群れが来ている。\n今だ。",
]
FISH_CUE_INTROS_DEEP = [   # E3 暗い海 / E4 虚海 のえぐみ
    "🌑 光の届かぬ水底で、何かの群れがうごめいている。\n竿先が、ひとりでに震えた。",
    "👁️ 海面の下、いくつもの淡い光が、こちらを見上げている。\n……糸を、垂らすか。",
    "🌌 黒い水の中を、形にならない群れが流れていく。\nそれを“魚”と呼んでいいのかは、分からない。",
]
def fish_cue_intro(area):
    pool = FISH_CUE_INTROS + (FISH_CUE_INTROS_DEEP if area >= 3 else [])
    return random.choice(pool)

def build_fish_school_embed(vp, remaining, total, note=""):
    """魚影演出。あと何回釣れるかを表示。note=直前の釣果。"""
    v = vp.get("voyage") or {}; area = area_of(v)
    desc = (note + "\n\n") if note else fish_cue_intro(area)
    e = discord.Embed(title="🎣 魚の群れ", description=desc, color=0x1f6f8b)
    e.add_field(name="🎣 残り", value=f"あと **{remaining}/{total}** 回", inline=True)
    e.add_field(name="📦 船倉（未確定）", value=f"**{v.get('hold',0):,}**", inline=True)
    e.add_field(name="🗺️ 海域", value=f"{V.AREA_EMOJI[area]} {V.AREA_NAMES[area]}", inline=True)
    e.set_footer(text="群れは、いつまでも待ってはくれない")
    return e

def build_fish_monster_embed(vp, spec):
    """魚影だと思ったら怪物だった――の急襲演出。"""
    name = spec.get("name", "何か"); st = "★" * int(spec.get("stars", 1))
    body = (f"🎣 糸を垂らした、その時――\n"
            f"水面が爆ぜた。掛かったのは、魚じゃない。\n"
            f"**{name}** だ！ {st}\n\n"
            "戦うか、逃げるか――今すぐ選べ。")
    return build_result_embed(vp, body, title="🌊 魚影の正体")

class FishingSchoolView(discord.ui.View):
    """魚影演出のミニ釣りループ。回数ぶん釣る／いつでも切り上げ可。mode='rumor'で伝説出やすい。"""
    def __init__(self, uid, gid, area, remaining, total, mode="normal", legend_hit=False, coin_bonus=1.0):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.area = area; self.remaining = remaining; self.total = total; self.mode = mode
        self.legend_hit = bool(legend_hit)
        try:
            self.coin_bonus = float(coin_bonus)
        except Exception:
            self.coin_bonus = 1.0
    async def _guard(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return False
        return True

    @discord.ui.button(label="🎣 釣る", style=discord.ButtonStyle.primary)
    async def cast(self, it, button):
        if not await self._guard(it): return
        from config import SUSPENSE_COLOR, FISHING_WAIT_NORMAL, FISHING_WAIT_SUPER
        from cogs import fish_assets as FA
        roll = _apply_voyage_coin_bonus_to_roll(roll_voyage_fish(self.uid, self.area, self.mode), self.coin_bonus)
        # 当たり待ち：通常の釣り演出（情景画像＋中立色）を航海釣りにも流用
        wait = FISHING_WAIT_SUPER if roll["rarity"] in ("super_rare", "legend") else FISHING_WAIT_NORMAL
        wait_embed = discord.Embed(color=SUSPENSE_COLOR)
        wait_embed.set_footer(text=f"{V.AREA_EMOJI.get(self.area, '🌊')} {V.AREA_NAMES.get(self.area, '海')}")
        scene = FA.scene_url(roll.get("effect_key"))
        if scene:
            wait_embed.set_image(url=scene)
        else:
            wait_embed.description = roll.get("effect_text") or "🎣 糸を垂らす……"
        await it.response.edit_message(embed=wait_embed, view=VoyageTheaterView(self.uid, self.gid))
        await asyncio.sleep(wait)
        if roll["rarity"] in ("super_rare", "legend"):
            shadow_embed = discord.Embed(color=SUSPENSE_COLOR)
            shadow_embed.set_image(url=FA.shadow_url())
            shadow_embed.set_footer(text=f"{V.AREA_EMOJI.get(self.area, '🌊')} {V.AREA_NAMES.get(self.area, '海')}")
            await it.edit_original_response(embed=shadow_embed, view=VoyageTheaterView(self.uid, self.gid))
            from config import FISHING_SHADOW_WAIT
            await asyncio.sleep(FISHING_SHADOW_WAIT)
        # 結果確定
        vp = db.get_voyage(self.uid); v = vp["voyage"]
        v["hold"] += roll["value"]
        shard = _try_shard(vp, "fish")           # E3はカケラドロップ
        add_xp(vp, V.XP_PER_FISH)
        is_new, new_crown = record_voyage_catch(self.uid, self.area, roll)
        comp = check_voyage_fish_complete(self.uid, self.gid, self.area)   # 🏆 コンプ報酬
        db.save_voyage(self.uid, vp)
        remaining = self.remaining - 1
        body = voyage_catch_body(roll, is_new, new_crown, comp) + shard
        if remaining <= 0:
            legend_hit = self.legend_hit or (roll.get("rarity") == "legend")
            tail = ("\n\n🌈 噂は、本物だった――群れは静かに、深みへ帰っていった。" if self.mode == "rumor" and legend_hit
                    else ("\n\n🌫️ 噂ほどではなかった。群れは静かに、深みへ帰っていった。" if self.mode == "rumor"
                          else "\n\n🐟 群れは、ゆっくりと深みへ去っていった。"))
            e = build_result_embed(vp, body + tail)
            e.color = roll["color"]
            await it.edit_original_response(embed=e, view=ContinueVoyageView(self.uid, self.gid, ""))
            return
        e = build_fish_school_embed(vp, remaining, self.total, body)
        e.color = roll["color"]
        await it.edit_original_response(
            embed=e, view=FishingSchoolView(self.uid, self.gid, self.area, remaining, self.total, self.mode, self.legend_hit or (roll.get("rarity") == "legend"), self.coin_bonus))

    @discord.ui.button(label="🚶 切り上げる", style=discord.ButtonStyle.secondary)
    async def leave(self, it, button):
        if not await self._guard(it): return
        await it.response.edit_message(
            embed=build_result_embed(db.get_voyage(self.uid),
                                     "🌊 群れを見送り、静かに先へ進んだ。"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

async def start_event_fishing(interaction, uid, gid, vp, fish_spec, intro, coin_bonus=1.0):
    """イベント結果から釣りを開始（ゴーシュ/伝説の噂など）。
    fish_spec例: {"casts":5, "mode":"rumor"}。竿が無ければ案内だけ。"""
    area = area_of(vp.get("voyage") or {})
    casts = int(fish_spec.get("casts", 3))
    mode = fish_spec.get("mode", "normal")
    if not vp.get("has_voyage_rod"):
        await interaction.edit_original_response(
            embed=build_result_embed(
                vp, intro + "\n\n――だが、**航海の釣り竿**を持っていない。\n"
                            "ドックで竿を仕立てれば、こういう時に活かせるのに……。"),
            view=ContinueVoyageView(uid, gid, ""))
        return
    e = build_fish_school_embed(vp, casts, casts, intro)
    await interaction.edit_original_response(
        embed=e, view=FishingSchoolView(uid, gid, area, casts, casts, mode, coin_bonus=coin_bonus))
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_port_embed(vp):
    if not vp["has_ship"]:
        return discord.Embed(
            title="⚓ 港 ── 造船所",
            description=("船はまだ無いようだな。\n"
                         f"**🚢 帆船**（☆2）を **{V.SHIPS['frigate']['price']:,}** ナトコインで仕立てれば、"
                         "未知の海へ漕ぎ出せる。\n（砲・装甲・艤装の部位に船装備を積んで戦う）"),
            color=0x16a085)
    lv_need = V.xp_to_next(vp["level"]) if vp["level"] < V.LEVEL_MAX else 0
    e = discord.Embed(title="⚓ 港 ── 母港", color=0x16a085,
                      description="航海の準備を整えよう。出航で船倉を満たし、引き返して入金だ。")
    e.add_field(name="🚢 船 攻/防",
                value=f"⚔️{ship_attack(vp)} 🛡️{ship_defense(vp)}", inline=True)
    e.add_field(name="❤️ 個人HP", value=f"{vp.get('cur_hp', max_hp(vp))}/{max_hp(vp)}", inline=True)
    e.add_field(name="🗡️ 個人 戦闘力", value=f"**{personal_power(vp)}**", inline=True)
    e.add_field(name="📊 レベル",
                value=f"Lv.**{vp['level']}**" + (f"（XP {vp['xp']}/{lv_need}）" if lv_need else "（MAX）"),
                inline=True)
    # ⚖️ カルマ ＋ 🧭 特殊ポーチ（永続ステータス）
    pouch = f"🧭 {shards_of(vp)}/{V.SHARD_NEEDED}" if shards_of(vp) > 0 else "🧭 0"
    e.add_field(name="⚖️ カルマ", value=karma_badge(vp), inline=True)
    e.add_field(name="🎒 特殊ポーチ", value=f"{pouch}", inline=True)
    # ⛽ 燃料タンク（給油した分だけ航海で進める）
    maxf = ship_max_fuel(vp); tank = vp.get("fuel_tank", 0)
    e.add_field(name="⛽ 燃料タンク", value=f"{tank:,}/{maxf:,}", inline=True)
    # 船の装備（部位）
    sd = ship_def_of(vp)
    eq = [f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']}"]
    for part in V.SHIP_PART_ORDER:
        meta = V.SHIP_PART_META[part]; inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
        if inst and pdef:
            eq.append(f"{meta['emoji']} {V.rarity_stars(pdef['rank'])} {pdef['name']}"
                      f"（{dura_bar(inst.get('dura',0), pdef.get('dura',1))}）")
        else:
            eq.append(f"{meta['emoji']} {meta['name']}：なし")
    # 🎣 釣り竿（船に付ける・永久。ドックで購入）
    if vp.get("has_voyage_rod"):
        eq.append(f"🎣 {V.VOYAGE_ROD_NAME}（✅ 装備中・永久）")
    else:
        eq.append(f"🎣 釣り竿：なし（ドックで {V.VOYAGE_ROD_PRICE:,}）")
    e.add_field(name="🚢 船の装備", value="\n".join(eq), inline=False)
    pe = []
    w = equipped_inst(vp, "weapon")
    if w and w["item"] in V.WEAPONS:
        wd = V.WEAPONS[w["item"]]; wt = V.WEAPON_TYPES[wd["wtype"]]
        pe.append(f"⚔️ {V.rarity_stars(wd['rank'])} {wd['name']}（{wt['name']}）")
    else:
        pe.append("⚔️ 武器：なし")
    for part in V.ARMOR_PART_ORDER:
        info = V.ARMOR_PARTS[part]; it = equipped_inst(vp, part)
        if it and it["item"] in info["items"]:
            idd = info["items"][it["item"]]
            pe.append(f"{info['emoji']} {V.rarity_stars(idd['rank'])} {idd['name']}")
        else:
            pe.append(f"{info['emoji']} {info['name']}：なし")
    e.add_field(name="🧍 個人の装備", value="\n".join(pe), inline=False)
    return e

def build_voyage_embed(vp, last_msg=None, title=None, color=None, footer=None):
    v = vp["voyage"]; s = V.SEAS[v["sea"]]
    area = area_of(v); ex = explores_done(v)
    desc = _pad_voyage_note(last_msg or s["flavor"], 5)
    e = discord.Embed(
        title=title or f"{s['name']} ── 航海中",
        description=desc, color=color if color is not None else VOYAGE_COL_NORMAL)
    e.add_field(name="🗺️ エリア",
                value=f"{V.AREA_EMOJI[area]} **{area} {V.AREA_NAMES[area]}**", inline=True)
    prog = min(ex, V.EXPLORE_TO_ADVANCE)
    if area < V.AREA_MAX:
        e.add_field(name="🔍 探索",
                    value=f"{prog}/{V.EXPLORE_TO_ADVANCE}" + ("　⛵進める！" if can_advance(v, shards_of(vp)) else ""),
                    inline=True)
    else:
        e.add_field(name="🔍 探索回数", value=f"{ex}", inline=True)
    e.add_field(name="📦 船倉（未確定）", value=f"**{v['hold']:,}**", inline=True)
    # 🧭 カケラ＝特殊ポーチ（永続）。1個でも持っていれば常時表示
    sh = shards_of(vp)
    if area == 3 or sh > 0:
        tag = ""
        if sh >= V.SHARD_NEEDED:
            tag = "　✨ 最深部へ進める！"
        # カケラ詳細はネタバレ防止のため航海中UIでは非表示
    # ⛽ 燃料タンク（残量/容量＋バー＋次コスト）
    mxf = ship_max_fuel(vp)
    fuel = v.get("fuel", mxf)
    ecost = V.explore_fuel_cost(area)
    home_cost = _voyage_return_home_cost(area)
    fuel_line = f"{fuel:,}/{mxf:,}\n{hp_bar(fuel, mxf, 10)}\n🔍探索 -{ecost:,}／🏠帰港目安 -{home_cost:,}"
    if area < V.AREA_MAX:
        fuel_line += f"／⛵移動 -{V.move_fuel_cost(area+1):,}"
    e.add_field(name="⛽ 燃料", value=fuel_line, inline=True)
    cond = []
    for part in ("cannon", "armor"):
        inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
        if inst and pdef:
            cond.append(f"{V.SHIP_PART_META[part]['emoji']}{dura_bar(inst.get('dura',0), pdef.get('dura',1))}")
    e.add_field(name="🛠️ 船", value=" ".join(cond) if cond else "—", inline=True)
    mxhp = max_hp(vp); curhp = vp.get("cur_hp", mxhp)
    e.add_field(name="❤️ HP",
                value=f"{max(0,curhp)}/{mxhp}\n{hp_bar(curhp, mxhp, 10)}", inline=True)
    e.add_field(name="⚖️ カルマ", value=karma_badge(vp), inline=True)
    e.add_field(name="🐾 所持ペット", value=f"{_pet_line(vp)}\n効果：{_pet_effect_line(vp)}", inline=False)
    active_buffs = _active_voyage_buffs_line(vp)
    if active_buffs:
        e.add_field(name="✨ 発動中の探索アイテム", value=active_buffs, inline=False)
    e.set_footer(text=footer or "🔍探索＝その場を探る／⛵進む＝奥のエリアへ(探索10回)／⚓引き返す＝1つ手前へ")
    return e

def _voyage_return_step_cost(area: int) -> int:
    """現在エリアから1段戻る/帰港するための燃料。"""
    return V.explore_fuel_cost(max(1, int(area)))

def _voyage_return_home_cost(area: int) -> int:
    """現在エリアから港まで戻る総燃料。"""
    return sum(_voyage_return_step_cost(a) for a in range(1, max(1, int(area)) + 1))

def _reset_retreat_chain(vp):
    v = (vp or {}).get("voyage") or {}
    if v.get("retreat_chain"):
        v["retreat_chain"] = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 母港ハブ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class PortView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(self.user_id)
        if not vp["has_ship"]:
            self.add_item(BuyShipButton())
        else:
            self.add_item(SailButton())
            self.add_item(DockButton())
            self.add_item(ShopButton())
            self.add_item(OagButton())
            self.add_item(PortInvButton())
            self.add_item(PortPhoneButton())
        if str(user_id) in ADMIN_USER_IDS:
            self.add_item(MockCombatButton())
        self.add_item(LeaveButton())

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class BuyShipButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=f"🚢 帆船を仕立てる（{V.SHIPS['frigate']['price']:,}）", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        uid, gid = view.user_id, view.gid
        price = V.SHIPS["frigate"]["price"]
        if db.get_balance(uid, gid) < price:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{price:,} 必要）", ephemeral=True); return
        vp = db.get_voyage(uid)
        if vp["has_ship"]:
            await interaction.response.send_message("もう船を持っている", ephemeral=True); return
        db.update_balance(uid, gid, -price)
        vp["has_ship"] = True
        vp["fuel_tank"] = V.SHIPS["frigate"]["max_fuel"]   # ⛽ 初回サービスで満タン
        vp["ship"] = "frigate"
        vp["cur_hp"] = max_hp(vp)
        vp["ship_parts"] = {"cannon": None, "armor": None, "rigging": None}
        vp["ship_skills"] = []
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid))
        await interaction.followup.send("🚢 帆船（☆2）を仕立てた！ショップで砲と装甲を積もう。", ephemeral=True)

# ━━━ 🛠️ ドック（給油・食料・釣り竿をまとめる）━━━
def build_dock_embed(vp, uid, gid):
    maxf = ship_max_fuel(vp); tank = vp.get("fuel_tank", 0)
    rod = "✅ 仕立て済み" if vp.get("has_voyage_rod") else f"未所持（{V.VOYAGE_ROD_PRICE:,}）"
    e = discord.Embed(title="🛠️ ドック", color=0x16a085,
                      description="出航前の補給と仕立て。給油・食料の仕入れ・釣り竿の用意はここで。")
    e.add_field(name="💰 所持金", value=f"**{db.get_balance(uid, gid):,}** ナトコイン", inline=False)
    e.add_field(name="⛽ 燃料タンク", value=f"{tank:,}/{maxf:,}", inline=True)
    e.add_field(name="🎣 釣り竿", value=rod, inline=True)
    return e

class DockButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛠️ ドック", style=discord.ButtonStyle.primary)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        await interaction.response.edit_message(
            embed=build_dock_embed(db.get_voyage(view.user_id), view.user_id, view.gid),
            view=DockView(view.user_id, view.gid))

class DockView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.user_id = str(uid); self.gid = str(gid)
        self.add_item(RefuelButton())
        self.add_item(FoodShopButton())
        self.add_item(RodShopButton())
        self.add_item(DockBackButton())
    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class DockBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ 港へ戻る", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_port_embed(db.get_voyage(view.user_id)), view=PortView(view.user_id, view.gid))

def _back_to_dock(view):
    """給油などの後にドック画面へ戻すためのヘルパ。"""
    return build_dock_embed(db.get_voyage(view.user_id), view.user_id, view.gid), DockView(view.user_id, view.gid)

class RefuelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⛽ 給油", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view = self.view
        if not await view.guard(interaction): return
        await interaction.response.edit_message(embed=build_dock_embed(db.get_voyage(view.user_id), view.user_id, view.gid),
                                                view=RefuelView(view.user_id, view.gid))

class RefuelView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.user_id=str(uid); self.gid=str(gid)
        self.add_item(RefuelFullButton())
        self.add_item(RefuelAmountSelect(uid, gid))
        back=discord.ui.Button(label="◀ ドックへ戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(it):
            if str(it.user.id)!=self.user_id:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(embed=build_dock_embed(db.get_voyage(self.user_id), self.user_id, self.gid), view=DockView(self.user_id,self.gid))
        back.callback=_back; self.add_item(back)
    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return False
        return True

class RefuelFullButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⛽ 満タン", style=discord.ButtonStyle.success, row=0)
    async def callback(self, it):
        view=self.view
        if not await view.guard(it): return
        await _buy_fuel(it, view.user_id, view.gid, None)

class RefuelAmountSelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.user_id=str(uid); self.gid=str(gid)
        opts=[]
        for amount in (1000,3000,5000,10000,20000):
            opts.append(discord.SelectOption(label=f"{amount:,} 給油", value=str(amount), description=f"約 {int(amount*V.FUEL_PRICE_PER):,} コイン"))
        super().__init__(placeholder="数字で給油量を選ぶ", options=opts, row=1)
    async def callback(self, it):
        if str(it.user.id)!=self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await _buy_fuel(it, self.user_id, self.gid, int(self.values[0]))

async def _buy_fuel(interaction, uid, gid, amount):
    vp=db.get_voyage(uid); maxf=ship_max_fuel(vp); tank=vp.get('fuel_tank',0)
    need=max(0, maxf-tank)
    if need<=0:
        await interaction.response.send_message("⛽ タンクはもう満タンだ。", ephemeral=True); return
    buy=need if amount is None else min(int(amount), need)
    cost=int(buy*V.FUEL_PRICE_PER)
    if db.get_balance(uid,gid)<cost:
        await interaction.response.send_message(f"💰 コインが足りない（{cost:,} 必要）", ephemeral=True); return
    vp['fuel_tank']=tank+buy
    db.update_balance(uid,gid,-cost); db.save_voyage(uid,vp)
    await interaction.response.edit_message(embed=build_dock_embed(vp,uid,gid), view=DockView(uid,gid))
    await interaction.followup.send(f"⛽ {buy:,} 給油した（-{cost:,}）。", ephemeral=True)

def build_foodshop_embed(vp, uid, gid):
    e = discord.Embed(title="🍖 ドックの食料品店", color=0xe67e22,
                      description="航海に備えて食料を仕入れよう。航海中、HP回復に使える。")
    e.add_field(name="💰 所持金", value=f"**{db.get_balance(uid, gid):,}** ナトコイン", inline=False)
    for fid, f in V.FOODS.items():
        have = vp.get("foods", {}).get(fid, 0)
        e.add_field(name=f"{f['emoji']} {f['name']}（所持{have}）",
                    value=f"HP+{int(f['heal_pct']*100)}%・**{f['price']:,}**コイン", inline=True)
    return e

class FoodShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🍖 食料", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        await interaction.response.edit_message(
            embed=build_foodshop_embed(db.get_voyage(view.user_id), view.user_id, view.gid),
            view=FoodShopView(view.user_id, view.gid))

class FoodShopView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.add_item(FoodItemSelect(uid, gid))
        back = discord.ui.Button(label="◀ ドックへ戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(it):
            if str(it.user.id) != self.uid:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(embed=build_dock_embed(db.get_voyage(self.uid), self.uid, self.gid),
                                           view=DockView(self.uid, self.gid))
        back.callback = _back
        self.add_item(back)

class FoodItemSelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        opts=[]
        for fid, f in V.FOODS.items():
            opts.append(discord.SelectOption(label=f"{f['name']} を選ぶ", emoji=f['emoji'], value=fid,
                description=f"{f['price']:,}コイン/個・HP+{int(f['heal_pct']*100)}%"))
        super().__init__(placeholder="買う食料を選ぶ", options=opts[:25], row=0)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_foodshop_embed(db.get_voyage(self.uid), self.uid, self.gid),
                                       view=FoodQtyView(self.uid, self.gid, self.values[0]))

class FoodQtyView(discord.ui.View):
    def __init__(self, uid, gid, fid):
        super().__init__(timeout=900)
        self.uid=str(uid); self.gid=str(gid); self.fid=fid
        self.add_item(FoodQtySelect(uid, gid, fid))
        back=discord.ui.Button(label="◀ 食料を選び直す", style=discord.ButtonStyle.secondary, row=1)
        async def _back(it):
            if str(it.user.id)!=self.uid:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(embed=build_foodshop_embed(db.get_voyage(self.uid), self.uid, self.gid), view=FoodShopView(self.uid,self.gid))
        back.callback=_back; self.add_item(back)

class FoodQtySelect(discord.ui.Select):
    def __init__(self, uid, gid, fid):
        self.uid=str(uid); self.gid=str(gid); self.fid=fid
        f=V.FOODS[fid]
        opts=[discord.SelectOption(label=f"×{q}", value=str(q), description=f"{f['price']*q:,}コイン") for q in FOOD_QTY_STEPS]
        super().__init__(placeholder=f"{f['name']}の個数を選ぶ", options=opts[:25], row=0)
    async def callback(self, it):
        if str(it.user.id)!=self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        q=int(self.values[0]); f=V.FOODS[self.fid]; cost=f['price']*q
        bal=db.get_balance(self.uid,self.gid)
        if bal<cost:
            await it.response.send_message(f"💰 コインが足りない（{cost:,} 必要）", ephemeral=True); return
        db.update_balance(self.uid,self.gid,-cost)
        vp=db.get_voyage(self.uid)
        vp.setdefault('foods',{})[self.fid]=vp.setdefault('foods',{}).get(self.fid,0)+q
        db.add_zukan(self.uid,'item_seen',self.fid); db.save_voyage(self.uid,vp)
        await it.response.edit_message(embed=build_foodshop_embed(vp,self.uid,self.gid), view=FoodShopView(self.uid,self.gid))
        await it.followup.send(f"{f['emoji']} **{f['name']} ×{q}** を買った（-{cost:,}）。", ephemeral=True)

# ━━━ 🎣 航海の釣り竿（ドックで購入・永久・船に付ける）━━━
def build_rodshop_embed(vp, uid, gid):
    owned = vp.get("has_voyage_rod", False)
    e = discord.Embed(title="🎣 ドックの釣具職人", color=0x16a085,
                      description=("「海の主たちを狙うなら、専用の竿がいる。\n"
                                   "　一度こしらえれば、**船に付けっぱなしで二度と折れん**。\n"
                                   "　……ただし安かない。覚悟して来な。」"))
    e.add_field(name="💰 所持金", value=f"**{db.get_balance(uid, gid):,}** ナトコイン", inline=False)
    if owned:
        e.add_field(name=V.VOYAGE_ROD_NAME,
                    value="✅ **仕立て済み**。魚影が現れた海域で釣りができる。", inline=False)
    else:
        e.add_field(name=V.VOYAGE_ROD_NAME,
                    value=(f"**{V.VOYAGE_ROD_PRICE:,}** ナトコイン（永久・1本のみ）\n"
                           "これが無いと、海の魚は掛けられない。\n"
                           "※ リール/ラインは海の釣りには効かない（金冠なし）"), inline=False)
    return e

class RodShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🎣 釣竿", style=discord.ButtonStyle.success)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        vp = db.get_voyage(view.user_id)
        await interaction.response.edit_message(
            embed=build_rodshop_embed(vp, view.user_id, view.gid),
            view=RodShopView(view.user_id, view.gid))

class RodShopView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(self.uid)
        if not vp.get("has_voyage_rod", False):
            self.add_item(RodBuyButton())
        self.add_item(RodBackButton())

class RodBuyButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=f"🎣 仕立てる（{V.VOYAGE_ROD_PRICE:,}）", style=discord.ButtonStyle.success)
    async def callback(self, it):
        view: RodShopView = self.view
        if str(it.user.id) != view.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(view.uid)
        if vp.get("has_voyage_rod"):
            await it.response.send_message("もう持っている。", ephemeral=True); return
        if db.get_balance(view.uid, view.gid) < V.VOYAGE_ROD_PRICE:
            await it.response.send_message(
                f"💰 ナトコインが足りない（{V.VOYAGE_ROD_PRICE:,} 必要）", ephemeral=True); return
        db.update_balance(view.uid, view.gid, -V.VOYAGE_ROD_PRICE)
        vp["has_voyage_rod"] = True
        db.save_voyage(view.uid, vp)
        await it.response.edit_message(
            embed=build_rodshop_embed(vp, view.uid, view.gid), view=RodShopView(view.uid, view.gid))
        await it.followup.send(
            f"{V.VOYAGE_ROD_NAME} を仕立てた！ これで魚影が現れた海域で釣りができる。", ephemeral=True)

class RodBackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ ドックへ戻る", style=discord.ButtonStyle.secondary)
    async def callback(self, it):
        view: RodShopView = self.view
        if str(it.user.id) != view.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(
            embed=build_dock_embed(db.get_voyage(view.uid), view.uid, view.gid), view=DockView(view.uid, view.gid))

class SailButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🧭 出航", style=discord.ButtonStyle.primary)
    async def callback(self, interaction):
        view: PortView = self.view
        if not await view.guard(interaction): return
        vp = db.get_voyage(view.user_id)
        # ⏳ 帰港後クールダウン：現実時間5分は再出航できない
        VOYAGE_COOLDOWN = 300
        left = VOYAGE_COOLDOWN - (time.time() - vp.get("last_voyage_end", 0))
        if left > 0:
            m, s = divmod(int(left) + 1, 60)
            await interaction.response.send_message(
                f"⏳ 航海から戻ったばかりだ。船を整えるのに **あと {m}分{s}秒** かかる。",
                ephemeral=True); return
        if any_part_broken(vp):
            await interaction.response.send_message(
                "🔧 装備が壊れている。先に修理しないと出航できない。", ephemeral=True); return
        if "fuel_tank" not in vp:   # 移行救済：既存の船持ちは初回だけ満タン
            vp["fuel_tank"] = ship_max_fuel(vp); db.save_voyage(view.user_id, vp)
        if vp.get("fuel_tank", 0) <= 0:
            await interaction.response.send_message(
                "⛽ タンクが空っぽだ。港で**給油**してから出航しよう。", ephemeral=True); return
        # 🎣 オーグの出航警告：初回は必ず／以降は燃料かHPが満タンでない時だけ引き止める
        first = not vp.get("oag_warned")
        low = (vp.get("fuel_tank", 0) < ship_max_fuel(vp)) or (vp.get("cur_hp", 1) < max_hp(vp))
        if first or low:
            if first:
                vp["oag_warned"] = True; db.save_voyage(view.user_id, vp)
            await interaction.response.edit_message(
                embed=build_oag_embed(OAG_WARN_FIRST if first else OAG_WARN_LOW),
                view=OagWarnView(view.user_id, view.gid))
            return
        await interaction.response.edit_message(
            embed=discord.Embed(title="🧭 出航 ── 海を選べ", color=discord.Color.teal(),
                                description="奥の海ほど高リターン・高リスク。船体tierで解放される。"),
            view=SeaSelectView(view.user_id, view.gid))

class ShopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏪 船装備ショップ", style=discord.ButtonStyle.secondary)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(view.user_id)),
            view=ShopView(view.user_id, view.gid))

class RepairButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🔧 修理", style=discord.ButtonStyle.secondary)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.send_message(
            embed=discord.Embed(title="🔧 修理 ── 準備中",
                                description="装備の修理対応は近日オープン予定。お楽しみに！",
                                color=0x7F8C8D), ephemeral=True)

class MockCombatButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚔️ 模擬戦(テスト)", style=discord.ButtonStyle.danger, row=1)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await start_board_test(interaction, view.user_id)

class PortInvButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📦 インベントリ", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(view.user_id)
        await interaction.response.edit_message(
            embed=build_inv_embed(vp, "equip"),
            view=InventoryView(view.user_id, view.gid, "equip", back="port"))

class PortPhoneButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="📱 スマホ", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        from cogs.phone import open_phone
        await open_phone(interaction, view.user_id, edit=False)

class LeaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🏘️ タウンに戻る", style=discord.ButtonStyle.secondary, row=2)
    async def callback(self, interaction):
        view = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        from cogs.menu import go_town
        await go_town(interaction, view.user_id)


def build_oag_embed(body=None):
    e = discord.Embed(
        description=body or OAG_GREETING,
        color=discord.Color.dark_gold())
    e.set_footer(text="伝説の釣り人 オーグ ── 港の助言役")
    return e

class OagButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🎣 オーグに話を聞く", style=discord.ButtonStyle.secondary, row=1)
    async def callback(self, interaction):
        view: PortView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_oag_embed(), view=OagTalkView(view.user_id, view.gid))

class OagTalkView(discord.ui.View):
    """オーグに聞く：トピックを選ぶ。"""
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        for key, (label, _txt) in OAG_TOPICS.items():
            self.add_item(OagTopicButton(key, label))
        back = discord.ui.Button(label="◀ 港へ戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(it):
            if str(it.user.id) != self.user_id:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)),
                view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class OagTopicButton(discord.ui.Button):
    def __init__(self, key, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.key = key
    async def callback(self, it):
        view: OagTalkView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        label, txt = OAG_TOPICS[self.key]
        body = f"🎣 **オーグ** ── {label}\n\n{txt}\n\n"
        # 末尾に「他に聞くか？」を添えて会話を続けやすく
        body += "「……他に聞きたいことはあるか？」"
        await it.response.edit_message(
            embed=build_oag_embed(body), view=OagTalkView(view.user_id, view.gid))

class OagWarnView(discord.ui.View):
    """出航前のオーグ警告：それでも出るか／やめるか。"""
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        go = discord.ui.Button(label="⚓ それでも出航する", style=discord.ButtonStyle.danger)
        async def _go(it):
            if str(it.user.id) != self.user_id:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(
                embed=discord.Embed(title="🧭 出航 ── 海を選べ", color=discord.Color.teal(),
                                    description="奥の海ほど高リターン・高リスク。船体tierで解放される。"),
                view=SeaSelectView(self.user_id, self.gid))
        go.callback = _go
        self.add_item(go)
        back = discord.ui.Button(label="🛟 港で整える", style=discord.ButtonStyle.secondary)
        async def _back(it):
            if str(it.user.id) != self.user_id:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)),
                view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 海セレクト
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class SeaSelectView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(self.user_id)
        for sea in V.SEA_ORDER:
            self.add_item(SeaButton(sea, can_enter_sea(vp, sea)))
        back = discord.ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)), view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class SeaButton(discord.ui.Button):
    def __init__(self, sea, unlocked):
        s = V.SEAS[sea]
        super().__init__(label=("" if unlocked else "🔒 ") + s["name"],
                         style=discord.ButtonStyle.primary if unlocked else discord.ButtonStyle.secondary,
                         disabled=not unlocked)
        self.sea = sea
    async def callback(self, interaction):
        view: SeaSelectView = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid = view.user_id, view.gid
        vp = db.get_voyage(uid)
        if not can_enter_sea(vp, self.sea):
            await interaction.response.send_message("🔒 この海にはまだ出られない（もっと上位の船が要る）", ephemeral=True); return
        vp["voyage"] = {"sea": self.sea, "area": 1, "explores": 0, "hold": 0,
                        "fuel": vp.get("fuel_tank", 0)}   # ⛽ タンクの中身を積んで出航（給油した分だけ進める）
        vp["fuel_tank"] = 0                              # タンクは空に（全部船に積んだ）
        # 出航時にHPを全回復しない。港での現在HPをそのまま航海へ持ち込む。
        vp["cur_hp"] = max(1, min(max_hp(vp), vp.get("cur_hp", max_hp(vp))))
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_voyage_embed(vp, f"⛵ {V.SEAS[self.sea]['name']} へ出航した！"),
            view=VoyageView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 演出中の固定UI（ボタンを消さず無効化して高さブレを防ぐ）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class VoyageTheaterView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=30)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(discord.ui.Button(label="🔍 探索中…", style=discord.ButtonStyle.secondary, disabled=True, row=0))
        self.add_item(discord.ui.Button(label="⛵ 進む", style=discord.ButtonStyle.secondary, disabled=True, row=0))
        self.add_item(discord.ui.Button(label="🏕️ 停泊", style=discord.ButtonStyle.secondary, disabled=True, row=0))
        self.add_item(discord.ui.Button(label="⚓ 引き返す", style=discord.ButtonStyle.secondary, disabled=True, row=0))


class VoyageItemSelect(discord.ui.Select):
    """航海中にも使える探索アイテム。"""
    def __init__(self, uid, gid):
        self.uid=str(uid); self.gid=str(gid)
        vp=db.get_voyage(uid); opts=[]
        for iid,n in vp.get('land_items',{}).items():
            if n>0 and iid in getattr(L,'LAND_ITEMS',{}):
                it=L.LAND_ITEMS[iid]
                opts.append(discord.SelectOption(label=f"{it['name']} ×{n}", emoji=it['emoji'], value=iid, description=it.get('desc','')[:90]))
        if not opts:
            opts=[discord.SelectOption(label="探索アイテムがない", value="__none__")]
        super().__init__(placeholder="🧭 探索アイテムを使う", options=opts[:25], row=1)
    async def callback(self, itx):
        if str(itx.user.id)!=self.uid:
            await itx.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        iid=self.values[0]; vp=db.get_voyage(self.uid)
        if iid=='__none__' or vp.get('land_items',{}).get(iid,0)<=0:
            await itx.response.send_message("使える探索アイテムがない。", ephemeral=True); return
        meta=L.LAND_ITEMS.get(iid)
        msg=""
        if iid=='bandage':
            mh=max_hp(vp); cur=vp.get('cur_hp', mh)
            if cur>=mh:
                await itx.response.send_message("❤️ HPは満タンだ。", ephemeral=True); return
            before=cur; vp['cur_hp']=min(mh, cur+int(mh*0.25))
            msg=f"🩹 **包帯** を巻いた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）"
        elif iid=='smoke_bomb':
            vp.setdefault('voyage_buffs',{})['smoke_bomb']=vp.setdefault('voyage_buffs',{}).get('smoke_bomb',0)+1
            msg="💨 **煙玉** を構えた。次の通常戦闘を避けやすくなる。"
        elif iid=='lucky_charm':
            vp.setdefault('voyage_buffs',{})['lucky_charm']=vp.setdefault('voyage_buffs',{}).get('lucky_charm',0)+10
            msg="🍀 **幸運のお守り** が淡く光った。10探索のあいだ、良い発見の気配が濃くなる。"
        elif iid=='old_map':
            vp.setdefault('voyage_buffs',{})['old_map']=vp.setdefault('voyage_buffs',{}).get('old_map',0)+10
            msg="🗺️ **古びた地図** を広げた。10探索のあいだ、選択イベントや発見を拾いやすくなる。"
        elif iid=='lantern':
            vp.setdefault('voyage_buffs',{})['lantern']=vp.setdefault('voyage_buffs',{}).get('lantern',0)+20
            msg="🔦 **探索ランタン** に火を入れた。20探索のあいだ、何もない海を避けやすくなる。"
        elif iid=='gold_compass':
            vp.setdefault('voyage_buffs',{})['gold_compass']=vp.setdefault('voyage_buffs',{}).get('gold_compass',0)+20
            msg="🧭 **黄金の羅針盤** が震えた。20探索のあいだ、コイン収穫が大きく増える。"
        elif iid in ('decoy_doll','guardian_feather'):
            await itx.response.send_message("これは死亡時に効果を発揮する貴重品。今は使わない方がいい。", ephemeral=True); return
        else:
            await itx.response.send_message("そのアイテムはまだ使えない。", ephemeral=True); return
        vp['land_items'][iid]-=1
        if vp['land_items'][iid]<=0: del vp['land_items'][iid]
        _reset_retreat_chain(vp)
        db.save_voyage(self.uid, vp)
        await itx.response.edit_message(embed=build_voyage_embed(vp, f"## 🧭 探索アイテム使用\n{msg}"), view=VoyageView(self.uid,self.gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 航海中
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class VoyageView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        # 「進む」は探索10回(＋エリア3はカケラ)で解禁。条件未達なら無効表示。
        try:
            _vp = db.get_voyage(str(user_id))
            v = _vp.get("voyage") or {}
        except Exception:
            _vp = {}; v = {}
        for child in list(self.children):
            if getattr(child, "label", "") == "⛵ 進む":
                if area_of(v) >= V.AREA_MAX or not can_advance(v, shards_of(_vp)):
                    child.disabled = True
        try:
            if any(n > 0 for n in _vp.get("land_items", {}).values()):
                self.add_item(VoyageItemSelect(user_id, gid))
        except Exception:
            pass

    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🔍 探索", style=discord.ButtonStyle.primary)
    async def explore(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if not vp.get("voyage"):
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        v = vp["voyage"]; area = area_of(v)
        cost = V.explore_fuel_cost(area)
        # 既存航海データの移行：fuel が無ければ満タンで初期化
        if "fuel" not in v:
            v["fuel"] = ship_max_fuel(vp)
        if v["fuel"] < cost:
            await interaction.response.send_message(
                f"⛽ 燃料が足りない（探索に {cost:,} 必要・残 {v['fuel']:,}）。引き返すしかない…", ephemeral=True); return
        if (not v.get("fuel_warned")) and (v["fuel"] - cost < _voyage_return_home_cost(area)):
            v["fuel_warned"] = True
            db.save_voyage(uid, vp)
            await interaction.response.send_message(
                f"⚠️ 次に探索すると、現在燃料では帰港目安 **{_voyage_return_home_cost(area):,}** を下回る。もう一度探索を押すと進む。",
                ephemeral=True); return
        if any_part_broken(vp):
            await interaction.response.send_message(
                "🛠️ 装備が壊れた！引き返して修理を。", ephemeral=True); return
        if vp.get("cur_hp", 1) <= 0:
            await interaction.response.send_message(
                "🛠️ 船体が大破している！引き返して修理を。", ephemeral=True); return
        _reset_retreat_chain(vp)
        v["fuel"] -= cost   # ⛽ タンクから探索ぶん消費
        pet_note = _apply_hamster_voyage_heal(vp)
        res = roll_explore(vp)
        db.save_voyage(uid, vp)   # 探索カウント／航海消耗／非戦闘の獲得を確定
        # 🔍 探索ウェイト演出（種類別の色・見出し／UI高さは固定）
        theater_kind = _voyage_kind_for_result(res)
        theater_embed = build_voyage_theater_embed(vp, theater_kind)
        if pet_note:
            theater_embed.description += f"\n{pet_note}"
        await interaction.response.edit_message(
            embed=theater_embed,
            view=VoyageTheaterView(uid, gid))
        await asyncio.sleep(1)
        if res[0] == "combat":
            _, spec, scale, vm, is_boss = res
            cat = enemy_category(spec)
            ek = spec.get("key")
            if ek and cat != "boss":   # ボスは挑むまで図鑑に伏せる
                db.add_zukan(uid, "enemy_seen", ek)
            await interaction.edit_original_response(
                embed=build_reveal_embed(vp, spec, cat),
                view=EncounterChoiceView(uid, gid, spec, scale, vm, is_boss, cat))
            return
        if res[0] == "choice":
            _, eid, vm = res
            d = VE.EVENT_DEFS[eid]
            # 自動結果イベント（autoキー）：選択肢なし・即適用
            if "auto" in d:
                text, combat, fish = apply_event_effects(vp, d["auto"], vm)
                db.save_voyage(uid, vp)
                if combat:
                    v = vp.get("voyage") or {}; area = area_of(v); sea = v["sea"]
                    spec = V.make_enemy_spec(combat, area) or dict(random.choice(V.PIRATE_RANKS))
                    scale = V.SEAS[sea]["danger"] * V.AREA_MULT[area]
                    cvm = vm  # 羅針盤などで補正済みの報酬倍率を引き継ぐ
                    await interaction.edit_original_response(
                        embed=build_ambush_embed(vp, spec),
                        view=ProceedCombatView(uid, gid, spec, scale, cvm, spec.get("is_boss", False)))
                    return
                if fish:
                    head = f"{d['emoji']} **{d['name']}**"
                    flav = d.get("flavor", "")
                    intro = (flav + "\n\n" if flav else "") + text
                    await start_event_fishing(interaction, uid, gid, vp, fish, intro, _coin_bonus_from_vm(vp, vm))
                    return
                head = f"{d['emoji']} **{d['name']}**"
                flav = d.get("flavor", "")
                body = (flav + "\n\n" if flav else "") + text
                await interaction.edit_original_response(
                    embed=build_result_embed(vp, body, title=f"{d['emoji']} {d['name']}"),
                    view=ContinueVoyageView(uid, gid, ""))
                return
            # 選択肢イベント＝別枠で「発見」を見せて選ばせる
            await interaction.edit_original_response(
                embed=build_result_embed(vp, d["flavor"], title=f"{d['emoji']} {d['name']}"),
                view=ChoiceView(uid, gid, eid, vm))
            return
        if res[0] == "fish_cue":
            # 🎣 魚を釣れる演出（魚影）。航海専用の釣り竿が無いと掛けられない
            _, _eid, vm = res
            vp = db.get_voyage(uid)
            coin_bonus = _coin_bonus_from_vm(vp, vm)
            if not vp.get("has_voyage_rod"):
                await interaction.edit_original_response(
                    embed=build_result_embed(
                        vp, "🐟 海面に、魚の群れが見えた。\n"
                            f"だが――これを掛けられるのは **{V.VOYAGE_ROD_NAME}** だけ。\n"
                            "ドックで仕立てなければ、ただ眺めて見送るしかない。"),
                    view=ContinueVoyageView(uid, gid, ""))
                return
            area = area_of(vp["voyage"])
            # ⚔️ 魚影が実は怪物だった＝戦闘になるパターン（エリア依存）
            if V.fish_cue_combat_roll(area):
                spec = V.pick_fish_cue_beast(area) or V.pick_enemy(area)
                sea = vp["voyage"]["sea"]
                scale = V.SEAS[sea]["danger"] * V.AREA_MULT[area]
                cvm = vm  # 羅針盤などで補正済みの報酬倍率を引き継ぐ
                cat = enemy_category(spec)
                if spec.get("key"):
                    db.add_zukan(uid, "enemy_seen", spec["key"])
                await interaction.edit_original_response(
                    embed=build_fish_monster_embed(vp, spec),
                    view=EncounterChoiceView(uid, gid, spec, scale, cvm, spec.get("is_boss", False), cat))
                return
            total = V.fish_school_casts(area)
            await interaction.edit_original_response(
                embed=build_fish_school_embed(vp, total, total),
                view=FishingSchoolView(uid, gid, area, total, total, coin_bonus=coin_bonus))
            return
        msg = res[1]
        if res[0] == "discover":
            await interaction.edit_original_response(
                embed=build_discover_embed(vp, msg), view=DiscoverView(uid, gid, msg))
            return
        if any_part_broken(vp):
            msg += "\n\n🛠️ **装備が限界だ…！引き返すしかない。**"
        await interaction.edit_original_response(embed=build_voyage_embed(vp, msg), view=VoyageView(uid, gid))

    @discord.ui.button(label="⛵ 進む", style=discord.ButtonStyle.success)
    async def advance(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        v = vp.get("voyage")
        if not v:
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        if vp.get("cur_hp", 1) <= 0:
            await interaction.response.send_message(
                "🛠️ 船体が大破している！引き返して修理を。", ephemeral=True); return
        if not can_advance(v, shards_of(vp)):
            if area_of(v) == 3 and shards_of(vp) < V.SHARD_NEEDED:
                await interaction.response.send_message(
                    f"🌟 最深部へは {V.SHARD_NAME} が {V.SHARD_NEEDED} 個必要（探索でカケラを集めよう）", ephemeral=True); return
            need = V.EXPLORE_TO_ADVANCE - explores_done(v)
            await interaction.response.send_message(
                f"🔍 このエリアをあと {max(0,need)} 回探索すれば進める", ephemeral=True); return
        # ⛽ エリア移動の燃料チェック＆消費
        to_area = area_of(v) + 1
        mcost = V.move_fuel_cost(to_area)
        if "fuel" not in v:
            v["fuel"] = ship_max_fuel(vp)
        if v["fuel"] < mcost:
            await interaction.response.send_message(
                f"⛽ 燃料が足りず先へ進めない（移動に {mcost:,} 必要・残 {v['fuel']:,}）。引き返すしかない…", ephemeral=True); return
        _reset_retreat_chain(vp)
        v["fuel"] -= mcost
        v["area"] += 1; v["explores"] = 0
        nm = f"{V.AREA_EMOJI[v['area']]} {V.AREA_NAMES[v['area']]}"
        # 🎬 エリア移動の演出（5秒ウェイト→別枠で世界観テキスト→次へ進む）
        trans = AREA_TRANSITION.get(v["area"],
                                    f"⛵ さらに奥へ。**{nm}** に進んだ。")
        body = f"**{nm}** に到達した。\n\n{trans}"
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_voyage_theater_embed(vp, "move"),
            view=VoyageTheaterView(uid, gid))
        await asyncio.sleep(5)
        await interaction.edit_original_response(
            embed=build_result_embed(vp, body, title=f"⛵ {nm} へ"),
            view=ContinueVoyageView(uid, gid, ""))

    @discord.ui.button(label="🏕️ 停泊", style=discord.ButtonStyle.secondary)
    async def stopover(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if not vp.get("voyage"):
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        _reset_retreat_chain(vp); db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_stopover_embed(vp), view=StopoverView(uid, gid))

    @discord.ui.button(label="⚓ 引き返す", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction, button):
        if not await self.guard(interaction): return
        uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        v = vp.get("voyage")
        if not v:
            await interaction.response.edit_message(embed=build_port_embed(vp), view=PortView(uid, gid)); return
        area = area_of(v)
        step_cost = _voyage_return_step_cost(area)
        if "fuel" not in v:
            v["fuel"] = ship_max_fuel(vp)
        chain = int(v.get("retreat_chain", 0)) + 1
        v["retreat_chain"] = chain
        db.save_voyage(uid, vp)
        if chain < 3:
            await interaction.response.edit_message(
                embed=build_voyage_embed(vp, f"⚓ 引き返す準備中…… **{chain}/3**。あと **{3-chain}回** 続けて押すと1エリア戻る。\n※探索・進む・停泊など別行動をすると中断される。"),
                view=VoyageView(uid, gid))
            return
        v["retreat_chain"] = 0
        if v["fuel"] < step_cost:
            db.save_voyage(uid, vp)
            await interaction.response.send_message(f"⛽ 引き返す燃料が足りない（必要 {step_cost:,}・残 {v['fuel']:,}）。", ephemeral=True); return
        v["fuel"] -= step_cost
        if area > 1:
            v["area"] -= 1
            v["explores"] = V.EXPLORE_TO_ADVANCE
            db.save_voyage(uid, vp)
            nm = f"{V.AREA_EMOJI[v['area']]} {V.AREA_NAMES[v['area']]}"
            await interaction.response.edit_message(
                embed=build_voyage_embed(vp, f"⚓ 進路を切り直し、燃料 **-{step_cost:,}**。**{nm}** に戻った。"),
                view=VoyageView(uid, gid))
            return
        # エリア1で3回引き返す＝帰港・入金
        hold = v["hold"]
        if hold > 0:
            db.update_balance(uid, gid, hold)
        vp["fuel_tank"] = v.get("fuel", 0)
        vp["voyage"] = None
        # 帰港時にHPを全回復しない。航海で削れたHPを港へ持ち帰る。
        vp["cur_hp"] = max(1, min(max_hp(vp), vp.get("cur_hp", max_hp(vp))))
        vp["last_voyage_end"] = time.time()
        db.save_voyage(uid, vp)
        if hold >= 100000:
            try:
                from cogs.bigwin import announce_big_win
                await announce_big_win(interaction, interaction.user, "航海", hold)
            except Exception:
                pass
        e = discord.Embed(title="⚓ 帰港",
            description=f"航海を終えた。\n帰港燃料 **-{step_cost:,}**。\n船倉の **{hold:,}** ナトコインを銀行に入金した！",
            color=discord.Color.gold())
        rc = repair_cost(vp)
        if rc > 0:
            e.add_field(name="🔧 整備", value=f"装備が傷んでいる（修理 **{rc:,}**）", inline=False)
        await interaction.response.edit_message(embed=e, view=PortView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 選択肢イベント（Phase4 器）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ChoiceView(discord.ui.View):
    def __init__(self, uid, gid, event_id, vm):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.event_id = event_id; self.vm = vm
        d = VE.EVENT_DEFS[event_id]
        for i, ch in enumerate(d["choices"]):
            self.add_item(ChoiceButton(i, ch))

    async def interaction_check(self, interaction):
        if str(interaction.user.id) != self.uid:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

class ChoiceButton(discord.ui.Button):
    def __init__(self, idx, ch):
        super().__init__(label=ch["label"], style=discord.ButtonStyle.secondary)
        self.idx = idx
    async def callback(self, interaction):
        view: ChoiceView = self.view
        uid, gid = view.uid, view.gid
        vp = db.get_voyage(uid)
        d = VE.EVENT_DEFS[view.event_id]
        ch = d["choices"][self.idx]
        # 🌑 クラーケンの影：大物の魚影(E1-2)の「狙う」からさらに20%で分岐
        if view.event_id == "fish_shadow" and "狙う" in ch["label"]:
            v = vp.get("voyage") or {}; area = area_of(v)
            if area <= 2 and random.random() < 0.20:
                await maybe_kraken_shadow(interaction, uid, gid, area)
                return
        # 商船イベントの「交易する」は、結果テキストだけで終わらせず、
        # 航海中の商船ショップ（燃料・食料・探索アイテム購入）を開く。
        if view.event_id == "merchant_verma" and ("交易" in ch.get("label", "") or "取引" in ch.get("label", "")):
            await interaction.response.edit_message(
                embed=build_trade_embed(vp, "⛵ ヴェルマ商会が補給品を並べた。必要なものを選べる。"),
                view=TradeView(uid, gid))
            return
        text, combat, fish = apply_event_effects(vp, ch["effects"], view.vm)
        db.save_voyage(uid, vp)
        if combat:
            # combatキー(ghost/ambush/merchant_raid等)→専用の敵スペック
            v = vp.get("voyage") or {}; area = area_of(v); sea = v["sea"]
            spec = V.make_enemy_spec(combat, area) or dict(random.choice(V.PIRATE_RANKS))
            scale = V.SEAS[sea]["danger"] * V.AREA_MULT[area]
            vm = view.vm  # 羅針盤などで補正済みの報酬倍率を引き継ぐ
            await interaction.response.edit_message(
                embed=build_ambush_embed(vp, spec),
                view=ProceedCombatView(uid, gid, spec, scale, vm, spec.get("is_boss", False)))
            return
        if fish:
            # 🎣 イベント由来の釣り（ゴーシュ/伝説の噂など）
            await interaction.response.defer()
            await start_event_fishing(interaction, uid, gid, vp, fish,
                                      f"{d['emoji']} **{d['name']}**\n\n{text}",
                                      _coin_bonus_from_vm(vp, view.vm))
            return
        await interaction.response.edit_message(
            embed=build_result_embed(vp, text, title=f"{d['emoji']} {d['name']}"),
            view=ContinueVoyageView(uid, gid, ""))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# View: 停泊（釣り／宴会／休息）Phase6
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_stopover_embed(vp, note=""):
    v = vp.get("voyage") or {}
    area = area_of(v); mxf = ship_max_fuel(vp); fuel = v.get("fuel", mxf)
    mh = max_hp(vp); cur = vp.get("cur_hp", mh)
    e = discord.Embed(title="🏕️ 停泊", color=0x27ae60,
                      description=(note + "\n\n" if note else "") +
                      "船を停めて、ひと息つく。だが停泊にも燃料は要る――長居しすぎれば、奥へは進めない。")
    e.add_field(name="❤️ 個人HP", value=f"{cur}/{mh}\n{hp_bar(cur, mh, 10)}", inline=True)
    e.add_field(name="⛽ 燃料", value=f"{fuel:,}/{mxf:,}", inline=True)
    e.add_field(name="🍖 食事", value=f"HP半分回復（-{V.STOPOVER_FEAST_FUEL:,}燃料）", inline=True)
    e.add_field(name="😴 休息", value=f"HP全回復（-{V.STOPOVER_REST_FUEL:,}燃料）", inline=True)
    return e

class StopoverView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
    async def guard(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True)
            return False
        return True

    def _fuel_ok(self, vp, cost):
        v = vp.get("voyage") or {}
        if "fuel" not in v: v["fuel"] = ship_max_fuel(vp)
        return v["fuel"] >= cost

    @discord.ui.button(label="🍖 食事（HP半分回復）", style=discord.ButtonStyle.success)
    async def feast(self, interaction, button):
        if not await self.guard(interaction): return
        vp = db.get_voyage(self.user_id); v = vp.get("voyage") or {}
        mh = max_hp(vp); before = vp.get("cur_hp", mh)
        if before >= mh:
            await interaction.response.send_message("❤️ HPは満タンだ。今は食べなくていい。", ephemeral=True); return
        if not self._fuel_ok(vp, V.STOPOVER_FEAST_FUEL):
            await interaction.response.send_message(f"⛽ 燃料が足りない（食事に {V.STOPOVER_FEAST_FUEL:,}）", ephemeral=True); return
        v["fuel"] -= V.STOPOVER_FEAST_FUEL
        vp["cur_hp"] = min(mh, before + (mh + 1) // 2)   # 食事＝半分回復（安い）
        db.save_voyage(self.user_id, vp)
        await interaction.response.edit_message(
            embed=build_stopover_embed(vp, f"🍖 食事をとった。HPが回復（{before}→{vp['cur_hp']}）。"), view=self)

    @discord.ui.button(label="😴 休息（HP全回復）", style=discord.ButtonStyle.success)
    async def rest(self, interaction, button):
        if not await self.guard(interaction): return
        vp = db.get_voyage(self.user_id); v = vp.get("voyage") or {}
        if not self._fuel_ok(vp, V.STOPOVER_REST_FUEL):
            await interaction.response.send_message(f"⛽ 燃料が足りない（休息に {V.STOPOVER_REST_FUEL:,}）", ephemeral=True); return
        v["fuel"] -= V.STOPOVER_REST_FUEL
        smh = max_hp(vp); before = vp.get("cur_hp", smh); vp["cur_hp"] = smh
        db.save_voyage(self.user_id, vp)
        await interaction.response.edit_message(
            embed=build_stopover_embed(vp, f"😴 錨を下ろし、ひと息ついた。HPが回復（{before}→{smh}）。"), view=self)

    @discord.ui.button(label="▶️ 次へ進む", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        if not await self.guard(interaction): return
        vp = db.get_voyage(self.user_id)
        await interaction.response.edit_message(
            embed=build_voyage_embed(vp, "⛵ 停泊を切り上げ、航海を再開する。"),
            view=VoyageView(self.user_id, self.gid))


# 船装備の装着可否（船rank+2 まで）
def ship_part_allowed_rank(vp):
    sd = ship_def_of(vp)
    return (sd["rank"] + V.RARITY_ENGRAVE_GAP) if sd else 0

# 船本体に刻める技種（slot=="ship_body"）／部位に刻める技種
SHIP_PART_SKILL_SLOT = {"cannon": "ship_cannon", "armor": "ship_armor", "rigging": "ship_rigging"}
SHIP_EQUIPMENT_SHOP_ENABLED = False  # 船装備は未実装扱い。購入・装着・船技刻印は一旦停止。

def ship_skill_fits(target, sid):
    """target: 'body' or 部位名。slotが一致すれば刻める。"""
    s = VS.SKILLS.get(sid)
    if not s: return False
    if target == "body":
        return s["slot"] == "ship_body"
    return s["slot"] == SHIP_PART_SKILL_SLOT.get(target)

def build_shop_embed(vp):
    sd = ship_def_of(vp)
    if not SHIP_EQUIPMENT_SHOP_ENABLED:
        e = discord.Embed(
            title="🏪 港の造船ショップ ── 準備中",
            color=discord.Color.gold(),
            description="船装備（砲・装甲・艤装）と船技はまだ未実装のため、現在は購入・装着できません。"
        )
    else:
        e = discord.Embed(title="🏪 港の造船ショップ", color=discord.Color.gold(),
                          description=(f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']} ── "
                                       f"☆{sd['rank']+V.RARITY_ENGRAVE_GAP}までの装備を積める。\n"
                                       "部位に船装備を挿し、船技を刻もう。"))
    for part in V.SHIP_PART_ORDER:
        meta = V.SHIP_PART_META[part]; pdef = ship_part_def(vp, part)
        if pdef:
            val = f"{V.rarity_stars(pdef['rank'])} {pdef['name']}（攻/防{pdef['power']}）"
            sk = ship_part_inst(vp, part).get("skills", [])
            if sk: val += " {" + "".join(VS.SKILLS[x]["emoji"] for x in sk) + "}"
        else:
            val = "空き"
        e.add_field(name=f"{meta['emoji']} {meta['name']}", value=val, inline=True)
    bsk = vp.get("ship_skills", [])
    e.add_field(name=f"🚢 船本体の技 [{len(bsk)}/{sd['skill_slots']}]",
                value=" ".join(VS.SKILLS[x]["name"] for x in bsk) if bsk else "空き", inline=False)
    return e

class ShopView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        if SHIP_EQUIPMENT_SHOP_ENABLED:
            self.add_item(ShipPartSelect(user_id, gid))
            self.add_item(ShipEngraveButton())
        else:
            self.add_item(ShipShopDisabledButton())
        back = discord.ui.Button(label="◀ 港へ戻る", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_port_embed(db.get_voyage(self.user_id)), view=PortView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipShopDisabledButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚧 船装備は準備中", style=discord.ButtonStyle.secondary, disabled=True, row=0)

class ShipPartSelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = []
        for part in V.SHIP_PART_ORDER:
            meta = V.SHIP_PART_META[part]
            opts.append(discord.SelectOption(label=f"{meta['name']}スロットに挿す", emoji=meta["emoji"], value=part))
        super().__init__(placeholder="🔧 部位に船装備を挿す", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        if not SHIP_EQUIPMENT_SHOP_ENABLED:
            await interaction.response.send_message("🚧 船装備はまだ未実装なので購入・装着できません。", ephemeral=True); return
        part = self.values[0]
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(self.user_id)),
            view=ShipPartBuyView(self.user_id, self.gid, part))

class ShipPartBuyView(discord.ui.View):
    def __init__(self, user_id, gid, part):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        items = V.SHIP_PARTS[part]["items"]
        if items:
            self.add_item(ShipPartBuySelect(user_id, gid, part))
        back = discord.ui.Button(label="◀ ショップへ", style=discord.ButtonStyle.secondary, row=1)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShopView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipPartBuySelect(discord.ui.Select):
    def __init__(self, user_id, gid, part):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        opts = []
        for iid, idd in V.SHIP_PARTS[part]["items"].items():
            opts.append(discord.SelectOption(
                label=f"{V.rarity_stars(idd['rank'])} {idd['name']}（{idd['power']}）", value=iid,
                description=f"耐久{idd['dura']}・{idd['price']:,}コイン"))
        super().__init__(placeholder=f"{V.SHIP_PART_META[part]['name']}を選ぶ", options=opts or [
            discord.SelectOption(label="（在庫なし）", value="none")], row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        if not SHIP_EQUIPMENT_SHOP_ENABLED:
            await interaction.response.send_message("🚧 船装備はまだ未実装なので購入できません。", ephemeral=True); return
        iid = self.values[0]
        if iid == "none":
            await interaction.response.send_message("まだ在庫が無い部位だ（艤装は今後）", ephemeral=True); return
        idd = V.SHIP_PARTS[self.part]["items"][iid]
        uid, gid, part = self.user_id, self.gid, self.part
        vp = db.get_voyage(uid)
        # レア度制限：船rank+2 まで
        if idd["rank"] > ship_part_allowed_rank(vp):
            await interaction.response.send_message(
                f"🔒 この船には ☆{ship_part_allowed_rank(vp)} までの装備しか積めない", ephemeral=True); return
        if db.get_balance(uid, gid) < idd["price"]:
            await interaction.response.send_message(
                f"❌ ナトコインが足りない（{idd['price']:,} 必要）", ephemeral=True); return
        # 既存装備の技は手元に戻す（装備替え）
        old = vp["ship_parts"].get(part)
        if old:
            for sid in old.get("skills", []):
                vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.update_balance(uid, gid, -idd["price"])
        vp["ship_parts"][part] = {"item": iid, "skills": [], "dura": idd["dura"]}
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(
            embed=build_shop_embed(vp), view=ShopView(uid, gid))
        await interaction.followup.send(
            f"🔧 **{idd['name']}** を{V.SHIP_PART_META[part]['name']}に装備（-{idd['price']:,}）", ephemeral=True)

class ShipEngraveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚒️ 船技を刻む", style=discord.ButtonStyle.primary, row=1)
    async def callback(self, interaction):
        view = self.view
        if str(interaction.user.id) != view.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        if not SHIP_EQUIPMENT_SHOP_ENABLED:
            await interaction.response.send_message("🚧 船技はまだ未実装なので刻めません。", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(view.user_id)),
            view=ShipEngraveView(view.user_id, view.gid))

class ShipEngraveView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); sd = ship_def_of(vp)
        targets = []
        # 船本体
        if sd and len(vp.get("ship_skills", [])) < sd["skill_slots"]:
            if any(vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits("body", s) for s in vp["learned_skills"]):
                targets.append(("body", "🚢 船本体"))
        # 部位
        for part in V.SHIP_PART_ORDER:
            inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
            if inst and pdef and len(inst.get("skills", [])) < pdef.get("slots", 1):
                if any(vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits(part, s) for s in vp["learned_skills"]):
                    targets.append((part, f"{V.SHIP_PART_META[part]['emoji']} {V.SHIP_PART_META[part]['name']}"))
        if targets:
            self.add_item(ShipEngraveTargetSelect(user_id, gid, targets))
        back = discord.ui.Button(label="◀ ショップへ", style=discord.ButtonStyle.secondary, row=2)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShopView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipEngraveTargetSelect(discord.ui.Select):
    def __init__(self, user_id, gid, targets):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = [discord.SelectOption(label=lbl, value=key) for key, lbl in targets]
        super().__init__(placeholder="刻む箇所を選ぶ", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await interaction.response.edit_message(
            embed=build_shop_embed(db.get_voyage(self.user_id)),
            view=ShipEngraveSkillView(self.user_id, self.gid, self.values[0]))

class ShipEngraveSkillView(discord.ui.View):
    def __init__(self, user_id, gid, target):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.target = target
        vp = db.get_voyage(user_id)
        owned = [s for s in vp["learned_skills"]
                 if vp["learned_skills"].get(s, 0) > 0 and ship_skill_fits(target, s)]
        if owned:
            self.add_item(ShipEngraveSkillSelect(user_id, gid, target, owned))
        back = discord.ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=1)
        async def _back(interaction):
            if str(interaction.user.id) != self.user_id:
                await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await interaction.response.edit_message(
                embed=build_shop_embed(db.get_voyage(self.user_id)), view=ShipEngraveView(self.user_id, self.gid))
        back.callback = _back
        self.add_item(back)

class ShipEngraveSkillSelect(discord.ui.Select):
    def __init__(self, user_id, gid, target, skills):
        self.user_id = str(user_id); self.gid = str(gid); self.target = target
        opts = [discord.SelectOption(label=VS.SKILLS[s]["name"], emoji=VS.SKILLS[s]["emoji"],
                value=s, description=VS.SKILLS[s]["desc"][:60]) for s in skills]
        super().__init__(placeholder="刻む船技を選ぶ", options=opts, row=0)
    async def callback(self, interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, target = self.user_id, self.gid, self.target; sid = self.values[0]
        vp = db.get_voyage(uid)
        if vp["learned_skills"].get(sid, 0) <= 0 or not ship_skill_fits(target, sid):
            await interaction.response.send_message("❌ ここには刻めない", ephemeral=True); return
        if target == "body":
            sd = ship_def_of(vp)
            if len(vp["ship_skills"]) >= sd["skill_slots"]:
                await interaction.response.send_message("⚠️ 船本体の技枠が満杯", ephemeral=True); return
            vp["ship_skills"].append(sid)
        else:
            inst = ship_part_inst(vp, target); pdef = ship_part_def(vp, target)
            if not inst:
                await interaction.response.send_message("その部位は空き", ephemeral=True); return
            if len(inst.get("skills", [])) >= pdef.get("slots", 1):
                await interaction.response.send_message("⚠️ その部位の技枠が満杯", ephemeral=True); return
            inst.setdefault("skills", []).append(sid)
        vp["learned_skills"][sid] -= 1
        if vp["learned_skills"][sid] <= 0: del vp["learned_skills"][sid]
        db.save_voyage(uid, vp)
        await interaction.response.edit_message(embed=build_shop_embed(vp), view=ShopView(uid, gid))
        await interaction.followup.send(f"⚒️ **{VS.SKILLS[sid]['name']}** を刻んだ！", ephemeral=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚒️ 装備屋 ＆ 📦 インベントリ（部位別・最大枠・装備/解除・売却・刻印）
#   装備は買うとインベントリに入る（武器5/胴3/脚3）。満杯は入れ替え（売却）。
#   技は装備中インスタンスに刻む（武器種別＆枠チェック）。技は装備について回る。
#   売却＝(装備価格＋刻んだ技価格の合計)÷10。技単体＝技価格÷10。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import voyage_skills as VS

def item_def(part, item_id):
    return V.WEAPONS.get(item_id) if part == "weapon" else V.ARMOR_PARTS[part]["items"].get(item_id)

def item_slots(part, item_id):
    d = item_def(part, item_id)
    return d.get("slots", 1) if d else 1

def item_label(part, inst, with_skills=True):
    d = item_def(part, inst["item"])
    if not d:
        return "不明な装備"
    star = V.rarity_stars(d["rank"])
    if part == "weapon":
        wt = V.WEAPON_TYPES[d["wtype"]]["name"]
        s = f"{star} {d['name']}（{wt}・攻{d['power']}・枠{d.get('slots',1)}）"
    else:
        s = f"{star} {d['name']}（防{d['power']}）"
    if with_skills and inst.get("skills"):
        s += " {" + "".join(VS.SKILLS[x]["emoji"] for x in inst["skills"]) + "}"
    return s

def inst_sell_value(part, inst):
    total = item_def(part, inst["item"])["price"]
    for sid in inst.get("skills", []):
        total += VS.SKILLS.get(sid, {}).get("price", 0)
    return total // 10

def _remove_item(vp, part, idx):
    """インベントリから装備を取り除き、装備中インデックスを補正して返す。"""
    lst = vp["inventory"][part]
    inst = lst.pop(idx)
    eq = vp["equipped"][part]
    if eq is not None:
        if eq == idx: vp["equipped"][part] = None
        elif eq > idx: vp["equipped"][part] = eq - 1
    return inst

def _return_skills(vp, inst):
    """装備に刻まれた技を手元(learned_skills)に戻す。"""
    for sid in inst.get("skills", []):
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
    inst["skills"] = []

PART_NAMES = {"weapon": "⚔️ 武器", "torso": "🦺 胴", "legs": "🦵 脚"}

def _skill_fits(part, item_id, sid):
    s = VS.SKILLS.get(sid)
    if not s: return False
    if part == "weapon":
        return s["slot"] == "weapon" and V.WEAPONS[item_id]["wtype"] in s.get("wtypes", [])
    return s["slot"] == "armor"

# ━━━━━━━━ 装備屋 ━━━━━━━━
def build_equipshop_embed(vp, uid=None, gid=None):
    e = discord.Embed(title="⚔️ リディア（装備屋）",
                      color=discord.Color.dark_orange(),
                      description="武器・防具・技を買い、装備に技を刻もう。\n"
                                  "武器の種別に合う技だけ刻める（杖＝回復専用 等）。装備売却は定価＋刻印技価格の1/10。")
    if uid and gid:
        e.add_field(name="💰 所持金", value=f"**{db.get_balance(uid, gid):,}** ナトコイン", inline=False)
    for part in ("weapon", "torso", "legs"):
        lst = vp["inventory"].get(part, [])
        eq_idx = vp["equipped"].get(part)
        if lst:
            rows = []
            for i, inst in enumerate(lst):
                d = item_def(part, inst["item"])
                nm = d["name"] if d else inst["item"]
                mark = "✅" if i == eq_idx else "▫️"
                sk = inst.get("skills", [])
                sktxt = "　刻:" + "・".join(VS.SKILLS[s]["name"] for s in sk) if sk else ""
                rows.append(f"{mark}{nm}{sktxt}")
            val = "\n".join(rows)
        else:
            val = "（未所持）"
        e.add_field(name=f"{PART_NAMES[part]}（{len(lst)}/{INV_CAP[part]}）",
                    value=val, inline=False)
    e.add_field(name="　", value="✅=装備中　▫️=所持（未装備）　※技は**装備中**の装備にしか刻めない", inline=False)
    inv = vp.get("learned_skills", {})
    have = [f"{VS.SKILLS[s]['emoji']}{VS.SKILLS[s]['name']}×{n}" for s, n in inv.items() if n > 0]
    e.add_field(name=f"🎒 所持技 {sum(inv.values())}/{SKILL_CAP}",
                value="　".join(have) if have else "なし", inline=False)
    e.add_field(name="🧰 技外しキット", value=f"{vp.get('unequip_kits',0)} 個", inline=True)
    return e

def _eqshop_back(user_id, gid):
    btn = discord.ui.Button(label="◀ 装備屋トップ", style=discord.ButtonStyle.secondary, row=2)
    async def _cb(it):
        if str(it.user.id) != str(user_id):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(user_id), user_id, gid),
                                       view=EquipShopView(user_id, gid))
    btn.callback = _cb
    return btn

# ── 装備屋から直接 装備する（買ったものを装備中にする）──
class ShopEquipView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id)
        self.has_items = any(vp["inventory"].get(p) for p in ("weapon", "torso", "legs"))
        if self.has_items:
            self.add_item(ShopEquipSelect(user_id, gid))
        self.add_item(_eqshop_back(user_id, gid))

class ShopEquipSelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            for i, inst in enumerate(vp["inventory"].get(part, [])):
                d = item_def(part, inst["item"])
                nm = d["name"] if d else inst["item"]
                eqmark = " ✅装備中" if vp["equipped"].get(part) == i else ""
                opts.append(discord.SelectOption(
                    label=f"{PART_NAMES[part]}：{nm}{eqmark}"[:90],
                    value=f"{part}:{i}"))
        super().__init__(placeholder="装備するものを選ぶ（✅装備中になる）", options=opts[:25])
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(self.user_id); vp["equipped"][part] = i; db.save_voyage(self.user_id, vp)
        d = item_def(part, vp["inventory"][part][i]["item"])
        await it.response.edit_message(embed=build_equipshop_embed(vp, self.user_id, self.gid),
                                       view=ShopEquipView(self.user_id, self.gid))
        await it.followup.send(f"🗡️ **{d['name'] if d else ''}** を装備した！これで技を刻めるよ。", ephemeral=True)

class EquipShopView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
    async def guard(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return False
        return True

    @discord.ui.button(label="🗡️ 武器を買う", style=discord.ButtonStyle.success, row=0)
    async def bw(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=BuyView(self.user_id, self.gid, "weapon"))
    @discord.ui.button(label="🛡️ 防具を買う", style=discord.ButtonStyle.success, row=0)
    async def ba(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=BuyView(self.user_id, self.gid, "armor"))
    @discord.ui.button(label="📜 技を買う", style=discord.ButtonStyle.success, row=0)
    async def bs(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=SkillBuyView(self.user_id, self.gid))
    @discord.ui.button(label="🗡️ 装備する", style=discord.ButtonStyle.primary, row=1)
    async def eq(self, it, b):
        if not await self.guard(it): return
        view = ShopEquipView(self.user_id, self.gid)
        if not view.has_items:
            await it.response.send_message("装備できる武器・防具を持ってない（先に買ってね）", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=view)
    @discord.ui.button(label="⚒️ 技を刻む", style=discord.ButtonStyle.primary, row=1)
    async def en(self, it, b):
        if not await self.guard(it): return
        view = EngravePartView(self.user_id, self.gid)
        if not view.usable_parts:
            await it.response.send_message(
                "⚒️ **刻める装備がない**。下のどれかが足りないよ：\n"
                "・武器/防具を**装備**してる？（📦インベントリで装備＝✅がつく）\n"
                "・刻める技を持ってる？（種別が合う必要：杖技は杖だけ等）\n"
                "・装備のスロットに空きある？", ephemeral=True)
            return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=view)
    @discord.ui.button(label="🔧 技を外す", style=discord.ButtonStyle.secondary, row=1)
    async def un(self, it, b):
        if not await self.guard(it): return
        view = UnengraveView(self.user_id, self.gid)
        if not view.has_pairs:
            await it.response.send_message(
                "🔧 **外せる技がない**。装備中の装備に技を刻んでいれば、ここから外せるよ。", ephemeral=True)
            return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=view)
    @discord.ui.button(label="🧰 外しキット購入", style=discord.ButtonStyle.success, row=1)
    async def bk(self, it, b):
        if not await self.guard(it): return
        uid, gid = self.user_id, self.gid
        if db.get_balance(uid, gid) < VS.UNEQUIP_KIT_PRICE:
            await it.response.send_message(f"❌ コインが足りない（{VS.UNEQUIP_KIT_PRICE:,}）", ephemeral=True); return
        db.update_balance(uid, gid, -VS.UNEQUIP_KIT_PRICE)
        vp = db.get_voyage(uid); vp["unequip_kits"] = vp.get("unequip_kits", 0) + 1; db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, self.user_id, self.gid), view=self)
        await it.followup.send(f"🧰 技外しキット購入（-{VS.UNEQUIP_KIT_PRICE:,}）", ephemeral=True)
    @discord.ui.button(label="💰 装備を売る", style=discord.ButtonStyle.danger, row=2)
    async def sell(self, it, b):
        if not await self.guard(it): return
        view = SellEquipView(self.user_id, self.gid)
        if not view.has_items:
            await it.response.send_message("売れる装備がないよ。", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=view)
    @discord.ui.button(label="📦 インベントリ", style=discord.ButtonStyle.primary, row=2)
    async def inv(self, it, b):
        if not await self.guard(it): return
        await open_inventory(it, self.user_id, back="equip")
    @discord.ui.button(label="◀ 商店街へ", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, it, b):
        if not await self.guard(it): return
        from cogs.menu import open_shopping_street
        await open_shopping_street(it, self.user_id, self.gid)

# ── 装備売却（定価＋刻印技価格の1/10。刻んだ技は手元に戻す）──
class SellEquipView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id)
        self.has_items = any(vp["inventory"].get(p) for p in ("weapon", "torso", "legs"))
        if self.has_items:
            self.add_item(SellEquipSelect(user_id, gid))
        self.add_item(_eqshop_back(user_id, gid))

class SellEquipSelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            for i, inst in enumerate(vp["inventory"].get(part, [])):
                d = item_def(part, inst["item"])
                nm = d["name"] if d else inst["item"]
                eqmark = "✅装備中 " if vp["equipped"].get(part) == i else ""
                skills = inst.get("skills", [])
                skill_txt = f"・刻印技{len(skills)}個は手元に戻る" if skills else ""
                opts.append(discord.SelectOption(
                    label=f"{PART_NAMES[part]}：{eqmark}{nm}"[:90],
                    value=f"{part}:{i}",
                    description=f"売値 {inst_sell_value(part, inst):,} コイン（価格の1/10）{skill_txt}"[:100]))
        super().__init__(placeholder="売る装備を選ぶ（売値は10分の1）", options=opts[:25])

    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid = self.user_id, self.gid
        part, idx_s = self.values[0].split(":"); idx = int(idx_s)
        vp = db.get_voyage(uid)
        if idx < 0 or idx >= len(vp["inventory"].get(part, [])):
            await it.response.send_message("その装備はもう見つからない。画面を開き直してね。", ephemeral=True); return
        inst = vp["inventory"][part][idx]
        d = item_def(part, inst["item"])
        name = d["name"] if d else inst["item"]
        sell = inst_sell_value(part, inst)
        had_skills = len(inst.get("skills", []))
        _return_skills(vp, inst)
        _remove_item(vp, part, idx)
        db.update_balance(uid, gid, sell)
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=SellEquipView(uid, gid))
        extra = f" 刻印技{had_skills}個は手元に戻した。" if had_skills else ""
        await it.followup.send(f"💰 **{name}** を売却した。+{sell:,} ナトコイン。{extra}", ephemeral=True)

# ── 装備購入（武器/防具）。満杯なら入れ替え ──
class BuyView(discord.ui.View):
    def __init__(self, user_id, gid, cat):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.cat = cat
        self.add_item(BuySelect(user_id, gid, cat))
        self.add_item(_eqshop_back(user_id, gid))

class BuySelect(discord.ui.Select):
    def __init__(self, user_id, gid, cat):
        self.user_id = str(user_id); self.gid = str(gid); self.cat = cat
        opts = []
        if cat == "weapon":
            for wid, wd in V.WEAPONS.items():
                if wd["rank"] != 1: continue   # 装備屋は☆1のみ（☆2☆3はドロップ）
                wt = V.WEAPON_TYPES[wd["wtype"]]["name"]
                opts.append(discord.SelectOption(
                    label=f"{V.rarity_stars(wd['rank'])} {wd['name']}（{wt}）", value=f"weapon:{wid}",
                    description=f"攻{wd['power']}・技枠{wd['slots']}・{wd['price']:,}コイン"))
        else:
            for part in V.ARMOR_PART_ORDER:
                info = V.ARMOR_PARTS[part]
                for iid, idd in info["items"].items():
                    if idd["rank"] != 1: continue   # 装備屋は☆1のみ
                    opts.append(discord.SelectOption(
                        label=f"{V.rarity_stars(idd['rank'])} {idd['name']}（{info['name']}）", value=f"{part}:{iid}",
                        description=f"防{idd['power']}・{idd['price']:,}コイン"))
        super().__init__(placeholder="買う装備を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, iid = self.values[0].split(":")
        d = item_def(part, iid); uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if db.get_balance(uid, gid) < d["price"]:
            await it.response.send_message(f"❌ コインが足りない（{d['price']:,}）", ephemeral=True); return
        if len(vp["inventory"][part]) >= INV_CAP[part]:
            # 満杯 → 入れ替えフロー
            await it.response.edit_message(
                embed=build_equipshop_embed(vp, uid, gid),
                view=SwapView(uid, gid, part, iid)); return
        db.update_balance(uid, gid, -d["price"])
        vp["inventory"][part].append({"item": iid, "skills": []})
        db.add_zukan(uid, "equip_seen", iid)
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=BuyView(uid, gid, self.cat))
        await it.followup.send(f"🛒 **{d['name']}** を購入！インベントリに追加（-{d['price']:,}）", ephemeral=True)

class SwapView(discord.ui.View):
    def __init__(self, user_id, gid, part, new_iid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(SwapSelect(user_id, gid, part, new_iid))
        self.add_item(_eqshop_back(user_id, gid))

class SwapSelect(discord.ui.Select):
    def __init__(self, user_id, gid, part, new_iid):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part; self.new_iid = new_iid
        vp = db.get_voyage(user_id)
        opts = []
        for i, inst in enumerate(vp["inventory"][part]):
            opts.append(discord.SelectOption(
                label=f"{item_label(part, inst, with_skills=False)[:80]}",
                value=str(i),
                description=f"売値 {inst_sell_value(part, inst):,}（これを売って入れ替え）"))
        super().__init__(placeholder=f"{PART_NAMES[part]}が満杯。どれと入れ替える？", options=opts[:25])
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, part = self.user_id, self.gid, self.part
        vp = db.get_voyage(uid); idx = int(self.values[0])
        d = item_def(part, self.new_iid)
        if db.get_balance(uid, gid) < d["price"]:
            await it.response.send_message(f"❌ コインが足りない（{d['price']:,}）", ephemeral=True); return
        old = vp["inventory"][part][idx]
        sell = inst_sell_value(part, old)
        _return_skills(vp, old)          # 売る前に刻印技は手元に戻す（技は失わない）
        _remove_item(vp, part, idx)
        db.update_balance(uid, gid, -d["price"] + sell)
        vp["inventory"][part].append({"item": self.new_iid, "skills": []})
        db.add_zukan(uid, "equip_seen", self.new_iid)
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=EquipShopView(uid, gid))
        await it.followup.send(
            f"🔄 入れ替え完了：**{d['name']}** を購入（-{d['price']:,}）／古い装備を売却（+{sell:,}）。"
            "刻んでた技は手元に戻したよ。", ephemeral=True)

# ── 技購入 ──
class SkillBuyView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        self.add_item(SkillBuySelect(user_id, gid)); self.add_item(_eqshop_back(user_id, gid))

class SkillBuySelect(discord.ui.Select):
    def __init__(self, user_id, gid):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = []
        for sid, s in VS.SKILLS.items():
            # ☆3技はガチャ/メダル交換限定。装備屋では販売しない。
            if int(s.get("rank", 1)) >= 3:
                continue
            # 装備屋の「技を買う」には個人用だけ表示。船技は港の船装備側で扱う。
            if str(s.get("slot", "")).startswith("ship_"):
                continue
            if s["slot"] == "weapon":
                tags = "・".join(V.WEAPON_TYPES[w]["name"] for w in s["wtypes"])
            elif s["slot"] == "armor":
                tags = "胴・脚"
            else:
                tags = "船"
            opts.append(discord.SelectOption(label=f"{s['name']}（{s['price']:,}）", emoji=s["emoji"],
                        value=sid, description=f"[{tags}] {s['desc'][:46]}"))
        super().__init__(placeholder="買う技を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        sid = self.values[0]; s = VS.SKILLS[sid]; uid, gid = self.user_id, self.gid
        vp = db.get_voyage(uid)
        if sum(vp["learned_skills"].values()) >= SKILL_CAP:
            await it.response.send_message(f"🎒 所持技が満杯（{SKILL_CAP}）。インベントリで技を売るか刻んで空けて。", ephemeral=True); return
        if db.get_balance(uid, gid) < s["price"]:
            await it.response.send_message(f"❌ コインが足りない（{s['price']:,}）", ephemeral=True); return
        db.update_balance(uid, gid, -s["price"])
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=SkillBuyView(uid, gid))
        await it.followup.send(f"📜 **{s['name']}** 購入！「技を刻む」で装備にセット（-{s['price']:,}）", ephemeral=True)

# ── 技を刻む（装備中の武器/防具インスタンスに）──
class EngravePartView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); usable = []
        for part in ("weapon", "torso", "legs"):
            inst = equipped_inst(vp, part)
            if not inst: continue
            if len(inst.get("skills", [])) >= item_slots(part, inst["item"]): continue
            if any(vp["learned_skills"].get(sid, 0) > 0 and _skill_fits(part, inst["item"], sid)
                   for sid in vp["learned_skills"]):
                usable.append(part)
        self.usable_parts = usable
        if usable: self.add_item(EngravePartSelect(user_id, gid, usable))
        self.add_item(_eqshop_back(user_id, gid))

class EngravePartSelect(discord.ui.Select):
    def __init__(self, user_id, gid, parts):
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id)
        opts = []
        for p in parts:
            inst = equipped_inst(vp, p)
            opts.append(discord.SelectOption(label=f"{PART_NAMES[p]}：{item_label(p, inst, False)[:70]}", value=p))
        super().__init__(placeholder="刻む装備（装備中）を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                       view=EngraveSkillView(self.user_id, self.gid, self.values[0]))

class EngraveSkillView(discord.ui.View):
    def __init__(self, user_id, gid, part):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        vp = db.get_voyage(user_id); inst = equipped_inst(vp, part)
        owned = [sid for sid in vp["learned_skills"]
                 if vp["learned_skills"].get(sid, 0) > 0 and inst and _skill_fits(part, inst["item"], sid)]
        if owned: self.add_item(EngraveSkillSelect(user_id, gid, part, owned))
        self.add_item(_eqshop_back(user_id, gid))

class EngraveSkillSelect(discord.ui.Select):
    def __init__(self, user_id, gid, part, skills):
        self.user_id = str(user_id); self.gid = str(gid); self.part = part
        opts = [discord.SelectOption(label=VS.SKILLS[s]["name"], emoji=VS.SKILLS[s]["emoji"],
                value=s, description=VS.SKILLS[s]["desc"][:60]) for s in skills]
        super().__init__(placeholder="刻む技を選ぶ", options=opts)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid, part = self.user_id, self.gid, self.part; sid = self.values[0]
        vp = db.get_voyage(uid); inst = equipped_inst(vp, part)
        if not inst:
            await it.response.send_message("装備していない", ephemeral=True); return
        if len(inst.get("skills", [])) >= item_slots(part, inst["item"]):
            await it.response.send_message("⚠️ 枠が満杯。先に外して（キット）", ephemeral=True); return
        if vp["learned_skills"].get(sid, 0) <= 0 or not _skill_fits(part, inst["item"], sid):
            await it.response.send_message("❌ ここには刻めない技", ephemeral=True); return
        vp["learned_skills"][sid] -= 1
        if vp["learned_skills"][sid] <= 0: del vp["learned_skills"][sid]
        inst.setdefault("skills", []).append(sid)
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=EquipShopView(uid, gid))
        await it.followup.send(f"⚒️ {PART_NAMES[part]} に **{VS.SKILLS[sid]['name']}** を刻んだ！", ephemeral=True)

# ── 技を外す（キット消費・装備中インスタンスから）──
class UnengraveView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
        vp = db.get_voyage(user_id); pairs = []
        for part in ("weapon", "torso", "legs"):
            inst = equipped_inst(vp, part)
            if inst:
                for i, sid in enumerate(inst.get("skills", [])):
                    pairs.append((part, i, sid))
        if pairs: self.add_item(UnengraveSelect(user_id, gid, pairs))
        self.has_pairs = bool(pairs)
        self.add_item(_eqshop_back(user_id, gid))

class UnengraveSelect(discord.ui.Select):
    def __init__(self, user_id, gid, pairs):
        self.user_id = str(user_id); self.gid = str(gid)
        opts = [discord.SelectOption(label=f"{PART_NAMES[p]}：{VS.SKILLS[sid]['name']} を外す", value=f"{p}:{i}")
                for p, i, sid in pairs]
        super().__init__(placeholder="外す技を選ぶ（キット1個）", options=opts[:25])
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        uid, gid = self.user_id, self.gid; part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(uid)
        if vp.get("unequip_kits", 0) <= 0:
            await it.response.send_message("🧰 キットが無い", ephemeral=True); return
        inst = equipped_inst(vp, part)
        if not inst or i >= len(inst.get("skills", [])):
            await it.response.send_message("もう外れている", ephemeral=True); return
        sid = inst["skills"].pop(i); vp["unequip_kits"] -= 1
        vp["learned_skills"][sid] = vp["learned_skills"].get(sid, 0) + 1
        db.save_voyage(uid, vp)
        await it.response.edit_message(embed=build_equipshop_embed(vp, uid, gid), view=EquipShopView(uid, gid))
        await it.followup.send(f"🔧 **{VS.SKILLS[sid]['name']}** を外した（キット-1）。技は手元へ。", ephemeral=True)

# ━━━━━━━━ 📦 インベントリ（タブ：装備/技/消耗品/船）━━━━━━━━
def build_inv_embed(vp, tab):
    if tab == "equip":
        e = discord.Embed(title="📦 インベントリ ── 🗡️ 装備", color=0x2E86C1)
        e.add_field(name="📊 ステータス",
                    value=(f"❤️ HP {vp.get('cur_hp', max_hp(vp))}/{max_hp(vp)}\n"
                           f"⚔️ 攻撃力 {attack_power(vp)}\n"
                           f"🛡️ 防御力 {defense_power(vp)}\n"
                           f"📊 レベル {vp['level']}（XP {vp['xp']}/{V.xp_to_next(vp['level'])}）\n"
                           f"🗡️ 総合戦闘力 **{personal_power(vp)}**"), inline=False)
        for part in ("weapon", "torso", "legs"):
            lst = vp["inventory"][part]; eq = vp["equipped"][part]
            if lst:
                lines = []
                for i, inst in enumerate(lst):
                    mark = "✅" if eq == i else "・"
                    lines.append(f"{mark} {item_label(part, inst)}")
                val = "\n".join(lines)
            else:
                val = "（なし）"
            e.add_field(name=f"{PART_NAMES[part]} {len(lst)}/{INV_CAP[part]}", value=val, inline=False)
    elif tab == "skill":
        e = discord.Embed(title="📦 インベントリ ── ⚔️ 技（未刻印）", color=0x2E86C1)
        inv = vp.get("learned_skills", {})
        lines = [f"{VS.SKILLS[s]['emoji']} {VS.SKILLS[s]['name']} ×{n}"
                 for s, n in inv.items() if n > 0]
        e.description = "\n".join(lines) if lines else "未刻印の技はなし"
        e.set_footer(text=f"所持 {sum(inv.values())}/{SKILL_CAP}　※技を選ぶと詳細／売却は装備屋で")
    elif tab == "item":
        e = discord.Embed(title="📦 インベントリ ── 🧪 消耗品", color=0x2E86C1)
        e.add_field(name="📊 ステータス",
                    value=(f"❤️ HP {vp.get('cur_hp', max_hp(vp))}/{max_hp(vp)}\n"
                           f"⚔️ 攻撃力 {attack_power(vp)}　🛡️ 防御力 {defense_power(vp)}\n"
                           f"📊 レベル {vp['level']}（XP {vp['xp']}/{V.xp_to_next(vp['level'])}）"),
                    inline=False)
        foods = vp.get("foods", {})
        food_lines = [f"{V.FOODS[k]['emoji']} {V.FOODS[k]['name']} ×{n}（HP+{int(V.FOODS[k]['heal_pct']*100)}%）"
                      for k, n in foods.items() if n > 0]
        e.add_field(name="🍖 食料", value="\n".join(food_lines) if food_lines else "なし", inline=False)
        land_inv = vp.get("land_items", {})
        land_lines = []
        for iid, n in land_inv.items():
            if n > 0 and iid in getattr(L, "LAND_ITEMS", {}):
                it = L.LAND_ITEMS[iid]
                land_lines.append(f"{it['emoji']} {it['name']} ×{n}（{it.get('desc','')}）")
        e.add_field(name="🧭 探索アイテム", value="\n".join(land_lines) if land_lines else "なし", inline=False)
        lottery = vp.get("lottery_tickets", 0)
        special = vp.get("special_items", []) or []
        other_lines = [f"技外しキット ×{vp.get('unequip_kits',0)}", f"🎖️ ガチャメダル ×{vp.get('gacha_medals',0)}"]
        if lottery:
            other_lines.append(f"{V.LOTTERY_ITEM['emoji']} {V.LOTTERY_ITEM['name']} ×{lottery}")
        if special:
            pet_counts = {}
            for x in special:
                if x in getattr(V, "PETS", {}): pet_counts[x] = pet_counts.get(x, 0) + 1
            for pid, n in pet_counts.items():
                pet = V.PETS[pid]
                other_lines.append(f"{pet['emoji']} {pet['name']} ×{n}（特殊アイテム）")
        e.add_field(name="🧰 その他", value="\n".join(other_lines), inline=False)
        mats = vp.get("materials", {})
        mat_lines = [f"{V.MATERIALS[k]['emoji']} {V.MATERIALS[k]['name']} ×{n}"
                     for k, n in mats.items() if n > 0]
        if mat_lines:
            e.add_field(name="💎 素材（将来クラフト用に保管中）",
                        value="　".join(mat_lines), inline=False)
    else:  # ship
        e = discord.Embed(title="📦 インベントリ ── 🚢 船", color=0x2E86C1,
                          description="船・船装備は **港** でいじれる（ここでは閲覧のみ）。")
        if not vp["has_ship"]:
            e.add_field(name="船", value="未所持（港で仕立てる）", inline=False)
        else:
            sd = ship_def_of(vp)
            e.add_field(name=f"🚢 {V.rarity_stars(sd['rank'])} {sd['name']}",
                        value=f"❤️HP {sd['base_hp']}／🛡️基礎防御 {sd['base_def']}／攻撃 {ship_attack(vp)}・防御 {ship_defense(vp)}",
                        inline=False)
            lines = []
            for part in V.SHIP_PART_ORDER:
                meta = V.SHIP_PART_META[part]; inst = ship_part_inst(vp, part); pdef = ship_part_def(vp, part)
                if inst and pdef:
                    sk = "".join(VS.SKILLS[x]["emoji"] for x in inst.get("skills", []))
                    lines.append(f"{meta['emoji']} {meta['name']}：{V.rarity_stars(pdef['rank'])} {pdef['name']}"
                                 f"（耐久 {inst.get('dura',0)}/{pdef.get('dura',1)}）{sk}")
                else:
                    lines.append(f"{meta['emoji']} {meta['name']}：なし")
            bsk = vp.get("ship_skills", [])
            if bsk:
                lines.append("🚢 船本体技：" + " ".join(VS.SKILLS[x]["name"] for x in bsk))
            e.add_field(name="🔧 部位", value="\n".join(lines), inline=False)
    return e

class InventoryView(discord.ui.View):
    def __init__(self, user_id, gid, tab="equip", back="town"):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.tab = tab; self.back = back
        # タブ
        for key, label in [("equip", "🗡️ 装備"), ("skill", "⚔️ 技"), ("item", "🧪 消耗品"), ("ship", "🚢 船")]:
            self.add_item(InvTabButton(key, label, key == tab))
        # 装備タブ専用：持ち替え・外す（売却は装備屋でのみ）
        vp = db.get_voyage(user_id)
        if tab == "equip":
            if any(vp["inventory"][p] for p in ("weapon", "torso", "legs")):
                self.add_item(EquipSwitchSelect(user_id, gid, back))
            if any(vp["equipped"][p] is not None for p in ("weapon", "torso", "legs")):
                self.add_item(UnequipPartSelect(user_id, gid, back))
        elif tab == "skill":
            if any(n > 0 for n in vp.get("learned_skills", {}).values()):
                self.add_item(SkillDetailSelect(user_id, gid, back))
        elif tab == "item":
            if any(n > 0 for n in vp.get("foods", {}).values()):
                self.add_item(FoodEatSelect(user_id, gid, back))
            if vp.get("lottery_tickets", 0) > 0:
                self.add_item(LotteryUseButton(user_id, gid, back))
        self.add_item(InvBackButton(user_id, gid, back))

class LotteryUseButton(discord.ui.Button):
    def __init__(self, user_id, gid, back):
        super().__init__(label="🎟️ 宝くじを使う", style=discord.ButtonStyle.success, row=2)
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.user_id)
        if vp.get("lottery_tickets", 0) <= 0:
            await it.response.send_message("🎟️ 宝くじがない。", ephemeral=True); return
        r = random.random(); prize = 0; label = "ハズレ"
        if r < 0.001:
            prize, label = 1_000_000, "超大当たり 100万コイン"
        elif r < 0.011:
            prize, label = 50_000, "大当たり 5万コイン"
        elif r < 0.061:
            prize, label = 10_000, "当たり 1万コイン"
        elif r < 0.161:
            prize, label = 1_000, "小当たり 1000コイン"
        elif r < 0.361:
            prize, label = 100, "末等 100コイン"
        vp["lottery_tickets"] = max(0, vp.get("lottery_tickets", 0) - 1)
        db.save_voyage(self.user_id, vp)
        if prize:
            db.update_balance(self.user_id, self.gid, prize)
        e = discord.Embed(title="🎟️ 宝くじ 開封", color=0xf1c40f if prize else 0x7f8c8d)
        e.description = "カリカリ……封を切る音が、妙に大きく聞こえる。\n\n" + (f"🎊 **{label}！**\n+{prize:,} ナトコイン" if prize else "……紙。完全に紙。\n**ハズレ**")
        await it.response.edit_message(embed=e, view=InventoryView(self.user_id, self.gid, "item", self.back))

class FoodEatSelect(discord.ui.Select):
    """🍖 食料を食べてHP回復（航海中の体力管理）。"""
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for fid, n in vp.get("foods", {}).items():
            if n > 0 and fid in V.FOODS:
                f = V.FOODS[fid]
                opts.append(discord.SelectOption(
                    label=f"{f['name']} ×{n}（HP+{int(f['heal_pct']*100)}%）",
                    emoji=f["emoji"], value=fid))
        super().__init__(placeholder="🍖 食料を食べる（HP回復）", options=opts[:25], row=1)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        fid = self.values[0]; f = V.FOODS[fid]
        vp = db.get_voyage(self.user_id)
        mh = max_hp(vp); cur = vp.get("cur_hp", mh)
        if cur >= mh:
            await it.response.send_message("❤️ HPは満タンだ。今は食べなくていい。", ephemeral=True); return
        heal = int(mh * f["heal_pct"]); before = cur
        vp["cur_hp"] = min(mh, cur + heal)
        vp["foods"][fid] -= 1
        if vp["foods"][fid] <= 0: del vp["foods"][fid]
        db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "item"),
                                       view=InventoryView(self.user_id, self.gid, "item", self.back))
        await it.followup.send(f"{f['emoji']} **{f['name']}** を食べた。HP {before}→{vp['cur_hp']}（+{vp['cur_hp']-before}）", ephemeral=True)

class InvTabButton(discord.ui.Button):
    def __init__(self, key, label, active):
        super().__init__(label=label, style=discord.ButtonStyle.primary if active else discord.ButtonStyle.secondary,
                         row=0, disabled=active)
        self.key = key
    async def callback(self, it):
        v = self.view
        if str(it.user.id) != v.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(embed=build_inv_embed(db.get_voyage(v.user_id), self.key),
                                       view=InventoryView(v.user_id, v.gid, self.key, v.back))

class EquipSwitchSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            for i, inst in enumerate(vp["inventory"][part]):
                eqmark = "（装備中）" if vp["equipped"][part] == i else ""
                opts.append(discord.SelectOption(
                    label=f"{PART_NAMES[part].split(' ')[1]}: {item_label(part, inst, False)[:70]}{eqmark}",
                    value=f"{part}:{i}"))
        super().__init__(placeholder="装備する（持ち替え）", options=opts[:25], row=1)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part, i = self.values[0].split(":"); i = int(i)
        vp = db.get_voyage(self.user_id); vp["equipped"][part] = i; db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "equip"),
                                       view=InventoryView(self.user_id, self.gid, "equip", self.back))

class UnequipPartSelect(discord.ui.Select):
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id); opts = []
        for part in ("weapon", "torso", "legs"):
            if vp["equipped"][part] is not None:
                opts.append(discord.SelectOption(label=f"{PART_NAMES[part]} を外す", value=part))
        super().__init__(placeholder="装備を外す", options=opts, row=2)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        part = self.values[0]
        vp = db.get_voyage(self.user_id); vp["equipped"][part] = None; db.save_voyage(self.user_id, vp)
        await it.response.edit_message(embed=build_inv_embed(vp, "equip"),
                                       view=InventoryView(self.user_id, self.gid, "equip", self.back))

class SkillDetailSelect(discord.ui.Select):
    """技を選ぶと詳細を表示（売却はしない。売却は装備屋のみ）。"""
    def __init__(self, user_id, gid, back):
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
        vp = db.get_voyage(user_id)
        opts = []
        for s, n in vp.get("learned_skills", {}).items():
            if n > 0 and s in VS.SKILLS:
                sk = VS.SKILLS[s]
                opts.append(discord.SelectOption(
                    label=f"{sk['name']} ×{n}", value=s, emoji=sk.get("emoji"),
                    description=f"{V.rarity_stars(sk.get('rank',1))}・{sk.get('type','')}"[:90]))
        super().__init__(placeholder="⚔️ 技を選んで詳細を見る", options=opts[:25], row=1)
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        sk = VS.SKILLS[self.values[0]]
        wt = "・".join(V.WEAPON_TYPES[w]["name"] if hasattr(V, "WEAPON_TYPES") and w in getattr(V, "WEAPON_TYPES", {}) else w
                      for w in sk.get("wtypes", [])) or "—"
        e = discord.Embed(title=f"{sk.get('emoji','⚔️')} {sk['name']}　{V.rarity_stars(sk.get('rank',1))}",
                          description=sk.get("desc", ""), color=0x9b59b6)
        lines = [f"種別：{sk.get('type','—')}", f"威力倍率：{sk.get('power','—')}", f"ヒット数：{sk.get('hits',1)}"]
        if sk.get("cooldown"): lines.append(f"クールダウン：{sk['cooldown']}ターン")
        if sk.get("charge"): lines.append(f"溜め：{sk['charge']}ターン")
        lines.append(f"対応武器：{wt}")
        e.add_field(name="性能", value="\n".join(lines), inline=False)
        e.set_footer(text="※売却・刻印は装備屋でできる")
        await it.response.send_message(embed=e, ephemeral=True)

class InvBackButton(discord.ui.Button):
    def __init__(self, user_id, gid, back):
        super().__init__(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=4)
        self.user_id = str(user_id); self.gid = str(gid); self.back = back
    async def callback(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        if self.back == "equip":
            await it.response.edit_message(embed=build_equipshop_embed(db.get_voyage(self.user_id), self.user_id, self.gid),
                                           view=EquipShopView(self.user_id, self.gid))
        elif self.back == "port":
            await it.response.edit_message(embed=build_port_embed(db.get_voyage(self.user_id)),
                                           view=PortView(self.user_id, self.gid))
        else:
            from cogs.menu import go_town
            await go_town(it, self.user_id)

async def _replace_or_send(interaction, *, embed, view=None, ephemeral=False):
    """ボタン操作なら既存メッセージを編集。slash等で編集できない時だけ新規送信。"""
    if interaction.response.is_done():
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            await interaction.followup.send(embed=embed, view=view, ephemeral=ephemeral)
        return
    try:
        await interaction.response.edit_message(embed=embed, view=view)
    except Exception:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=ephemeral)

async def open_inventory(interaction, user_id=None, back="town"):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    await _replace_or_send(interaction, embed=build_inv_embed(vp, "equip"), view=InventoryView(uid, gid, "equip", back))

async def open_equip_shop(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    await _replace_or_send(interaction, embed=build_equipshop_embed(vp, uid, gid), view=EquipShopView(uid, gid))

# ━━━━━━━━ 🛒 道具屋（商店街専用。ドック/船屋へは戻さない）━━━━━━━━
def _daily_random_shop_items(gid):
    """ランダム入荷：日付＋ギルドで固定。毎日ラインナップが変わる。"""
    import datetime, hashlib, random as _r
    candidates = [iid for iid, it in getattr(L, "LAND_ITEMS", {}).items() if it.get("shop") == "random"]
    seed = f"{datetime.date.today().isoformat()}:{gid}:landshop"
    rng = _r.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:12], 16))
    rng.shuffle(candidates)
    return candidates[:2]


def build_itemshop_embed(vp, uid, gid):
    e = discord.Embed(
        title="🛒 ポロ（道具屋）",
        color=0xe67e22,
        description=(
            "『腹が減ったら歩けないし、備えがなければ帰れないよ。』\n"
            "旅の食料と、街道で役立つ小道具が並んでいる。"
        ),
    )
    e.add_field(name="💰 所持金", value=f"**{db.get_balance(uid, gid):,}** ナトコイン", inline=False)
    # 常設：食料
    for fid, f in V.FOODS.items():
        have = vp.get("foods", {}).get(fid, 0)
        e.add_field(
            name=f"{f['emoji']} {f['name']}（所持{have}）",
            value=f"HP+{int(f['heal_pct']*100)}%・**{f['price']:,}**コイン",
            inline=True,
        )
    # 常設：探索アイテム（包帯）
    always = [iid for iid, it in getattr(L, "LAND_ITEMS", {}).items() if it.get("shop") == "always"]
    daily = _daily_random_shop_items(gid)
    lines = []
    for iid in always + daily:
        it = L.LAND_ITEMS[iid]
        have = vp.get("land_items", {}).get(iid, 0)
        tag = "常設" if it.get("shop") == "always" else "本日入荷"
        lines.append(f"{it['emoji']} **{it['name']}**（{tag}/所持{have}）\n{it['desc']}・**{it['price']:,}**コイン")
    e.add_field(name="🛤️ 街道消耗品", value="\n".join(lines) if lines else "本日の入荷なし", inline=False)
    e.set_footer(text="ポロは商品棚の奥を時々入れ替えている。")
    return e

class ItemShopView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.add_item(ItemFoodBuySelect(uid, gid))
        self.add_item(ItemLandItemBuySelect(uid, gid))
        self.add_item(ItemShopBackButton(uid, gid))

class QuantityBuyModal(discord.ui.Modal):
    def __init__(self, uid, gid, kind, item_id, name, emoji, price, have):
        super().__init__(title=f"{name}を買う")
        self.uid = str(uid); self.gid = str(gid)
        self.kind = kind; self.item_id = item_id
        self.name = name; self.emoji = emoji; self.price = int(price); self.have = int(have)
        self.qty = discord.ui.TextInput(
            label=f"購入数（1個 {self.price:,}コイン / 所持 {self.have}）",
            placeholder="例: 3",
            min_length=1,
            max_length=5,
        )
        self.add_item(self.qty)

    async def on_submit(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        raw = str(self.qty.value).replace(",", "").replace("，", "").strip()
        try:
            q = int(raw)
        except ValueError:
            await it.response.send_message("数字で入力してね。", ephemeral=True); return
        if q <= 0:
            await it.response.send_message("1個以上で入力してね。", ephemeral=True); return
        if q > 999:
            await it.response.send_message("一度に買えるのは999個まで。", ephemeral=True); return
        cost = self.price * q
        bal = db.get_balance(self.uid, self.gid)
        if bal < cost:
            await it.response.send_message(f"💰 コインが足りない（必要 {cost:,} / 所持 {bal:,}）。", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        if self.kind == "food":
            vp.setdefault("foods", {})[self.item_id] = vp.setdefault("foods", {}).get(self.item_id, 0) + q
        else:
            vp.setdefault("land_items", {})[self.item_id] = vp.setdefault("land_items", {}).get(self.item_id, 0) + q
        db.update_balance(self.uid, self.gid, -cost)
        db.add_zukan(self.uid, "item_seen", self.item_id)
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(embed=build_itemshop_embed(vp, self.uid, self.gid), view=ItemShopView(self.uid, self.gid))
        await it.followup.send(f"{self.emoji} **{self.name} ×{q}** を購入した（-{cost:,}）。", ephemeral=True)

class ItemLandItemBuySelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(uid)
        ids = [iid for iid, it in getattr(L, "LAND_ITEMS", {}).items() if it.get("shop") == "always"] + _daily_random_shop_items(gid)
        opts = []
        for iid in ids:
            it = L.LAND_ITEMS[iid]
            have = vp.get("land_items", {}).get(iid, 0)
            opts.append(discord.SelectOption(
                label=f"{it['name']} / {it['price']:,}コイン", emoji=it["emoji"], value=iid,
                description=f"所持{have}・{it.get('desc','')[:70]}"))
        if not opts:
            opts = [discord.SelectOption(label="本日の入荷なし", value="__none__")]
        super().__init__(placeholder="🛤️ 街道の小道具を選ぶ", options=opts[:25], row=1)
    async def callback(self, itx):
        if str(itx.user.id) != self.uid:
            await itx.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        iid = self.values[0]
        if iid == "__none__" or iid not in getattr(L, "LAND_ITEMS", {}):
            await itx.response.send_message("ポロは棚を指差した。今は空っぽだ。", ephemeral=True); return
        meta = L.LAND_ITEMS[iid]
        price = int(meta.get("price", 0))
        if price <= 0:
            await itx.response.send_message("ポロは首を横に振った。これは値札のない品らしい。", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        have = vp.get("land_items", {}).get(iid, 0)
        await itx.response.send_modal(QuantityBuyModal(self.uid, self.gid, "land", iid, meta["name"], meta["emoji"], price, have))

class ItemShopBackButton(discord.ui.Button):
    def __init__(self, uid, gid):
        super().__init__(label="◀ 商店街へ戻る", style=discord.ButtonStyle.secondary, row=2)
        self.uid = str(uid); self.gid = str(gid)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        from cogs.menu import open_shopping_street
        await open_shopping_street(it, self.uid, self.gid)

class ItemFoodBuySelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(uid)
        opts = []
        for fid, f in V.FOODS.items():
            have = vp.get("foods", {}).get(fid, 0)
            opts.append(discord.SelectOption(
                label=f"{f['name']} / {f['price']:,}コイン", emoji=f["emoji"], value=fid,
                description=f"所持{have}・HP+{int(f['heal_pct']*100)}%"))
        super().__init__(placeholder="🍖 食料を選ぶ", options=opts[:25], row=0)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        fid = self.values[0]
        if fid not in V.FOODS:
            await it.response.send_message("ポロは首をかしげた。その品は見当たらない。", ephemeral=True); return
        f = V.FOODS[fid]
        vp = db.get_voyage(self.uid)
        have = vp.get("foods", {}).get(fid, 0)
        await it.response.send_modal(QuantityBuyModal(self.uid, self.gid, "food", fid, f["name"], f["emoji"], int(f["price"]), have))

async def open_item_shop(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    await _replace_or_send(interaction, embed=build_itemshop_embed(vp, uid, gid), view=ItemShopView(uid, gid))
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎰 技ガチャ屋
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _gacha_skill3_pool():
    return [sid for sid, sk in VS.SKILLS.items()
            if sk.get("rank") == 3 and sk.get("slot") in ("weapon", "armor")]

GACHA_FOOD_POOL = ["hardtack", "jerky", "feast"]
GACHA_LAND_COMMON_POOL = ["bandage"]
GACHA_RARE_ITEM_POOL = ["smoke_bomb", "lucky_charm", "old_map"]
GACHA_UNCOMMON_ITEM_POOL = ["lantern", "gold_compass"]
GACHA_EPIC_ITEM_POOL = ["decoy_doll", "guardian_feather"]

def _add_gacha_medals(uid: str, count: int):
    vp = db.get_voyage(uid)
    vp["gacha_medals"] = vp.get("gacha_medals", 0) + int(count) * V.GACHA_MEDAL_PER_PULL
    db.save_voyage(uid, vp)
    return vp["gacha_medals"]

def _give_food_or_bandage(vp, uid: str):
    # コモン枠：食料と包帯。食料はfoods、包帯はland_itemsへ。
    if random.random() < 0.25:
        iid = "bandage"
        vp.setdefault("land_items", {})[iid] = vp.setdefault("land_items", {}).get(iid, 0) + 1
        db.add_zukan(uid, "item_seen", iid)
        it = L.LAND_ITEMS[iid]
        return {"kind": "item_common", "text": f"{it['emoji']} {it['name']}", "id": iid}
    fid = random.choices(GACHA_FOOD_POOL, weights=[45, 35, 20], k=1)[0]
    vp.setdefault("foods", {})[fid] = vp.setdefault("foods", {}).get(fid, 0) + 1
    db.add_zukan(uid, "item_seen", fid)
    f = V.FOODS[fid]
    return {"kind": "food", "text": f"{f['emoji']} {f['name']}", "id": fid}

def _give_land_item(vp, uid: str, pool, kind: str):
    iid = random.choice(pool)
    vp.setdefault("land_items", {})[iid] = vp.setdefault("land_items", {}).get(iid, 0) + 1
    db.add_zukan(uid, "item_seen", iid)
    it = L.LAND_ITEMS[iid]
    return {"kind": kind, "text": f"{it['emoji']} {it['name']}", "id": iid}

def _roll_skill_gacha(uid: str):
    vp = db.get_voyage(uid)
    r = random.random()
    cursor = V.GACHA_SKILL3_RATE
    if r < cursor:
        pool = _gacha_skill3_pool()
        sid = random.choice(pool)
        vp.setdefault("learned_skills", {})[sid] = vp.setdefault("learned_skills", {}).get(sid, 0) + 1
        db.add_zukan(uid, "skill_seen", sid)
        sk = VS.SKILLS[sid]
        result = {"kind": "skill3", "text": f"{V.rarity_stars(3)} {sk['emoji']} {sk['name']}", "id": sid}
    else:
        cursor += V.GACHA_PET_RATE
        if r < cursor:
            pid = random.choice(list(V.PETS.keys()))
            vp.setdefault("special_items", []).append(pid)
            db.add_zukan(uid, "item_seen", pid)
            pet = V.PETS[pid]
            result = {"kind": "pet", "text": f"{pet['emoji']} {pet['name']}", "id": pid}
        else:
            cursor += V.GACHA_EPIC_ITEM_RATE
            if r < cursor:
                result = _give_land_item(vp, uid, GACHA_EPIC_ITEM_POOL, "item_epic")
            else:
                cursor += V.GACHA_RARE_ITEM_RATE
                if r < cursor:
                    result = _give_land_item(vp, uid, GACHA_RARE_ITEM_POOL, "item_rare")
                else:
                    cursor += V.GACHA_UNCOMMON_ITEM_RATE
                    if r < cursor:
                        result = _give_land_item(vp, uid, GACHA_UNCOMMON_ITEM_POOL, "item_uncommon")
                    else:
                        cursor += V.GACHA_FOOD_RATE
                        if r < cursor:
                            result = _give_food_or_bandage(vp, uid)
                        else:
                            vp["lottery_tickets"] = vp.get("lottery_tickets", 0) + 1
                            db.add_zukan(uid, "item_seen", V.LOTTERY_ITEM_ID)
                            result = {"kind": "lottery", "text": f"{V.LOTTERY_ITEM['emoji']} {V.LOTTERY_ITEM['name']}", "id": V.LOTTERY_ITEM_ID}
    db.save_voyage(uid, vp)
    return result

def build_skill_gacha_embed(uid: str, gid: str):
    bal = db.get_balance(uid, gid)
    vp = db.get_voyage(uid)
    medals = vp.get("gacha_medals", 0)
    e = discord.Embed(
        title="🎰 ノワール（ガチャ屋） ── 深淵スキルカプセル",
        description=(
            "ノワールが黒い箱を撫でる。中から、金属音とも心音ともつかない音。\n\n"
            f"**1回** {V.GACHA_PRICE:,} コイン / **10連** {V.GACHA_TEN_PRICE:,} コイン\n"
            f"🎖️ **ガチャメダル**：1回につき +{V.GACHA_MEDAL_PER_PULL}枚\n\n"
            "🌈 **☆3技**：0.2%\n"
            "🐾 **ペット**：0.1%\n"
            "🟣 **幻の探索アイテム**：0.1%（身代わり人形 / 守護の羽）\n"
            "🔵 **レア探索アイテム**：2.2%（煙玉 / お守り / 地図）\n"
            "🟢 **探索アイテム**：4.0%（ランタン / 羅針盤）\n"
            "⚪ **食料・包帯**：45.0%\n"
            "🎟️ **宝くじ**：残り\n\n"
            f"現在残高：**{bal:,}** ナトコイン\n"
            f"所持メダル：🎖️ **{medals:,}枚**\n"
            f"☆3交換まで：**{max(0, V.GACHA_SKILL3_EXCHANGE_MEDALS-medals):,}枚** / ペット交換まで：**{max(0, V.GACHA_PET_EXCHANGE_MEDALS-medals):,}枚**"
        ),
        color=0x8e44ad,
    )
    e.set_footer(text="※メダル交換：好きな☆3技=200枚 / 好きなペット=400枚")
    return e

class SkillGachaView(discord.ui.View):
    def __init__(self, user_id, gid):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid)
    async def guard(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたのガチャではありません", ephemeral=True); return False
        return True
    async def _spin(self, it, count: int):
        if not await self.guard(it): return
        price = V.GACHA_TEN_PRICE if count == 10 else V.GACHA_PRICE
        if db.get_balance(self.user_id, self.gid) < price:
            await it.response.send_message(f"❌ コインが足りない（必要 {price:,}）", ephemeral=True); return
        db.update_balance(self.user_id, self.gid, -price)
        medals_now = _add_gacha_medals(self.user_id, count)
        e = discord.Embed(title="🎰 技ガチャ 起動", description="🔒 ロック解除中……\n▓▓░░░░░░░░", color=0x2c3e50)
        await it.response.edit_message(embed=e, view=None)
        await asyncio.sleep(1.2)
        e.description = "⚙️ 歯車が噛み合う。\n▓▓▓▓▓░░░░░\n\n**まだ開かない。**"
        await it.edit_original_response(embed=e)
        await asyncio.sleep(1.4)
        e.description = "💜 箱の奥が光った。\n▓▓▓▓▓▓▓▓░░\n\n心臓に悪い沈黙が流れる。"
        await it.edit_original_response(embed=e)
        await asyncio.sleep(1.6)
        results = [_roll_skill_gacha(self.user_id) for _ in range(count)]
        hot = [r for r in results if r["kind"] in ("skill3", "pet", "item_epic")]
        if hot:
            flash = discord.Embed(title="🔥🔥🔥 激熱演出 🔥🔥🔥", description="画面が白く焼ける。\n鐘が鳴る。\n**これは、ただのハズレではない。**", color=0xff3b30)
            await it.edit_original_response(embed=flash)
            await asyncio.sleep(2.0)
        labels = {
            "skill3": "🌈 **大当たり**",
            "pet": "🐾 **ペット降臨**",
            "item_epic": "🟣 **幻影反応**",
            "item_rare": "🔵 **レア**",
            "item_uncommon": "🟢 **小当たり**",
            "food": "⚪",
            "item_common": "⚪",
            "lottery": "・",
        }
        lines = [f"{labels.get(r['kind'], '・')} {r['text']}" for r in results]
        color = 0xffd700 if any(r["kind"] == "skill3" for r in results) else (0xff3b30 if hot else 0x7f8c8d)
        title = "🎉 技ガチャ 結果" if hot else "🎰 技ガチャ 結果"
        e = discord.Embed(title=title, description="\n".join(lines), color=color)
        e.set_footer(text=f"🎖️メダル +{count} → {medals_now:,}枚 / -{price:,} コイン / 残高 {db.get_balance(self.user_id, self.gid):,}")
        await it.edit_original_response(embed=e, view=SkillGachaView(self.user_id, self.gid))
    @discord.ui.button(label="1回まわす（10,000）", style=discord.ButtonStyle.primary, row=0)
    async def once(self, it, b):
        await self._spin(it, 1)
    @discord.ui.button(label="10連まわす（90,000）", style=discord.ButtonStyle.danger, row=0)
    async def ten(self, it, b):
        await self._spin(it, 10)
    @discord.ui.button(label="🏅 メダル交換所", style=discord.ButtonStyle.success, row=1)
    async def exchange(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_gacha_exchange_embed(self.user_id), view=GachaExchangeView(self.user_id, self.gid))
    @discord.ui.button(label="📦 インベントリ", style=discord.ButtonStyle.secondary, row=2)
    async def inv(self, it, b):
        if not await self.guard(it): return
        await open_inventory(it, self.user_id, back="town")
    @discord.ui.button(label="◀ 商店街へ", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, it, b):
        if not await self.guard(it): return
        from cogs.menu import open_shopping_street
        await open_shopping_street(it, self.user_id, self.gid)

def build_gacha_exchange_embed(uid: str):
    vp = db.get_voyage(uid)
    medals = vp.get("gacha_medals", 0)
    return discord.Embed(
        title="🏅 ガチャメダル交換所",
        description=(
            f"所持メダル：🎖️ **{medals:,}枚**\n\n"
            f"🌈 好きな☆3技：**{V.GACHA_SKILL3_EXCHANGE_MEDALS}枚**\n"
            f"🐾 好きなペット：**{V.GACHA_PET_EXCHANGE_MEDALS}枚**\n\n"
            "運に見放されても、箱は少しずつこちらを覚えていく。"
        ),
        color=0xf1c40f,
    )

class SkillExchangeSelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        opts = []
        for sid in _gacha_skill3_pool()[:25]:
            sk = VS.SKILLS[sid]
            opts.append(discord.SelectOption(label=sk["name"][:100], value=sid, emoji=sk.get("emoji", "🌈"), description="☆3技 200枚"))
        super().__init__(placeholder="🌈 交換する☆3技を選ぶ（200枚）", min_values=1, max_values=1, options=opts, row=0)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの交換所ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        if vp.get("gacha_medals", 0) < V.GACHA_SKILL3_EXCHANGE_MEDALS:
            await it.response.send_message(f"🎖️ メダルが足りない（必要 {V.GACHA_SKILL3_EXCHANGE_MEDALS}枚）", ephemeral=True); return
        sid = self.values[0]
        vp["gacha_medals"] -= V.GACHA_SKILL3_EXCHANGE_MEDALS
        vp.setdefault("learned_skills", {})[sid] = vp.setdefault("learned_skills", {}).get(sid, 0) + 1
        db.save_voyage(self.uid, vp)
        db.add_zukan(self.uid, "skill_seen", sid)
        sk = VS.SKILLS[sid]
        await it.response.edit_message(embed=build_gacha_exchange_embed(self.uid), view=GachaExchangeView(self.uid, self.gid))
        await it.followup.send(f"🌈 **{sk['emoji']} {sk['name']}** と交換した！（🎖️-{V.GACHA_SKILL3_EXCHANGE_MEDALS}）", ephemeral=True)

class PetExchangeSelect(discord.ui.Select):
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        opts = [discord.SelectOption(label=p["name"], value=pid, emoji=p.get("emoji", "🐾"), description="ペット 400枚") for pid, p in V.PETS.items()]
        super().__init__(placeholder="🐾 交換するペットを選ぶ（400枚）", min_values=1, max_values=1, options=opts, row=1)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの交換所ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        if vp.get("gacha_medals", 0) < V.GACHA_PET_EXCHANGE_MEDALS:
            await it.response.send_message(f"🎖️ メダルが足りない（必要 {V.GACHA_PET_EXCHANGE_MEDALS}枚）", ephemeral=True); return
        pid = self.values[0]
        vp["gacha_medals"] -= V.GACHA_PET_EXCHANGE_MEDALS
        vp.setdefault("special_items", []).append(pid)
        db.save_voyage(self.uid, vp)
        db.add_zukan(self.uid, "item_seen", pid)
        pet = V.PETS[pid]
        await it.response.edit_message(embed=build_gacha_exchange_embed(self.uid), view=GachaExchangeView(self.uid, self.gid))
        await it.followup.send(f"🐾 **{pet['emoji']} {pet['name']}** と交換した！（🎖️-{V.GACHA_PET_EXCHANGE_MEDALS}）", ephemeral=True)

class GachaExchangeView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.add_item(SkillExchangeSelect(uid, gid))
        self.add_item(PetExchangeSelect(uid, gid))
    async def guard(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの交換所ではありません", ephemeral=True); return False
        return True
    @discord.ui.button(label="◀ ガチャ屋へ", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, it, b):
        if not await self.guard(it): return
        await it.response.edit_message(embed=build_skill_gacha_embed(self.uid, self.gid), view=SkillGachaView(self.uid, self.gid))

async def open_skill_gacha(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    await _replace_or_send(interaction, embed=build_skill_gacha_embed(uid, gid), view=SkillGachaView(uid, gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 戦闘UI（CombatView）── エンジン voyage_combat を Discord で操作
#   通常攻撃／通常防御／✨特技(刻んだ技・CD/溜め制限)／敵AI。海戦・白兵 共通。
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import voyage_combat as C

def hp_bar(cur, mx, width=12):
    cur = max(0, cur); ratio = cur / mx if mx else 0
    f = round(width * ratio)
    return "🟩" * f + "⬛" * (width - f) if ratio > 0.3 else "🟥" * f + "⬛" * (width - f)

def board_skills(vp):
    """装備中の武器/胴/脚に刻まれた『白兵』技を集める。"""
    out = []
    for part in ("weapon", "torso", "legs"):
        inst = equipped_inst(vp, part)
        if inst:
            out += [s for s in inst.get("skills", []) if VS.SKILLS[s]["phase"] == "board"]
    return out

def naval_skills(vp):
    """船本体＋部位に刻まれた『海戦』技を集める。"""
    out = [s for s in vp.get("ship_skills", []) if VS.SKILLS[s]["phase"] == "naval"]
    for part in ("cannon", "armor", "rigging"):
        inst = vp["ship_parts"].get(part)
        if inst:
            out += [s for s in inst.get("skills", []) if VS.SKILLS[s]["phase"] == "naval"]
    return out

_ENEMY_SKILLS = {1: [], 2: [], 3: ["kyougeki"], 4: ["kyougeki", "shukketsu"], 5: ["kyougeki", "konshin"]}

# ── 敵ステ導出（sea_power/crew_power × combat_scale）──
def make_naval_ally(vp):
    """自船の海戦コンバタント。HPは ship_hp_cur を持ち越し（0以下は全快扱い＝出航直後など）。"""
    mx = max_hp(vp)
    cur = vp.get("cur_hp", mx)
    if cur <= 0:
        cur = mx
    c = C.make_combatant("自船", "🚢", mx, ship_attack(vp), ship_defense(vp), naval_skills(vp), ai_tier=0)
    c["hp"] = min(mx, cur)
    return c

def make_naval_enemy(spec, scale):
    S = spec["sea_power"] * V.combat_scale(scale)
    hp = max(1, round(S * V.NAVAL_E_HP_MULT))
    atk = max(1, round(S * V.NAVAL_E_ATK_MULT))
    dfn = max(0, round(S * V.NAVAL_E_DEF_MULT))
    tier = spec.get("tier", 3)
    return C.make_combatant(spec["name"], spec["emoji"], hp, atk, dfn,
                            skills=V.NAVAL_ENEMY_SKILLS.get(tier, []), ai_tier=tier)

def make_board_ally(vp):
    """白兵コンバタント。個人HPは毎戦全快。武器の手数(hits)で通常攻撃が多段になる。
    技ダメージは武器powerに依存せず、レベル+武器☆の基礎値で決まる（A案＝武器種で技は横並び）。"""
    c = C.make_combatant("あなた", "🧑", max_hp(vp),
                         attack_power(vp), defense_power(vp), board_skills(vp))
    lv_atk = _level_stat_bonus(vp.get("level", 1))
    w = equipped_inst(vp, "weapon")
    if w and w["item"] in V.WEAPONS:
        wd = V.WEAPONS[w["item"]]
        c["base_hits"] = wd.get("hits", 1)
        c["offhand_power"] = round(wd["power"] * V.OFFHAND_HIT_MULT)   # 2発目以降は武器power×0.6（レベル抜き）
        c["skill_base"] = lv_atk + V.SKILL_BASE_BY_RANK.get(wd["rank"], 30)  # 技基礎値＝レベル分+武器☆分
    else:
        c["skill_base"] = lv_atk
    return c

def make_board_enemy(spec, scale, defense=False):
    # 乗り込む側(攻)=敵全員で強い／乗り込まれる側(防衛)=敵一部で弱い
    mult = V.BOARD_DEFENSE_CREW_MULT if defense else 1.0
    Cw = spec["crew_power"] * V.combat_scale(scale) * mult
    # 経験値逃走モンスターなどは「硬くて1〜2ダメずつ削る」専用HPを持てる。
    # fixed_hp がある場合でも攻撃力・防御力はエリア基準のまま作る。
    hp = int(spec.get("fixed_hp")) if spec.get("fixed_hp") is not None else max(1, round(Cw * V.BOARD_E_HP_MULT * spec.get("hp_mult", 1.0)))
    atk = max(1, round(Cw * V.BOARD_E_ATK_MULT * spec.get("atk_mult", 1.0)))
    dfn = max(0, round(Cw * V.BOARD_E_DEF_MULT * spec.get("def_mult", 1.0)))
    tier = spec.get("tier", 3)
    skills = spec.get("skills") or _ENEMY_SKILLS.get(tier, [])
    c = C.make_combatant(spec["name"], spec["emoji"], hp, atk, dfn,
                         skills=skills, ai_tier=tier)
    # 💎 経験値逃走モンスター専用：どれだけ攻撃力・技倍率・貫通が高くても、
    # プレイヤー側から受けるダメージを戦闘エンジン側で固定化する。
    # 防御力だけで調整すると多段技・貫通・DoTで壊れるため、ここで明示フラグを渡す。
    if spec.get("is_xp_runner"):
        c["xp_damage_cap"] = True
    c["first_strike"] = spec.get("first_strike", False)   # 伏兵＝先制攻撃
    if spec.get("escape_chance"):
        c["escape_chance"] = float(spec.get("escape_chance", 0))
        c["escape_name"] = spec.get("name", c.get("name", "敵"))
    return c

def build_combat_embed(state):
    a = state["ally"]; e = state["enemy"]
    title = "⚔️ 白兵戦" if state["phase"] == "board" else "🚢 海戦"
    col = discord.Color.dark_red() if state["phase"] == "board" else discord.Color.dark_teal()
    emb = discord.Embed(title=f"{title} ── ターン {state['turn']}", color=col)
    emb.add_field(name=f"{e['emoji']} {e['name']}",
                  value=f"HP {max(0,e['hp'])}/{e['max_hp']}\n{hp_bar(e['hp'],e['max_hp'])}", inline=False)
    emb.add_field(name=f"{a['emoji']} {a['name']}  ⚔️{a['atk']} 🛡️{a['def']}",
                  value=f"HP {max(0,a['hp'])}/{a['max_hp']}\n{hp_bar(a['hp'],a['max_hp'])}", inline=False)
    if state["log"]:
        emb.add_field(name="📜 経過", value="\n".join(state["log"][-8:]), inline=False)
    if a.get("charging"):
        emb.set_footer(text=f"💢 {VS.SKILLS[a['charging']]['name']} 溜め中…次の行動で解放！")
    return emb

def _default_on_end(user_id):
    """模擬戦用：終了で結果＋閉じるボタン。"""
    async def _end(interaction, state):
        res = "🏆 勝利！" if state["result"] == "win" else "💀 敗北…"
        emb = build_combat_embed(state)
        emb.add_field(name="― 決着 ―", value=res, inline=False)
        await interaction.response.edit_message(embed=emb, view=CombatEndView(user_id))
    return _end

async def _advance(interaction, holder, action):
    """味方行動を解決して再描画。終了なら on_end に委譲（遷移/精算はそこで）。"""
    state = holder.state
    C.take_turn(state, action)
    # 💎 経験値逃走モンスター：ターン終了ごとに確率で逃走。
    # 勝敗ではないので land_on_end 側で専用処理する。
    if not state.get("over") and state.get("enemy", {}).get("escape_chance"):
        import random as _random
        if _random.random() < float(state["enemy"].get("escape_chance", 0)):
            state["over"] = True
            state["result"] = "escaped"
            state.setdefault("log", []).append(f"💨 {state['enemy'].get('escape_name', state['enemy'].get('name','敵'))} は光を散らして逃げ去った！")
    if state["over"]:
        await holder.on_end(interaction, state)
    else:
        await interaction.response.edit_message(
            embed=build_combat_embed(state),
            view=CombatView(holder.user_id, holder.gid, state,
                            on_end=holder.on_end, flee_cb=holder.flee_cb, flee_pct=holder.flee_pct))


class CombatItemSelect(discord.ui.Select):
    """戦闘中に使える探索アイテム（包帯/煙玉のみ）。食事は使わせない。"""
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(self.uid)
        opts = []
        for iid in ("bandage", "smoke_bomb"):
            n = vp.get("land_items", {}).get(iid, 0)
            if n > 0 and iid in getattr(L, "LAND_ITEMS", {}):
                it = L.LAND_ITEMS[iid]
                desc = "戦闘中にHPを25%回復" if iid == "bandage" else "この戦闘から即撤退（ボス以外）"
                opts.append(discord.SelectOption(label=f"{it['name']} ×{n}", emoji=it.get("emoji"), value=iid, description=desc))
        if not opts:
            opts = [discord.SelectOption(label="使える探索アイテムがない", value="__none__")]
        super().__init__(placeholder="🎒 探索アイテムを使う", options=opts[:25], row=3)

    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        iid = self.values[0]
        vp = db.get_voyage(view.user_id)
        if iid == "__none__" or vp.get("land_items", {}).get(iid, 0) <= 0:
            await it.response.send_message("使える探索アイテムがない。", ephemeral=True); return
        a = view.state["ally"]
        if iid == "bandage":
            if a.get("hp", 0) >= a.get("max_hp", 1):
                await it.response.send_message("❤️ HPは満タンだ。", ephemeral=True); return
            heal = max(1, int(a["max_hp"] * 0.25)); before = a["hp"]
            a["hp"] = min(a["max_hp"], a["hp"] + heal)
            item_log = f"🩹 包帯を使った。HP {before}→{a['hp']}"
        elif iid == "smoke_bomb":
            if view.flee_cb is None:
                await it.response.send_message("💨 この戦闘では煙玉を使えない。", ephemeral=True); return
            vp["land_items"][iid] -= 1
            if vp["land_items"][iid] <= 0: del vp["land_items"][iid]
            db.save_voyage(view.user_id, vp)
            view.state["_force_flee_success_once"] = True
            await view.flee_cb(it, view.state)
            return
        else:
            await it.response.send_message("そのアイテムは戦闘中には使えない。", ephemeral=True); return
        vp["land_items"][iid] -= 1
        if vp["land_items"][iid] <= 0: del vp["land_items"][iid]
        db.save_voyage(view.user_id, vp)
        await _advance(it, view, {"kind": "item", "text": item_log})

class CombatView(discord.ui.View):
    def __init__(self, user_id, gid, state, on_end=None, flee_cb=None, flee_pct=None):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.state = state
        self.on_end = on_end or _default_on_end(self.user_id)
        self.flee_cb = flee_cb; self.flee_pct = flee_pct
        a = state["ally"]
        if a.get("charging"):
            self.add_item(CmdButton("💥 解放する", discord.ButtonStyle.danger, {"kind": "attack"}))
        else:
            self.add_item(CmdButton("🗡️ 攻撃", discord.ButtonStyle.danger, {"kind": "attack"}))
            self.add_item(CmdButton("🛡️ 防御", discord.ButtonStyle.primary, {"kind": "defend"}))
            us = C.usable_skills(a)
            if us:
                self.add_item(SkillCommandSelect(us))
        if flee_cb is not None and not a.get("charging"):
            self.add_item(FleeButton(flee_pct))
        try:
            vp = db.get_voyage(self.user_id)
            if any(vp.get("land_items", {}).get(iid, 0) > 0 for iid in ("bandage", "smoke_bomb")) and not a.get("charging"):
                self.add_item(CombatItemSelect(self.user_id, self.gid))
        except Exception:
            pass

class CmdButton(discord.ui.Button):
    def __init__(self, label, style, action):
        super().__init__(label=label, style=style, row=0)
        self.action = action
    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await _advance(it, view, self.action)

class SkillCommandSelect(discord.ui.Select):
    def __init__(self, skill_ids):
        opts = []
        for sid in skill_ids[:25]:
            s = VS.SKILLS[sid]
            note = "溜め技" if s.get("charge", 0) > 0 else (f"CD{s['cooldown']}" if s.get("cooldown", 0) else "")
            opts.append(discord.SelectOption(label=s["name"], emoji=s["emoji"], value=sid,
                                             description=f"{note}　{s['desc'][:40]}".strip()))
        super().__init__(placeholder="✨ 特技を選ぶ", options=opts, row=1)
    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await _advance(it, view, {"kind": "skill", "sid": self.values[0]})

class FleeButton(discord.ui.Button):
    def __init__(self, flee_pct=None):
        label = "🏳️ 撤退" if flee_pct is None else f"🏳️ 撤退（成功{int(round(flee_pct*100))}%）"
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=2)
    async def callback(self, it):
        view: CombatView = self.view
        if str(it.user.id) != view.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await view.flee_cb(it, view.state)

class CombatEndView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = str(user_id)
    @discord.ui.button(label="閉じる", style=discord.ButtonStyle.secondary)
    async def close(self, it, b):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの戦闘ではありません", ephemeral=True); return
        await it.response.edit_message(content="模擬戦を終えた。", embed=None, view=None)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌊 航海復帰（戦闘/撤退の後、航海画面に戻す）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ContinueVoyageView(discord.ui.View):
    def __init__(self, user_id, gid, msg):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid); self.msg = msg
    @discord.ui.button(label="▶️ 次へ進む", style=discord.ButtonStyle.primary)
    async def back(self, it, b):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.user_id)
        if not vp.get("voyage"):
            await it.response.edit_message(embed=build_port_embed(vp), view=PortView(self.user_id, self.gid)); return
        await it.response.edit_message(embed=build_voyage_embed(vp, self.msg), view=VoyageView(self.user_id, self.gid))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 海賊/ボス遭遇＝海戦→白兵の実コマンド戦フロー
#   敵船HP0 → 乗り込み白兵(攻) ：勝=撃破・報酬／負=撤退(船倉無事)
#   自船HP0 → 防衛白兵(守)      ：勝=撃退(船倉無事/船大破)／負=💀全損(船倉ロスト)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⛵ 船・怪異の遭遇＝影 → 正体 → 対応 の3段演出
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def enemy_category(spec):
    """遭遇の種別を判定。海賊/商船/軍船/アンデッド/海獣/難破者/ボス。"""
    key = spec.get("key", "")
    if spec.get("boss") or spec.get("is_boss"): return "boss"
    if key in ("merchant_raid", "merchant_big"): return "merchant"
    if key == "navy": return "military"
    if spec.get("undead"): return "undead"
    if key in ("piranha", "shark", "venom_serpent", "serpent"): return "beast"
    if key == "castaway_foe": return "castaway"
    return "pirate"

def grant_random_equip(uid, vp, star):
    """その☆の武器/防具から1個をランダムでインベントリに付与。図鑑も記録。戻り値=表示文字列。"""
    pool = []  # (part, item_key, name)
    for wid, w in V.WEAPONS.items():
        if w["rank"] == star:
            pool.append(("weapon", wid, f"🗡️ {w['name']}"))
    for part in V.ARMOR_PART_ORDER:
        for iid, d in V.ARMOR_PARTS[part]["items"].items():
            if d["rank"] == star:
                pool.append((part, iid, f"🛡️ {d['name']}"))
    if not pool:
        return None
    part, ikey, label = random.choice(pool)
    vp.setdefault("inventory", {}).setdefault(part, [])
    vp["inventory"][part].append({"item": ikey, "skills": []})  # レアドロップは満杯でも受け取る
    db.add_zukan(uid, "equip_seen", ikey)
    return f"{label}（★{star}）"

def _add_craft_material(uid, vp, mat_id, n=1):
    if mat_id not in getattr(V, "MATERIALS", {}):
        return None
    vp.setdefault("materials", {})
    vp["materials"][mat_id] = vp["materials"].get(mat_id, 0) + int(n)
    if uid is not None:
        db.add_zukan(uid, "item_seen", mat_id)
    m = V.MATERIALS[mat_id]
    return f"{m['emoji']} **{m['name']}**（素材）"

def drop_loot(uid, vp, spec):
    """敵撃破時のドロップ（素材＋食料＋装備）。インベントリに加算し図鑑も記録。戻り値=表示行リスト。"""
    out = []
    cat = enemy_category(spec); stars = int(spec.get("stars", 1))
    # 💎 素材（カテゴリ×☆。ボスは海賊扱いで一旦☆2素材も）
    drop_cat = "pirate" if cat == "boss" else cat
    keys = V.materials_for(drop_cat, max(stars, 2) if cat == "boss" else stars)
    if keys and random.random() < V.MATERIAL_DROP_RATE:
        mat = random.choice(keys); m = V.MATERIALS[mat]
        vp.setdefault("materials", {}); vp["materials"][mat] = vp["materials"].get(mat, 0) + 1
        db.add_zukan(uid, "item_seen", mat)
        out.append(f"{m['emoji']} **{m['name']}**（素材）")
    # ⚒️ 鍛冶素材（海洋エリア素材。☆4ボス素材とは別枠）
    if hasattr(V, "roll_craft_material"):
        area = int(spec.get("area", 1) or 1)
        cmid = V.roll_craft_material("voyage", area, bonus=(1.4 if stars >= 3 else 1.0))
        got_cm = _add_craft_material(uid, vp, cmid, 1) if cmid else None
        if got_cm:
            out.append(got_cm)
    # 🍖 食料
    if random.random() < V.FOOD_DROP_RATE:
        food = random.choice(list(V.FOODS.keys())); f = V.FOODS[food]
        vp.setdefault("foods", {}); vp["foods"][food] = vp["foods"].get(food, 0) + 1
        db.add_zukan(uid, "item_seen", food)
        out.append(f"{f['emoji']} **{f['name']}**（食料）")
    # 🗡️ 装備（人型のみ・敵☆に対応・武器か防具ランダム1個）
    if cat in V.HUMANOID_CATS:
        for eq_star, rate in V.EQUIP_DROP_RATES.get(stars, []):
            if random.random() < rate:
                got = grant_random_equip(uid, vp, eq_star)
                if got:
                    out.append(f"✨ {got} を入手！")
                break  # 1回の撃破で装備は1個まで
    return out

def _discover_drop(uid, vp, kind):
    """発見系のドロップ：島→食料／渦・海淵→燃料樽＋海洋クラフト素材。"""
    v = vp["voyage"]
    lines = []
    area = int(v.get("area", 1) or 1)
    # ⚒️ 海洋素材：発見イベントでも手に入る。
    if hasattr(V, "roll_craft_material"):
        bonus = 1.35 if kind in ("island", "maelstrom", "abyss") else 1.0
        cmid = V.roll_craft_material("voyage", area, bonus=bonus)
        got_cm = _add_craft_material(uid, vp, cmid, 1) if cmid else None
        if got_cm:
            lines.append(f"\n🌊 {got_cm} を見つけた。")
        if random.random() < 0.05:
            extras = []
            for _ in range(random.randint(1, 3)):
                emid = V.roll_craft_material("voyage", area, bonus=1.0)
                g = _add_craft_material(uid, vp, emid, 1) if emid else None
                if g: extras.append(g)
            if extras:
                lines.append("\n✨ 漂着物が多い！ " + " / ".join(extras))
    if kind == "island" and random.random() < V.FOOD_DROP_RATE:
        food = random.choice(list(V.FOODS.keys())); f = V.FOODS[food]
        vp.setdefault("foods", {}); vp["foods"][food] = vp["foods"].get(food, 0) + 1
        db.add_zukan(uid, "item_seen", food)
        lines.append(f"\n🍖 {f['emoji']} **{f['name']}** も見つけた！（食料）")
    if kind in ("maelstrom", "abyss") and random.random() < V.BARREL_DROP_RATE:
        b = V.FUEL_BARREL
        before = v.get("fuel", 0)
        v["fuel"] = min(ship_max_fuel(vp), before + b["fuel"])
        gained = v["fuel"] - before
        db.add_zukan(uid, "item_seen", "fuel_barrel")
        lines.append(f"\n🛢️ **{b['name']}** を回収！ その場で燃料 **+{gained:,}**")
    return "".join(lines)

def shadow_intro(spec):
    """段階1：正体を伏せた前口上。☆が高いほど物々しく、海の意思が滲む。"""
    cat = enemy_category(spec); st = int(spec.get("stars", 1))
    if cat == "boss":
        if st >= 5:
            return ("👁️ 海が、軋んでいる",
                    "波が、ぴたりと止んだ。風も、鳥の声も、何もかもが消える。\n"
                    "遥か沖――海面の下で、**世界の底そのもの**が、ゆっくりと身じろぎした。\n"
                    "近づくほどに、見られているのがわかる。海にではない。\n"
                    "もっと遠く、**手の届かない場所にいる“何か”**に。\n"
                    "これは“遭遇”などという言葉で済むものではない。")
        return ("👁️ 海が、静まりかえった",
                "理由もなく、波が凪いだ。\n"
                "遥か沖――海面の下を、**途方もなく巨大な何か**が、ゆっくりと回頭している。\n"
                "近づくほどに、空気が鉛のように重くなっていく。\n"
                "海が、お前をそこへ呼んでいる。")
    if cat == "undead":
        tones = {
            1: "水面に、ぼんやりと人のかたちをした影が、ひとつ漂っている……",
            2: "気づけば、冷たい霧が船を包んでいた。霧の奥に、いくつもの影が立ち尽くしている。",
            3: ("ぞわり、と首筋を冷気が撫でた。**何かが、ずっと付いて来ている**。\n"
                "海が、底から死者を吐き出しているかのようだ。"),
            4: "潮の匂いに、腐臭が混じる。海面の下、いくつもの白い顔が、じっとこちらを見上げている――",
            5: ("海面が、ありえない方向へ波打つ。\n"
                "深みから、**かつて人だったもの**が、ゆっくりと浮かび上がってくる。\n"
                "海は、沈めたはずの者すら、呼び戻すのだ――"),
        }
        return ("🌫️ 冷たい気配", tones.get(st, tones[2]))
    if cat == "beast":
        tones = {
            1: "水面を、すいすいと走る小さな影がいくつも見える。",
            2: "波の下で、何かがこちらの様子をうかがっているようだ。",
            3: ("船の真下を、**長く太い影**が、ぬるりと横切った。\n"
                "まるで海が、こちらへ獲物を差し向けたかのように。"),
            4: "海面が大きくうねる。海中の巨影が、船の周りをゆっくりと一周した。値踏みされている。",
            5: ("海そのものが、ぐぅっと盛り上がる。\n"
                "**桁外れの巨体**が、お前を餌として見定めている。\n"
                "――これもまた、海の“試し”のひとつなのか。"),
        }
        return ("🌊 水面の異変", tones.get(st, tones[2]))
    if cat == "castaway":
        return ("🪦 漂流物",
                "波間に、ぼろぼろの小舟が漂っている。\n"
                "人影が、ぐったりと舟べりに凭れている……生きているのか？\n"
                "助けるか――だが海の上では、情けが仇になることもある。")
    # 船系（pirate / merchant / military）＝旗（正体）は伏せる
    tones = {
        1: "遠くに、小さな**船影**が見えてきた。ありふれた船のようだが……",
        2: "**一隻の船**が、まっすぐこちらへ近づいてくる。まだ、旗は見えない。",
        3: ("近づいてくる船影――**掲げた旗が、まだ読めない**。\n"
            "海面が、心なしかざわついている。気を抜くな。"),
        4: ("**重武装の船影**だ。ただ者じゃない。\n"
            "不思議と、海はその船を避けるように静まっている。舵を握る手に、力がこもる。"),
        5: ("水平線を覆うほどの威容。\n"
            "海そのものが、あれを“客”として迎えるように、すうっと凪いでいく。\n"
            "……あれは、**伝説に語られる船**ではないのか。"),
    }
    return ("⛵ 怪しい影の船", tones.get(st, tones[2]))

def build_approach_embed(vp, spec):
    title, body = shadow_intro(spec)
    body += "\n\n*――押したら、何があるんだ……？*"
    return build_result_embed(vp, body, title=title)

def _danger_sea_story(spec, cat):
    """★4以上の海敵用：敵ごとの専用演出。未定義はカテゴリ文へフォールバック。"""
    name = spec.get("name", "敵")
    stories = {
        "血錨のレヴィアタン": ("海面が、不自然なほど平らになった。\n"
            "次の瞬間、船底の下を**島ほどの影**が横切る。錨のような赤い鱗が、深みでぎらりと光った。\n"
            "帆布が震えている。風ではない。船そのものが、恐怖を覚えている。"),
        "大洋艦隊の軍人": ("霧の向こうから、規則正しい櫂の音が近づいてくる。\n"
            "軍艦の砲門が、こちらへ静かに向いた。号砲は威嚇ではない。命令だ。\n"
            "従うか、欺くか、撃つか。ここでの判断は、海の評判に残る。"),
        "大型商船の護衛団": ("水平線に、豪奢な帆が並んだ。だが宝船ではない。\n"
            "周囲を固める護衛船の甲板には、弩と大盾が隙間なく並んでいる。\n"
            "欲を出せば、船ごと蜂の巣になる。それでも積荷の匂いは甘い。"),
        "深淵のクラーケン": ("海面に、丸い波紋がいくつも開いた。\n"
            "やがて黒い腕が、音もなく海から持ち上がる。一本ではない。船を数えるように、何本も。\n"
            "この海域では、逃げ道すら触手の影に沈む。"),
        "古き海龍ヨルムン": ("空と海の境界が、ぐにゃりと歪んだ。\n"
            "海の果てから、龍の背が連なって現れる。長すぎて、どこまでが胴なのか見えない。\n"
            "伝説は近づいてきたのではない。こちらが、伝説の腹の中へ迷い込んだのだ。"),
        "呑まれた提督": ("沈んだはずの軍楽が、海中から聞こえる。\n"
            "朽ちた軍帽をかぶった影が、舳先の前に立っていた。背後には、沈没船の乗組員たち。\n"
            "彼はまだ、終わった戦争の号令を待っている。"),
        "巨大な影": ("船の下で、夜より黒い何かが反転した。\n"
            "姿は見えない。だが水面に浮かぶ泡だけで、その大きさがわかってしまう。\n"
            "追えば深淵。退けば生還。そういう類の影だ。"),
    }
    if name in stories:
        return stories[name]
    if int(spec.get("stars", 1)) >= 4:
        return ("波音が低く沈み、甲板の空気が一気に重くなる。\n"
                f"{spec.get('emoji','⚠️')} **{name}** は、普段の敵とは明らかに格が違う。\n"
                "近づけば戦いになる。だが、海はまだ引き返す余地を残している。")
    return None

def build_reveal_embed(vp, spec, cat):
    st = "★" * int(spec.get("stars", 1))
    danger = _danger_sea_story(spec, cat)
    if danger:
        body = (f"{spec.get('emoji','⚠️')} **{spec.get('name','敵')}** {st}\n\n{danger}\n\n"
                "**この先は非常に危険そうだ。どう動く？**")
        return build_result_embed(vp, body, title="⚠️ 危険な遭遇")
    if cat == "boss":
        body = (f"{spec['emoji']} **……これは、何だ。** {st}\n"
                "見たこともない巨大な気配が、すぐそこまで来ている。\n"
                "近づけば、否応なく相対することになるだろう。\n\n**挑むか――退くか。**")
        return build_result_embed(vp, body, title="👁️ 未知の巨影")
    name = spec["name"]
    intro = {
        "pirate":   f"🏴‍☠️ **{name}** だ！ {st}\n獲物を見つけた目で、まっすぐ突っ込んでくる。",
        "undead":   f"{spec['emoji']} **{name}**。 {st}\nこの世のものではない。逃げ道を塞ぐように、こちらを囲み始める。",
        "beast":    f"{spec['emoji']} **{name}**！ {st}\n本能のまま、船を獲物と見定めている。",
        "castaway": f"🪦 **{name}**。 {st}\n助けを求める声――だが、その目は妙にぎらついている。",
        "merchant": f"⚓ **{name}** のようだ。 {st}\n警戒しつつも、向こうも取引の相手を探している様子だ。",
        "military": f"🚢 **{name}** だ。 {st}\n規律ある動き。停船を命じる号砲が鳴った――検品を受けろ、ということらしい。",
    }[cat]
    return build_result_embed(vp, intro, title="⚓ 正体判明")

def build_ambush_embed(vp, spec):
    """イベント由来の戦闘＝影演出を挟まず『いきなり！』の急襲。"""
    name = spec.get("name", "敵"); st = "★" * int(spec.get("stars", 1))
    body = (f"⚔️ **{name}** が、不意を突いて仕掛けてきた！ {st}\n"
            "身構える間もない――応戦するしかない！")
    return build_result_embed(vp, body, title="⚠️ 急襲ッ！")

class ShipApproachView(discord.ui.View):
    """段階1：影。『様子をうかがう』で正体へ。"""
    def __init__(self, uid, gid, spec, scale, vm, is_boss):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.spec = spec
        self.scale = scale; self.vm = vm; self.is_boss = is_boss
    @discord.ui.button(label="▶️ 様子をうかがう…", style=discord.ButtonStyle.primary)
    async def reveal(self, it, b):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        cat = enemy_category(self.spec)
        ek = self.spec.get("key")
        if ek and cat != "boss":   # ボスは挑むまで図鑑に伏せる
            db.add_zukan(self.uid, "enemy_seen", ek)
        # ⚡ テンポ改善：正体判明前の「息を殺す……」中継演出は挟まない。
        await it.response.edit_message(
            embed=build_reveal_embed(vp, self.spec, cat),
            view=EncounterChoiceView(self.uid, self.gid, self.spec, self.scale, self.vm, self.is_boss, cat))


# ━━━ 💰 商船との取引（食料まとめ買い＋燃料1000刻み）━━━
TRADE_UNIT = lambda: V.FUEL_PRICE_PER * 1.6   # 商船は港より割高（航海中の緊急補給価格）

def build_trade_embed(vp, note=None):
    v = vp.get("voyage") or {}
    maxf = ship_max_fuel(vp); cur = v.get("fuel", 0)
    desc = ("商人が積荷を広げた。\n"
            "**船倉のコイン**で、燃料・食料・探索アイテムを買える。\n"
            "（港より少し割高だ）")
    if note:
        desc += f"\n\n{note}"
    e = discord.Embed(title="💰 商船との取引", description=desc, color=0xf1c40f)
    e.add_field(name="📦 船倉", value=f"**{v.get('hold',0):,}**", inline=True)
    e.add_field(name="⛽ 燃料", value=f"{cur:,}/{maxf:,}", inline=True)
    e.add_field(name="⛽ 商船給油", value=" / ".join(f"+{x:,}" for x in TRADE_FUEL_STEPS), inline=False)
    foods = v and vp.get("foods", {}) or {}
    if any(foods.get(fid, 0) for fid in V.FOODS):
        fl = "・".join(f"{V.FOODS[fid]['emoji']}{n}" for fid, n in foods.items() if n)
        e.add_field(name="🍖 所持食料", value=fl, inline=False)
    land_items = vp.get("land_items", {}) or {}
    if any(land_items.get(iid, 0) for iid in getattr(L, "LAND_ITEMS", {})):
        il = "・".join(f"{L.LAND_ITEMS[iid]['emoji']}{n}" for iid, n in land_items.items() if n and iid in L.LAND_ITEMS)
        e.add_field(name="🧭 所持探索アイテム", value=il or "なし", inline=False)
    return e

class TradeView(discord.ui.View):
    def __init__(self, uid, gid):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid)
        self.add_item(TradeFuelSelect(self.uid))
        self.add_item(TradeFoodSelect(self.uid))
        self.add_item(TradeLandItemSelect(self.uid, self.gid))
        done = discord.ui.Button(label="✅ 取引を終える", style=discord.ButtonStyle.secondary, row=3)
        async def _done(it):
            if str(it.user.id) != self.uid:
                await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
            await it.response.edit_message(
                embed=build_result_embed(db.get_voyage(self.uid), "💰 取引を終え、商人と別れた。", title="💰 取引"),
                view=ContinueVoyageView(self.uid, self.gid, ""))
        done.callback = _done
        self.add_item(done)

class TradeFuelSelect(discord.ui.Select):
    def __init__(self, uid):
        self.uid = str(uid)
        unit = TRADE_UNIT()
        opts = [discord.SelectOption(label=f"⛽ 燃料 +{step:,}", value=str(step),
                                     description=f"{int(step*unit):,}コイン")
                for step in TRADE_FUEL_STEPS]
        super().__init__(placeholder="⛽ 給油する（数字を選ぶ・商船価格）", options=opts, row=0)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid); v = vp["voyage"]
        maxf = ship_max_fuel(vp); cur = v.get("fuel", 0); need = maxf - cur
        unit = TRADE_UNIT()
        if need <= 0:
            await it.response.edit_message(
                embed=build_trade_embed(vp, "🛢️ 燃料はもう満タンだ。"),
                view=TradeView(self.uid, str(self.view.gid)))
            return
        step = int(self.values[0])
        add = min(step, need)
        affordable = int(v.get("hold", 0) / unit)
        add = min(add, affordable)
        if add <= 0:
            await it.response.edit_message(
                embed=build_trade_embed(vp, "💰 船倉が足りず、燃料を買えなかった。"),
                view=TradeView(self.uid, str(self.view.gid))); return
        cost = int(add * unit)
        v["fuel"] = cur + add; v["hold"] -= cost
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_trade_embed(vp, f"⛽ 燃料を **{add:,}** 補給した（-{cost:,}）。"),
            view=TradeView(self.uid, str(self.view.gid)))


class TradeLandItemSelect(discord.ui.Select):
    """商船で探索アイテムを買う。船倉コイン払い・港/街より少し割高。"""
    def __init__(self, uid, gid):
        self.uid = str(uid); self.gid = str(gid)
        vp = db.get_voyage(uid)
        ids = [iid for iid, it in getattr(L, "LAND_ITEMS", {}).items() if it.get("shop") == "always"] + _daily_random_shop_items(gid)
        opts = []
        for iid in ids:
            it = L.LAND_ITEMS[iid]
            base_price = int(it.get("price", 0))
            if base_price <= 0:
                continue
            price = int(base_price * 1.25)
            have = vp.get("land_items", {}).get(iid, 0)
            opts.append(discord.SelectOption(
                label=f"{it['name']} / {price:,}コイン", emoji=it["emoji"], value=iid,
                description=f"所持{have}・{it.get('desc','')[:65]}"))
        if not opts:
            opts = [discord.SelectOption(label="探索アイテムの在庫なし", value="__none__")]
        super().__init__(placeholder="🧭 探索アイテムを買う（商船価格）", options=opts[:25], row=2)

    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        iid = self.values[0]
        if iid == "__none__" or iid not in getattr(L, "LAND_ITEMS", {}):
            await it.response.send_message("商人は肩をすくめた。今は在庫がないらしい。", ephemeral=True); return
        meta = L.LAND_ITEMS[iid]
        base_price = int(meta.get("price", 0))
        if base_price <= 0:
            await it.response.send_message("これは売り物ではないらしい。", ephemeral=True); return
        price = int(base_price * 1.25)
        vp = db.get_voyage(self.uid); v = vp["voyage"]
        hold = int(v.get("hold", 0))
        if hold < price:
            await it.response.edit_message(
                embed=build_trade_embed(vp, f"💰 船倉が足りない（必要 {price:,} / 船倉 {hold:,}）。"),
                view=TradeView(self.uid, self.gid)); return
        v["hold"] = hold - price
        vp.setdefault("land_items", {})[iid] = vp.setdefault("land_items", {}).get(iid, 0) + 1
        db.add_zukan(self.uid, "item_seen", iid)
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_trade_embed(vp, f"{meta['emoji']} **{meta['name']} ×1** を買った（-{price:,}）。"),
            view=TradeView(self.uid, self.gid))

class TradeFoodSelect(discord.ui.Select):
    def __init__(self, uid):
        self.uid = str(uid)
        opts = []
        for fid, f in V.FOODS.items():
            for q in FOOD_QTY_STEPS:
                opts.append(discord.SelectOption(
                    label=f"{f['name']} ×{q}", emoji=f["emoji"], value=f"{fid}:{q}",
                    description=f"{f['price']*q:,}コイン・HP+{int(f['heal_pct']*100)}%"))
        super().__init__(placeholder="🍖 食料を買う（まとめ買いOK）", options=opts, row=1)
    async def callback(self, it):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid); v = vp["voyage"]
        fid, q = self.values[0].split(":"); q = int(q); f = V.FOODS[fid]
        cost = f["price"] * q; hold = v.get("hold", 0)
        if hold < cost:
            can = hold // f["price"]
            if can <= 0:
                await it.response.edit_message(
                    embed=build_trade_embed(vp, f"💰 船倉が足りない（{f['price']:,} 必要）。"),
                    view=TradeView(self.uid, str(self.view.gid))); return
            q = can; cost = f["price"] * q
        v["hold"] -= cost
        vp.setdefault("foods", {}); vp["foods"][fid] = vp["foods"].get(fid, 0) + q
        db.add_zukan(self.uid, "item_seen", fid)
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_trade_embed(vp, f"{f['emoji']} **{f['name']} ×{q}** を買った（-{cost:,}）。"),
            view=TradeView(self.uid, str(self.view.gid)))

def _voyage_minor_reward(uid, vp, vm, label="痕跡"): 
    """危険海敵を戦わず処理した時の小さな揺らぎ。戦闘報酬とは別の軽量報酬。"""
    v = vp.get("voyage") or {}
    roll = random.random()
    if roll < 0.34:
        val = max(100, int(_scaled({"base_min": 180, "base_max": 520}, vm) * 0.35))
        v["hold"] = v.get("hold", 0) + val
        return f"💰 {label}から、流された小箱を回収した。船倉に **+{val:,}**"
    if roll < 0.58:
        area = area_of(v) if v else 1
        cmid = V.roll_craft_material("voyage", area, bonus=0.8) if hasattr(V, "roll_craft_material") else None
        got = _add_craft_material(uid, vp, cmid, 1) if cmid else None
        return f"💎 {label}を調べ、{got} を拾った。" if got else f"{label}を調べたが、使えそうなものは無かった。"
    if roll < 0.78:
        xp = max(1, int(V.XP_PER_ISLAND * 0.35))
        leveled = add_xp(vp, xp)
        return f"✨ 危険を読む勘が磨かれた。 **XP +{xp}**" + (f"\n## 🎉 レベルアップ！ → Lv{vp['level']}" if leveled else "")
    return "何も得られなかった。だが、船を沈めずに済んだ。"

class EncounterChoiceView(discord.ui.View):
    """段階2：正体判明→種別ごとの対応。"""
    def __init__(self, uid, gid, spec, scale, vm, is_boss, cat):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.spec = spec
        self.scale = scale; self.vm = vm; self.is_boss = is_boss; self.cat = cat
        if int(spec.get("stars", 1)) >= 4:
            # ★4以上は必ず3〜4択。戦闘は「戦う/挑む/襲撃」選択時のみ。
            if cat == "merchant":
                self._add("👁️ 様子を見る", discord.ButtonStyle.secondary, self._observe)
                self._add("💰 取引を試す", discord.ButtonStyle.success, self._trade)
                self._add("⚔️ 襲撃する", discord.ButtonStyle.danger, self._fight)
                self._add("⛵ 遠回りする", discord.ButtonStyle.secondary, self._ignore)
            elif cat == "military":
                self._add("🪖 検品を受ける", discord.ButtonStyle.primary, self._inspect)
                self._add("👁️ 旗と進路を見る", discord.ButtonStyle.secondary, self._observe)
                self._add("⚔️ 強行突破", discord.ButtonStyle.danger, self._fight)
                self._add("⛵ 航路を逸らす", discord.ButtonStyle.secondary, self._ignore)
            elif cat == "boss":
                self._add("👁️ 様子を見る", discord.ButtonStyle.secondary, self._observe)
                self._add("⚔️ 挑む", discord.ButtonStyle.danger, self._fight)
                self._add("🌫️ やり過ごす", discord.ButtonStyle.secondary, self._hide)
                self._add("🏃 退く", discord.ButtonStyle.secondary, self._ignore)
            else:
                self._add("👁️ 様子を見る", discord.ButtonStyle.secondary, self._observe)
                self._add("⚔️ 戦う", discord.ButtonStyle.danger, self._fight)
                self._add("🌫️ やり過ごす", discord.ButtonStyle.secondary, self._hide)
                self._add("🏳️ 逃げる", discord.ButtonStyle.secondary, self._flee)
            return
        if cat in ("pirate", "undead", "beast", "castaway"):
            self._add("⚔️ 戦う", discord.ButtonStyle.danger, self._fight)
            self._add("🏳️ 逃げる", discord.ButtonStyle.secondary, self._flee)
        elif cat == "merchant":
            self._add("💰 取引する", discord.ButtonStyle.success, self._trade)
            self._add("⚔️ 襲撃する", discord.ButtonStyle.danger, self._fight)
            self._add("⛵ 見送る", discord.ButtonStyle.secondary, self._ignore)
        elif cat == "military":
            self._add("🪖 検品を受ける", discord.ButtonStyle.primary, self._inspect)
            self._add("⚔️ 襲撃する", discord.ButtonStyle.danger, self._fight)
            self._add("⛵ 見送る", discord.ButtonStyle.secondary, self._ignore)
        elif cat == "boss":
            self._add("⚔️ 挑む", discord.ButtonStyle.danger, self._fight)
            self._add("🏃 退く", discord.ButtonStyle.secondary, self._ignore)
    def _add(self, label, style, cb):
        b = discord.ui.Button(label=label, style=style); b.callback = cb; self.add_item(b)
    def _chk(self, it): return str(it.user.id) == self.uid
    def _enc(self):
        return NavalEncounter(self.uid, self.gid, self.spec, self.scale, self.vm, self.is_boss)

    async def _fight(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await self._enc().start(it)

    async def _flee(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        crew_eff = self.spec.get("crew_power", 50) * V.combat_scale(self.scale)
        chance = V.flee_success_chance(ship_power(vp), crew_eff)
        if random.random() < chance:
            await it.response.edit_message(
                embed=build_result_embed(vp, "🏳️ うまく舵を切り、相手を振り切った！", title="🏳️ 逃走成功"),
                view=ContinueVoyageView(self.uid, self.gid, ""))
        else:
            await it.response.edit_message(
                embed=build_result_embed(vp, "❌ 逃げ切れない…！ じわじわ距離を詰められ、ついに舷側がぶつかる――", title="⚔️ 捕捉された"),
                view=ProceedCombatView(self.uid, self.gid, self.spec, self.scale, self.vm, self.is_boss))

    async def _ignore(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        msg = "🏃 深追いはせず、そっと進路を変えた。" if self.cat == "boss" else "⛵ 関わらず、静かに航路を逸らした。"
        await it.response.edit_message(
            embed=build_result_embed(db.get_voyage(self.uid), msg, title="⛵ 見送り"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

    async def _observe(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        line = _voyage_minor_reward(self.uid, vp, self.vm, "危険な航跡")
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_result_embed(vp, f"👁️ 距離を保って、相手の出方を見た。\n{line}", title="👁️ 様子を見る"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

    async def _hide(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        if random.random() < 0.45:
            line = _voyage_minor_reward(self.uid, vp, self.vm, "去った後の波間")
        else:
            line = "帆を落とし、波音に紛れる。危険な気配は、こちらを見失ったように遠ざかった。"
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_result_embed(vp, line, title="🌫️ やり過ごす"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

    async def _trade(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        await it.response.edit_message(
            embed=build_trade_embed(vp),
            view=TradeView(self.uid, self.gid))

    async def _inspect(self, it):
        if not self._chk(it):
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid); v = vp["voyage"]; k = karma_of(vp)
        if k >= V.KARMA_GOOD_THRESHOLD:
            adjust_karma(vp, V.KARMA_DELTA["small"])
            body = "🪖 積荷を検められた。やましいものは何も無い。\n軍人は敬礼し、追い風の海域を教えて去っていった。"
        elif k <= V.KARMA_EVIL_THRESHOLD:
            fine = int(v.get("hold", 0) * 0.3)
            v["hold"] = max(0, v.get("hold", 0) - fine)
            body = f"🪖 積荷から、後ろ暗い品が見つかった。\n科料として船倉から **{fine:,}** を没収された…（船倉に手を出されるのは、お前の行いゆえだ）"
        else:
            body = "🪖 積荷を検められた。特に問題なし。軍船は無言で去っていった。"
        db.save_voyage(self.uid, vp)
        await it.response.edit_message(
            embed=build_result_embed(vp, body, title="🪖 検品"),
            view=ContinueVoyageView(self.uid, self.gid, ""))

class ProceedCombatView(discord.ui.View):
    """逃走失敗→『次へ』で戦闘へなだれ込む。"""
    def __init__(self, uid, gid, spec, scale, vm, is_boss):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.spec = spec
        self.scale = scale; self.vm = vm; self.is_boss = is_boss
    @discord.ui.button(label="⚔️ 応戦する", style=discord.ButtonStyle.danger)
    async def go(self, it, b):
        if str(it.user.id) != self.uid:
            await it.response.send_message("これはあなたの画面ではありません", ephemeral=True); return
        await NavalEncounter(self.uid, self.gid, self.spec, self.scale, self.vm, self.is_boss).start(it)

class NavalEncounter:
    def __init__(self, uid, gid, spec, scale, vm_eff, is_boss=False):
        self.uid = str(uid); self.gid = str(gid)
        self.spec = spec; self.scale = scale; self.vm_eff = vm_eff
        self.is_boss = is_boss
        # 白兵力（個人vs個人）。crew_power 基準。旧sea_powerしか無い敵はフォールバック。
        self.crew_eff = spec.get("crew_power", spec.get("sea_power", 50)) * V.combat_scale(scale)

    def _flee_pct(self, vp):
        return V.flee_success_chance(ship_power(vp), self.crew_eff)

    async def start(self, interaction):
        vp = db.get_voyage(self.uid)
        # 📖 敵対図鑑：遭遇した敵を「見た」記録
        ekey = self.spec.get("key")
        if ekey:
            db.add_zukan(self.uid, "enemy_seen", ekey)
        # いきなり白兵戦（海戦パートは廃止）。砲・装甲の耐久消費は据え置き（修理代シンク）
        for part in ("cannon", "armor"):
            inst = vp["ship_parts"].get(part)
            if inst:
                inst["dura"] = max(0, inst.get("dura", 0) - V.NAVAL_DURA_COST)
        db.save_voyage(self.uid, vp)
        ally = make_board_ally(vp)
        enemy = make_board_enemy(self.spec, self.scale, defense=False)
        state = C.new_battle("board", ally, enemy)
        view = CombatView(self.uid, self.gid, state, on_end=self.on_board_end,
                          flee_cb=(self.on_flee if V.NAVAL_ALLOW_FLEE else None),
                          flee_pct=(self._flee_pct(vp) if V.NAVAL_ALLOW_FLEE else None))
        emb = build_combat_embed(state)
        stars = "★" * int(self.spec.get("stars", 1))
        head = f"{self.spec['emoji']} **{self.spec['name']}** {stars}"
        head += "（この海域の主）！" if self.is_boss else " が現れた！"
        emb.description = f"{head}（白兵力 {int(self.crew_eff)}）\n斬り合いだ！"
        await interaction.response.edit_message(embed=emb, view=view)

    async def on_flee(self, interaction, state):
        vp = db.get_voyage(self.uid)
        force_success = bool(state.pop("_force_flee_success_once", False))
        chance = 1.0 if force_success else self._flee_pct(vp)
        if force_success or random.random() < chance:
            # 撤退成功：離脱（報酬なし）
            await interaction.response.edit_message(
                embed=_result_embed(state, "💨 煙玉" if force_success else "🏳️ 撤退成功",
                                    ("煙に紛れて、確実に離脱した。（報酬なし）" if force_success else f"{self.spec['name']} を振り切って離脱した。（報酬なし）")),
                view=ContinueVoyageView(self.uid, self.gid, "🏳️ 戦いを避けて航海を続ける。"))
            return
        # 撤退失敗：隙を突かれ敵の一撃。戦闘続行
        state["log"] = ["🏃💨 撤退失敗！隙を突かれた…"]
        if not state["over"]:
            C.resolve_action(state, "enemy", C.enemy_action(state))
        if not state["over"]:
            C.end_round(state)
        if state["over"]:
            await self.on_board_end(interaction, state)
        else:
            await interaction.response.edit_message(
                embed=build_combat_embed(state),
                view=CombatView(self.uid, self.gid, state, on_end=self.on_board_end,
                                flee_cb=self.on_flee, flee_pct=chance))

    async def on_board_end(self, interaction, state):
        board_win = (state["result"] == "win")
        vp = db.get_voyage(self.uid)
        # 📖 敵対図鑑：倒したら「討伐の証」記録
        if board_win:
            ekey = self.spec.get("key")
            if ekey:
                db.add_zukan(self.uid, "enemy_kill", ekey)
        tag, body, cont = apply_encounter_outcome(
            vp, self.spec, self.vm_eff, self.is_boss, board_win)
        if board_win:
            # 💎🍖 撃破ドロップ（素材＋食料）
            loot = drop_loot(self.uid, vp, self.spec)
            if loot:
                body += "\n\n🎁 戦利品： " + "・".join(loot)
            db.save_voyage(self.uid, vp)
            await interaction.response.edit_message(
                embed=_result_embed(state, tag, body),
                view=ContinueVoyageView(self.uid, self.gid, cont))
        else:
            # 💀 敗北＝HP1で強制帰港（航海はここで終了）
            v = vp["voyage"]
            hold = v.get("hold", 0)
            if hold > 0:
                db.update_balance(self.uid, self.gid, hold)
            vp["fuel_tank"] = v.get("fuel", 0)   # 余った燃料はタンクに戻す
            vp["voyage"] = None
            vp["cur_hp"] = 1                      # ボロボロで帰還
            vp["last_voyage_end"] = time.time()  # ⏳ 5分クールダウン開始
            db.save_voyage(self.uid, vp)
            body += (f"\n\n💀 …視界が、暗転する。"
                     f"\n🌀 ――気づけば、船は港に舫われていた。**沈んだはずなのに。**"
                     f"\n海は、まだお前を手放す気がないらしい。"
                     f"\n船倉の残り **{hold:,}** ナトコインは、なぜか銀行に収まっていた。"
                     f"\n🛌 **HPは1**。休息か食事で立て直そう。")
            await interaction.response.edit_message(
                embed=_result_embed(state, tag, body),
                view=PortView(self.uid, self.gid))

def _naval_combat_coin_factor(spec, area=None):
    """海戦コイン報酬の微調整。E1だけ稼ぎ過多を抑え、E2以降は現状維持。"""
    try:
        a = int(area if area is not None else spec.get("area", 1))
    except Exception:
        a = int(spec.get("area", 1) or 1)
    if a == 1:
        return 0.75
    return 1.0

def apply_encounter_outcome(vp, spec, vm_eff, is_boss, board_win):
    """白兵戦の結果から船倉・XP・カケラを精算（discord非依存・純ロジック）。
    勝ち＝敵を討って報酬／負け＝全損。戻り値: (tag, body, cont)。vp は in-place 更新。"""
    v = vp["voyage"]
    shard_key = "boss" if is_boss else "pirate_win"
    if board_win:
        base = random.uniform(V.PIRATE_BASE_REWARD["base_min"], V.PIRATE_BASE_REWARD["base_max"])
        area = int(spec.get("area") or area_of(v) or 1)
        rew = int(base * spec["reward_mult"] * vm_eff * NAVAL_COMBAT_REWARD_MULT * _naval_combat_coin_factor(spec, area))
        v["hold"] += rew
        xp = V.voyage_combat_xp(spec, win=True) if hasattr(V, "voyage_combat_xp") else V.XP_PER_PIRATE_WIN
        xp = max(1, int(xp))
        leveled = add_xp(vp, xp)
        tag = "🏆 撃破"
        body = f"**{spec['name']}** を討ち取った！ 船倉に **+{rew:,}**\n✨ 経験値 **+{xp}**" + (f"\n## 🎉 レベルアップ！ → Lv{vp['level']}" if leveled else "")
        sh = _try_shard(vp, shard_key)
        if sh: body += sh
        cont = "⛵ 戦果を抱えて航海を続ける。"
    else:
        lost = int(v["hold"] * V.WRECK_HOLD_LOSS)
        v["hold"] -= lost
        xp = V.voyage_combat_xp(spec, win=False) if hasattr(V, "voyage_combat_xp") else V.XP_PER_PIRATE_LOSE
        xp = max(1, int(xp))
        leveled = add_xp(vp, xp)
        tag = "💀 敗北"
        body = f"斬り合いに敗れた…船倉の **{lost:,}** を失った。\n✨ 敗北経験値 **+{xp}**" + (f"\n## 🎉 レベルアップ！ → Lv{vp['level']}" if leveled else "")
        specials = vp.get("special_items", [])
        if specials:
            body += f"\n🎒 特殊アイテム **{len(specials)}個** は辛うじて持ち帰った。"
        if shards_of(vp) > 0:
            body += f"\n🧭 {V.SHARD_NAME} **{shards_of(vp)}/{V.SHARD_NEEDED}** は特殊ポーチの中。失わずに済んだ。"
        body += "\n🛠️ **船も傷ついた**…引き返して立て直せ。"
        cont = "⚓ 命からがら引き返そう。"
    return tag, body, cont

def _result_embed(state, tag, body):
    emb = build_combat_embed(state)
    # 結果テキストは field ではなく description に入れる（航海中と同じ大きさで見せる）
    emb.description = f"**― {tag} ―**\n{body}"
    return emb

# ━━━ 📖 敵対図鑑 ━━━
def build_enemy_zukan_embed(uid):
    """全敵を☆別に並べ、遭遇=名前/未遭遇=???/討伐=⚔️ で表示。"""
    seen = set(db.get_zukan(uid, "enemy_seen"))
    killed = set(db.get_zukan(uid, "enemy_kill"))
    cat = [(k, t) for k, t in V.ENEMY_TYPES.items() if not t.get("special")]
    total_keys = [k for k, _ in cat]
    by_star = {}
    for k, t in cat:
        if k in seen:
            mark = " ⚔️**討伐済**" if k in killed else ""
            nm = f"{t['emoji']} {t['name']}{mark}"
        else:
            nm = "❔ ？？？"
        by_star.setdefault(t["stars"], []).append(nm)
    seen_n = len([k for k in total_keys if k in seen])
    kill_n = len([k for k in total_keys if k in killed])
    emb = discord.Embed(
        title="📖 敵対図鑑",
        description=f"遭遇 **{seen_n}/{len(total_keys)}** ・ 討伐 **{kill_n}/{len(total_keys)}**\n"
                    f"（★は強さ。★2以上は生半可な装備じゃ勝てない）",
        color=0x8b0000)
    for star in sorted(by_star):
        emb.add_field(name="★" * star, value="\n".join(by_star[star]), inline=False)
    return emb

class EnemyZukanView(discord.ui.View):
    def __init__(self, user_id, gid=None):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.gid = str(gid) if gid else None
    @discord.ui.button(label="◀ 図鑑トップへ", style=discord.ButtonStyle.secondary)
    async def back(self, it, b):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.zukan import ZukanCategoryView, build_category_embed
        await it.response.edit_message(embed=build_category_embed(self.user_id),
                                       view=ZukanCategoryView(self.user_id))

# ━━━ 🗡️🛡️📜🎒 装備・技・アイテム図鑑 ━━━
def build_weapon_zukan_embed(uid=None):
    seen = set(db.get_zukan(uid, "equip_seen")) if uid else set()
    if uid:  # 今持ってる武器も既知扱い
        vp = db.get_voyage(uid)
        for inst in vp.get("inventory", {}).get("weapon", []):
            seen.add(inst["item"])
    emb = discord.Embed(title="🗡️ 武器図鑑", color=0x95a5a6)
    lines = []
    for wid, w in sorted(V.WEAPONS.items(), key=lambda x: (x[1]["rank"], x[0])):
        if wid in seen:
            wt = V.WEAPON_TYPES.get(w["wtype"], {}).get("name", w["wtype"])
            lines.append(f"{V.rarity_stars(w['rank'])} **{w['name']}**（{wt}・攻{w['power']}×{w['hits']}・技枠{w['slots']}）")
        else:
            lines.append(f"{V.rarity_stars(w['rank'])} ？？？")
    emb.description = "\n".join(lines)
    return emb

def build_armor_zukan_embed(uid=None):
    seen = set(db.get_zukan(uid, "equip_seen")) if uid else set()
    if uid:  # 今持ってる防具も既知扱い
        vp = db.get_voyage(uid)
        for part in V.ARMOR_PART_ORDER:
            for inst in vp.get("inventory", {}).get(part, []):
                seen.add(inst["item"])
    emb = discord.Embed(title="🛡️ 防具図鑑", color=0x95a5a6)
    lines = []
    for part in V.ARMOR_PART_ORDER:
        info = V.ARMOR_PARTS[part]
        for iid, d in sorted(info["items"].items(), key=lambda x: (x[1]["rank"], x[0])):
            if iid in seen:
                lines.append(f"{V.rarity_stars(d['rank'])} **{d['name']}**（{info['name']}・防{d['power']}）")
            else:
                lines.append(f"{V.rarity_stars(d['rank'])} ？？？（{info['name']}）")
    emb.description = "\n".join(lines)
    return emb

def owned_skill_ids(vp):
    """プレイヤーが入手済みの技ID集合（手持ち＋装備に刻んだもの＋船パーツ）。"""
    out = set(k for k, c in vp.get("learned_skills", {}).items() if c > 0)
    for _part, lst in vp.get("inventory", {}).items():
        if isinstance(lst, list):
            for inst in lst:
                out.update(inst.get("skills", []) or [])
    for _part, inst in vp.get("ship_parts", {}).items():
        if inst:
            out.update(inst.get("skills", []) or [])
    return out

def build_skill_zukan_embed(uid=None):
    emb = discord.Embed(title="📜 技図鑑", color=0x9b59b6)
    owned = owned_skill_ids(db.get_voyage(uid)) if uid else set()
    lines = []
    for sid, s in sorted(VS.SKILLS.items(), key=lambda x: (x[1].get("rank", 2), x[0])):
        if s.get("slot") not in ("weapon", "armor"):
            continue  # 船戦の技は除外（白兵技のみ）
        stars = V.rarity_stars(s.get("rank", 2))
        if sid not in owned:
            # 未入手は名前・効果を伏せる（☆だけ見せて収集欲をくすぐる）
            lines.append(f"{stars} ❔ ？？？")
            continue
        if s.get("slot") == "weapon":
            tags = "・".join(V.WEAPON_TYPES[w]["name"] for w in s.get("wtypes", []))
        else:
            tags = "胴・脚"
        lines.append(f"{stars} {s['emoji']} **{s['name']}**　[{tags}] {s['desc']}")
    emb.description = "\n".join(lines)
    return emb

# 図鑑の素材表示は、細かいエリア別にバラすと縦に伸びすぎるため大分類にまとめる。
MATERIAL_CATEGORY_DEFS = {
    "road": {
        "label": "🛤️ 街道素材",
        "groups": ("plain", "forest", "mountain", "common"),
    },
    "ocean": {
        "label": "🌊 大洋素材",
        "groups": ("shallow", "ocean", "offshore"),
    },
    "special_material": {
        "label": "💠 特殊素材",
        "groups": ("rare", "spoils"),
    },
}

def _compact_lines(lines, per_line=3):
    """Embedの縦伸び防止。3個ずつ横並びにする。"""
    return "\n".join("　".join(lines[i:i+per_line]) for i in range(0, len(lines), per_line))

def build_item_zukan_embed(uid=None):
    seen = set(db.get_zukan(uid, "item_seen")) if uid else set()
    emb = discord.Embed(
        title="🎒 アイテム図鑑",
        description="見つけた品だけ記録される。種類ごとにまとめて表示する。",
        color=0xe67e22)

    # 🧪 消費アイテム：食料・燃料樽・抽選券など
    consumable_lines = []
    for fid, f in V.FOODS.items():
        consumable_lines.append(f"{f['emoji']} **{f['name']}**" if fid in seen else "❔ ？？？")
    consumable_lines.append("🛢️ **燃料樽**" if "fuel_barrel" in seen else "❔ ？？？")
    consumable_lines.append(f"{V.LOTTERY_ITEM['emoji']} **{V.LOTTERY_ITEM['name']}**" if getattr(V, "LOTTERY_ITEM_ID", "lottery_ticket") in seen else "❔ ？？？")
    emb.add_field(name="🧪 消費アイテム", value=_compact_lines(consumable_lines), inline=False)

    # 🧭 探索アイテム：街道・航海どちらでも使う小道具
    land_lines = []
    for iid, it in getattr(L, "LAND_ITEMS", {}).items():
        land_lines.append(f"{it['emoji']} **{it['name']}**" if iid in seen else "❔ ？？？")
    if land_lines:
        got_land = len([iid for iid in getattr(L, "LAND_ITEMS", {}) if iid in seen])
        emb.add_field(name=f"🧭 探索アイテム（{got_land}/{len(getattr(L, 'LAND_ITEMS', {}))}）", value=_compact_lines(land_lines), inline=False)

    # ✨ 特殊アイテム：かけら・ペット・特殊ポーチ系
    sp_lines = [
        V.SHARD_NAME if "shard" in seen else "❔ ？？？",
        SHADOW_DARK_SHARD if "shadow_dark_shard" in seen else "❔ ？？？",
    ]
    for pid, pet in getattr(V, "PETS", {}).items():
        sp_lines.append(f"{pet['emoji']} **{pet['name']}**" if pid in seen else "❔ ？？？")
    emb.add_field(name="✨ 特殊アイテム", value=_compact_lines(sp_lines), inline=False)

    # 💎 素材：街道／大洋／特殊素材に圧縮
    total_mats = len(V.MATERIALS)
    got_mats = len([mid for mid in V.MATERIALS if mid in seen])
    for cat in ("road", "ocean", "special_material"):
        meta = MATERIAL_CATEGORY_DEFS[cat]
        mids = [mid for mid, m in V.MATERIALS.items() if (m.get("group") or "spoils") in meta["groups"]]
        if not mids:
            continue
        lines = []
        for mid in mids:
            m = V.MATERIALS[mid]
            lines.append(f"{m['emoji']} **{m['name']}**" if mid in seen else "❔ ？？？")
        got = len([mid for mid in mids if mid in seen])
        emb.add_field(name=f"{meta['label']}（{got}/{len(mids)}）", value=_compact_lines(lines), inline=False)

    emb.set_footer(text=f"素材記録 {got_mats}/{total_mats}。海素材は浅瀬5・大洋5・沖合5の計15種。必要ならE3/E4用に追加可能。")
    return emb

class SimpleZukanView(discord.ui.View):
    """単一embedの図鑑（図鑑トップへ戻るだけ）。"""
    def __init__(self, user_id):
        super().__init__(timeout=900)
        self.user_id = str(user_id)
    @discord.ui.button(label="◀ 図鑑トップへ", style=discord.ButtonStyle.secondary)
    async def back(self, it, b):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.zukan import ZukanCategoryView, build_category_embed
        await it.response.edit_message(embed=build_category_embed(self.user_id),
                                       view=ZukanCategoryView(self.user_id))

# ━━━ 🎣 海洋図鑑（4エリア・タブ切替）━━━
VOYAGE_FISH_RARITY_ORDER = ["common", "uncommon", "rare", "super_rare", "legend"]
VOYAGE_FISH_RARITY_HEAD = {
    "common":"🐟 コモン", "uncommon":"🐠 アンコモン", "rare":"✨ レア",
    "super_rare":"💎 スーパーレア", "legend":"🌈 レジェンド",
}
VOYAGE_FISH_AREA_COLOR = {1: 0x3498db, 2: 0x2980b9, 3: 0x34495e, 4: 0x1a0d2e}

def _reached_e4(uid):
    """E4（虚海）に到達できる/したか。カケラが揃った or E4で魚を釣った実績で判定。"""
    if not uid:
        return False
    try:
        vp = db.get_voyage(uid)
        if vp.get("shards", 0) >= V.SHARD_NEEDED:
            return True
    except Exception:
        pass
    if db.get_zukan(uid, "voyage_fish_4") or db.get_zukan(uid, "voyage_fish_4_trash"):
        return True
    return False

def _area_label(uid, area):
    """図鑑のエリア表示。未到達のE4は名前を伏せる。"""
    if area == 4 and not _reached_e4(uid):
        return "？？？"
    return V.AREA_NAMES[area]

def build_voyage_fish_zukan_embed(uid, area=1):
    """海洋図鑑：1エリアぶんを表示。釣った魚=名前/未取得=❔、金冠所持は👑。"""
    lst = V.VOYAGE_FISH_BY_AREA[area]
    seen = set(db.get_zukan(uid, f"voyage_fish_{area}")) if uid else set()
    crowns = set(db.get_crowns(uid, f"voyage_fish_{area}")) if uid else set()
    trash_seen = set(db.get_zukan(uid, f"voyage_fish_{area}_trash")) if uid else set()
    fish_total = len([f for f in lst if f["rarity"] != "trash"])
    got = len([f for f in lst if f["rarity"] != "trash" and f["name"] in seen])
    reward = int(V.VOYAGE_FISH_COMPLETE_REWARD.get(area, 0) * VOYAGE_COIN_REWARD_MULT)
    if got >= fish_total and fish_total > 0:
        comp_txt = f"　🏆 **コンプリート！**（報酬 {reward:,}）"
    else:
        comp_txt = f"　🏆 コンプ報酬 {reward:,}"
    emb = discord.Embed(
        title=(f"🎣 海洋図鑑 — {_area_label(uid, area)}" if area == 4 and not _reached_e4(uid) else f"🎣 海洋図鑑 — E{area} {_area_label(uid, area)}"),
        description=f"釣った魚 **{got}/{fish_total}** 種　👑金冠 {len(crowns)}{comp_txt}",
        color=VOYAGE_FISH_AREA_COLOR.get(area, 0x1abc9c))
    for rar in VOYAGE_FISH_RARITY_ORDER:
        fishes = [f for f in lst if f["rarity"] == rar]
        if not fishes: continue
        lines = []
        for f in fishes:
            if f["name"] in seen:
                cr = "👑" if f["name"] in crowns else ""
                lines.append(f"{f['emoji']} {f['name']}{cr}（{f['value']:,}）")
            else:
                lines.append("❔ ？？？")
        n = len([f for f in fishes if f['name'] in seen])
        emb.add_field(name=f"{VOYAGE_FISH_RARITY_HEAD[rar]}（{n}/{len(fishes)}）",
                      value="\n".join(lines), inline=False)
    # ごみ（サルベージ）は折りたたみ的に1行
    trash = [f for f in lst if f["rarity"] == "trash"]
    tline = "　".join(f"{f['emoji']}{f['name']}" if f["name"] in trash_seen else "❔" for f in trash)
    tn = len([f for f in trash if f["name"] in trash_seen])
    emb.add_field(name=f"🗑️ サルベージ（{tn}/{len(trash)}）", value=tline, inline=False)
    return emb

class VoyageFishZukanView(discord.ui.View):
    """海洋図鑑：E1〜E4をボタンで切替。"""
    def __init__(self, user_id, area=1):
        super().__init__(timeout=900)
        self.user_id = str(user_id); self.area = area
        for a in (1, 2, 3, 4):
            b = discord.ui.Button(
                label=("？？？" if a == 4 and not _reached_e4(self.user_id) else f"E{a} {_area_label(self.user_id, a)}"),
                style=discord.ButtonStyle.primary if a == area else discord.ButtonStyle.secondary,
                row=0)
            b.callback = self._mk(a)
            self.add_item(b)
        back = discord.ui.Button(label="◀ 図鑑トップへ", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._back
        self.add_item(back)
    def _mk(self, a):
        async def cb(it):
            if str(it.user.id) != self.user_id:
                await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
            await it.response.edit_message(
                embed=build_voyage_fish_zukan_embed(self.user_id, a),
                view=VoyageFishZukanView(self.user_id, a))
        return cb
    async def _back(self, it):
        if str(it.user.id) != self.user_id:
            await it.response.send_message("あなたの図鑑ではありません", ephemeral=True); return
        from cogs.zukan import ZukanCategoryView, build_category_embed
        await it.response.edit_message(embed=build_category_embed(self.user_id),
                                       view=ZukanCategoryView(self.user_id))

# ━━━ 🌑 クラーケンの影（専用イベント戦闘）━━━
#   仕様：最初の数ターンは無視→突然の一撃／HP半分で🖤黒い欠片(毎回)／
#         HP閾値で「興味を失い撤退」＝削りきれない／逃走100%・全損なし。
SHADOW_MAX_HP        = 1800     # 巨大な影のHP（クラーケン基準。削りきれない＝下の撤退閾値で去る）
SHADOW_RETREAT_RATIO = 0.35     # これ以下まで削ると興味を失い撤退（倒せない）
SHADOW_SHARD_RATIO   = 0.50     # これ以下で🖤黒い欠片ドロップ
SHADOW_IGNORE_TURNS  = 2        # 最初の数ターンは攻撃してこない
SHADOW_DARK_SHARD    = "🖤 黒い禍々しい欠片"

def build_wait_embed(text, color=None):
    """演出ウェイト用の「……」表示embed（ボタン無しで数秒見せる）。"""
    return discord.Embed(
        description=text,
        color=color if color is not None else discord.Color.dark_teal())

# ━━━ 🎣 伝説の釣り人オーグ：港の助言役（実はラスボス級の悪……という伏線）━━━
OAG_GREETING = (
    "🎣 **伝説の釣り人 オーグ**\n\n"
    "「よう。……海はレベル10くらいないと、行くのは控えたほうがいいかもな。\n"
    "　もちろん利益も大きいから、絶対とは言わんが……。\n\n"
    "　何か聞きたいことはあるか？」"
)
OAG_TOPICS = {
    "sea": ("🌊 海の広さ",
        "「海はいくつもの海域に分かれている。\n"
        "　**E1 浅瀬** … 入り口の海。まずはここで慣れろ。\n"
        "　**E2 大洋** … 広く深い海。手強い奴も増えてくる。\n"
        "　**E3 暗い海** … 光の届かぬ深みだ。\n"
        "　…たまにな、暗い海で **光る何か** が落ちているらしい。あれは何だろうな……？\n"
        "　E3は特別危険な地域だ。**遭遇率も高い**らしいぞ。気をつけろよ！」"),
    "fuel": ("⛽ 燃料とHP",
        "「船は燃料で動く。海域を進むほど燃料を食うぞ。\n"
        "　港でタンクを満たしてから出るのが鉄則だ。\n"
        "　**常に満タンで出航を心がけるんだぞ**……。\n"
        "　HPも同じだ。傷ついたまま無理をするな。停泊で休めば回復する。」"),
    "karma": ("⚖️ カルマ値",
        "「カルマってのは、評判みたいなものらしいな。\n"
        "　基本的に、悪いことをしすぎると……\n"
        "　味方になってくれるはずの奴も、敵対することがあるらしい。\n\n"
        "　だが安心しろ。**俺はお前がどんな評判になっても、恩があるからな。**\n"
        "　**常にお前の味方だぞ！**」"),
    "stop": ("🏕️ 停泊",
        "「航海の途中、停泊すれば一息つける。\n"
        "　**食事**でHPを少し、**休息**で全回復だ。どっちも燃料を使うがな。\n"
        "　無理に進むより、停泊で立て直すのも腕のうちだぞ。」"),
    "fish": ("🎣 釣り",
        "「海で釣りをするには――**🎣 航海の釣り竿** がいる。ドックで仕立てられる、船に付ける専用の竿だ。\n"
        "　陸のリールやラインは効かん。あれは船の上じゃ使えんからな。\n"
        "　しかも、いつでも釣れるわけじゃない。**魚の群れ（魚影）が現れた時だけ**だ。\n"
        "　群れが来たら、去る前に手早くな。**掛けられる回数は決まってる**ぞ。\n"
        "　……それと。魚影だと思って糸を垂らしたら、**とんでもないモノ**が食らいついてくることがある。覚悟しておけ。」"),
}
OAG_WARN_FIRST = (
    "🎣 **オーグ**\n\n"
    "「待て。……海は危険だ。\n"
    "　一度沈めば、船倉の積み荷をごっそり失うこともある。\n"
    "　**慎重に行くんだぞ。**\n\n"
    "　……それでも、行くか？」"
)
OAG_WARN_LOW = (
    "🎣 **オーグ**\n\n"
    "「おい、**燃料かHPが満タンじゃない**ぞ。\n"
    "　常に満タンで出航を心がけろと言ったろう……。\n"
    "　港で整えてからでも遅くはない。\n\n"
    "　……それでも、行くか？」"
)

# 🎬 エリア移動時の演出テキスト（別枠で表示・暗いトーン・E4は観測者の薄い伏線）
AREA_TRANSITION = {
    2: ("🌊 波が高くなってきた。風に、潮とは違う匂いが混じる。\n"
        "見たことのない海鳥が、こちらを一度だけ振り返って消えた。\n"
        "……まだ、先がありそうだ。"),
    3: ("🌫️ 海の色が、深く沈んだ青に変わった。\n"
        "波の音の奥に、何かがこちらを **見ている** 気配がある。\n"
        "引き返すなら、今かもしれない。それでも――先へ?"),
    4: ("🌟 カケラが光を放ち、海が音もなく裂けていく。\n"
        "**虚海（うつろうみ）――最深部に到達した。** ここはずっと、何かが“待って”いた場所だ。\n"
        "手の届かない遠くから、視線だけが、静かに注がれている。"),
}

async def maybe_kraken_shadow(interaction, uid, gid, area):
    """大物の魚影から分岐。挑む/見送るの選択を出す。"""
    emb = discord.Embed(
        title="🌑 巨大な影",
        description=("大物かと思った――が、違う。\n"
                     "海の彼方を、**とほうもなく巨大な影**が、ゆっくりと奥へ去っていく。\n\n"
                     "⚠️ これはこの海域の格を**遥かに超えた**存在。戦えば、ただでは済まない。\n"
                     "それでも――挑むか？"),
        color=0x0d0d1a)
    await interaction.response.edit_message(embed=emb, view=KrakenShadowChoiceView(uid, gid, area))

class KrakenShadowChoiceView(discord.ui.View):
    def __init__(self, uid, gid, area):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area
    def _chk(self, it): return str(it.user.id) == self.uid
    @discord.ui.button(label="⚔️ 挑む（かなり危険）", style=discord.ButtonStyle.danger)
    async def fight(self, it, b):
        if not self._chk(it):
            await it.response.send_message("あなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid)
        db.add_zukan(self.uid, "enemy_seen", "kraken_shadow")   # 図鑑に「巨大な影」記録
        st = {"ehp": SHADOW_MAX_HP, "turn": 0, "php": max_hp(vp), "shard": False, "log": []}
        emb = _shadow_embed(st)
        emb.description = "🌑 巨大な影が、すぐ目の前に。こちらを気にも留めていない…"
        await it.response.edit_message(embed=emb, view=KrakenShadowFightView(self.uid, self.gid, self.area, st))
    @discord.ui.button(label="⚓ 見送る（賢明）", style=discord.ButtonStyle.secondary)
    async def leave(self, it, b):
        if not self._chk(it):
            await it.response.send_message("あなたの画面ではありません", ephemeral=True); return
        await it.response.edit_message(
            embed=discord.Embed(title="⚓ 見送った",
                description="影が完全に見えなくなるまで、息を潜めていた。\n…賢明な判断だ。",
                color=0x2c3e50),
            view=ContinueVoyageView(self.uid, self.gid, "⛵ 何事もなかったように航海を続ける。"))

def _shadow_embed(st):
    ratio = st["ehp"] / SHADOW_MAX_HP
    bar = "🟪" * round(ratio * 10) + "⬛" * (10 - round(ratio * 10))
    emb = discord.Embed(title="🌑 巨大な影との対峙", color=0x0d0d1a)
    emb.add_field(name="影の様子", value=f"{bar}", inline=False)
    emb.add_field(name="あなたのHP", value=f"❤️ {st['php']}", inline=True)
    if st["log"]:
        emb.add_field(name="― 経過 ―", value="\n".join(st["log"][-4:]), inline=False)
    return emb

class KrakenShadowFightView(discord.ui.View):
    def __init__(self, uid, gid, area, st):
        super().__init__(timeout=900)
        self.uid = str(uid); self.gid = str(gid); self.area = area; self.st = st
    def _chk(self, it): return str(it.user.id) == self.uid

    @discord.ui.button(label="⚔️ 斬りかかる", style=discord.ButtonStyle.danger)
    async def slash(self, it, b):
        if not self._chk(it):
            await it.response.send_message("あなたの画面ではありません", ephemeral=True); return
        vp = db.get_voyage(self.uid); st = self.st
        st["turn"] += 1
        # プレイヤーの一撃
        dmg = C.dmg_calc(attack_power(vp), 40, 1.0)
        st["ehp"] = max(0, st["ehp"] - dmg)
        st["log"].append(f"⚔️ あなたの斬撃！ 影に {dmg} ダメージ")
        ratio = st["ehp"] / SHADOW_MAX_HP

        # 🖤 HP半分で黒い欠片（毎回・遭遇ごと）
        if (not st["shard"]) and ratio <= SHADOW_SHARD_RATIO:
            st["shard"] = True
            vp.setdefault("special_items", []).append(SHADOW_DARK_SHARD)
            db.save_voyage(self.uid, vp)
            st["log"].append(f"💢 影の体表から、何かが剥がれ落ちた…**{SHADOW_DARK_SHARD}** を拾った！")

        # 撤退閾値＝削りきれない（興味を失い去る）
        if ratio <= SHADOW_RETREAT_RATIO:
            emb = _shadow_embed(st)
            emb.description = ("🌑 影は、ふと動きを止めた。\n"
                               "そして――こちらへの興味を失ったように、**悠然と深みへ去っていく**。\n"
                               "…結局、その身に届くことはなかった。")
            await it.response.edit_message(
                embed=emb,
                view=ContinueVoyageView(self.uid, self.gid, "⛵ 影の余韻を背に、航海を続ける。"))
            return

        # 敵の行動：最初の数ターンは無視→以降も半分は手を出さない（舐めた余裕）
        if st["turn"] <= SHADOW_IGNORE_TURNS:
            st["log"].append(random.choice([
                "🌑 影はこちらを一瞥もしない…", "🌑 影は微動だにしない。", "🌑 影は退屈そうに揺れている…"]))
        elif random.random() < 0.5:
            st["log"].append(random.choice([
                "🌑 影は気まぐれに身を揺らすだけだ…", "🌑 影はあくびをするように漂う。",
                "🌑 影はお前など眼中にない。"]))
        else:
            ehit = C.dmg_calc(int(SHADOW_MAX_HP * 0.045), defense_power(vp), 1.0)
            st["php"] = max(0, st["php"] - ehit)
            st["log"].append(f"💥 **突然、影が身をよじった！** あなたに {ehit} の衝撃！")
            if st["php"] <= 0:
                emb = _shadow_embed(st)
                emb.description = ("🌑 影の一撃に吹き飛ばされた。\n"
                                   "意識が遠のく中、影は静かに去っていった…\n（全損はなし・船倉は無事）")
                await it.response.edit_message(
                    embed=emb,
                    view=ContinueVoyageView(self.uid, self.gid, "⚓ 命があっただけ、良しとしよう。"))
                return

        emb = _shadow_embed(st)
        emb.description = "🌑 影は、まだそこにいる。"
        await it.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="🏃 逃げる（必ず成功）", style=discord.ButtonStyle.secondary)
    async def flee(self, it, b):
        if not self._chk(it):
            await it.response.send_message("あなたの画面ではありません", ephemeral=True); return
        # 逃走100%
        await it.response.edit_message(
            embed=discord.Embed(title="🏃💨 離脱",
                description="影に気づかれないよう、そっと舵を切った。\n…深追いは、しないでおこう。",
                color=0x2c3e50),
            view=ContinueVoyageView(self.uid, self.gid, "⛵ 航海を続ける。"))

async def start_board_test(interaction, user_id=None):
    """admin用：装備中ロードアウトで海賊と白兵模擬戦。"""
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    ally = make_board_ally(vp)
    pr = dict(random.choice(V.PIRATE_RANKS[:3]))  # 模擬戦は中堅まで
    enemy = make_board_enemy(pr, 1.0)
    state = C.new_battle("board", ally, enemy)
    holder = CombatView(uid, gid, state)
    emb = build_combat_embed(state)
    emb.description = f"{pr['emoji']} **{pr['name']}** が斬りかかってきた！（模擬戦）"
    if interaction.response.is_done():
        await interaction.followup.send(embed=emb, view=holder, ephemeral=True)
    else:
        await interaction.response.send_message(embed=emb, view=holder, ephemeral=True)

# 公開エントリ（fund.py の港ハブから呼ばれる）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def open_voyage(interaction, user_id=None):
    uid = str(user_id or interaction.user.id); gid = str(interaction.guild.id)
    vp = db.get_voyage(uid)
    # 航海中だった場合は航海画面へ復帰
    if vp.get("voyage"):
        embed = build_voyage_embed(vp, "⛵ 航海の続きだ。")
        view = VoyageView(uid, gid)
    else:
        embed = build_port_embed(vp); view = PortView(uid, gid)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)

class Voyage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    await bot.add_cog(Voyage(bot))
