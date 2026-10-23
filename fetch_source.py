"""원문 기사를 받아 본문 텍스트를 slides/<날짜>/source.txt에 저장한다.
check.py는 카드의 숫자를 이 파일과 대조한다 — 모델이 쓴 요약이 아니라 실제 원문과 맞춰 보기 위해서다.

python fetch_source.py <기사 URL> slides/2026-10-23
"""
import io, os, sys
from collect import get, strip
import re


def main(url, out):
    page = get(url).decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", page)
    paras = [strip(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", page)]
    text = "\n".join(p for p in paras if len(p) > 40)
    if len(text) < 800:
        sys.exit(f"본문이 너무 짧다 ({len(text)}자) — 다른 기사를 고를 것")
    os.makedirs(out, exist_ok=True)
    with io.open(os.path.join(out, "source.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(url + "\n\n" + text + "\n")
    print(f"원문 {len(text)}자 저장")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
