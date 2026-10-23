"""post.json → cards.html → card_NN.jpg (1080×1350, 인스타는 JPEG만 받는다).

python render.py slides/2026-10-23

카드 글자에는 <em>(노란 강조)과 <br>만 쓸 수 있다. 나머지 태그는 글자로 찍힌다.
글이 넘쳐 위쪽 태그·쪽수와 겹치면 overflow.txt에 적고 실패로 끝난다 — check.py가 이걸 본다.
"""
import html, io, json, os, re, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(io.open(os.path.join(HERE, "config.json"), encoding="utf-8"))
FONT = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"


def rich(s):
    s = html.escape(s or "")
    return re.sub(r"&lt;(/?em|br ?/?)&gt;", r"<\1>", s)


def card(c, i, n, no):
    bg = (f'<div class="bg" style="background-image:url({c["photo"]});background-position:{c.get("pos", "center")}"></div>'
          if c.get("photo") else "")  # 사진이 없으면 장식 없이 바탕색만 (외곽선 숫자 배경은 2026-10-23 본인 지시로 없앰)
    tag = f'<span class="tag">{html.escape(CFG["tag"])} {no}</span>' if i == 1 else ""
    sub = "".join(f'<p class="sub{" lead" if j == 0 and c.get("lead") else ""}">{rich(s)}</p>'
                  for j, s in enumerate(c.get("sub", [])))
    rows = "".join(f'<div class="row"><b>{rich(k)}</b><span>{rich(v)}</span></div>' for k, v in c.get("rows", []))
    return f"""<section class="card{'' if c.get('photo') else ' plain'}">{bg}<div class="shade"></div>
  <div class="body"><h1 class="{c.get('size', '')}">{rich(c['h1'])}</h1>{sub}{f'<div class="list">{rows}</div>' if rows else ''}</div>
  {tag}<span class="pill">{i}/{n}</span><div class="rule"></div>
  {f'<span class="pc">{html.escape(c["credit"])}</span>' if c.get("credit") else ''}
  <div class="credit">{html.escape(CFG["credit"])}</div></section>"""


def main(day):
    post = json.load(io.open(os.path.join(day, "post.json"), encoding="utf-8"))
    cards, n = post["cards"], len(post["cards"])
    css = io.open(os.path.join(HERE, "templates", "cards.css"), encoding="utf-8").read()
    css = css.replace("--accent:#F5C451", f"--accent:{CFG['accent']}")
    doc = (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><link rel="stylesheet" href="{FONT}">'
           f"<style>{css}</style></head><body>"
           + "".join(card(c, i, n, post.get("no", "")) for i, c in enumerate(cards, 1)) + "</body></html>")
    page_path = os.path.join(day, "cards.html")
    io.open(page_path, "w", encoding="utf-8", newline="\n").write(doc)

    for old in os.listdir(day):
        if re.match(r"card_\d+\.jpg$", old):
            os.remove(os.path.join(day, old))
    bad = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto("file:///" + os.path.abspath(page_path).replace("\\", "/"))
        pg.wait_for_load_state("networkidle")
        pg.evaluate("document.fonts.ready")
        for i, el in enumerate(pg.query_selector_all(".card"), 1):
            top = el.evaluate("c => c.querySelector('.body').getBoundingClientRect().top - c.getBoundingClientRect().top")
            if top < 150:  # 태그(78px)·쪽수(70px) 줄을 침범
                bad.append(f"{i}번 카드 글 넘침 (본문 시작 {top:.0f}px)")
            el.screenshot(path=os.path.join(day, f"card_{i:02d}.jpg"), type="jpeg", quality=92)
        b.close()
    ov = os.path.join(day, "overflow.txt")
    if bad:
        io.open(ov, "w", encoding="utf-8").write("\n".join(bad))
        sys.exit("\n".join(bad))
    if os.path.exists(ov):
        os.remove(ov)
    print(f"카드 {n}장 렌더링")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
