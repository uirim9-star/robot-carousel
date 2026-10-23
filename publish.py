"""검문을 통과한 최신 캐러셀 1건을 인스타그램·스레드에 올린다 (GitHub Actions가 매일 08:00 KST에 부른다).

python publish.py             # 발행 (하루 1건 한도)
python publish.py --dry       # 무엇을 어떤 주소로 올릴지만 출력
python publish.py --insights  # 발행한 글의 성과를 data/stats.jsonl에 적는다

토큰은 환경변수에서만 읽는다: IG_ACCESS_TOKEN, THREADS_ACCESS_TOKEN. 둘 중 있는 쪽만 올린다.
인스타는 공개 URL의 JPEG만 받으므로, 이미지는 이 공개 저장소의 raw 주소로 넘긴다.
"""
import datetime, glob, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from check import digest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("GITHUB_REPOSITORY", "uirim9-star/robot-carousel")
RAW = f"https://raw.githubusercontent.com/{REPO}/main"
IG = "https://graph.instagram.com/v23.0"
TH = "https://graph.threads.net/v1.0"
KST = datetime.timezone(datetime.timedelta(hours=9))


def call(base, token, method, path, **params):
    params["access_token"] = token
    data = urllib.parse.urlencode(params).encode()
    url = f"{base}/{path}" + ("" if method == "POST" else "?" + data.decode())
    req = urllib.request.Request(url, data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: {e.read().decode()[:300]}") from None


def wait(base, token, cid, field, done):
    """컨테이너가 준비될 때까지 기다린다 (보통 몇 초, 최대 2분)."""
    for _ in range(24):
        st = call(base, token, "GET", cid, fields=field).get(field, "")
        if st == done:
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"컨테이너 {cid} 상태 {st}")
        time.sleep(5)
    raise RuntimeError(f"컨테이너 {cid} 준비 안 됨")


def instagram(token, urls, caption):
    kids = [call(IG, token, "POST", "me/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    for k in kids:
        wait(IG, token, k, "status_code", "FINISHED")
    cid = call(IG, token, "POST", "me/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    wait(IG, token, cid, "status_code", "FINISHED")
    return call(IG, token, "POST", "me/media_publish", creation_id=cid)["id"]


def threads(token, urls, text):
    kids = [call(TH, token, "POST", "me/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"]
            for u in urls]
    for k in kids:
        wait(TH, token, k, "status", "FINISHED")
    cid = call(TH, token, "POST", "me/threads", media_type="CAROUSEL", children=",".join(kids), text=text)["id"]
    wait(TH, token, cid, "status", "FINISHED")
    return call(TH, token, "POST", "me/threads_publish", creation_id=cid)["id"]


def posted_today():
    today = datetime.datetime.now(KST).date().isoformat()
    for p in glob.glob(os.path.join(HERE, "slides", "*", "posted.json")):
        if json.load(io.open(p, encoding="utf-8"))["posted_at"].startswith(today):
            return True
    return False


def pick():
    """아직 안 올린 것 중 가장 최신이고 PC 검문을 통과한(checked.txt 지문이 맞는) 하루치. 사흘 넘은 것은 뉴스가 아니라 버린다."""
    cut = (datetime.datetime.now(KST).date() - datetime.timedelta(days=3)).isoformat()
    for day in sorted(glob.glob(os.path.join(HERE, "slides", "*")), reverse=True):
        name = os.path.basename(day)
        if (name < cut or not os.path.exists(os.path.join(day, "post.json"))
                or any(os.path.exists(os.path.join(day, f)) for f in ("posted.json", "SKIP.txt"))):
            continue
        ok = os.path.join(day, "checked.txt")
        if os.path.exists(ok) and io.open(ok, encoding="utf-8").read().strip() == digest(day):
            return day
        print(f"{name}: PC 검문 통과 기록이 없거나 그 뒤 바뀜 — 건너뜀")
    return None


def post(dry=False):
    if posted_today():
        return print("오늘은 이미 올렸다 (하루 1건)")
    day = pick()
    if not day:
        return print("올릴 캐러셀이 없다")
    name = os.path.basename(day)
    meta = json.load(io.open(os.path.join(day, "post.json"), encoding="utf-8"))
    urls = [f"{RAW}/slides/{name}/{f}" for f in sorted(os.listdir(day)) if f.startswith("card_") and f.endswith(".jpg")]
    if dry:
        return print(f"[dry] {name} · {len(urls)}장\n" + "\n".join(urls) + "\n\n" + meta["caption_threads"])
    result, errors = {}, []
    for label, env, fn, text in (("instagram", "IG_ACCESS_TOKEN", instagram, meta["caption_ig"]),
                                 ("threads", "THREADS_ACCESS_TOKEN", threads, meta["caption_threads"])):
        if not os.environ.get(env):
            print(f"{env} 없음 — {label} 건너뜀")
            continue
        try:
            result[label] = fn(os.environ[env], urls, text)
            print(f"{label} 발행: {result[label]}")
        except Exception as e:
            errors.append(f"{label}: {e}")
    if result:
        with io.open(os.path.join(day, "posted.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"posted_at": datetime.datetime.now(KST).isoformat(timespec="seconds"), **result}, f, indent=1)
    if errors:
        sys.exit("\n".join(errors))


def insights():
    out = os.path.join(HERE, "data", "stats.jsonl")
    now = datetime.datetime.now(KST).isoformat(timespec="seconds")
    ig, th = os.environ.get("IG_ACCESS_TOKEN"), os.environ.get("THREADS_ACCESS_TOKEN")
    rows = []
    for p in sorted(glob.glob(os.path.join(HERE, "slides", "*", "posted.json")))[-14:]:  # 최근 2주만 다시 잰다
        meta, day = json.load(io.open(p, encoding="utf-8")), os.path.basename(os.path.dirname(p))
        try:
            if ig and meta.get("instagram"):
                d = call(IG, ig, "GET", f"{meta['instagram']}/insights", metric="reach,likes,comments,saved,shares")
                rows.append({"at": now, "day": day, "on": "instagram", **{m["name"]: m["values"][0]["value"] for m in d["data"]}})
            if th and meta.get("threads"):
                d = call(TH, th, "GET", f"{meta['threads']}/insights", metric="views,likes,replies,reposts")
                rows.append({"at": now, "day": day, "on": "threads", **{m["name"]: m["values"][0]["value"] for m in d["data"]}})
        except Exception as e:
            print(f"{day} 성과 조회 실패: {e}")
    try:
        if ig:
            rows.append({"at": now, "on": "instagram", "followers": call(IG, ig, "GET", "me", fields="followers_count")["followers_count"]})
        if th:
            rows.append({"at": now, "on": "threads", "followers": call(TH, th, "GET", "me/threads_insights", metric="followers_count")["data"][0]["total_value"]["value"]})
    except Exception as e:
        print("팔로워 수 조회 실패:", e)
    with io.open(out, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"성과 {len(rows)}줄 기록")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    insights() if "--insights" in sys.argv else post(dry="--dry" in sys.argv)
