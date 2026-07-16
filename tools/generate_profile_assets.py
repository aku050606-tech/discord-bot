from __future__ import annotations
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import math, random

W,H=1600,860
OUT=Path(__file__).resolve().parents[1]/'assets'/'profile'/'backgrounds'
OUT.mkdir(parents=True, exist_ok=True)

def grad(top,bottom):
    im=Image.new('RGB',(W,H)); d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/(H-1)
        c=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        d.line((0,y,W,y),fill=c)
    return im.convert('RGBA')

def glow(im, xy, radius, color, alpha=150):
    lay=Image.new('RGBA',im.size,(0,0,0,0)); d=ImageDraw.Draw(lay)
    x,y=xy; d.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(*color,alpha))
    lay=lay.filter(ImageFilter.GaussianBlur(radius/2)); im.alpha_composite(lay)

def stars(im, seed, count, area=(0,0,W,H), colors=((180,210,255),(255,255,255))):
    r=random.Random(seed); d=ImageDraw.Draw(im)
    x1,y1,x2,y2=area
    for _ in range(count):
        x=r.randint(x1,x2); y=r.randint(y1,y2); s=r.choice([1,1,1,2,2,3])
        c=r.choice(colors); a=r.randint(100,255)
        d.ellipse((x-s,y-s,x+s,y+s),fill=(*c,a))

def mountains(d, base_y, color, seed, amp=180, n=8):
    r=random.Random(seed); pts=[(0,H)]
    x=0
    while x<W:
        pts.append((x,base_y-r.randint(40,amp))); x+=W//n
    pts.extend([(W,H),(0,H)]); d.polygon(pts,fill=color)

def castle(d, x,y,scale,color):
    towers=[(0,50,55,210),(65,10,125,210),(138,70,180,210),(190,35,245,210)]
    for x1,y1,x2,y2 in towers:
        box=(x+x1*scale,y+y1*scale,x+x2*scale,y+y2*scale)
        d.rectangle(box,fill=color)
        cx=(box[0]+box[2])/2; d.polygon([(box[0]-7*scale,box[1]),(cx,box[1]-35*scale),(box[2]+7*scale,box[1])],fill=color)
    d.rectangle((x,y+170*scale,x+245*scale,y+230*scale),fill=color)

def city(d, horizon, seed, neon=False):
    r=random.Random(seed); x=0
    while x<W:
        bw=r.randint(45,115); bh=r.randint(120,420)
        col=(5,11,24,255) if not neon else (4,10,25,255)
        d.rectangle((x,horizon-bh,x+bw,horizon),fill=col)
        for wy in range(horizon-bh+18,horizon-10,28):
            for wx in range(x+12,x+bw-8,22):
                if r.random()<.45:
                    c=r.choice([(40,170,255,220),(255,60,190,210),(250,200,80,190)]) if neon else (70,110,175,130)
                    d.rectangle((wx,wy,wx+6,wy+10),fill=c)
        x+=bw+r.randint(3,12)

def theme_devi():
    im=grad((27,4,50),(3,1,10)); d=ImageDraw.Draw(im)
    stars(im,11,180,(0,0,W,480),((230,120,255),(120,50,190)))
    glow(im,(1240,170),150,(150,50,225),170); d.ellipse((1130,60,1390,320),fill=(184,105,245,230)); d.ellipse((1200,28,1450,280),fill=(19,3,35,255))
    mountains(d,620,(8,2,16,255),5,260,9); castle(d,1060,330,.95,(5,1,12,255))
    # devil mascot silhouette
    cx,cy=900,415; d.ellipse((cx-65,cy-65,cx+65,cy+65),fill=(4,1,8,255));
    d.polygon([(cx-55,cy-45),(cx-110,cy-120),(cx-20,cy-70)],fill=(4,1,8,255)); d.polygon([(cx+55,cy-45),(cx+110,cy-120),(cx+20,cy-70)],fill=(4,1,8,255))
    d.arc((cx-38,cy-10,cx+38,cy+48),0,180,fill=(220,120,255,255),width=5); d.ellipse((cx-33,cy-15,cx-20,cy-2),fill=(255,80,180,255)); d.ellipse((cx+20,cy-15,cx+33,cy-2),fill=(255,80,180,255))
    return im

def theme_sakura():
    im=grad((57,16,68),(11,6,24)); d=ImageDraw.Draw(im); stars(im,12,120,(0,0,W,430),((255,205,235),(220,160,255)))
    glow(im,(1260,150),120,(255,170,220),120); d.ellipse((1160,50,1370,260),fill=(255,220,235,230)); d.ellipse((1215,30,1410,230),fill=(45,12,58,255))
    # pagoda silhouettes
    for i,(x,y,s) in enumerate([(1100,430,1.0),(1300,500,.72)]):
        for k in range(4):
            yy=y-k*55*s; w=(150-k*18)*s
            d.polygon([(x-w/2,yy),(x+w/2,yy),(x+w*.35,yy-18*s),(x-w*.35,yy-18*s)],fill=(8,4,14,255))
        d.rectangle((x-18*s,y-220*s,x+18*s,y),fill=(8,4,14,255))
    # branch and blossoms
    d.line((720,80,980,310),fill=(35,12,28,255),width=22)
    r=random.Random(4)
    for _ in range(150):
        x=r.randint(700,1120); y=int(80+(x-700)*.55+r.randint(-100,90)); rad=r.randint(3,8)
        d.ellipse((x-rad,y-rad,x+rad,y+rad),fill=r.choice([(255,125,190,220),(255,190,220,210),(230,105,180,190)]))
    return im

def theme_cyber():
    im=grad((2,25,45),(2,4,12)); d=ImageDraw.Draw(im); city(d,650,33,True)
    # rain + roads
    r=random.Random(2)
    for _ in range(240):
        x=r.randint(0,W); y=r.randint(0,H); c=r.choice([(0,180,255,100),(255,40,180,80)])
        d.line((x,y,x-8,y+28),fill=c,width=1)
    d.polygon([(600,H),(860,650),(1050,650),(1500,H)],fill=(4,8,18,255));
    for x,c in [(840,(0,220,255,180)),(1030,(255,50,185,170))]: d.line((x,650,x+(x-935)*2,H),fill=c,width=5)
    glow(im,(1180,250),170,(0,180,255),110); glow(im,(1430,300),150,(255,30,170),90)
    return im

def theme_space():
    im=grad((20,7,55),(2,3,18)); d=ImageDraw.Draw(im); stars(im,51,360,(0,0,W,H),((160,190,255),(255,255,255),(200,120,255)))
    glow(im,(1180,185),190,(130,60,230),130); d.ellipse((1030,35,1330,335),fill=(82,45,155,255)); d.ellipse((1075,70,1295,290),fill=(30,18,85,255))
    d.arc((970,115,1400,250),185,355,fill=(210,135,255,220),width=15)
    # floating islands
    for x,y,s in [(900,430,1),(1260,500,.7),(1450,350,.5)]:
        d.polygon([(x-100*s,y),(x+100*s,y),(x+55*s,y+50*s),(x,y+150*s),(x-55*s,y+50*s)],fill=(12,8,30,255))
        d.ellipse((x-80*s,y-30*s,x+80*s,y+30*s),fill=(20,20,45,255))
    return im

def theme_ocean():
    im=grad((3,48,85),(0,8,24)); d=ImageDraw.Draw(im)
    # surface rays
    for x in range(0,W,100): d.polygon([(x,0),(x+55,0),(x+240,H),(x+170,H)],fill=(30,160,220,16))
    # bubbles/jellyfish
    r=random.Random(8)
    for _ in range(110):
        x=r.randint(650,1550); y=r.randint(50,750); rr=r.randint(2,12); d.ellipse((x-rr,y-rr,x+rr,y+rr),outline=(80,190,240,r.randint(50,130)),width=1)
    for x,y,s in [(1240,230,1),(1430,430,.7),(980,520,.55)]:
        glow(im,(x,y),45*s,(80,180,255),90); d.pieslice((x-35*s,y-25*s,x+35*s,y+35*s),180,360,fill=(130,190,255,160))
        for q in (-20,-7,7,20): d.arc((x+q*s-8,y,x+q*s+8,y+75*s),80,260,fill=(120,180,250,150),width=max(1,int(2*s)))
    # whale
    d.ellipse((800,250,1170,400),fill=(6,32,60,220)); d.polygon([(1130,310),(1240,235),(1215,350)],fill=(6,32,60,220)); d.polygon([(830,330),(760,420),(915,355)],fill=(6,32,60,220))
    return im

def theme_fantasy():
    im=grad((42,58,90),(7,12,24)); d=ImageDraw.Draw(im); stars(im,71,110,(0,0,W,300),((220,230,255),(255,220,150)))
    glow(im,(1270,145),130,(255,200,100),100); d.ellipse((1170,45,1370,245),fill=(255,225,170,220)); d.ellipse((1230,20,1415,215),fill=(43,55,82,255))
    mountains(d,620,(10,17,28,255),6,260,8); castle(d,1080,320,1.0,(7,12,22,255))
    # dragon silhouette
    d.polygon([(860,210),(970,160),(1080,210),(1000,220),(1100,280),(970,245),(900,290),(925,225)],fill=(7,10,18,230))
    d.arc((855,180,1030,270),190,350,fill=(210,170,100,100),width=3)
    return im

def theme_city():
    im=grad((8,18,42),(3,5,14)); d=ImageDraw.Draw(im); stars(im,88,100,(0,0,W,350),((130,170,255),(255,255,255))); city(d,690,74,False)
    glow(im,(1250,170),140,(75,120,240),80); d.ellipse((1160,70,1350,260),fill=(175,200,245,180)); d.ellipse((1210,45,1390,225),fill=(9,18,43,255))
    # balcony silhouette
    d.rectangle((750,680,1550,710),fill=(2,3,8,255)); d.line((750,610,1550,610),fill=(70,90,130,130),width=4)
    return im

def theme_hell():
    im=grad((68,8,12),(12,1,3)); d=ImageDraw.Draw(im)
    glow(im,(1230,160),170,(255,40,20),160); d.ellipse((1090,20,1370,300),fill=(110,0,4,255)); d.ellipse((1135,65,1325,255),fill=(15,0,2,255)); d.arc((1085,15,1375,305),0,360,fill=(255,60,25,240),width=12)
    mountains(d,620,(18,1,3,255),13,320,10); castle(d,1090,340,.95,(7,0,1,255))
    # lava cracks
    r=random.Random(15)
    for _ in range(35):
        x=r.randint(700,1550); y=r.randint(620,850); pts=[(x,y)]
        for k in range(4): x+=r.randint(-30,35); y+=r.randint(20,55); pts.append((x,y))
        d.line(pts,fill=(255,70,20,220),width=r.randint(2,5))
    return im

def theme_snow():
    im=grad((10,38,74),(4,15,32)); d=ImageDraw.Draw(im)
    # aurora
    lay=Image.new('RGBA',(W,H),(0,0,0,0)); ld=ImageDraw.Draw(lay)
    for i,c in enumerate([(60,255,205,80),(70,130,255,70),(170,80,255,55)]):
        pts=[]
        for x in range(0,W+80,80): pts.append((x,80+i*45+math.sin(x/170+i)*45))
        pts += [(W,330+i*20),(0,330+i*20)]
        ld.polygon(pts,fill=c)
    lay=lay.filter(ImageFilter.GaussianBlur(35)); im.alpha_composite(lay)
    stars(im,99,180,(0,0,W,400),((210,235,255),(255,255,255)))
    mountains(d,620,(8,24,44,255),16,260,9); mountains(d,690,(16,40,65,255),18,190,10); castle(d,1120,370,.8,(6,17,32,255))
    r=random.Random(21)
    for _ in range(160):
        x=r.randint(0,W); y=r.randint(0,H); s=r.choice([1,2,3]); d.ellipse((x-s,y-s,x+s,y+s),fill=(230,245,255,r.randint(80,210)))
    return im

def theme_forest():
    im=grad((3,38,37),(1,10,14)); d=ImageDraw.Draw(im)
    glow(im,(1170,300),220,(20,220,155),90)
    # giant tree
    d.polygon([(1120,700),(1080,420),(1010,300),(1085,360),(1130,130),(1180,350),(1290,260),(1210,420),(1260,700)],fill=(3,18,18,255))
    for cx,cy,rx,ry in [(1070,220,180,120),(1200,200,210,135),(1290,290,170,110),(980,320,150,100)]: d.ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill=(5,42,37,230))
    r=random.Random(44)
    for _ in range(220):
        x=r.randint(650,1550); y=r.randint(80,740); s=r.choice([1,1,2,3]); c=r.choice([(45,255,180,190),(120,255,210,150),(255,240,120,140)]); d.ellipse((x-s,y-s,x+s,y+s),fill=c)
    # deer
    d.ellipse((760,570,860,630),fill=(4,25,24,255)); d.rectangle((815,610,830,700),fill=(4,25,24,255)); d.ellipse((840,535,890,575),fill=(4,25,24,255)); d.line((860,545,842,505),fill=(4,25,24,255),width=5); d.line((870,545,890,505),fill=(4,25,24,255),width=5)
    return im

THEMES={'devi':theme_devi,'sakura':theme_sakura,'cyber':theme_cyber,'space':theme_space,'ocean':theme_ocean,'fantasy':theme_fantasy,'city':theme_city,'hell':theme_hell,'snow':theme_snow,'forest':theme_forest}
for name,fn in THEMES.items():
    im=fn().convert('RGB')
    # subtle vignette
    vig=Image.new('L',(W,H),0); vd=ImageDraw.Draw(vig)
    for i in range(180):
        a=int(190*(i/180)**2); vd.rounded_rectangle((i,i,W-i,H-i),radius=40,outline=a,width=2)
    black=Image.new('RGB',(W,H),(0,0,0)); im=Image.composite(black,im,vig)
    im.save(OUT/f'{name}.png',quality=94,optimize=True)
print('generated', len(THEMES), 'backgrounds at', OUT)
