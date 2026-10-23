"""카드 배경 사진을 Wikimedia Commons에서 자유 라이선스 사진만 골라 받는다.

python photos.py slides/2026-10-23

post.json의 카드마다 "photo_query"(영어 검색어)가 있으면 사진을 받아 "photo"·"credit"을 채운다.
맞는 사진이 없으면 비워 둔다 — 그 카드는 사진 대신 숫자 외곽선 배경으로 나간다(기자단 EP04와 같은 방식).
"""
import hashlib, io, json, os, re, sys, urllib.parse
from collect import get, strip

API = "https://commons.wikimedia.org/w/api.php"
FREE = re.compile(r"^(CC0|CC BY(-SA)? [\d.]+|Public domain)", re.I)


def find(query):
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
        return ii["thumburl"], f"사진 {artist} · {lic}"
    return None, None


STOCK = re.compile(r"getty|shutterstock|associated press|\bAP\b|reuters|alamy|bloomberg", re.I)


def press(day, post):
    """기사 대표 사진(og:image)을 표지에 쓴다. 단, 원문이 «Source: <회사>»로 밝힌 회사 제공 사진일 때만.
    게티·AP·로이터 같은 통신사·스톡 사진은 쓰지 않는다. config.json의 press_photo가 true일 때만 돈다."""
    src = io.open(os.path.join(day, "source.txt"), encoding="utf-8").read()
    m = re.search(r"\|\s*Source:\s*([^\n|]{2,40})", src)
    if not m or STOCK.search(m.group(1)):
        return print("표지: 회사 제공 사진 표기가 없거나 통신사·스톡 사진 → 건너뜀")
    page = get(post["source"]["url"]).decode("utf-8", "replace")
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
    cache = {}
    for i, card in enumerate(post["cards"], 1):
        q = card.get("photo_query")
        if not q or card.get("photo"):
            continue
        if q not in cache:
            try:
                cache[q] = find(q)
            except Exception as e:
                print(f"{i}번 검색 실패: {e}")
                cache[q] = (None, None)
        url, credit = cache[q]
        if not url:
            print(f"{i}번 '{q}': 자유 라이선스 사진 없음 → 외곽선 배경")
            continue
        name = f"photos/{hashlib.md5(url.encode()).hexdigest()[:10]}.jpg"
        if not os.path.exists(os.path.join(day, name)):
            with open(os.path.join(day, name), "wb") as f:
                f.write(get(url))
        card["photo"], card["credit"] = name, credit
        print(f"{i}번 '{q}': {credit}")
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(post, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
