import time
import signal
import sys
import requests
import xml.etree.ElementTree as ET

# ---- fill these in ----
HOST = "172.16.17.1:8090"
USERNAME = "vip"
PASSWORD = "0987654321"          
PRODUCTTYPE = 0                  
LIVE_INTERVAL_SEC = 150          
# ------------------------

BASE = f"http://{HOST}"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
})

def epoch_ms() -> str:
    return str(int(time.time() * 1000))

def login() -> bool:
    payload = {
        "mode": 191,
        "username": USERNAME,
        "password": PASSWORD,
        "a": epoch_ms(),
        "producttype": PRODUCTTYPE,
    }
    resp = session.post(f"{BASE}/login.xml", data=payload, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    status = root.findtext("status")
    message = root.findtext("message")
    print(f"[login] status={status!r} message={message!r}")

    if status == "CHALLENGE":
        print("[login] server returned CHALLENGE state -- unhandled, aborting.")
        return False

    return status == "LIVE" or status is None 


def send_live() -> str:
    """Returns the ack value: 'ack', 'nack', 'login_again', or 'live_off'."""
    params = {
        "mode": 192,
        "username": USERNAME,
        "a": epoch_ms(),
        "producttype": PRODUCTTYPE,
    }
    resp = session.get(f"{BASE}/live", params=params, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ack = root.findtext("ack") or ""
    livemsg = root.findtext("livemessage") or ""
    print(f"[live] ack={ack!r} livemessage={livemsg!r}")
    return ack


def logout():
    payload = {
        "mode": 193,
        "username": USERNAME,
        "a": epoch_ms(),
        "producttype": PRODUCTTYPE,
    }
    try:
        session.post(f"{BASE}/logout.xml", data=payload, timeout=10)
        print("[logout] sent")
    except requests.RequestException as e:
        print(f"[logout] failed: {e}")


def handle_sigint(signum, frame):
#    logout()
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, handle_sigint)

    if not login():
        sys.exit(1)

    while True:
        try:
            ack = send_live()
        except requests.RequestException as e:
            print(f"[live] request failed: {e} -- retrying in {LIVE_INTERVAL_SEC}s")
            time.sleep(LIVE_INTERVAL_SEC)
            continue

        if ack in ("nack", "login_again"):
            print("[live] session dropped by server, re-authenticating...")
            if not login():
                print("[live] re-login failed, giving up.")
                sys.exit(1)

        time.sleep(LIVE_INTERVAL_SEC)


if __name__ == "__main__":
    main()
