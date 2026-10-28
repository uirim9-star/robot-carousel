"""발행 전 자동 검문. 하나라도 걸리면 그날은 발행하지 않는다 — 틀린 글보다 빈 날이 낫다.

python check.py slides/2026-10-23   # 통과면 exit 0, 아니면 이유를 출력하고 exit 1

post.json 형식:
{
 "no": 1, "source": {"title", "url", "outlet"},
 "meta": {"topic": "휴머노이드", "hook": "결론", "photo_cover": false},   # 가능한 값은 META

 "facts": [{"ko": "9천만 달러", "quote": "raised $90 million"}],   # 카드의 숫자마다 원문 문장 근거
 "cards": [{"h1", "sub": [...], "rows": [[k, v]], "glyph", "photo_query", "photo", "credit", "pos", "lead", "size"}],
 "caption_ig": "...", "caption_threads": "..."
}
"""
import io, json, os, re, sys

LIMITS = {"h1": 40, "sub": 90, "row": 40}
BANNED = ["최초", "혁명", "충격", "역대급", "미쳤", "소름", "무조건", "100%", "AI 요약", "AI가 요약"]
IMG = (1080, 1350)
REPORT_VERBS = ["밝혔", "설명했", "발표했", "전했", "에 따르면", "것으로 알려", "예정이다", "주목된다"]
CALQUES = ["되어진", "에 대해", "을 통해", "를 통해", "에 있어서", "때려박", "갈아끼",  # WRITING.md 2절
           "시사하는 바", "결론적으로", "요약하면", "주목할 만", "혁신적"]
META = {"topic": ["휴머노이드", "모델·소프트웨어", "투자·상장", "공장·물류 도입", "자영업·중소기업", "기타"],
        "hook": ["왜", "숫자 대비", "원인→결과", "유행어 해설", "인물+주장", "결론"],  # STYLE.md 제목 공식 A~E (결론은 No.1 이전 방식)
        "photo_cover": [True, False]}


def norm(s):
    return re.sub(r"\s+", " ", s.replace(",", "")).lower()


def plain(s):
    return re.sub(r"<[^>]+>", "", s or "")


def numbers(s):
    return set(re.findall(r"\d+(?:\.\d+)?", plain(s).replace(",", "")))


def check(day):
    errs = []
    try:
        post = json.load(io.open(os.path.join(day, "post.json"), encoding="utf-8"))
    except Exception as e:
        return [f"post.json 읽기 실패: {e}"]
    src_path = os.path.join(day, "source.txt")
    if not os.path.exists(src_path):
        return ["source.txt 없음 (fetch_source.py를 먼저)"]
    src = norm(io.open(src_path, encoding="utf-8").read())

    url = post.get("source", {}).get("url", "")
    if not url or url not in io.open(src_path, encoding="utf-8").readline():
        errs.append("source.url이 source.txt의 원문 주소와 다름")
    meta = post.get("meta", {})  # review.py가 무엇이 먹혔는지 묶어 보는 꼬리표
    for k, ok in META.items():
        if meta.get(k) not in ok:
            errs.append(f"meta.{k}={meta.get(k)!r} (가능: {', '.join(map(str, ok))})")
    cards = post.get("cards", [])
    if not 5 <= len(cards) <= 10:
        errs.append(f"카드 {len(cards)}장 (5~10장이어야 함)")

    # 근거 문장이 원문에 그대로 있어야 그 숫자를 쓸 수 있다
    allowed = set()
    for f in post.get("facts", []):
        if norm(f.get("quote", "")) in src:
            allowed |= numbers(f.get("ko", ""))
        else:
            errs.append(f"근거 문장이 원문에 없음: {f.get('quote', '')[:60]}")

    texts = []
    for i, c in enumerate(cards, 1):
        if len(plain(c.get("h1", ""))) > LIMITS["h1"]:
            errs.append(f"{i}번 제목 {len(plain(c['h1']))}자 (> {LIMITS['h1']})")
        for s in c.get("sub", []):
            if len(plain(s)) > LIMITS["sub"]:
                errs.append(f"{i}번 본문 {len(plain(s))}자 (> {LIMITS['sub']})")
        for k, v in c.get("rows", []):
            if len(plain(k + v)) > LIMITS["row"]:
                errs.append(f"{i}번 표 줄 {len(plain(k + v))}자 (> {LIMITS['row']})")
        texts.append((f"{i}번 카드", " ".join([c.get("h1", "")] + c.get("sub", []) + [k + " " + v for k, v in c.get("rows", [])])))
        if c.get("photo") and not os.path.exists(os.path.join(day, c["photo"])):
            errs.append(f"{i}번 사진 파일 없음")
    texts += [("인스타 캡션", post.get("caption_ig", "")), ("스레드 캡션", post.get("caption_threads", ""))]

    for where, t in texts:
        for n in numbers(t) - allowed:
            if n not in src:
                errs.append(f"{where}의 숫자 {n}: 원문에도 facts에도 근거 없음")
        for w in BANNED:
            if w in t:
                errs.append(f"{where}에 과장어 «{w}»")
        for w in CALQUES:
            if w in t:
                errs.append(f"{where}에 번역투·상투구 «{w}» (WRITING.md)")
        if "—" in t or "·" in t or re.search(r"(?<!\d)–|–(?!\d)", t):
            errs.append(f"{where}에 em dash·가운데점·en dash (WRITING.md: 쉼표, 콜론, 괄호, «와/과»로)")

    ig, th = post.get("caption_ig", ""), post.get("caption_threads", "")

    # 말투 (STYLE.md 4절): 기사체를 기계적으로 걸러 낸다
    prose = " ".join(plain(s) for c in cards for s in c.get("sub", []) if not s.startswith("출처")) + " " + ig + " " + th
    ends = re.findall(r"([가-힣])[.?](?=\s|$|”|\")", prose)
    if ends and sum(e == "요" for e in ends) / len(ends) < 0.5:
        errs.append(f"말투: «~요»로 끝나는 문장이 {sum(e == '요' for e in ends)}/{len(ends)} — 절반 이상이어야 함 (기사체)")
    for w in REPORT_VERBS:
        if w in prose:
            errs.append(f"말투: 보도 동사 «{w}»")
    card_text = " ".join(t for where, t in texts if where.endswith("카드"))
    for where, t in [("카드", card_text), ("인스타 캡션", ig), ("스레드 캡션", th)]:
        if len(re.findall(r"뜻이|뜻입", plain(t))) > 2:
            errs.append(f"말투: {where}에 «~라는 뜻이에요» 종결이 3회 이상 (WRITING.md: 2회까지)")
    last = " ".join(plain(s) for s in cards[-1].get("sub", []) + [cards[-1].get("h1", "")]) if cards else ""
    if "?" not in last + ig:
        errs.append("말투: 마지막 장이나 인스타 캡션에 독자에게 묻는 문장이 없음")
    if not ig or len(ig) > 2200:
        errs.append(f"인스타 캡션 {len(ig)}자 (1~2200)")
    if not th or len(th) > 500:
        errs.append(f"스레드 캡션 {len(th)}자 (1~500)")
    if url in ig or url in th or re.search(r"(?m)^원문", ig + "\n" + th):
        errs.append("캡션에 원문 링크·«원문» 줄이 있음 (STYLE.md 5절: 넣지 않는다)")

    if os.path.exists(os.path.join(day, "overflow.txt")):
        errs.append("렌더링 글 넘침: " + io.open(os.path.join(day, "overflow.txt"), encoding="utf-8").read())
    jpgs = sorted(f for f in os.listdir(day) if re.match(r"card_\d+\.jpg$", f))
    if len(jpgs) != len(cards):
        errs.append(f"이미지 {len(jpgs)}장 ≠ 카드 {len(cards)}장 (render.py를 다시)")
    else:
        from PIL import Image
        for f in jpgs:
            if Image.open(os.path.join(day, f)).size != IMG:
                errs.append(f"{f} 크기가 {IMG}가 아님")
    return errs


def digest(day):
    """post.json과 카드 이미지의 지문. 원문(source.txt)은 저작권 때문에 공개 저장소에 올리지 않으므로,
    Actions는 검문을 다시 돌리지 못하고 «PC에서 통과한 뒤 바뀌지 않았는지»만 이 지문으로 확인한다."""
    import hashlib
    h = hashlib.sha256()
    for f in ["post.json"] + sorted(f for f in os.listdir(day) if re.match(r"card_\d+\.jpg$", f)):
        h.update(open(os.path.join(day, f), "rb").read())  # .gitattributes가 slides/의 줄바꿈 변환을 막는다
    return h.hexdigest()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    day = sys.argv[1]
    errs = check(day)
    ok = os.path.join(day, "checked.txt")
    if errs:
        if os.path.exists(ok):
            os.remove(ok)
        print("\n".join(errs))
        sys.exit(1)
    io.open(ok, "w", encoding="utf-8", newline="\n").write(digest(day) + "\n")
    print("통과")
