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


def main(day):
    path = os.path.join(day, "post.json")
    post = json.load(io.open(path, encoding="utf-8"))
    os.makedirs(os.path.join(day, "photos"), exist_ok=True)
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
