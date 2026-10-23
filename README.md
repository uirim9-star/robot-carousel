# robot-carousel

해외 로봇 뉴스 1건을 매일 한국어 캐러셀(7장)로 만들어 인스타그램·스레드에 자동 발행한다.
디자인은 창업기자단 EP04 카드뉴스(2026-10-13)를 그대로 옮겼다.

- 밤 22:00 PC: `run_hidden.vbs` → `run_local.bat` → `claude -p` + `ROUTINE.md`
  수집(`collect.py`) → 원문(`fetch_source.py`) → `post.json` → 사진(`photos.py`, Wikimedia 자유 라이선스만) → `render.py` → `check.py`
- 아침 08:00 GitHub Actions: `publish.py` (검문 재실행 → 인스타·스레드 캐러셀) → `--insights`
- 브랜드 문구: `config.json`
- 토큰: `.env` → `python tokens.py --sync` (GitHub 시크릿 등록·30일 갱신)
