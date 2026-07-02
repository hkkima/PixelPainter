# PixelPainter (Web)

이미지를 진짜 픽셀아트로 변환하는 **서버 없는 웹앱**. 브라우저 안에서 Python
(Pyodide + numpy/scipy/Pillow)으로 우리 변환 엔진을 그대로 돌린다. GitHub Pages 같은
정적 호스팅에 그대로 올릴 수 있다.

- 단일 파일 `index.html` 로 완결 (엔진은 base64로 내장, 별도 파일 불필요)
- 첫 실행은 Python 런타임을 내려받느라 **20~40초** 걸릴 수 있음(이후 캐시로 빨라짐)
- 슬라이더를 움직이면 실시간으로 변환, 결과 이미지는 다운로드 아이콘으로 저장

## GitHub Pages 로 올리기 (5분)

1. GitHub 에서 새 저장소(repository)를 만든다. 예: `pixelpainter` (Public).
2. 이 폴더의 `index.html` 을 저장소 **루트에 업로드**한다.
   - 웹 UI: 저장소 → **Add file → Upload files** → `index.html` 끌어다 놓기 → **Commit**.
   - 또는 git: `git add index.html && git commit -m "add app" && git push`.
3. 저장소 → **Settings → Pages** 로 이동.
4. **Build and deployment → Source** 를 **Deploy from a branch** 로 두고,
   **Branch** 를 `main` / `/ (root)` 로 선택 → **Save**.
5. 1~2분 뒤 상단에 표시되는 주소(`https://<아이디>.github.io/pixelpainter/`)로 접속.

> 루트가 지저분한 게 싫으면 `index.html` 을 `docs/` 폴더에 넣고, Pages Source 의
> 폴더를 `/docs` 로 지정해도 된다.

## 커스텀 도메인 / 다른 정적 호스트

Netlify, Cloudflare Pages, Vercel(정적) 등 어디든 `index.html` 하나만 올리면 동일하게
동작한다. 서버가 필요 없다.

## 참고

- 엔진 원본은 상위 폴더의 `pxcore.py`. 엔진을 고치면
  `python build_web.py` 로 `index.html` 을 다시 생성한다(빌더 스크립트 참고).
- 무거운 첫 로딩이 부담이면, 순수 JavaScript/Canvas 재작성 버전으로 바꾸면 즉시 로딩이
  가능하다(엔진을 통째로 JS로 옮기는 작업 필요).
- 아웃라인/라인클린업은 데스크톱 버전과 동일하게 기본 비활성(결과 부진).

## 한계

- Pyodide 특성상 초기 로딩이 느리고, `floyd` 디더는 브라우저에서 특히 느리다
  (`ordered` 권장).
- 아주 큰 해상도(수백 px) + 캐릭터/풀 일러스트는 브라우저에서 변환에 수 초 걸릴 수 있다.
