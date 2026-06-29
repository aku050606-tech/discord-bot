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
    # ━━━━━ 白兵技 ☆2（実効1.2倍に統一）━━━━━
    "kyougeki": {
        "name": "強撃", "emoji": "⚔️", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "gun", "greatsword"], "rank": 2,
        "type": "attack", "power": 1.6, "hits": 1, "cost": 0, "cooldown": 2,
        "acc": 0.95, "charge": 0, "price": 50000,
        "desc": "渾身の一撃。個人力の1.6倍。剣・銃・大剣向け。",
    },
    "rengeki": {
        "name": "連撃", "emoji": "🌀", "phase": "board", "slot": "weapon",
        "wtypes": ["twin", "bow"], "rank": 2,
        "type": "attack", "power": 0.53, "hits": 3, "cost": 0, "cooldown": 2,
        "acc": 0.9, "charge": 0, "price": 50000,
        "desc": "素早い三連撃。手数で押し切る。双剣・弓向け。",
    },
    "konshin": {
        "name": "渾身斬り", "emoji": "💢", "phase": "board", "slot": "weapon",
        "wtypes": ["staff", "greatsword"], "rank": 2,
        "type": "attack", "power": 2.4, "hits": 1, "cost": 0, "cooldown": 0,
        "acc": 1.0, "charge": 1, "price": 50000,
        "desc": "1ターン溜めて大ダメージ。2ターンに1回の必殺。",
    },
    "shukketsu": {
        "name": "出血斬り", "emoji": "🩸", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "katana", "twin"], "rank": 2,
        "type": "dot", "power": 0.5, "hits": 1, "cost": 0, "cooldown": 2,
        "acc": 0.9, "charge": 0, "dot_power": 0.29, "dot_turns": 3, "price": 50000,
        "desc": "斬りつけて出血。3ターン継続でじわじわ削る。",
    },
    "oukyu": {
        "name": "応急手当", "emoji": "💊", "phase": "board", "slot": "weapon",
        "wtypes": ["staff"], "rank": 2,
        "type": "heal", "power": 0.0, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "heal_flat": 40, "heal_ratio": 0.0, "price": 50000,
        "desc": "傷の手当てでHP回復。杖専用＝ヒーラーの要。",
    },
    "snipe": {
        "name": "狙撃", "emoji": "🎯", "phase": "board", "slot": "weapon",
        "wtypes": ["bow", "gun"], "rank": 2,
        "type": "attack", "power": 1.8, "hits": 1, "cost": 0, "cooldown": 3,
        "acc": 0.95, "charge": 0, "price": 50000,
        "desc": "狙いを定めた一撃。個人力の1.8倍。CD長め。弓・銃向け。",
    },
    "piercing": {
        "name": "貫通弾", "emoji": "🔩", "phase": "board", "slot": "weapon",
        "wtypes": ["gun", "bow"], "rank": 2,
        "type": "pierce", "power": 1.4, "hits": 1, "pierce": 0.6, "cost": 0, "cooldown": 2,
        "acc": 0.95, "charge": 0, "price": 50000,
        "desc": "装甲を貫く一撃。敵防御の60%を無視。硬い敵に刺さる。",
    },
    "issen": {
        "name": "一閃", "emoji": "⚡", "phase": "board", "slot": "weapon",
        "wtypes": ["greatsword", "sword"], "rank": 2,
        "type": "attack", "power": 2.0, "hits": 1, "cost": 0, "cooldown": 4,
        "acc": 1.0, "charge": 0, "price": 50000,
        "desc": "渾身の一閃。個人力の2.0倍。CD最長の一撃必殺。大剣・剣向け。",
    },
    # ── 防具技（defend）── 胴/脚 に刻める ──
    "teppeki": {
        "name": "鉄壁", "emoji": "🛡️", "phase": "board", "slot": "armor", "rank": 2,
        "type": "defend", "power": 0.0, "hits": 0, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "reduce": 0.7, "price": 50000,
        "desc": "1ターン構える。受けるダメージを70%カット。",
    },
    # ━━━━━ 白兵技 ☆3（☆2比 約1.4倍・技ガチャ専用 price=0）━━━━━
    "kyougeki3": {
        "name": "強撃・改", "emoji": "⚔️", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "gun", "greatsword"], "rank": 3,
        "type": "attack", "power": 2.24, "hits": 1, "cost": 0, "cooldown": 2,
        "acc": 0.95, "charge": 0, "price": 250000,
        "desc": "☆3。強撃の上位。個人力の2.24倍。",
    },
    "rengeki3": {
        "name": "連撃・改", "emoji": "🌀", "phase": "board", "slot": "weapon",
        "wtypes": ["twin", "bow"], "rank": 3,
        "type": "attack", "power": 0.742, "hits": 3, "cost": 0, "cooldown": 2,
        "acc": 0.9, "charge": 0, "price": 250000,
        "desc": "☆3。連撃の上位。三連撃が冴え渡る。",
    },
    "konshin3": {
        "name": "渾身斬り・改", "emoji": "💢", "phase": "board", "slot": "weapon",
        "wtypes": ["staff", "greatsword"], "rank": 3,
        "type": "attack", "power": 3.36, "hits": 1, "cost": 0, "cooldown": 0,
        "acc": 1.0, "charge": 1, "price": 250000,
        "desc": "☆3。溜めて放つ極大の一撃。",
    },
    "shukketsu3": {
        "name": "出血斬り・改", "emoji": "🩸", "phase": "board", "slot": "weapon",
        "wtypes": ["sword", "katana", "twin"], "rank": 3,
        "type": "dot", "power": 0.7, "hits": 1, "cost": 0, "cooldown": 2,
        "acc": 0.9, "charge": 0, "dot_power": 0.406, "dot_turns": 3, "price": 250000,
        "desc": "☆3。深い傷でより激しく出血させる。",
    },
    "oukyu3": {
        "name": "応急手当・改", "emoji": "💊", "phase": "board", "slot": "weapon",
        "wtypes": ["staff"], "rank": 3,
        "type": "heal", "power": 0.0, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "heal_flat": 56, "heal_ratio": 0.0, "price": 250000,
        "desc": "☆3。より多くのHPを回復する。",
    },
    "snipe3": {
        "name": "狙撃・改", "emoji": "🎯", "phase": "board", "slot": "weapon",
        "wtypes": ["bow", "gun"], "rank": 3,
        "type": "attack", "power": 2.52, "hits": 1, "cost": 0, "cooldown": 3,
        "acc": 0.95, "charge": 0, "price": 250000,
        "desc": "☆3。狙撃の上位。個人力の2.52倍。",
    },
    "piercing3": {
        "name": "貫通弾・改", "emoji": "🔩", "phase": "board", "slot": "weapon",
        "wtypes": ["gun", "bow"], "rank": 3,
        "type": "pierce", "power": 1.96, "hits": 1, "pierce": 0.65, "cost": 0, "cooldown": 2,
        "acc": 0.95, "charge": 0, "price": 250000,
        "desc": "☆3。より深く装甲を貫く。防御65%無視。",
    },
    "issen3": {
        "name": "一閃・改", "emoji": "⚡", "phase": "board", "slot": "weapon",
        "wtypes": ["greatsword", "sword"], "rank": 3,
        "type": "attack", "power": 2.8, "hits": 1, "cost": 0, "cooldown": 4,
        "acc": 1.0, "charge": 0, "price": 250000,
        "desc": "☆3。一閃の極み。個人力の2.8倍。",
    },
    "teppeki3": {
        "name": "鉄壁・改", "emoji": "🛡️", "phase": "board", "slot": "armor", "rank": 3,
        "type": "defend", "power": 0.0, "hits": 0, "cost": 0, "cooldown": 1,
        "acc": 1.0, "charge": 0, "reduce": 0.8, "price": 250000,
        "desc": "☆3。受けるダメージを80%カット。",
    },
    # ── 船技（海戦）── 船の部位に刻める ──
    "seisha": {
        "name": "斉射", "emoji": "💥", "phase": "naval", "slot": "ship_cannon",
        "type": "attack", "power": 1.7, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 0.95, "charge": 0, "price": 8000,
        "desc": "全砲門の一斉射撃。船力の1.4倍を敵船に。【砲】",
    },
    "tekkoudan": {
        "name": "徹甲弾", "emoji": "🎯", "phase": "naval", "slot": "ship_cannon",
        "type": "pierce", "power": 1.1, "hits": 1, "cost": 0, "cooldown": 1,
        "acc": 0.9, "charge": 0, "pierce": 0.8, "price": 12000,
        "desc": "装甲を貫く徹甲弾。敵防御の60%を無視。【砲】",
    },
    "enmaku": {
        "name": "煙幕", "emoji": "🌫️", "phase": "naval", "slot": "ship_armor",
        "type": "defend", "power": 0.0, "hits": 0, "cost": 0, "cooldown": 4,
        "acc": 1.0, "charge": 0, "reduce": 0.35, "duration": 3, "price": 7000,
        "desc": "煙幕を展開。1ターン敵砲撃の被弾を50%軽減。【装甲】",
    },
    "zenshin": {
        "name": "全速前進", "emoji": "🌊", "phase": "naval", "slot": "ship_body",
        "type": "defend", "power": 0.0, "hits": 0, "cost": 0, "cooldown": 4,
        "acc": 1.0, "charge": 0, "reduce": 0.3, "counter": 0.2, "duration": 3, "price": 9000,
        "desc": "舵を切って回避機動。被弾を抑えつつ次の砲撃で反撃。【船本体】",
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
