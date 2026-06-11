TELEGRAM_BOT_TOKEN = "여기에_봇_토큰"
TELEGRAM_CHAT_ID   = "여기에_채팅_ID"

TICKETEK_URL = (
    "https://premier.ticketek.com.au"
    "/events/BRON2626/venues/SUN"
    "/performances/EBRC0000026L/tickets"
)
TIXEL_URL = (
    "https://tixel.com/au/sports-tickets"
    "/2026/08/27/brisbane-broncos-suncorp-stadium"
)

CHECK_INTERVAL        = 1800  # 초 (30분)
TIXEL_SURGE_THRESHOLD = 10    # 리스팅 수가 이 이상이면 급증으로 판단
MAX_FAIL_COUNT        = 5     # 연속 실패 이 횟수 초과 시 에러 알림
STATE_FILE            = "state.json"
