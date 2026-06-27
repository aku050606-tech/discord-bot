"""⚔️ 戦闘エンジン（航海システム）── 海戦・白兵で共通のコマンドバトル。
HP制／通常攻撃・通常防御・特技(刻んだ技)／クールダウン・溜め条件／DoT／敵AI(格で賢さ変化)。
純ロジック（discord非依存）。UIは cogs/voyage.py の CombatView が薄く乗る。
"""
import random
import voyage_skills as VS


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 戦闘員・バトル生成
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_combatant(name, emoji, hp, atk, defense, skills, ai_tier=0):
    return {
        "name": name, "emoji": emoji,
        "hp": hp, "max_hp": hp,
        "atk": atk, "def": defense,
        "skills": list(skills),   # 刻まれた技ID
        "cd": {},                 # {sid: 残ターン}
        "charging": None,         # 溜め中の技ID
        "guard": 0.0,             # 次の被ダメ軽減率（自ターンまで）
        "counter": 0.0,           # 反撃ダメージ率（被弾時に返す）
        "dots": [],               # [{"dmg":int,"turns":int,"name":str}]
        "ai_tier": ai_tier,
    }


def new_battle(phase, ally, enemy):
    """phase: 'board'(白兵) / 'naval'(海戦)"""
    return {"phase": phase, "ally": ally, "enemy": enemy,
            "turn": 1, "log": [], "over": False, "result": None}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ダメージ計算（攻撃力 vs 防御力）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DMG_VARIANCE = 0.10   # ダメージ乱数の幅（±10%）。大きいほどバラつく。

def dmg_calc(atk, defn, mult, pierce=0.0, variance=True):
    eff_def = max(0.0, defn * (1.0 - pierce))
    raw = atk * mult
    dealt = raw * (100.0 / (100.0 + eff_def))   # 防御を%軽減として扱う
    if variance:
        dealt *= random.uniform(1.0 - DMG_VARIANCE, 1.0 + DMG_VARIANCE)
    return max(1, round(dealt))


def _deal(state, attacker, defender, amount):
    """ガード軽減・反撃を適用して defender にダメージ。"""
    amount = round(amount * (1.0 - defender.get("guard", 0.0)))
    amount = max(0, amount)
    defender["hp"] -= amount
    line = f"  → {defender['name']} に {amount} ダメージ"
    # 反撃
    if defender.get("counter", 0.0) > 0 and amount > 0:
        ref = max(1, round(amount * defender["counter"]))
        attacker["hp"] -= ref
        line += f"（{defender['name']} の反撃で {attacker['name']} に {ref}）"
    return amount, line


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 技が「今撃てるか」（クールダウン・溜め）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def skill_status(c, sid):
    """(usable:bool, reason:str)。reason は不可理由 or 'charge'(溜め開始) など。"""
    s = VS.SKILLS.get(sid)
    if not s:
        return False, "不明"
    if c["cd"].get(sid, 0) > 0:
        return False, f"CD{c['cd'][sid]}"
    if c.get("charging") and c["charging"] != sid:
        return False, "溜め中"
    return True, ""


def usable_skills(c):
    """UI用：このターン選べる技ID一覧（CD/溜め考慮）。"""
    out = []
    for sid in c["skills"]:
        ok, _ = skill_status(c, sid)
        if ok:
            out.append(sid)
    return out


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 行動の解決
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _begin_turn(c):
    c["guard"] = 0.0
    c["counter"] = 0.0


def resolve_action(state, side, action):
    """side: 'ally'/'enemy'。action: {'kind':'attack'/'defend'/'skill','sid':?}"""
    attacker = state[side]
    defender = state["enemy" if side == "ally" else "ally"]
    _begin_turn(attacker)
    kind = action["kind"]

    # 溜め解放（前ターンから溜めていた技が自動発動）
    if attacker.get("charging"):
        sid = attacker["charging"]
        attacker["charging"] = None
        return _fire_skill(state, attacker, defender, sid, released=True)

    if kind == "attack":
        d = dmg_calc(attacker["atk"], defender["def"], 1.0)
        amt, line = _deal(state, attacker, defender, d)
        state["log"].append(f"{attacker['emoji']} {attacker['name']} の攻撃！{line}")
    elif kind == "defend":
        attacker["guard"] = 0.5
        state["log"].append(f"🛡️ {attacker['name']} は身を守った（次の被弾-50%）")
    elif kind == "skill":
        return _use_skill(state, attacker, defender, action["sid"])
    _post(state)


def _use_skill(state, attacker, defender, sid):
    s = VS.SKILLS[sid]
    # 溜め技：初回選択は溜めに入る
    if s.get("charge", 0) > 0 and attacker.get("charging") != sid:
        attacker["charging"] = sid
        state["log"].append(f"💢 {attacker['name']} は {s['name']} を溜め始めた…！")
        _post(state)
        return
    return _fire_skill(state, attacker, defender, sid)


def _fire_skill(state, attacker, defender, sid, released=False):
    s = VS.SKILLS[sid]
    pre = "💥 溜め解放！" if released else ""
    t = s["type"]
    if t in ("attack", "pierce"):
        hits = s.get("hits", 1)
        pierce = s.get("pierce", 0.0)
        total = 0
        for _ in range(hits):
            if random.random() > s.get("acc", 1.0):
                state["log"].append(f"{attacker['emoji']} {s['name']} … 外した！")
                continue
            d = dmg_calc(attacker["atk"], defender["def"], s["power"], pierce)
            amt, line = _deal(state, attacker, defender, d)
            total += amt
        state["log"].append(f"{pre}{s['emoji']} {attacker['name']} の【{s['name']}】！ 計{total}ダメージ")
    elif t == "dot":
        d = dmg_calc(attacker["atk"], defender["def"], s["power"])
        amt, line = _deal(state, attacker, defender, d)
        dd = max(1, round(attacker["atk"] * s.get("dot_power", 0.3)))
        defender["dots"].append({"dmg": dd, "turns": s.get("dot_turns", 3), "name": s["name"]})
        state["log"].append(f"{s['emoji']} {attacker['name']} の【{s['name']}】！{line}（出血{s.get('dot_turns',3)}T）")
    elif t == "heal":
        heal = s.get("heal_flat", 0) + round(attacker["max_hp"] * s.get("heal_ratio", 0.0))
        attacker["hp"] = min(attacker["max_hp"], attacker["hp"] + heal)
        state["log"].append(f"{s['emoji']} {attacker['name']} は【{s['name']}】で {heal} 回復")
    elif t == "defend":
        attacker["guard"] = s.get("reduce", 0.5)
        if s.get("counter", 0) > 0:
            attacker["counter"] = s["counter"]
        state["log"].append(f"{s['emoji']} {attacker['name']} は【{s['name']}】で身構えた")
    # クールダウン設定
    if s.get("cooldown", 0) > 0:
        attacker["cd"][sid] = s["cooldown"] + 1  # 終了処理で1引かれるため+1
    _post(state)


def _post(state):
    """勝敗判定（DoT等の後始末は end_round で）。"""
    if state["ally"]["hp"] <= 0 or state["enemy"]["hp"] <= 0:
        state["over"] = True
        state["result"] = "win" if state["enemy"]["hp"] <= 0 else "lose"


def end_round(state):
    """1ラウンド（味方→敵）終了時：DoT・CD・溜めCDの処理。"""
    for who in ("ally", "enemy"):
        c = state[who]
        # DoT
        rem = []
        for dot in c["dots"]:
            c["hp"] -= dot["dmg"]
            dot["turns"] -= 1
            state["log"].append(f"🩸 {c['name']} は{dot['name']}の出血で {dot['dmg']}")
            if dot["turns"] > 0:
                rem.append(dot)
        c["dots"] = rem
        # CD
        for k in list(c["cd"].keys()):
            c["cd"][k] -= 1
            if c["cd"][k] <= 0:
                del c["cd"][k]
    state["turn"] += 1
    if state["ally"]["hp"] <= 0 or state["enemy"]["hp"] <= 0:
        state["over"] = True
        state["result"] = "win" if state["enemy"]["hp"] <= 0 else "lose"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 敵AI（格＝ai_tier で賢さ変化）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def enemy_action(state):
    e = state["enemy"]; ally = state["ally"]
    tier = e.get("ai_tier", 1)
    hp_ratio = e["hp"] / max(1, e["max_hp"])
    skills = usable_skills(e)

    # tier1-2：ほぼ脳筋。たまに防御
    if tier <= 2:
        if random.random() < 0.15:
            return {"kind": "defend"}
        if skills and random.random() < 0.25:
            return {"kind": "skill", "sid": random.choice(skills)}
        return {"kind": "attack"}

    # tier3：HP低下で防御、技も使う
    if tier == 3:
        if hp_ratio < 0.3 and random.random() < 0.4:
            heal = [s for s in skills if VS.SKILLS[s]["type"] == "heal"]
            return {"kind": "skill", "sid": heal[0]} if heal else {"kind": "defend"}
        if skills and random.random() < 0.45:
            return {"kind": "skill", "sid": random.choice(skills)}
        return {"kind": "attack"}

    # tier4-5：賢い。相手の溜めを読んで防御、低HPで回復、隙に大技
    if ally.get("charging") and random.random() < 0.6:
        return {"kind": "defend"}   # 溜めを警戒して構える
    if hp_ratio < 0.35:
        heal = [s for s in skills if VS.SKILLS[s]["type"] == "heal"]
        if heal and random.random() < 0.6:
            return {"kind": "skill", "sid": heal[0]}
    atk_skills = [s for s in skills if VS.SKILLS[s]["type"] in ("attack", "pierce", "dot")]
    if atk_skills and random.random() < 0.6:
        # 一番強い倍率を選ぶ
        best = max(atk_skills, key=lambda s: VS.SKILLS[s].get("power", 0))
        return {"kind": "skill", "sid": best}
    return {"kind": "attack"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1ターン進行（味方の行動 → 敵の行動 → ラウンド終了）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _offhand_strike(state):
    """双剣の追撃。白兵のみ・武器power分だけ（レベルボーナス抜き＝案B）。溜め中は出ない。"""
    a = state["ally"]; e = state["enemy"]
    if a.get("charging"):
        return
    d = dmg_calc(a["offhand_power"], e["def"], 1.0)
    amt, line = _deal(state, a, e, d)
    state["log"].append(f"  🗡️ 追撃！{e['name']} に {amt}")
    if e["hp"] <= 0:
        state["over"] = True; state["result"] = "win"


def take_turn(state, ally_action):
    """味方の行動を解決し、敵が生きていれば敵も行動、ラウンドを締める。"""
    state["log"] = []   # このターンのログだけ保持
    resolve_action(state, "ally", ally_action)
    # 双剣の追撃（白兵のみ・武器power分＝レベル抜き）
    if (not state["over"] and state["phase"] == "board"
            and state["ally"].get("offhand_power")):
        _offhand_strike(state)
    if not state["over"]:
        resolve_action(state, "enemy", enemy_action(state))
    if not state["over"]:
        end_round(state)
    return state
