import json, os, hashlib, re, time, requests
from datetime import datetime
from config import (
    STATE_FILE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TICKETEK_URL, TIXEL_URL, TIXEL_SURGE_THRESHOLD,
    CHECK_INTERVAL, MAX_FAIL_COUNT,
)

# ── 상수 ──────────────────────────────────────────────────────────────────────

DEFAULT_STATE = {
    "ticketek_hash": None,
    "tixel_listing_count": None,
    "tixel_min_price": None,
    "fail_count": 0,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.google.com.au/",
}

# ── 상태 저장/로드 ─────────────────────────────────────────────────────────────

def load_state():
    if not os.path.exists(STATE_FILE):
        return DEFAULT_STATE.copy()
    with open(STATE_FILE) as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ── HTTP 헬퍼 ─────────────────────────────────────────────────────────────────

def fetch_page(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            return r.text
        return None
    except requests.RequestException:
        return None

# ── 텔레그램 ──────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
    except requests.RequestException:
        pass

# ── Ticketek 체커 ─────────────────────────────────────────────────────────────

def check_ticketek(state):
    alerts = []
    html = fetch_page(TICKETEK_URL)
    if html is None:
        return alerts

    new_hash = hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()

    if state["ticketek_hash"] and state["ticketek_hash"] != new_hash:
        alerts.append(
            "🔴 <b>Ticketek 페이지 변화 감지!</b>\n"
            "내용이 변경됐어요. 직접 확인해보세요:\n"
            "https://premier.ticketek.com.au/events/BRON2626/venues/SUN"
            "/performances/EBRC0000026L/tickets"
        )

    prices = re.findall(r'\$\d+(?:\.\d+)?', html)
    if prices:
        alerts.append(
            f"💰 <b>Ticketek 가격 등장!</b>\n"
            f"발견된 가격: {', '.join(sorted(set(prices))[:5])}\n"
            "티켓 오픈됐을 가능성이 높아요. 지금 바로 확인!\n"
            "https://premier.ticketek.com.au/events/BRON2626/venues/SUN"
            "/performances/EBRC0000026L/tickets"
        )

    state["ticketek_hash"] = new_hash
    return alerts

# ── Tixel 체커 ────────────────────────────────────────────────────────────────

def check_tixel(state):
    alerts = []
    html = fetch_page(TIXEL_URL)
    if html is None:
        return alerts

    count_match = re.search(r'(\d+)\s+listings?\s+available', html, re.IGNORECASE)
    new_count = int(count_match.group(1)) if count_match else None

    price_match = re.search(r'\$(\d+(?:\.\d+)?)\s+ea', html)
    new_price = float(price_match.group(1)) if price_match else None

    if (new_count is not None
            and state["tixel_listing_count"] is not None
            and new_count >= TIXEL_SURGE_THRESHOLD
            and new_count > state["tixel_listing_count"]):
        alerts.append(
            f"📈 <b>Tixel 2차마켓 물량 급증!</b>\n"
            f"{state['tixel_listing_count']}개 → {new_count}개\n"
            "공식 티켓 오픈 신호일 수 있어요. 확인:\n"
            "https://tixel.com/au/sports-tickets/2026/08/27"
            "/brisbane-broncos-suncorp-stadium"
        )

    if new_count is not None:
        state["tixel_listing_count"] = new_count
    if new_price is not None:
        state["tixel_min_price"] = new_price

    return alerts

# ── 메인 루프 ─────────────────────────────────────────────────────────────────

def run_checks(state):
    all_alerts = []
    try:
        all_alerts += check_ticketek(state)
        all_alerts += check_tixel(state)
        state["fail_count"] = 0
    except Exception as e:
        state["fail_count"] = state.get("fail_count", 0) + 1
        if state["fail_count"] >= MAX_FAIL_COUNT:
            all_alerts.append(
                f"⚠️ <b>봇 에러 발생!</b>\n"
                f"연속 {state['fail_count']}회 실패\n"
                f"에러: {str(e)[:100]}"
            )
    return all_alerts

HEARTBEAT_INTERVAL = 3600  # 1시간마다 생존 알림

def main():
    state = load_state()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    send_telegram(f"🚀 브롱코스 티켓 모니터 시작!\n{now}\n30분마다 체크할게요.")
    print(f"[{now}] 모니터 시작")

    last_heartbeat = time.time()

    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        alerts = run_checks(state)
        save_state(state)

        for alert in alerts:
            send_telegram(alert)
            print(f"[{now}] 알림 전송: {alert[:60]}")

        if not alerts:
            print(f"[{now}] 변화 없음")

        if time.time() - last_heartbeat >= HEARTBEAT_INTERVAL:
            send_telegram(
                f"🫡 변화 없음, 주시 중!\n"
                f"Ticketek + Tixel 모두 이상 없어요.\n"
                f"⏰ {now}"
            )
            last_heartbeat = time.time()

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
