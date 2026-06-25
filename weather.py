"""天候・時間エンジン v2（決定論的 / 9ヶ所対応）"""
import hashlib
from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))

TIME_PERIODS = [
    {"key":"asa","name":"朝","emoji":"🌄"},{"key":"hiru","name":"昼","emoji":"☀️"},
    {"key":"yugata","name":"夕方","emoji":"🌇"},{"key":"yoru","name":"夜","emoji":"🌃"},
    {"key":"shinya","name":"深夜","emoji":"🌌"},{"key":"akegata","name":"明け方","emoji":"🌅"},
]
PERIOD_MINUTES = 120
N_PERIODS = len(TIME_PERIODS)
SPOTS = (1, 2, 3)
SPOT_PHASE_STEP = 2
AREA_BASE_PHASE = {"lake":0,"river":1,"sea":3}
AREAS = ("lake","river","sea")
AREA_NAMES = {"lake":"湖","river":"川","sea":"海"}

WEATHER = {
    "clear":     {"name":"晴れ","emoji":"☀️","weight":40,"gate":None,"limited":False},
    "cloudy":    {"name":"曇り","emoji":"☁️","weight":30,"gate":None,"limited":False},
    "rain":      {"name":"雨","emoji":"🌧️","weight":8,"gate":None,"limited":True},
    "fog":       {"name":"霧","emoji":"🌫️","weight":8,"gate":None,"limited":True},
    "glow":      {"name":"朝焼け/夕焼け","emoji":"🌅","weight":7,"gate":"glow","limited":True},
    "storm":     {"name":"嵐","emoji":"⛈️","weight":6,"gate":None,"limited":True,"chest":True},
    "blood_moon":{"name":"赤い月","emoji":"🩸","weight":4,"gate":"night","limited":True,"boss":True},
}
WEATHER_UPDATE_MINUTES = 30
GATE_PERIODS = {"glow":{"asa","yugata"}, "night":{"yoru","shinya"}}

def _epoch_minutes(now=None):
    if now is None: now = datetime.now(timezone.utc)
    return int(now.timestamp() // 60)
def _phase(area, spot):
    return AREA_BASE_PHASE.get(area,0) + (spot-1)*SPOT_PHASE_STEP
def _period_at(area, spot, em):
    return TIME_PERIODS[(em//PERIOD_MINUTES + _phase(area,spot)) % N_PERIODS]
def get_time_period(area, spot=1, now=None):
    return _period_at(area, spot, _epoch_minutes(now))
def _seeded_rand(*parts):
    h = hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8],16)/0xFFFFFFFF
def _weather_at(area, spot, em):
    bucket = em//WEATHER_UPDATE_MINUTES
    period = _period_at(area,spot,em)["key"]
    cand = []
    for key,w in WEATHER.items():
        g = w["gate"]
        if g is not None and period not in GATE_PERIODS.get(g,set()): continue
        cand.append((key,w["weight"]))
    total = sum(wt for _,wt in cand)
    r = _seeded_rand(area,spot,bucket)*total
    acc=0.0; chosen=cand[0][0]
    for key,wt in cand:
        acc+=wt
        if r<acc: chosen=key; break
    out=dict(WEATHER[chosen]); out["key"]=chosen; return out
def get_weather(area, spot=1, now=None):
    return _weather_at(area, spot, _epoch_minutes(now))
def describe(area, spot, now=None):
    p=get_time_period(area,spot,now); return f"{p['emoji']}{p['name']}"

def scan_forecast(weathers=("storm","fog"), hours=12, now=None):
    em0=_epoch_minutes(now); steps=(hours*60)//WEATHER_UPDATE_MINUTES; best={}
    for area in AREAS:
        for spot in SPOTS:
            for s in range(steps+1):
                w=_weather_at(area,spot,em0+s*WEATHER_UPDATE_MINUTES)
                if w["key"] in weathers:
                    mins=s*WEATHER_UPDATE_MINUTES
                    if area not in best or mins<best[area]["minutes_ahead"]:
                        best[area]={"area":area,"spot":spot,"weather":w["key"],"minutes_ahead":mins}
                    break
    return [best[a] for a in AREAS if a in best]

def current_weathers(now=None):
    em=_epoch_minutes(now)
    return [{"area":a,"spot":s,**_weather_at(a,s,em)} for a in AREAS for s in SPOTS]
def blood_moon_now(now=None):
    for w in current_weathers(now):
        if w["key"]=="blood_moon": return {"area":w["area"],"spot":w["spot"]}
    return None
def next_blood_moon(hours=12, now=None):
    em0=_epoch_minutes(now); steps=(hours*60)//WEATHER_UPDATE_MINUTES; best=None
    for area in AREAS:
        for spot in SPOTS:
            for s in range(steps+1):
                if _weather_at(area,spot,em0+s*WEATHER_UPDATE_MINUTES)["key"]=="blood_moon":
                    mins=s*WEATHER_UPDATE_MINUTES
                    if best is None or mins<best["minutes_ahead"]:
                        best={"area":area,"spot":spot,"minutes_ahead":mins}
                    break
    return best
