"""픽셀아트 변환 코어 v3 - 각 단계 토글 가능."""
import numpy as np
from PIL import Image
from scipy import ndimage
import colorsys

# ---------- 배경/크롭/스케일 (v2 유지) ----------
def make_alpha(arr, light=190, sat=28, close_iter=1):
    r,g,b=arr[...,0].astype(int),arr[...,1].astype(int),arr[...,2].astype(int)
    mx=np.maximum(np.maximum(r,g),b); mn=np.minimum(np.minimum(r,g),b)
    bg_like=(mx>light)&((mx-mn)<sat)
    lbl,_=ndimage.label(bg_like)
    border=set(lbl[0,:])|set(lbl[-1,:])|set(lbl[:,0])|set(lbl[:,-1]); border.discard(0)
    fg=~np.isin(lbl,list(border))
    fg=ndimage.binary_closing(fg,iterations=close_iter); fg=ndimage.binary_fill_holes(fg)
    return (fg*255).astype(np.uint8)

def crop_to_content(arr,alpha,pad=2):
    ys,xs=np.where(alpha>0)
    if len(xs)==0: return arr,alpha
    y0,y1,x0,x1=ys.min(),ys.max(),xs.min(),xs.max()
    y0=max(0,y0-pad);x0=max(0,x0-pad);y1=min(arr.shape[0]-1,y1+pad);x1=min(arr.shape[1]-1,x1+pad)
    return arr[y0:y1+1,x0:x1+1],alpha[y0:y1+1,x0:x1+1]

def target_size(w,h,L):
    return (L,max(1,round(h*L/w))) if w>=h else (max(1,round(w*L/h)),L)

def premult_downscale(rgb,alpha,size):
    a=alpha.astype(np.float32)/255.0; pm=rgb.astype(np.float32)*a[...,None]
    pm_s=np.asarray(Image.fromarray(np.clip(pm,0,255).astype(np.uint8)).resize(size,Image.BOX),dtype=np.float32)
    a_s=np.asarray(Image.fromarray(alpha).resize(size,Image.BOX),dtype=np.float32)/255.0
    with np.errstate(divide="ignore",invalid="ignore"):
        rgb_s=np.where(a_s[...,None]>0.001,pm_s/a_s[...,None],0)
    return np.clip(rgb_s,0,255).astype(np.uint8),(a_s*255).astype(np.uint8)

# ---------- 램프 팔레트 (HSB + 휴 시프트) ----------
def build_ramp_palette(rgb, alpha, n_ramps=8, steps=5, hue_shift=18.0, sat_boost=1.15):
    """불투명 픽셀을 n_ramps개 베이스로 군집. 각 베이스마다 밝기 steps단 램프를
    - 채도는 강하게 유지(어두울수록 +채도), 밝은 끝만 살짝 하강
    - 휴 시프트(어두울수록 +hue, 밝을수록 -hue) 적용해 합성."""
    from sklearn.cluster import KMeans
    mask=alpha>0
    px=rgb[mask].astype(np.float32)
    if len(px)==0: px=rgb.reshape(-1,3).astype(np.float32)
    if len(px)>20000:
        idx=np.random.RandomState(0).choice(len(px),20000,replace=False); px=px[idx]
    k=min(n_ramps,max(1,len(np.unique(px.astype(np.uint8),axis=0))))
    km=KMeans(n_clusters=k,n_init=4,random_state=0).fit(px)
    pal=[]
    for c,lab in zip(km.cluster_centers_,range(k)):
        member=px[km.labels_==lab]
        hsv=np.array([colorsys.rgb_to_hsv(*(p/255.0)) for p in member[::max(1,len(member)//500)]])
        base_h,base_s,base_v=colorsys.rgb_to_hsv(*(c/255.0))
        vs=hsv[:,2]
        vmin,vmax=np.percentile(vs,15),np.percentile(vs,85)
        if vmax-vmin<0.22:            # 최소 스팬 보장
            mid=(vmin+vmax)/2; vmin,vmax=max(0.05,mid-0.13),min(1.0,mid+0.13)
        vmin=max(0.05,vmin-0.03); vmax=min(1.0,vmax+0.05)
        for i in range(steps):
            frac=i/(steps-1) if steps>1 else 0.5
            V=vmin+(vmax-vmin)*frac
            # 채도: 강하게 유지, 어두운쪽 더 진하게(1.18) 밝은쪽만 약간 하강(0.80)
            S=float(np.clip(base_s*sat_boost*(1.18-0.38*frac),0.0,1.0))
            H=(base_h*360.0 + hue_shift*(0.5-frac)*2.0)%360.0
            r,g,b=colorsys.hsv_to_rgb(H/360.0,S,V)
            pal.append([r*255,g*255,b*255])
    pal=np.array(pal,dtype=np.float32)
    uniq=np.unique(np.round(pal).astype(np.int32),axis=0).astype(np.float32)
    return uniq


def median_palette(rgb, colors):
    q=Image.fromarray(rgb,"RGB").quantize(colors=colors,method=Image.MEDIANCUT)
    pal=np.array(q.getpalette()[:colors*3],dtype=np.float32).reshape(-1,3)
    return pal

# ---------- 팔레트 매핑 + 디더링 (none/ordered/floyd) ----------
def _bayer(n):
    if n==1: return np.array([[0.0]])
    m=_bayer(n//2)
    return np.block([[4*m,4*m+2],[4*m+3,4*m+1]])/(n*n)

def _nearest(flat, palette):
    out=np.empty(len(flat),dtype=np.int32)
    P=palette[None,:,:]
    step=4096
    for i in range(0,len(flat),step):
        chunk=flat[i:i+step][:,None,:]
        d=((chunk-P)**2).sum(2)
        out[i:i+step]=d.argmin(1)
    return out

def _palette_spread(palette):
    # 각 색에서 가장 가까운 다른 색까지 거리의 중앙값
    P=palette; D=np.sqrt(((P[:,None,:]-P[None,:,:])**2).sum(2))
    np.fill_diagonal(D,1e9)
    return float(np.median(D.min(1)))

def map_to_palette(rgb, palette, dither="none", bayer_n=4, strength=1.0):
    h,w=rgb.shape[:2]; flat=rgb.reshape(-1,3).astype(np.float32)
    if dither=="ordered":
        spread=_palette_spread(palette)*strength
        bm=_bayer(bayer_n); th=(np.tile(bm,(h//bayer_n+1,w//bayer_n+1))[:h,:w]-0.5)
        flat=flat+ (th.reshape(-1,1)*spread)
        idx=_nearest(np.clip(flat,0,255),palette)
        res=palette[idx].reshape(h,w,3)
    elif dither=="floyd":
        img=flat.reshape(h,w,3).copy()
        for y in range(h):
            for x in range(w):
                old=img[y,x].copy()
                ni=_nearest(old[None,:],palette)[0]; new=palette[ni]
                img[y,x]=new; err=old-new
                if x+1<w: img[y,x+1]+=err*7/16
                if y+1<h:
                    if x>0: img[y+1,x-1]+=err*3/16
                    img[y+1,x]+=err*5/16
                    if x+1<w: img[y+1,x+1]+=err*1/16
        res=img
    else:
        idx=_nearest(flat,palette); res=palette[idx].reshape(h,w,3)
    return np.clip(res,0,255).astype(np.uint8)

# ---------- 라인 클린업 (고아 픽셀 제거) ----------
def cleanup_lines(rgb, alpha, min_cluster=2):
    """색이 동일한 아주 작은 섬(<min_cluster+1 px)을 주변 최빈색으로 흡수."""
    out=rgb.copy()
    flat=rgb.reshape(-1,3)
    cols,inv=np.unique(flat,axis=0,return_inverse=True)
    inv=inv.reshape(rgb.shape[:2])
    for ci in range(len(cols)):
        m=(inv==ci)&(alpha>0)
        lbl,n=ndimage.label(m)
        if n==0: continue
        sizes=ndimage.sum(np.ones_like(lbl),lbl,range(1,n+1))
        for li,sz in enumerate(sizes,1):
            if sz<=min_cluster:
                ys,xs=np.where(lbl==li)
                for y,x in zip(ys,xs):
                    nb=[]
                    for dy,dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                        yy,xx=y+dy,x+dx
                        if 0<=yy<rgb.shape[0] and 0<=xx<rgb.shape[1] and alpha[yy,xx]>0 and inv[yy,xx]!=ci:
                            nb.append(tuple(rgb[yy,xx]))
                    if nb:
                        out[y,x]=max(set(nb),key=nb.count)
    return out

# ---------- 아웃라인 (dark / selout) ----------
def add_outline(rgb, alpha, mode="dark", darken=0.45):
    """실루엣 바깥 1px 링에 어두운 아웃라인. selout은 위/아래로 명암 차등."""
    if mode=="none": return rgb, alpha
    m=alpha>0
    dil=ndimage.binary_dilation(m,iterations=1)
    ring=dil&(~m)
    out=rgb.copy(); a=alpha.copy()
    ys,xs=np.where(ring)
    H=rgb.shape[0]
    for y,x in zip(ys,xs):
        # 인접 전경색 평균을 어둡게
        nb=[]
        for dy,dx in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]:
            yy,xx=y+dy,x+dx
            if 0<=yy<rgb.shape[0] and 0<=xx<rgb.shape[1] and m[yy,xx]:
                nb.append(rgb[yy,xx])
        if not nb: continue
        base=np.mean(nb,axis=0)
        f=darken
        if mode=="selout":
            f=0.30 if y< H*0.5 else 0.55   # 위(광원)는 덜, 아래는 더 어둡게
        out[y,x]=np.clip(base*(1-f),0,255)
        a[y,x]=255
    return out, a

def add_edges(rgb, alpha, palette, thresh=60, darken=0.55, thin=True):
    """내부 색/명암 경계를 감지해 어둡게(잉크). 팔레트에 스냅해 색 규율 유지.
    풀 일러스트처럼 배경이 있는 그림에서 '덩어리 윤곽'을 만들어 준다."""
    m=alpha>0
    lum=0.299*rgb[...,0]+0.587*rgb[...,1]+0.114*rgb[...,2]
    gx=ndimage.sobel(lum,axis=1,mode="nearest"); gy=ndimage.sobel(lum,axis=0,mode="nearest")
    mag=np.hypot(gx,gy)
    edge=(mag>thresh)&m
    if thin:
        # 이중 두께 방지: 더 어두운(안쪽) 픽셀만 잉크로
        darker=lum<=ndimage.minimum_filter(lum,size=3)+1
        edge=edge&darker
    out=rgb.copy().astype(np.float32)
    ink=out[edge]*(1-darken)
    # 팔레트 스냅
    if len(ink):
        idx=_nearest(np.clip(ink,0,255),palette)
        out[edge]=palette[idx]
    return np.clip(out,0,255).astype(np.uint8)


def finish_alpha(alpha_arr, mode, thresh):
    a=Image.fromarray(alpha_arr)
    if mode=="binary": return a.point(lambda v:255 if v>=thresh else 0)
    return a

# ---------- 통합 파이프라인 ----------
def pixelate(path, res, cfg):
    arr=np.asarray(Image.open(path).convert("RGB"))
    return pixelate_rgb(arr, res, cfg)

def pixelate_rgb(arr, res, cfg):
    arr=np.ascontiguousarray(arr[...,:3]).astype(np.uint8)
    if cfg.get("removebg",True):
        alpha=make_alpha(arr,cfg.get("light",190),cfg.get("sat",28))
    else:
        alpha=np.full(arr.shape[:2],255,np.uint8)
    if cfg.get("crop",True):
        arr,alpha=crop_to_content(arr,alpha)
    h,w=arr.shape[:2]; size=target_size(w,h,res)
    rgb_s,a_s=premult_downscale(arr,alpha,size)
    # 팔레트
    if cfg.get("palette","median")=="ramp":
        pal=build_ramp_palette(rgb_s,a_s,cfg.get("ramps",8),cfg.get("ramp_steps",5),
                               cfg.get("hue_shift",18.0),cfg.get("sat_boost",1.05))
    else:
        pal=median_palette(rgb_s,cfg.get("colors",24))
    q=map_to_palette(rgb_s,pal,cfg.get("dither","none"),cfg.get("bayer",4),cfg.get("strength",1.0))
    if cfg.get("cleanup",False):
        q=cleanup_lines(q,a_s,cfg.get("min_cluster",2))
    ol=cfg.get("outline","none")
    if ol in ("ink","all"):
        q=add_edges(q,a_s,pal,cfg.get("edge_thresh",60),cfg.get("edge_darken",0.55))
    if ol in ("dark","selout","all"):
        sil="selout" if ol=="selout" else "dark"
        q,a_s=add_outline(q,a_s,sil,cfg.get("darken",0.45))
    out=Image.fromarray(q,"RGB").convert("RGBA")
    out.putalpha(finish_alpha(a_s,"binary" if cfg.get("removebg",True) else "keep",cfg.get("athresh",128)))
    return out,size,pal

def upscale(img,target_long=512):
    w,h=img.size; f=max(1,target_long//max(w,h))
    return img.resize((w*f,h*f),Image.NEAREST)
