#!/usr/bin/env python3
"""PixelPainter GUI - 파라미터를 슬라이더로 만지며 실시간 미리보기.

실행:
  pip install gradio        # 최초 1회
  python3 gui.py            # 브라우저에서 http://127.0.0.1:7860 열림

엔진은 pxcore.py 를 그대로 사용한다.
"""
import os
import sys

# PyInstaller(frozen) 대응: 번들 임시폴더를 import 경로에 추가
_BUNDLE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if _BUNDLE not in sys.path:
    sys.path.insert(0, _BUNDLE)

import numpy as np
from PIL import Image
import pxcore as P

# 출력/샘플 폴더: exe로 실행 시 exe 옆, 스크립트 실행 시 스크립트 옆
if getattr(sys, "frozen", False):
    APPDIR = os.path.dirname(sys.executable)
else:
    APPDIR = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(APPDIR, "out")

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
         colors, dither, bayer, strength, outline, darken, edge_thresh, edge_darken,
         cleanup, min_cluster):
    return dict(
        removebg=removebg, crop=crop, athresh=int(athresh),
        palette=palette, colors=int(colors),
        ramps=int(ramps), ramp_steps=int(ramp_steps),
        hue_shift=float(hue_shift), sat_boost=float(sat_boost),
        dither=dither, bayer=int(bayer), strength=float(strength),
        outline=outline, darken=float(darken),
        edge_thresh=float(edge_thresh), edge_darken=float(edge_darken),
        cleanup=cleanup, min_cluster=int(min_cluster),
    )


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


def render(img, res, preview_px, removebg, crop, athresh, palette, ramps, ramp_steps,
           hue_shift, sat_boost, colors, dither, bayer, strength, outline, darken,
           edge_thresh, edge_darken, cleanup, min_cluster):
    if img is None:
        return None, None, "이미지를 올려주세요 냥"
    arr = np.asarray(img.convert("RGB"))
    cfg = _cfg(removebg, crop, athresh, palette, ramps, ramp_steps, hue_shift,
               sat_boost, colors, dither, bayer, strength, outline, darken,
               edge_thresh, edge_darken, cleanup, min_cluster)
    out, size, pal = P.pixelate_rgb(arr, int(res), cfg)
    prev = P.upscale(out, int(preview_px))
    info = (f"출력 해상도: {size[0]}×{size[1]}  |  팔레트: {len(pal)}색  |  "
            f"팔레트모드: {palette}  |  디더: {dither}(b{bayer}, {strength:g})")
    return prev, _palette_strip(pal), info


def save_png(img, res, preview_px, removebg, crop, athresh, palette, ramps, ramp_steps,
             hue_shift, sat_boost, colors, dither, bayer, strength, outline, darken,
             edge_thresh, edge_darken, cleanup, min_cluster):
    if img is None:
        return "이미지가 없어요 냥"
    arr = np.asarray(img.convert("RGB"))
    cfg = _cfg(removebg, crop, athresh, palette, ramps, ramp_steps, hue_shift, sat_boost,
               colors, dither, bayer, strength, outline, darken, edge_thresh, edge_darken,
               cleanup, min_cluster)
    out, size, pal = P.pixelate_rgb(arr, int(res), cfg)
    os.makedirs(OUTDIR, exist_ok=True)
    tag = f"gui_{size[0]}x{size[1]}_{palette}_{dither}"
    raw = os.path.join(OUTDIR, tag + ".png")
    out.save(raw)
    P.upscale(out, 512).save(os.path.join(OUTDIR, tag + "_preview.png"))
    return f"저장됨: {raw}  ({size[0]}×{size[1]}, {len(pal)}색)"


_CSS = """
/* 스티키가 붙으려면 조상 요소가 스크롤 컨테이너를 만들지 않아야 한다 */
.gradio-container, .main, .contain, .app, .fillable { overflow: visible !important; }
#mainrow { align-items: flex-start !important; }
#rightcol { position: sticky !important; top: 8px; align-self: flex-start; }
"""

def build_app():
    import gradio as gr
    here = APPDIR
    samples = [os.path.join(here, f) for f in
               ["kkami coin.png", "kkami ui 8.png", "kkami_face_love.png", "kkami_full.png"]
               if os.path.exists(os.path.join(here, f))]

    with gr.Blocks(title="PixelPainter") as app:
        gr.Markdown("## 🎨 PixelPainter — 픽셀아트 변환 파라미터 패널\n"
                    "슬라이더를 움직이면 오른쪽 미리보기가 실시간 갱신됩니다.")
        with gr.Row(elem_id="mainrow"):
            with gr.Column(scale=1, elem_id="leftcol"):
                img = gr.Image(type="pil", label="입력 이미지", height=240)
                if samples:
                    gr.Examples(samples, inputs=img, label="샘플")
                preset = gr.Dropdown(list(PRESETS.keys()), label="프리셋 (선택 시 값 자동 채움)")
                with gr.Accordion("기본", open=True):
                    res = gr.Slider(16, 320, value=128, step=1, label="해상도(긴 변 px)")
                    preview_px = gr.Slider(128, 768, value=512, step=32, label="미리보기 확대 px")
                with gr.Accordion("배경 / 크롭", open=False):
                    removebg = gr.Checkbox(True, label="배경 제거 (투명 스프라이트)")
                    crop = gr.Checkbox(True, label="콘텐츠 크롭")
                    athresh = gr.Slider(0, 255, value=128, step=1, label="알파 임계값(글로우 억제↑)")
                with gr.Accordion("팔레트", open=True):
                    palette = gr.Radio(["ramp", "median"], value="ramp", label="팔레트 모드")
                    ramps = gr.Slider(2, 16, value=8, step=1, label="램프 개수(베이스색)")
                    ramp_steps = gr.Slider(2, 8, value=5, step=1, label="램프 단계(명암 계단)")
                    hue_shift = gr.Slider(0, 40, value=18, step=1, label="휴 시프트(°)")
                    sat_boost = gr.Slider(0.8, 1.5, value=1.15, step=0.05, label="채도 부스트")
                    colors = gr.Slider(4, 64, value=32, step=1, label="색 수 (median 모드)")
                with gr.Accordion("디더링", open=True):
                    dither = gr.Radio(["none", "ordered", "floyd"], value="ordered", label="디더 방식")
                    bayer = gr.Radio([2, 4, 8], value=4, label="Bayer 행렬")
                    strength = gr.Slider(0, 2, value=1.0, step=0.1, label="디더 강도")
                with gr.Accordion("실험 (기본 OFF)", open=False):
                    outline = gr.Radio(["none", "dark", "selout", "ink", "all"], value="none", label="아웃라인")
                    darken = gr.Slider(0, 1, value=0.45, step=0.05, label="실루엣 어둡기")
                    edge_thresh = gr.Slider(10, 150, value=60, step=1, label="ink 엣지 감도")
                    edge_darken = gr.Slider(0, 1, value=0.55, step=0.05, label="ink 어둡기")
                    cleanup = gr.Checkbox(False, label="라인 클린업")
                    min_cluster = gr.Slider(1, 6, value=2, step=1, label="최소 클러스터")
            with gr.Column(scale=1, elem_id="rightcol"):
                preview = gr.Image(label="미리보기 (nearest 확대)", height=420)
                pal_img = gr.Image(label="팔레트", height=40)
                info = gr.Markdown()
                save_btn = gr.Button("💾 PNG 저장 (out/ 폴더)", variant="primary")
                saved = gr.Markdown()

        controls = [res, preview_px, removebg, crop, athresh, palette, ramps, ramp_steps,
                    hue_shift, sat_boost, colors, dither, bayer, strength, outline, darken,
                    edge_thresh, edge_darken, cleanup, min_cluster]
        outputs = [preview, pal_img, info]

        for c in [img] + controls:
            ev = c.release if isinstance(c, gr.Slider) else c.change
            ev(render, [img] + controls, outputs)

        def apply_preset(name):
            p = PRESETS.get(name)
            keys = ["res", "removebg", "crop", "athresh", "palette", "ramps",
                    "ramp_steps", "hue_shift", "sat_boost", "colors", "dither",
                    "bayer", "strength"]
            if not p:
                return [gr.update() for _ in keys]
            return [gr.update(value=p[k]) for k in keys]

        preset.change(apply_preset, preset,
                      [res, removebg, crop, athresh, palette, ramps, ramp_steps,
                       hue_shift, sat_boost, colors, dither, bayer, strength]).then(
                      render, [img] + controls, outputs)

        save_btn.click(save_png, [img] + controls, saved)
    return app


if __name__ == "__main__":
    build_app().launch(inbrowser=True, css=_CSS)
