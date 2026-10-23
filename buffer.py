"""Buffer GraphQL API로 인스타·스레드에 올리고 성과를 읽는다. Meta 개발자 앱 없이 쓰는 경로다.

python buffer.py --channels   # 연결된 채널 확인 (키가 맞는지 시험)

키는 환경변수 BUFFER_API_KEY에서만 읽는다. 무료 플랜: 키 1개, 하루 요청 250회.
"""
import json, os, sys, urllib.error, urllib.request

API = "https://api.buffer.com"
SERVICES = ("instagram", "threads")


def gql(query, **variables):
    req = urllib.request.Request(API, data=json.dumps({"query": query, "variables": variables}).encode(), headers={
        "Authorization": f"Bearer {os.environ['BUFFER_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Buffer {e.code}: {e.read().decode()[:300]}") from None
    if d.get("errors"):
        raise RuntimeError(f"Buffer: {d['errors'][0].get('message')}")
    return d["data"]


def channels():
    """{'instagram': 채널id, 'threads': 채널id}. config.json의 channels에 적힌 계정 이름만 쓴다 —
    같은 Buffer에 다른 용도의 계정(vibe_bizmaker 등)이 함께 연결돼 있어서다."""
    want = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"), encoding="utf-8"))["channels"]
    out = {}
    for org in gql("query { account { organizations { id } } }")["account"]["organizations"]:
        for c in gql("query($o: OrganizationId!) { channels(input: {organizationId: $o}) { id name service } }",
                     o=org["id"])["channels"]:
            if c["service"] in SERVICES and c["name"] == want.get(c["service"]):
                out.setdefault(c["service"], c["id"])
    return out


def create(channel_id, service, text, urls):
    """이미지 여러 장 = 캐러셀. 바로 발행(shareNow)한다 — 예약은 Actions의 cron이 맡는다."""
    inp = {"channelId": channel_id, "text": text, "mode": "shareNow", "schedulingType": "automatic",
           "needsApproval": False, "assets": [{"image": {"url": u}} for u in urls]}
    if service == "instagram":  # AI가 쓴 글이라 인스타 «AI 정보» 표시를 켠다
        inp["metadata"] = {"instagram": {"type": "carousel", "shouldShareToFeed": True, "isAiGenerated": True}}
    d = gql("""mutation($i: CreatePostInput!) { createPost(input: $i) {
              ... on PostActionSuccess { post { id } }
              ... on MutationError { message } } }""", i=inp)["createPost"]
    if "message" in d:
        raise RuntimeError(f"Buffer {service}: {d['message']}")
    return d["post"]["id"]


def metrics(post_id):
    """글 하나의 지표를 review.py가 쓰는 이름으로 바꿔 돌려준다."""
    p = gql("query($id: PostId!) { post(input: {id: $id}) { status externalLink metrics { type name value } } }",
            id=post_id)["post"]
    names = {"reach": "reach", "likes": "likes", "comments": "comments", "saves": "saved", "saved": "saved",
             "shares": "shares", "views": "views", "impressions": "views", "replies": "replies", "reposts": "reposts"}
    row = {"status": p.get("status"), "link": p.get("externalLink")}
    for m in p.get("metrics") or []:
        key = names.get(str(m.get("type") or m.get("name")).lower())
        if key:
            row[key] = m["value"]
    return row


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--channels" in sys.argv:
        print(channels() or "인스타·스레드 채널이 연결돼 있지 않다")
