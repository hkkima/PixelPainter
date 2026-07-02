#!/usr/bin/env python3
"""pixelate.py - 픽셀아트 변환 CLI v3 (엔진: pxcore.py)

단계별 토글:
  배경제거(--nobg로 끄기) / 크롭(--nocrop) / 팔레트(median|ramp) /
  디더링(none|ordered|floyd) / 라인클린업(--cleanup) / 아웃라인(none|dark|selout)

예)
  # 램프 팔레트 + 오더드 디더링(기본)
  python3 pixelate.py "kkami coin.png" --res 64 --athresh 170 --outdir out
  # 배경 있는 풀 일러스트
  python3 pixelate.py kkami_full.png --res 200 --nobg --nocrop --outdir out
  # 아웃라인/클린업 추가
  python3 pixelate.py "kkami coin.png" --res 64 --outline selout --cleanup --outdir out
"""
import argparse, os
import pxcore as P


def build_cfg(a):
    return dict(
        removebg=not a.nobg, crop=not a.nocrop,
        light=a.light, sat=a.sat, athresh=a.athresh,
        palette=a.palette, colors=a.colors,
        ramps=a.ramps, ramp_steps=a.ramp_steps,
        hue_shift=a.hue_shift, sat_boost=a.sat_boost,
        dither=a.dither, bayer=a.bayer, strength=a.strength,
        cleanup=a.cleanup, min_cluster=a.min_cluster,
        outline=a.outline, darken=a.darken,
        edge_thresh=a.edge_thresh, edge_darken=a.edge_darken,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--res", type=int, required=True, help="긴 변 목표 픽셀")
    # 배경/크롭
    ap.add_argument("--nobg", action="store_true", help="배경 제거 끄기(풀 일러스트)")
    ap.add_argument("--nocrop", action="store_true")
    ap.add_argument("--light", type=int, default=190)
    ap.add_argument("--sat", type=int, default=28)
    ap.add_argument("--athresh", type=int, default=128)
    # 팔레트
    ap.add_argument("--palette", choices=["median", "ramp"], default="ramp")
    ap.add_argument("--colors", type=int, default=32, help="median 색수")
    ap.add_argument("--ramps", type=int, default=8, help="램프(베이스색) 개수")
    ap.add_argument("--ramp-steps", type=int, default=5, dest="ramp_steps")
    ap.add_argument("--hue-shift", type=float, default=18.0, dest="hue_shift")
    ap.add_argument("--sat-boost", type=float, default=1.15, dest="sat_boost")
    # 디더링
    ap.add_argument("--dither", choices=["none", "ordered", "floyd"], default="ordered")
    ap.add_argument("--bayer", type=int, choices=[2, 4, 8], default=4)
    ap.add_argument("--strength", type=float, default=1.0, help="디더 강도")
    # 라인클린업
    ap.add_argument("--cleanup", action="store_true")
    ap.add_argument("--min-cluster", type=int, default=2, dest="min_cluster")
    # 아웃라인
    ap.add_argument("--outline", choices=["none", "dark", "selout", "ink", "all"], default="none",
                    help="none|dark(실루엣)|selout(실루엣 명암차)|ink(내부경계)|all")
    ap.add_argument("--darken", type=float, default=0.45, help="실루엣 아웃라인 어둡기")
    ap.add_argument("--edge-thresh", type=float, default=60.0, dest="edge_thresh", help="ink 엣지 감도(낮을수록 촘촘)")
    ap.add_argument("--edge-darken", type=float, default=0.55, dest="edge_darken", help="ink 어둡기")
    # 출력
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--preview", type=int, default=512)
    a = ap.parse_args()

    cfg = build_cfg(a)
    out, size, pal = P.pixelate(a.input, a.res, cfg)
    base = os.path.splitext(os.path.basename(a.input))[0].replace(" ", "_")
    tag = "%s_%dx%d_%s_%s" % (base, size[0], size[1], a.palette, a.dither)
    os.makedirs(a.outdir, exist_ok=True)
    out.save(os.path.join(a.outdir, tag + ".png"))
    P.upscale(out, a.preview).save(os.path.join(a.outdir, tag + "_preview.png"))
    print(tag, size, "palette:", len(pal), "colors")


if __name__ == "__main__":
    main()
