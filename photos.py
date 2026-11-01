"""카드 배경 사진을 Wikimedia Commons에서 자유 라이선스 사진만 골라 받는다.

python photos.py slides/2026-10-23

사진 사다리 (2026-11-01 구의림 지시: «맞는 사진이 없으면 비우지 말고 써도 되는 가장 가까운 사진으로 채운다»)
  1 표지: 기사 회사 제공 사진(og:image, «Source: 회사»일 때만)
  2 "photo_query": 기사 속 그 로봇·제품·장소          → «사진 작가 · 라이선스»
  3 "photo_scene": 같은 장면(창고, 조립 라인, 주방 등)  → «참고 사진 · 작가 · 라이선스»
  4 주제 기본 장면 TOPIC_SCENES[meta.topic]             → «참고 사진 · …»
  5 그래도 없으면 글만
각 칸은 Wikimedia Commons → Openverse 순으로 찾는다. 자유 라이선스(CC0·BY·BY-SA·퍼블릭 도메인)만 받는다.
한 캐러셀 안에서 같은 사진은 두 번 쓰지 않는다. 마지막 카드(마무리)는 채우지 않는다.
"""
import hashlib, io, json, os, re, sys, urllib.parse
from collect import get, strip

API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/?license=by,by-sa,cc0,pdm&page_size=20&q="  # form-judge/tools/fetch_photos.py와 같은 필터
TOPIC_SCENES = {  # 루틴이 photo_scene을 빠뜨렸을 때의 주제 기본 장면 (check.py META topic과 같은 이름). 카드마다 돌려 쓴다
    # 사람 얼굴이 주인공이 되기 쉬운 검색어(barista, chef, worker)와 엉뚱한 로봇(NASA rover)이 나오는 'robotics laboratory'는 뺐다 (2026-11-01 시험)
    "휴머노이드": ["humanoid robot", "robot hand", "industrial robot arm", "robot exhibition booth"],
    "모델·소프트웨어": ["industrial robot arm", "robot hand", "server room", "circuit board"],
    "투자·상장": ["industrial robot arm factory", "stock exchange building", "warehouse robot", "factory production line"],
    "공장·물류 도입": ["warehouse robot", "industrial robot assembly line", "warehouse shelves", "factory production line"],
    "자영업·중소기업": ["restaurant kitchen interior", "serving robot restaurant", "commercial kitchen equipment", "cafe interior"],
    "기타": ["industrial robot arm", "robot hand", "factory production line", "warehouse robot"],
}
STOCK_WORDS = re.compile(r"getty|shutterstock|reuters|alamy|bloomberg|associated press", re.I)
FREE = re.compile(r"^(CC0|CC BY(-SA)? [\d.]+|Public domain)", re.I)


def wikimedia(query):
    q = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
        "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiurlwidth": 1600})
    pages = json.loads(get(f"{API}?{q}")).get("query", {}).get("pages", {})
    for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        ii = p["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "")
        if not FREE.match(lic) or ii["width"] < 1000:
            continue
        artist = strip(meta.get("Artist", {}).get("value", ""))[:40] or "Wikimedia Commons"
        yield ii["thumburl"], artist, lic


def openverse(query):
    for r in json.loads(get(OPENVERSE + urllib.parse.quote(query))).get("results", []):
        if (r.get("width") or 0) < 1000 or STOCK_WORDS.search(f'{r.get("creator")} {r.get("source")}'):
            continue
        lic = r["license"].upper() if r["license"] in ("cc0", "pdm") else f'CC {r["license"].upper()} {r.get("license_version") or ""}'.strip()
        yield r["url"], (r.get("creator") or "Openverse")[:40], lic


def candidates(query, used=(), n=6):
    """한 검색어로 자유 라이선스 후보 여러 장. [(url, «작가 · 라이선스»)]"""
    out = []
    for source in (wikimedia, openverse):
        try:
            for url, artist, lic in source(query):
                if url not in used and url not in [u for u, _ in out]:
                    out.append((url, f"{artist} · {lic}"))
                if len(out) >= n:
                    return out
        except Exception as e:
            print(f"  {source.__name__} '{query}' 검색 실패: {e}")
    return out


def find(query, used=()):
    """자유 라이선스 사진 하나. used에 있는 주소는 건너뛴다. 반환 (url, «작가 · 라이선스») 또는 (None, None)."""
    for source in (wikimedia, openverse):
        try:
            for url, artist, lic in source(query):
                if url not in used:
                    return url, f"{artist} · {lic}"
        except Exception as e:
            print(f"  {source.__name__} '{query}' 검색 실패: {e}")
    return None, None


STOCK = re.compile(r"getty|shutterstock|associated press|\bAP\b|reuters|alamy|bloomberg", re.I)


def press(day, post):
    """기사 대표 사진(og:image)을 표지에 쓴다. 단, 원문이 «Source: <회사>»로 밝힌 회사 제공 사진일 때만.
    게티·AP·로이터 같은 통신사·스톡 사진은 쓰지 않는다. config.json의 press_photo가 true일 때만 돈다."""
    src = io.open(os.path.join(day, "source.txt"), encoding="utf-8").read()
    page = get(post["source"]["url"]).decode("utf-8", "replace")
    # 사진 출처 표기: The Robot Report는 «| Source: 회사», TechCrunch는 «Image Credits: 회사»
    m = re.search(r"\|\s*Source:\s*([^\n|]{2,40})", src) \
        or re.search(r"Image Credits:?\s*(?:</[^>]+>\s*)*([^<]{2,40})", page)
    if not m or STOCK.search(m.group(1)):
        return print("표지: 회사 제공 사진 표기가 없거나 통신사·스톡 사진 → 건너뜀")
    og = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page) \
        or re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', page)
    if not og or STOCK.search(og.group(1)):
        return print("표지: 대표 사진 없음 또는 스톡 사진 → 건너뜀")
    url = og.group(1).replace("&amp;", "&")
    name = f"photos/{hashlib.md5(url.encode()).hexdigest()[:10]}.jpg"
    with open(os.path.join(day, name), "wb") as f:
        f.write(get(url))
    post["cards"][0]["photo"], post["cards"][0]["credit"] = name, f"사진 {m.group(1).strip()}"
    print(f"표지: 회사 제공 사진 ({m.group(1).strip()})")


COVER_N = 6  # 표지 후보 수


def cover_candidates(day, post):
    """표지 후보 6장을 받고 cover_cands.jpg(번호 붙은 대조표)를 만든다. 기본은 1번.
    표지 기준(2026-11-01 구의림 확정): 목표는 넘기던 손을 멈추게 하는 것.
      ✔ 주인공 하나, 일하는 동작  ✔ 제목이 던진 질문의 «장면»  ✔ 사진이 화면 60% 이상 보임(render.py가 위 62%에 깐다)
      우선: 기사 회사 사진 → 같은 일을 하는 장면(사람 손·장비 포함 가능)
      ✘ 건물 외관, 빈 공간, 흐린 배경
    검색 순위로 고르지 않는다. 루틴이 대조표를 보고 기준에 맞는 번호를 `python photos.py D --cover K`로 고른다."""
    from PIL import Image, ImageDraw
    c1 = post["cards"][0]
    pool = []
    for q, label in ((c1.get("photo_query"), "사진"), (c1.get("photo_cover"), "참고 사진"), (c1.get("photo_scene"), "참고 사진")):
        if q and len(pool) < COVER_N:
            pool += [(u, f"{label} {c}", q) for u, c in candidates(q, [u for u, _, _ in pool], COVER_N - len(pool))]
    got, seen = [], set()
    for url, credit, q in pool:
        name = f"photos/cover_{hashlib.md5(url.encode()).hexdigest()[:10]}.jpg"
        try:
            if not os.path.exists(os.path.join(day, name)):
                data = get(url)
                with open(os.path.join(day, name), "wb") as f:
                    f.write(data)
            Image.open(os.path.join(day, name)).verify()
            h = hashlib.md5(open(os.path.join(day, name), "rb").read()).hexdigest()
            if h in seen:  # Wikimedia·Openverse에 같은 사진이 둘 다 있으면 한 번만
                continue
            seen.add(h)
            got.append({"photo": name, "credit": credit, "query": q})
        except Exception as e:
            print(f"  표지 후보 받기 실패({e})")
    post["cover_candidates"] = got
    if not got:
        return print("표지: 후보 없음 → 글만")
    w, h = 360, 288
    sheet = Image.new("RGB", (3 * w + 40, ((len(got) + 2) // 3) * (h + 40) + 10), "#e8e8ed")
    d = ImageDraw.Draw(sheet)
    for k, g in enumerate(got):
        im = Image.open(os.path.join(day, g["photo"])).convert("RGB")
        im = im.resize((w, int(im.height * w / im.width))) if im.width else im
        x, y = 10 + (k % 3) * (w + 10), 10 + (k // 3) * (h + 40)
        sheet.paste(im.crop((0, 0, w, min(h, im.height))), (x, y))
        d.text((x + 6, y + h + 6), f"{k + 1}  {g['query'][:30]}", fill="#1d1d1f")
    sheet.save(os.path.join(day, "cover_cands.jpg"), quality=88)
    pick_cover(day, post, 1)
    print(f"표지 후보 {len(got)}장 → {os.path.join(day, 'cover_cands.jpg')} (기본 1번)")


def pick_cover(day, post, k):
    g = post["cover_candidates"][k - 1]
    post["cards"][0]["photo"], post["cards"][0]["credit"] = g["photo"], g["credit"]
    post.setdefault("meta", {})["photo_cover"] = True


def main(day):
    path = os.path.join(day, "post.json")
    post = json.load(io.open(path, encoding="utf-8"))
    os.makedirs(os.path.join(day, "photos"), exist_ok=True)
    cfg = json.load(io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))
    if cfg.get("press_photo") and not post["cards"][0].get("photo"):
        try:
            press(day, post)
        except Exception as e:
            print(f"표지 사진 실패: {e}")
    if not post["cards"][0].get("photo"):
        cover_candidates(day, post)
    used = {c.get("photo") for c in post["cards"]}  # (파일 이름 — 주소 중복은 아래 used.add로 막는다)
    topic = post.get("meta", {}).get("topic", "기타")
    last = len(post["cards"])
    for i, card in enumerate(post["cards"], 1):
        if card.get("photo") or i == last or i == 1:  # 이미 있거나, 마무리 카드, 표지(위에서 따로 고름)
            continue
        ladder = [(card.get("photo_query"), "사진"), (card.get("photo_scene"), "참고 사진")]
        scenes = TOPIC_SCENES.get(topic, TOPIC_SCENES["기타"])
        ladder += [(scenes[(i - 1 + k) % len(scenes)], "참고 사진") for k in range(len(scenes))]  # 카드마다 다른 장면부터
        name = None
        for q, label in ladder:
            if not q:
                continue
            for _ in range(3):  # 받기가 막힌 사진(403 등)은 건너뛰고 다음 후보
                url, credit = find(q, used)
                if not url:
                    break
                used.add(url)
                name = f"photos/{hashlib.md5(url.encode()).hexdigest()[:10]}.jpg"
                try:
                    if not os.path.exists(os.path.join(day, name)):
                        data = get(url)
                        with open(os.path.join(day, name), "wb") as f:
                            f.write(data)
                    break
                except Exception as e:
                    print(f"  받기 실패({e}) → 다음 후보")
                    name = None
            if name:
                break
        if not name:
            print(f"{i}번: 자유 라이선스 사진 없음 → 글만")
            continue
        card["photo"], card["credit"] = name, f"{label} {credit}"
        print(f"{i}번 '{q}': {label} {credit}")
    n = sum(1 for c in post["cards"] if c.get("photo"))
    print(f"사진 {n}/{last}장")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)


def choose(day, k):
    path = os.path.join(day, "post.json")
    post = json.load(io.open(path, encoding="utf-8"))
    pick_cover(day, post, k)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)
    print(f"표지: {k}번 {post['cards'][0]['credit']}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--cover" in sys.argv:  # python photos.py D --cover K
        choose(sys.argv[1], int(sys.argv[sys.argv.index("--cover") + 1]))
    else:
        main(sys.argv[1])
