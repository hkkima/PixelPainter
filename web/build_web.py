import base64, pathlib, re
_HERE = pathlib.Path(__file__).resolve().parent

pxcore = (_HERE.parent / "pxcore.py").read_text(encoding="utf-8")
b64 = base64.b64encode(pxcore.encode("utf-8")).decode("ascii")

# ---------------------------------------------------------------------------
# Pyodide 안에서 도는 파이썬 (gradio 없이 우리 엔진만). JS 가 run() 을 호출한다.
# HTML-안전: '</script' 를 쓰지 않는다. 나머지 '<' 는 <script> 안에서 안전.
# ---------------------------------------------------------------------------
PYCODE = '''
import base64, io, json
import numpy as np
from PIL import Image
exec(base64.b64decode(PXCORE_B64).decode("utf-8"), globals())

def _to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

def _cfg(d):
    return dict(
        removebg=bool(d["removebg"]), crop=bool(d["crop"]),
        athresh=int(d["athresh"]), palette=str(d["palette"]),
        colors=int(d["colors"]), ramps=int(d["ramps"]),
        ramp_steps=int(d["ramp_steps"]), hue_shift=float(d["hue_shift"]),
        sat_boost=float(d["sat_boost"]), dither=str(d["dither"]),
        bayer=int(d["bayer"]), strength=float(d["strength"]),
        outline="none", darken=0.45, edge_thresh=60, edge_darken=0.55,
        cleanup=False, min_cluster=2,
    )

def run(png_b64, cfg_json):
    d = json.loads(cfg_json)
    raw = base64.b64decode(png_b64)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    arr = np.asarray(im)
    out, size, pal = pixelate_rgb(arr, int(d["res"]), _cfg(d))
    prev = upscale(out, int(d["preview_px"]))
    palcols = [[int(v) for v in row] for row in np.asarray(pal).astype(int).tolist()]
    return json.dumps(dict(
        preview=_to_b64(prev), pixel=_to_b64(out),
        w=int(size[0]), h=int(size[1]), pal=palcols,
    ))
'''

HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>PixelPainter</title>
<style>
  :root { --bg:#0f1115; --panel:#171a21; --line:#262b36; --fg:#e6e8ee; --mut:#9aa3b2; --accent:#6ea8fe; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  header { padding:18px 22px; border-bottom:1px solid var(--line); }
  header h1 { margin:0; font-size:18px; }
  header p { margin:4px 0 0; color:var(--mut); font-size:13px; }
  .wrap { display:grid; grid-template-columns: 340px 1fr; gap:20px; padding:20px; align-items:start; }
  @media (max-width: 820px){ .wrap { grid-template-columns: 1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; }
  .right { position:sticky; top:16px; }
  fieldset { border:1px solid var(--line); border-radius:10px; margin:0 0 14px; padding:12px; }
  legend { color:var(--mut); font-size:12px; padding:0 6px; }
  label { display:block; font-size:13px; margin:10px 0 4px; }
  label:first-child { margin-top:0; }
  .row { display:flex; align-items:center; gap:10px; }
  .row output { color:var(--accent); font-variant-numeric: tabular-nums; min-width:44px; text-align:right; font-size:12px; }
  input[type=range]{ width:100%; accent-color:var(--accent); }
  select, input[type=file]{ width:100%; background:#0d0f14; color:var(--fg);
         border:1px solid var(--line); border-radius:8px; padding:8px; font-size:13px; }
  .checks label, .radios label { display:inline-flex; align-items:center; gap:6px; margin:6px 12px 0 0; font-size:13px; }
  .checks, .radios { display:flex; flex-wrap:wrap; }
  .imgbox { background:
      linear-gradient(45deg,#1b1f27 25%,transparent 25%),
      linear-gradient(-45deg,#1b1f27 25%,transparent 25%),
      linear-gradient(45deg,transparent 75%,#1b1f27 75%),
      linear-gradient(-45deg,transparent 75%,#1b1f27 75%);
      background-size:20px 20px; background-position:0 0,0 10px,10px -10px,-10px 0;
      border:1px solid var(--line); border-radius:10px; min-height:220px;
      display:flex; align-items:center; justify-content:center; overflow:hidden; }
  .imgbox img { image-rendering: pixelated; max-width:100%; max-height:460px; display:block; }
  #palette { display:flex; height:26px; border-radius:6px; overflow:hidden; border:1px solid var(--line); margin-top:10px; }
  #palette span { flex:1 1 auto; }
  #info { color:var(--mut); font-size:12px; margin-top:8px; }
  .btn { display:inline-block; margin-top:10px; background:var(--accent); color:#0b0d12;
         text-decoration:none; font-weight:600; font-size:13px; padding:9px 14px; border-radius:8px; }
  .btn[aria-disabled=true]{ opacity:.4; pointer-events:none; }
  #status { position:fixed; inset:0; background:rgba(10,12,16,.86); display:flex;
            align-items:center; justify-content:center; text-align:center; z-index:9; }
  #status.hidden{ display:none; }
  #status .box { max-width:420px; padding:24px; }
  .spin { width:34px; height:34px; border:3px solid var(--line); border-top-color:var(--accent);
          border-radius:50%; margin:0 auto 14px; animation:sp 1s linear infinite; }
  @keyframes sp { to { transform: rotate(360deg); } }
  small.mut { color:var(--mut); }
</style>
</head>
<body>
<header>
  <h1>PixelPainter — 픽셀아트 변환</h1>
  <p>브라우저 안에서 Python 엔진(numpy/scipy/Pillow)이 그대로 돕니다. 이미지를 올리고 값을 조절하세요.</p>
</header>

<div class="wrap">
  <div class="panel">
    <label>입력 이미지</label>
    <input type="file" id="file" accept="image/*" />
    <div class="imgbox" style="min-height:180px; margin-top:10px;">
      <img id="src" alt="" />
    </div>

    <label style="margin-top:14px;">프리셋</label>
    <select id="preset">
      <option value="">— 선택 —</option>
      <option value="coin">coin (아이콘)</option>
      <option value="ui">ui (버튼)</option>
      <option value="character">character (투명)</option>
      <option value="full">full (배경 포함)</option>
    </select>

    <fieldset style="margin-top:14px;">
      <legend>기본</legend>
      <label>해상도 (긴 변 px)</label>
      <div class="row"><input type="range" id="res" min="16" max="320" step="1" value="128"><output id="res_v"></output></div>
      <label>미리보기 확대 px</label>
      <div class="row"><input type="range" id="preview_px" min="128" max="768" step="32" value="512"><output id="preview_px_v"></output></div>
    </fieldset>

    <fieldset>
      <legend>배경 / 크롭</legend>
      <div class="checks">
        <label><input type="checkbox" id="removebg" checked> 배경 제거</label>
        <label><input type="checkbox" id="crop" checked> 콘텐츠 크롭</label>
      </div>
      <label>알파 임계값</label>
      <div class="row"><input type="range" id="athresh" min="0" max="255" step="1" value="128"><output id="athresh_v"></output></div>
    </fieldset>

    <fieldset>
      <legend>팔레트</legend>
      <div class="radios" id="palette">
        <label><input type="radio" name="palette" value="ramp" checked> ramp</label>
        <label><input type="radio" name="palette" value="median"> median</label>
      </div>
      <label>램프 개수</label>
      <div class="row"><input type="range" id="ramps" min="2" max="16" step="1" value="8"><output id="ramps_v"></output></div>
      <label>램프 단계</label>
      <div class="row"><input type="range" id="ramp_steps" min="2" max="8" step="1" value="5"><output id="ramp_steps_v"></output></div>
      <label>휴 시프트 (도)</label>
      <div class="row"><input type="range" id="hue_shift" min="0" max="40" step="1" value="18"><output id="hue_shift_v"></output></div>
      <label>채도 부스트</label>
      <div class="row"><input type="range" id="sat_boost" min="0.8" max="1.5" step="0.05" value="1.15"><output id="sat_boost_v"></output></div>
      <label>색 수 (median 모드)</label>
      <div class="row"><input type="range" id="colors" min="4" max="64" step="1" value="32"><output id="colors_v"></output></div>
    </fieldset>

    <fieldset>
      <legend>디더링</legend>
      <div class="radios" id="dither">
        <label><input type="radio" name="dither" value="none"> none</label>
        <label><input type="radio" name="dither" value="ordered" checked> ordered</label>
        <label><input type="radio" name="dither" value="floyd"> floyd</label>
      </div>
      <div class="radios" id="bayer" style="margin-top:8px;">
        <label><input type="radio" name="bayer" value="2"> 2</label>
        <label><input type="radio" name="bayer" value="4" checked> 4</label>
        <label><input type="radio" name="bayer" value="8"> 8</label>
      </div>
      <label>디더 강도</label>
      <div class="row"><input type="range" id="strength" min="0" max="2" step="0.1" value="1.0"><output id="strength_v"></output></div>
    </fieldset>
  </div>

  <div class="panel right">
    <label>미리보기 (nearest 확대)</label>
    <div class="imgbox"><img id="preview" alt="결과가 여기에 표시됩니다" /></div>
    <div id="palette_strip"></div>
    <div id="info">이미지를 올리면 변환됩니다.</div>
    <a id="download" class="btn" aria-disabled="true" download="pixelart.png" href="#">실물 해상도 PNG 다운로드</a>
    <div style="margin-top:8px;"><small class="mut">floyd 디더는 느립니다. ordered 권장.</small></div>
  </div>
</div>

<div id="status"><div class="box">
  <div class="spin"></div>
  <div id="status_msg">Python 런타임 불러오는 중…<br><small class="mut">첫 실행은 20~40초 걸릴 수 있어요 (이후 캐시로 빨라짐)</small></div>
</div></div>

<script id="pycode" type="text/python">__PYCODE__</script>
<script src="https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js"></script>
<script>
const PRESETS = {
  coin:      {res:64,  removebg:true,  crop:true,  athresh:170, palette:"ramp", ramps:7,  ramp_steps:5, hue_shift:18, sat_boost:1.15, colors:32, dither:"ordered", bayer:4, strength:1.0},
  ui:        {res:96,  removebg:true,  crop:true,  athresh:128, palette:"ramp", ramps:6,  ramp_steps:4, hue_shift:18, sat_boost:1.15, colors:24, dither:"ordered", bayer:4, strength:1.0},
  character: {res:128, removebg:true,  crop:true,  athresh:128, palette:"ramp", ramps:8,  ramp_steps:5, hue_shift:18, sat_boost:1.15, colors:40, dither:"ordered", bayer:4, strength:1.0},
  full:      {res:200, removebg:false, crop:false, athresh:128, palette:"ramp", ramps:10, ramp_steps:6, hue_shift:18, sat_boost:1.15, colors:60, dither:"ordered", bayer:4, strength:1.0},
};
const SLIDERS = ["res","preview_px","athresh","ramps","ramp_steps","hue_shift","sat_boost","colors","strength"];
const $ = (id) => document.getElementById(id);

let runFn = null;
let imgB64 = null;
let busy = false, pending = false;
let timer = null;

function syncOutputs(){
  for (const id of SLIDERS){ const o = $(id + "_v"); if (o) o.textContent = $(id).value; }
}
function radioVal(name){ const el = document.querySelector('input[name="'+name+'"]:checked'); return el ? el.value : null; }
function setRadio(name, val){ const el = document.querySelector('input[name="'+name+'"][value="'+val+'"]'); if (el) el.checked = true; }

function gatherCfg(){
  return {
    res:+$("res").value, preview_px:+$("preview_px").value,
    removebg:$("removebg").checked, crop:$("crop").checked, athresh:+$("athresh").value,
    palette:radioVal("palette"), ramps:+$("ramps").value, ramp_steps:+$("ramp_steps").value,
    hue_shift:+$("hue_shift").value, sat_boost:+$("sat_boost").value, colors:+$("colors").value,
    dither:radioVal("dither"), bayer:+radioVal("bayer"), strength:+$("strength").value,
  };
}

function applyPreset(name){
  const p = PRESETS[name]; if (!p) return;
  for (const k of ["res","athresh","ramps","ramp_steps","hue_shift","sat_boost","colors","strength"]) $(k).value = p[k];
  $("removebg").checked = p.removebg; $("crop").checked = p.crop;
  setRadio("palette", p.palette); setRadio("dither", p.dither); setRadio("bayer", String(p.bayer));
  syncOutputs();
  schedule();
}

function schedule(){ clearTimeout(timer); timer = setTimeout(convert, 180); }

async function convert(){
  if (!runFn || !imgB64){ return; }
  if (busy){ pending = true; return; }
  busy = true;
  $("info").textContent = "변환 중…";
  try {
    const res = runFn(imgB64, JSON.stringify(gatherCfg()));
    const r = JSON.parse(res);
    $("preview").src = "data:image/png;base64," + r.preview;
    const dl = $("download");
    dl.href = "data:image/png;base64," + r.pixel;
    dl.setAttribute("aria-disabled", "false");
    const strip = $("palette_strip");
    strip.id = "palette_strip";
    strip.innerHTML = '<div id="palette">' + r.pal.map(c =>
      '<span style="background:rgb('+c[0]+','+c[1]+','+c[2]+')"></span>').join("") + '</div>';
    $("info").textContent = "출력 " + r.w + "×" + r.h + "  |  팔레트 " + r.pal.length + "색  |  "
                          + radioVal("palette") + " / " + radioVal("dither");
  } catch (e){
    $("info").textContent = "변환 오류: " + e;
    console.error(e);
  }
  busy = false;
  if (pending){ pending = false; convert(); }
}

// 컨트롤 이벤트
for (const id of SLIDERS){ $(id).addEventListener("input", () => { syncOutputs(); schedule(); }); }
for (const id of ["removebg","crop"]) $(id).addEventListener("change", schedule);
for (const name of ["palette","dither","bayer"])
  document.querySelectorAll('input[name="'+name+'"]').forEach(el => el.addEventListener("change", schedule));
$("preset").addEventListener("change", (e) => applyPreset(e.target.value));

$("file").addEventListener("change", (e) => {
  const f = e.target.files[0]; if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    const url = reader.result;                 // data:image/...;base64,XXXX
    $("src").src = url;
    imgB64 = String(url).split(",")[1];
    convert();
  };
  reader.readAsDataURL(f);
});

// Pyodide 부팅
(async () => {
  try {
    syncOutputs();
    const pyodide = await loadPyodide();
    $("status_msg").innerHTML = '패키지 설치 중… (numpy · scipy · scikit-learn · Pillow)<br><small class="mut">잠시만요</small>';
    await pyodide.loadPackage(["numpy", "scipy", "scikit-learn", "Pillow"]);
    pyodide.runPython($("pycode").textContent);
    runFn = pyodide.globals.get("run");
    $("status").classList.add("hidden");
  } catch (e){
    $("status_msg").innerHTML = 'Python 런타임 로드 실패: ' + e;
    console.error(e);
  }
})();
</script>
</body>
</html>
"""

pycode_with_b64 = 'PXCORE_B64 = "' + b64 + '"\n' + PYCODE
out = HTML.replace("__PYCODE__", pycode_with_b64)
(_HERE / "index.html").write_text(out, encoding="utf-8")
print("index.html 생성:", len(out), "bytes | base64 pxcore:", len(b64), "chars")
# HTML-안전성 재확인: 파이썬 코드에 </script 가 없어야 한다
assert "</script" not in pycode_with_b64.lower(), "python code contains </script"
print("HTML-안전성 OK (</script 없음)")
