"""해외 로봇 뉴스 수집 — RSS 몇 곳에서 새 기사만 data/items.jsonl에 덧붙인다.

python collect.py          # 수집
python collect.py --fresh [시간]  # 최근 48시간(기본) 기사 중 아직 안 쓴 것 목록 (루틴이 고를 후보)
"""
import datetime, email.utils, html, io, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "data", "items.jsonl")
USED = os.path.join(HERE, "data", "used.txt")
UA = {"User-Agent": "Mozilla/5.0 (robot-carousel)"}
FEEDS = {
    "therobotreport": "https://www.therobotreport.com/feed/",
    "ieee-spectrum": "https://spectrum.ieee.org/feeds/topic/robotics.rss",
    "techcrunch": "https://techcrunch.com/category/robotics/feed/",
    "robohub": "https://robohub.org/feed/",
    # 자영업·중소기업 갈래 (식당·소매 현장의 자동화 기술)
    "restaurant-dive": "https://www.restaurantdive.com/feeds/topic/technology/",
    "retail-dive": "https://www.retaildive.com/feeds/topic/technology/",
}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def feed(name, url):
    root = ET.fromstring(get(url))
    for it in root.iter("item"):
        pub = it.findtext("pubDate")
        try:
            when = email.utils.parsedate_to_datetime(pub).astimezone(datetime.timezone.utc).isoformat()
        except Exception:
            when = ""
        yield {"source": name, "title": strip(it.findtext("title")), "url": (it.findtext("link") or "").strip(),
               "published": when, "summary": strip(it.findtext("description"))[:600]}


def load():
    if not os.path.exists(DB):
        return []
    with io.open(DB, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def collect():
    seen = {i["url"] for i in load()}
    new, errors = [], []
    for name, url in FEEDS.items():
        try:
            for it in feed(name, url):
                if it["url"] and it["url"] not in seen:
                    seen.add(it["url"])
                    new.append(it)
        except Exception as e:  # 한 곳이 깨져도 나머지는 받는다
            errors.append(f"{name}: {e}")
    with io.open(DB, "a", encoding="utf-8", newline="\n") as f:
        for it in new:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"새 기사 {len(new)}건" + (f" · 실패 {errors}" if errors else ""))


def fresh(hours=48):
    used = set(io.open(USED, encoding="utf-8").read().split()) if os.path.exists(USED) else set()
    cut = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)).isoformat()
    for it in sorted(load(), key=lambda i: i["published"], reverse=True):
        if it["published"] >= cut and it["url"] not in used:
            print(f"- [{it['source']}] {it['title']}\n  {it['url']}\n  {it['summary'][:200]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--fresh" in sys.argv:
        i = sys.argv.index("--fresh")
        fresh(int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 48)
    else:
        collect()
