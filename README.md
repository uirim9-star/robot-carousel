# robot-carousel

해외 로봇 뉴스 1건을 매일 한국어 캐러셀(7장)로 만들어 인스타그램·스레드에 자동 발행한다.
디자인은 창업기자단 EP04 카드뉴스(2026-10-13)를 그대로 옮겼다.

- 밤 22:00 PC: `run_hidden.vbs` → `run_local.bat` → `claude -p` + `ROUTINE.md`
  수집(`collect.py`) → 원문(`fetch_source.py`) → `post.json` → 사진(`photos.py`, Wikimedia 자유 라이선스만) → `render.py` → `check.py`
- 아침 08:00 GitHub Actions: `publish.py` (검문 재실행 → 인스타·스레드 캐러셀) → `--insights`
- 브랜드 문구: `config.json`
- 토큰: `.env` → `python tokens.py --sync` (GitHub 시크릿 등록·30일 갱신)

## 피드백 루프
- 매일 08:00 Actions: `publish.py --insights` → `data/stats.jsonl`(도달·저장·공유 등), `data/comments.jsonl`(댓글·답글)
- 매일 밤 루틴 첫 단계: `review.py` → `data/review.md`(글별 점수, 주제·훅·표지사진별 평균, 팔로워 증감, 정정 요청 후보)
  → 루틴이 `LESSONS.md`(규칙·이번 주 실험)를 읽고 그날 글에 반영
- 월요일 루틴: 묶음당 n≥5·차이 30%↑만 규칙으로 승격, 실험 변수 1개 교체, `data/weekly.md`에 사람용 주간 요약
- 정정 요청 댓글: 원문과 대조해 `data/corrections.md`에 판정만 남긴다. 답글·정정 게시는 사람이 한다
- 필요한 추가 권한: 인스타 `instagram_business_manage_insights`·`instagram_business_manage_comments`, 스레드 `threads_manage_insights`·`threads_read_replies`
