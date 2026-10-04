from __future__ import annotations
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import random

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


THEMES={'devi':theme_devi,'sakura':theme_sakura}
for name,fn in THEMES.items():
    im=fn().convert('RGB')
    # subtle vignette
    vig=Image.new('L',(W,H),0); vd=ImageDraw.Draw(vig)
    for i in range(180):
        a=int(190*(i/180)**2); vd.rounded_rectangle((i,i,W-i,H-i),radius=40,outline=a,width=2)
    black=Image.new('RGB',(W,H),(0,0,0)); im=Image.composite(black,im,vig)
    im.save(OUT/f'{name}.png',quality=94,optimize=True)
print('generated', len(THEMES), 'backgrounds at', OUT)
