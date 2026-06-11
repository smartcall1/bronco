import os, sys, json, tempfile, hashlib
from unittest.mock import patch, MagicMock

# config/monitor를 임포트 가능하게 경로 추가 후 임시 디렉토리로 이동
_orig_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _orig_dir)
os.chdir(tempfile.mkdtemp())

from monitor import (
    load_state, save_state, DEFAULT_STATE,
    fetch_page, send_telegram,
    check_ticketek, check_tixel,
)

# ── Task 1: state ──────────────────────────────────────────────────────────────

def test_load_state_returns_default_when_no_file():
    if os.path.exists("state.json"):
        os.remove("state.json")
    result = load_state()
    assert result == DEFAULT_STATE

def test_save_and_load_roundtrip():
    state = {"ticketek_hash": "abc123", "tixel_listing_count": 5,
             "tixel_min_price": 79.26, "fail_count": 0}
    save_state(state)
    assert load_state() == state

# ── Task 2: fetch_page + send_telegram ────────────────────────────────────────

def test_fetch_page_returns_text_on_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "<html>hello</html>"
    with patch("monitor.requests.get", return_value=mock_resp):
        result = fetch_page("https://example.com")
    assert result == "<html>hello</html>"

def test_fetch_page_returns_none_on_403():
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    with patch("monitor.requests.get", return_value=mock_resp):
        result = fetch_page("https://example.com")
    assert result is None

def test_send_telegram_posts_to_api():
    with patch("monitor.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        send_telegram("테스트 메시지")
    assert mock_post.called
    assert "테스트 메시지" in str(mock_post.call_args)

# ── Task 3: Ticketek 체커 ──────────────────────────────────────────────────────

def test_check_ticketek_detects_hash_change():
    old_hash = hashlib.md5(b"old content").hexdigest()
    state = {"ticketek_hash": old_hash, "tixel_listing_count": None,
             "tixel_min_price": None, "fail_count": 0}
    with patch("monitor.fetch_page", return_value="new content"):
        alerts = check_ticketek(state)
    assert any("변화" in a for a in alerts)
    assert state["ticketek_hash"] == hashlib.md5(b"new content").hexdigest()

def test_check_ticketek_detects_price():
    state = {"ticketek_hash": None, "tixel_listing_count": None,
             "tixel_min_price": None, "fail_count": 0}
    with patch("monitor.fetch_page", return_value="tickets from $75 and $120"):
        alerts = check_ticketek(state)
    assert any("가격" in a for a in alerts)

def test_check_ticketek_returns_empty_when_no_change():
    content = "same content"
    h = hashlib.md5(content.encode()).hexdigest()
    state = {"ticketek_hash": h, "tixel_listing_count": None,
             "tixel_min_price": None, "fail_count": 0}
    with patch("monitor.fetch_page", return_value=content):
        alerts = check_ticketek(state)
    assert alerts == []

# ── Task 4: Tixel 체커 ────────────────────────────────────────────────────────

TIXEL_HTML_SURGE = """
<html><body>
<span>47 listings available</span>
<span>$55.00 ea • 2 tickets</span>
</body></html>
"""

TIXEL_HTML_NORMAL = """
<html><body>
<span>2 listings available</span>
<span>$79.26 ea • 2 tickets</span>
</body></html>
"""

def test_check_tixel_detects_listing_surge():
    state = {"ticketek_hash": None, "tixel_listing_count": 2,
             "tixel_min_price": 79.26, "fail_count": 0}
    with patch("monitor.fetch_page", return_value=TIXEL_HTML_SURGE):
        alerts = check_tixel(state)
    assert any("급증" in a for a in alerts)
    assert state["tixel_listing_count"] == 47

def test_check_tixel_no_alert_when_normal():
    state = {"ticketek_hash": None, "tixel_listing_count": 2,
             "tixel_min_price": 79.26, "fail_count": 0}
    with patch("monitor.fetch_page", return_value=TIXEL_HTML_NORMAL):
        alerts = check_tixel(state)
    assert alerts == []

def test_check_tixel_parses_listing_count():
    state = {"ticketek_hash": None, "tixel_listing_count": None,
             "tixel_min_price": None, "fail_count": 0}
    with patch("monitor.fetch_page", return_value=TIXEL_HTML_NORMAL):
        check_tixel(state)
    assert state["tixel_listing_count"] == 2
    assert state["tixel_min_price"] == 79.26
