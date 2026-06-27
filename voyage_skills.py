# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚔️ 技カタログ（航海システム）── 付け替え式・無レア・武器種別で装着制限
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  方針:
#   ・技は装備とは独立カタログ。装備の技スロットに後からセット（付け替え式）。
#   ・一度刻んだ技は固定。外す/付け替えには「技外しキット」が必要。
#   ・武器技は「対応する武器種別(wtypes)」の武器にしか刻めない。
#       例：応急手当(回復)は 杖 専用 → 攻撃武器には刺さらない＝ヒーラー専用化。
#   ・防具技(slot="armor")は 胴/脚 どちらにも刻める。
#   ・まず6種。大海原で回せる範囲。奥の海・新武器種で追って増やす。
#
#  slot     : "weapon"(武器に刻む) / "armor"(胴・脚に刻む) / "cannon"/"sarmor"/"hull"(船)
#  wtypes   : slot=="weapon" のとき、刻める武器種別(剣sword/刀katana/双剣twin/杖staff/弓bow/銃gun)
#  type     : attack / defend / heal / dot / pierce
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SKILLS = {
    # ── 武器技（attack/dot/heal）── 武器種別で装着制限 ──
    "kyougeki": {
        "name": "強撃", "emoji": "⚔️", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "katana", "twin"],
        "type": "attack", "power": 1.6, "hits": 1, "cost": 0, "cooldown": 0,
        "acc": 0.95, "charge": 0, "price": 5000,
        "desc": "渾身の一撃。個人力の1.6倍を確実に叩き込む。",
    },
    "rengeki": {
        "name": "連撃", "emoji": "🌀", "phase": "board", "slot": "weapon",
        "wtypes": ["twin", "sword"],
        "type": "attack", "power": 0.6, "hits": 3, "cost": 0, "cooldown": 0,
        "acc": 0.9, "charge": 0, "price": 6000,
        "desc": "素早い三連斬り。1発は軽いが手数で押し切る。双剣と好相性。",
    },
    "konshin": {
        "name": "渾身斬り", "emoji": "💢", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "katana"],
        "type": "attack", "power": 3.0, "hits": 1, "cost": 0, "cooldown": 0,
        "acc": 0.9, "charge": 1, "price": 12000,
        "desc": "1ターン溜めて次に大ダメージ。決まれば一撃必殺級。",
    },
    "shukketsu": {
        "name": "出血斬り", "emoji": "🩸", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "katana", "twin"],
        "type": "dot", "power": 0.8, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 0.9, "charge": 0, "dot_power": 0.35, "dot_turns": 3, "price": 8000,
        "desc": "斬りつけて出血させる。3ターン継続でじわじわ削る。",
    },
    "oukyu": {
        "name": "応急手当", "emoji": "💊", "phase": "board", "slot": "weapon",
        "wtypes": ["staff"],
        "type": "heal", "power": 0.0, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "heal_flat": 40, "heal_ratio": 0.0, "price": 7000,
        "desc": "傷の手当てでHP回復。杖専用＝ヒーラーの要。",
    },
    # ── 防具技（defend）── 胴/脚 に刻める ──
    "teppeki": {
        "name": "鉄壁", "emoji": "🛡️", "phase": "board", "slot": "armor",
        "type": "defend", "power": 0.0, "hits": 0, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "reduce": 0.7, "price": 5000,
        "desc": "1ターン構える。受けるダメージを70%カット。",
    },
}

# ── ある武器に、その技を刻めるか（武器種別で判定）──
def skill_fits_weapon(skill_id, wtype):
    s = SKILLS.get(skill_id)
    if not s or s["slot"] != "weapon":
        return False
    return wtype in s.get("wtypes", [])

# ── 刻みスロット種(weapon/armor) に対する技ID一覧 ──
def skills_for_slot(slot):
    return [sid for sid, s in SKILLS.items() if s["slot"] == slot]

# ── 技外しキット（付け替えに必要なアイテム）──
UNEQUIP_KIT_PRICE = 3000
