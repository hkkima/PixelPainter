import base64, pathlib, os
_HERE = pathlib.Path(__file__).resolve().parent

pxcore = (_HERE.parent / "pxcore.py").read_text(encoding="utf-8")
b64 = base64.b64encode(pxcore.encode("utf-8")).decode("ascii")

# 앱 엔트리포인트 (HTML-안전: '<letter' 와 '&' 를 쓰지 않는다)
APP = '''
import base64
import numpy as np
from PIL import Image
exec(base64.b64decode(PXCORE_B64).decode("utf-8"), globals())
import gradio as gr

PRESETS = {
    "coin (아이콘)":    dict(res=64,  removebg=True,  crop=True,  athresh=170,
                            palette="ramp", ramps=7,  ramp_steps=5, hue_shift=18, sat_boost=1.15,
                            colors=32, dither="ordered", bayer=4, strength=1.0),
    "ui (버튼)":        dict(res=96,  removebg=True,  crop=True,  athresh=128,
                            palette="ramp", ramps=6,  ramp_steps=4, hue_shift=18, sat_boost=1.15,
                            colors=24, dither="ordered", bayer=4, strength=1.0),
    "character (투명)": dict(res=128, removebg=True,  crop=True,  athresh=128,
                            palette="ramp", ramps=8,  ramp_steps=5, hue_shift=18, sat_boost=1.15,
                            colors=40, dither="ordered", bayer=4, strength=1.0),
    "full (배경 포함)": dict(res=200, removebg=False, crop=False, athresh=128,
                            palette="ramp", ramps=10, ramp_steps=6, hue_shift=18, sat_boost=1.15,
                            colors=60, dither="ordered", bayer=4, strength=1.0),
}

def _cfg(removebg, crop, athresh, palette, ramps, ramp_steps, hue_shift, sat_boost,
         colors, dither, bayer, strength):
    return dict(removebg=removebg, crop=crop, athresh=int(athresh),
                palette=palette, colors=int(colors), ramps=int(ramps),
                ramp_steps=int(ramp_steps), hue_shift=float(hue_shift),
                sat_boost=float(sat_boost), dither=dither, bayer=int(bayer),
                strength=float(strength), outline="none", darken=0.45,
                edge_thresh=60, edge_darken=0.55, cleanup=False, min_cluster=2)

def _palette_strip(pal, width=320, h=28):
    n = len(pal)
    if n == 0:
        return Image.new("RGB", (width, h), (240, 240, 240))
    sw = max(1, width // n)
    img = Image.new("RGB", (sw * n, h), (255, 255, 255))
    px = img.load()
    for i, c in enumerate(pal.astype(int)):
        col = tuple(int(v) for v in c)
        for x in range(sw):
            for y in range(h):
                px[i * sw + x, y] = col
    return img.resize((width, h), Image.NEAREST)

def convert(img, res, preview_px, removebg, crop, athresh, palette, ramps, ramp_steps,
            hue_shift, sat_boost, colors, dither, bayer, strength):
    if img is None:
        return None, None, None, "이미지를 올려주세요 냥"
    arr = np.asarray(img.convert("RGB"))
    cfg = _cfg(removebg, crop, athresh, palette, ramps, ramp_steps, hue_shift,
               sat_boost, colors, dither, bayer, strength)
    out, size, pal = pixelate_rgb(arr, int(res), cfg)
    prev = upscale(out, int(preview_px))
    info = "출력 " + str(size[0]) + "x" + str(size[1]) + "  |  팔레트 " + str(len(pal)) + "색  |  " + palette + " / " + dither
    return prev, out, _palette_strip(pal), info

def apply_preset(name):
    p = PRESETS.get(name)
    keys = ["res", "removebg", "crop", "athresh", "palette", "ramps",
            "ramp_steps", "hue_shift", "sat_boost", "colors", "dither",
            "bayer", "strength"]
    if not p:
        return [gr.update() for _ in keys]
    return [gr.update(value=p[k]) for k in keys]

with gr.Blocks(title="PixelPainter") as demo:
    gr.Markdown("## PixelPainter (Web) — 픽셀아트 변환\\n브라우저에서 바로 돌아갑니다. 이미지를 올리고 슬라이더를 움직여 보세요.")
    with gr.Row(elem_id="mainrow"):
        with gr.Column(scale=1, elem_id="leftcol"):
            img = gr.Image(type="pil", label="입력 이미지", height=240)
            preset = gr.Dropdown(list(PRESETS.keys()), label="프리셋 (선택 시 값 자동 채움)")
            with gr.Accordion("기본", open=True):
                res = gr.Slider(16, 320, value=128, step=1, label="해상도(긴 변 px)")
                preview_px = gr.Slider(128, 768, value=512, step=32, label="미리보기 확대 px")
            with gr.Accordion("배경 / 크롭", open=False):
                removebg = gr.Checkbox(True, label="배경 제거 (투명 스프라이트)")
                crop = gr.Checkbox(True, label="콘텐츠 크롭")
                athresh = gr.Slider(0, 255, value=128, step=1, label="알파 임계값(글로우 억제 up)")
            with gr.Accordion("팔레트", open=True):
                palette = gr.Radio(["ramp", "median"], value="ramp", label="팔레트 모드")
                ramps = gr.Slider(2, 16, value=8, step=1, label="램프 개수")
                ramp_steps = gr.Slider(2, 8, value=5, step=1, label="램프 단계")
                hue_shift = gr.Slider(0, 40, value=18, step=1, label="휴 시프트(도)")
                sat_boost = gr.Slider(0.8, 1.5, value=1.15, step=0.05, label="채도 부스트")
                colors = gr.Slider(4, 64, value=32, step=1, label="색 수 (median 모드)")
            with gr.Accordion("디더링", open=True):
                dither = gr.Radio(["none", "ordered", "floyd"], value="ordered", label="디더 방식")
                bayer = gr.Radio([2, 4, 8], value=4, label="Bayer 행렬")
                strength = gr.Slider(0, 2, value=1.0, step=0.1, label="디더 강도")
        with gr.Column(scale=1, elem_id="rightcol"):
            preview = gr.Image(label="미리보기 (nearest 확대)", height=380)
            pixel = gr.Image(label="실물 해상도 PNG (다운로드 아이콘 클릭)", height=160)
            pal_img = gr.Image(label="팔레트", height=40)
            info = gr.Markdown()

    controls = [res, preview_px, removebg, crop, athresh, palette, ramps, ramp_steps,
                hue_shift, sat_boost, colors, dither, bayer, strength]
    outputs = [preview, pixel, pal_img, info]
    for c in [img] + controls:
        ev = c.release if isinstance(c, gr.Slider) else c.change
        ev(convert, [img] + controls, outputs)
    preset.change(apply_preset, preset,
                  [res, removebg, crop, athresh, palette, ramps, ramp_steps,
                   hue_shift, sat_boost, colors, dither, bayer, strength]).then(
                  convert, [img] + controls, outputs)

demo.launch()
'''

HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>PixelPainter</title>
<script type="module" src="https://cdn.jsdelivr.net/npm/@gradio/lite/dist/lite.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@gradio/lite/dist/lite.css" />
<style>
  body { margin: 0; }
  .gradio-container, .main, .contain, .app, .fillable { overflow: visible !important; }
  #mainrow { align-items: flex-start !important; }
  #rightcol { position: sticky !important; top: 8px; align-self: flex-start; }
  #loading { font-family: sans-serif; padding: 24px; color: #555; }
</style>
</head>
<body>
<div id="loading">PixelPainter 로딩 중… (첫 실행은 Python 런타임 다운로드로 20~40초 걸릴 수 있어요)</div>
<gradio-lite>
<gradio-requirements>
numpy
scipy
pillow
</gradio-requirements>
__APP__
</gradio-lite>
<script>
  // gradio-lite가 마운트되면 로딩 문구 제거
  const _obs = new MutationObserver(() => {
    if (document.querySelector('gradio-lite .gradio-container')) {
      const el = document.getElementById('loading'); if (el) el.remove();
    }
  });
  _obs.observe(document.body, {childList:true, subtree:true});
</script>
</body>
</html>
"""

app_with_b64 = 'PXCORE_B64 = "' + b64 + '"\n' + APP
out = HTML.replace("__APP__", app_with_b64)
(_HERE / "index.html").write_text(out, encoding="utf-8")
print("index.html 생성:", len(out), "bytes | base64 pxcore:", len(b64), "chars")
# 앱 코드 HTML-안전성 재확인
import re
risky = re.findall(r'<[A-Za-z/!?]', APP)
print("APP '<letter' 위험 패턴:", risky if risky else "없음(안전)")
print("APP '&' 개수:", APP.count("&"))
