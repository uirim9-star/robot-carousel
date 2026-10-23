"""성과를 모아 피드백 보고서(data/review.md)를 만든다. 밤 루틴이 글을 쓰기 전에 읽는다.

python review.py          # data/review.md 생성

점수 — 플랫폼마다 «도달 대비 얼마나 반응했나»로 잰다. 저장·공유는 알고리즘이 가장 크게 보는 신호라 3배.
  인스타: (저장×3 + 공유×3 + 댓글×2 + 좋아요) / 도달
  스레드: (리포스트×3 + 답글×2 + 좋아요) / 조회
발행 후 48시간이 안 된 글은 숫자가 덜 찼으므로 비교에서 뺀다.
묶음(주제·훅·표지 사진)마다 평균을 내되, 글이 5건 미만이면 «표본 부족»으로 표시한다 — 그걸로 규칙을 만들지 않는다.
"""
import datetime, glob, io, json, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
KST = datetime.timezone(datetime.timedelta(hours=9))
MIN_N = 5
FIX_WORDS = re.compile(r"틀렸|틀린|잘못|오류|오타|정정|사실이 아|아닌데|아닙니다|wrong|incorrect", re.I)


def jsonl(name):
    p = os.path.join(DATA, name)
    return [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


def score(r):
    if r["on"] == "instagram":
        base, s = r.get("reach", 0), 3 * r.get("saved", 0) + 3 * r.get("shares", 0) + 2 * r.get("comments", 0) + r.get("likes", 0)
    else:
        base, s = r.get("views", 0), 3 * r.get("reposts", 0) + 2 * r.get("replies", 0) + r.get("likes", 0)
    return s / base if base else 0.0


def posts():
    """발행된 글마다 post.json의 meta와 발행 시각."""
    out = {}
    for p in glob.glob(os.path.join(HERE, "slides", "*", "posted.json")):
        day = os.path.basename(os.path.dirname(p))
        post = json.load(io.open(os.path.join(os.path.dirname(p), "post.json"), encoding="utf-8"))
        out[day] = {"no": post.get("no"), "title": re.sub(r"<[^>]+>", " ", post["cards"][0]["h1"]).strip(),
                    "meta": post.get("meta", {}), "posted_at": json.load(io.open(p, encoding="utf-8"))["posted_at"]}
    return out


def main():
    now = datetime.datetime.now(KST)
    info = posts()
    latest = {}  # (day, on) → 가장 최근 측정
    for r in jsonl("stats.jsonl"):
        if "day" in r:
            latest[(r["day"], r["on"])] = r
    rows = []
    for (day, on), r in sorted(latest.items()):
        p = info.get(day)
        if not p:
            continue
        age = (now - datetime.datetime.fromisoformat(p["posted_at"])).total_seconds() / 3600
        rows.append({"day": day, "on": on, "score": score(r), "reach": r.get("reach", r.get("views", 0)),
                     "ripe": age >= 48, **p})

    L = [f"# 피드백 보고서 — {now:%Y-%m-%d %H:%M} KST", ""]
    if not rows:
        L += ["아직 성과 데이터가 없다. 발행·측정이 쌓이면 채워진다.", ""]
    for on in ("instagram", "threads"):
        mine = [r for r in rows if r["on"] == on]
        if not mine:
            continue
        ripe = [r for r in mine if r["ripe"]]
        avg = sum(r["score"] for r in ripe) / len(ripe) if ripe else 0
        L += [f"## {on} — 글 {len(mine)}건 (비교 가능 {len(ripe)}건, 평균 점수 {avg:.3f})", "",
              "| 날짜 | No. | 표지 | 도달 | 점수 | 평균 대비 |", "|---|---|---|---|---|---|"]
        for r in sorted(mine, key=lambda r: r["day"], reverse=True)[:14]:
            rel = f"{r['score'] / avg:.0%}" if avg and r["ripe"] else "48시간 전"
            L.append(f"| {r['day']} | {r['no']} | {r['title'][:24]} | {r['reach']} | {r['score']:.3f} | {rel} |")
        L.append("")
        for key in ("topic", "hook", "photo_cover"):
            groups = defaultdict(list)
            for r in ripe:
                groups[str(r["meta"].get(key, "?"))].append(r["score"])
            if len(groups) < 2:
                continue
            L.append(f"- **{key}별**: " + " · ".join(
                f"{g} {sum(v) / len(v):.3f} (n={len(v)}{', 표본 부족' if len(v) < MIN_N else ''})"
                for g, v in sorted(groups.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))))
        L.append("")

    fol = defaultdict(list)
    for r in jsonl("stats.jsonl"):
        if "followers" in r:
            fol[r["on"]].append((r["at"], r["followers"]))
    if fol:
        L.append("## 팔로워")
        for on, v in fol.items():
            v.sort()
            cut = (now - datetime.timedelta(days=7, minutes=-5)).isoformat()
            before = [f for at, f in v if at <= cut]
            base = before[-1] if before else v[0][1]  # 7일치가 안 쌓였으면 첫 기록과 비교
            L.append(f"- {on}: 현재 {v[-1][1]} (7일 전 대비 {v[-1][1] - base:+d})")
        L.append("")

    fixes = [c for c in jsonl("comments.jsonl") if FIX_WORDS.search(c.get("text", ""))]
    done = set(io.open(os.path.join(DATA, "fixed.txt"), encoding="utf-8").read().split()) \
        if os.path.exists(os.path.join(DATA, "fixed.txt")) else set()
    todo = [c for c in fixes if c["id"] not in done]
    L.append(f"## 정정 요청 후보 {len(todo)}건")
    L += [f"- `{c['id']}` {c['day']} {c['on']} @{c.get('username', '?')}: {c['text'][:120]}" for c in todo] or ["- 없음"]
    L.append("")

    io.open(os.path.join(DATA, "review.md"), "w", encoding="utf-8", newline="\n").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
