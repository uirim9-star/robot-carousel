"""인스타·스레드 토큰을 만료되지 않게 관리한다 (sv-watcher threads_token.py를 두 플랫폼으로 넓힌 것). 토큰 값은 출력하지 않는다.

python tokens.py --sync    # .env의 토큰을 장기 토큰으로 바꾸고/30일마다 갱신하고, GitHub 시크릿에 올린다
python tokens.py --check   # 토큰이 살아 있는지만 확인 (계정 이름 출력)

.env (저장소에 올라가지 않는다):
  IG_ACCESS_TOKEN=...        인스타 (Business Login for Instagram 토큰)
  IG_APP_SECRET=...          선택 — 단기 토큰을 60일 토큰으로 바꿀 때
  THREADS_ACCESS_TOKEN=...   스레드
  THREADS_APP_SECRET=...     선택
  *_TOKEN_REFRESHED=날짜     이 스크립트가 적는다
"""
import datetime, io, json, os, subprocess, sys, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
REFRESH_AFTER_DAYS = 30  # 장기 토큰은 60일. 절반쯤에서 갱신한다
PLATFORMS = {  # 접두어: (주소, 교환 grant, 갱신 grant)
    "IG": ("https://graph.instagram.com", "ig_exchange_token", "ig_refresh_token"),
    "THREADS": ("https://graph.threads.net", "th_exchange_token", "th_refresh_token"),
}


def load():
    if not os.path.exists(ENV):
        sys.exit(".env 없음 — IG_ACCESS_TOKEN=... / THREADS_ACCESS_TOKEN=... 를 적어 두세요")
    env = {}
    for line in io.open(ENV, encoding="utf-8-sig"):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def save(env):
    with io.open(ENV, "w", encoding="utf-8", newline="\n") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")


def get(url, **params):
    try:
        with urllib.request.urlopen(f"{url}?" + urllib.parse.urlencode(params), timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": json.loads(e.read() or b"{}").get("error", {}).get("message", str(e))}


def who(prefix, token):
    base = PLATFORMS[prefix][0]
    d = get(f"{base}/{'v23.0' if prefix == 'IG' else 'v1.0'}/me", fields="username", access_token=token)
    return d.get("username"), d.get("error")


def sync_one(env, prefix):
    key, base, exch, refr = f"{prefix}_ACCESS_TOKEN", *PLATFORMS[prefix]
    token = env.get(key)
    if not token:
        return print(f"{key} 없음 — 건너뜀")
    user, err = who(prefix, token)
    if not user:
        return print(f"{prefix} 토큰이 안 먹힘: {err}")
    print(f"{prefix} 토큰 확인: @{user}")
    stamp = f"{prefix}_TOKEN_REFRESHED"
    last = env.get(stamp)
    if env.get(f"{prefix}_APP_SECRET") and not last:
        d = get(f"{base}/access_token", grant_type=exch, client_secret=env[f"{prefix}_APP_SECRET"], access_token=token)
        if "access_token" in d:
            token = d["access_token"]
            print(f"  장기 토큰으로 바꿈 (유효 {d.get('expires_in', 0) // 86400}일)")
    due = not last or (datetime.date.today() - datetime.date.fromisoformat(last)).days >= REFRESH_AFTER_DAYS
    if last and due:
        d = get(f"{base}/refresh_access_token", grant_type=refr, access_token=token)
        if "access_token" in d:
            token = d["access_token"]
            print(f"  갱신 (유효 {d.get('expires_in', 0) // 86400}일)")
        else:
            print(f"  갱신 실패: {d.get('error')} — 토큰을 새로 받아야 할 수 있음")
    if not due and token == env[key]:
        return print(f"  갱신할 때 아님 (마지막 {last})")
    # 값은 stdin으로만 넘긴다 (명령줄·로그에 남지 않게)
    r = subprocess.run(["gh", "secret", "set", key], input=token, text=True, capture_output=True, cwd=HERE)
    if r.returncode != 0:
        sys.exit(f"GitHub 시크릿 저장 실패: {r.stderr.strip()[:200]}")
    print(f"  GitHub 시크릿 {key} 저장")
    env[key], env[stamp] = token, datetime.date.today().isoformat()
    save(env)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    env = load()
    for prefix in PLATFORMS:
        if "--check" in sys.argv:
            if env.get(f"{prefix}_ACCESS_TOKEN"):
                u, e = who(prefix, env[f"{prefix}_ACCESS_TOKEN"])
                print(f"{prefix}: @{u}" if u else f"{prefix}: 실패 {e}")
        else:
            sync_one(env, prefix)
