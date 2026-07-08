"""Send daily 'set your predictions' push reminders via Firebase Cloud Messaging.

Runs on a GitHub Actions cron (~every 15 min). For each user who enabled
reminders, we compare their chosen local time to the current time in their
timezone. If the reminder time falls within the window since the last run and
we haven't already sent today, we push an FCM notification.

Requires the FIREBASE_SERVICE_ACCOUNT secret (the service account JSON) so we
can mint an OAuth token for the FCM HTTP v1 API.
"""
import json
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta, timezone

FIREBASE_URL = "https://wc2026-predictor-56ab2-default-rtdb.firebaseio.com"
PROJECT_ID = "wc2026-predictor-56ab2"
FCM_ENDPOINT = f"https://fcm.googleapis.com/v1/projects/{PROJECT_ID}/messages:send"

# How wide a window a single run covers. The cron runs every 15 min; we look
# back 20 min to tolerate late/slow runs without double-sending (the per-day
# dedupe stamp is the real guard against duplicates).
WINDOW_MINUTES = 20


def firebase_get(path):
    url = f"{FIREBASE_URL}/{path}.json"
    try:
        resp = urllib.request.urlopen(url)
        return json.loads(resp.read())
    except Exception as e:
        print(f"  Error reading {path}: {e}")
        return None


def firebase_put(path, value):
    url = f"{FIREBASE_URL}/{path}.json"
    data = json.dumps(value).encode()
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"  Error writing {path}: {e}")
        return False


def get_access_token(sa_info):
    """Mint an OAuth2 access token from the service account via JWT bearer grant."""
    import base64
    import hashlib
    try:
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        raise SystemExit("cryptography package required: pip install cryptography")

    def b64url(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claim = {
        "iss": sa_info["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = b64url(json.dumps(header).encode()) + b"." + b64url(json.dumps(claim).encode())

    private_key = serialization.load_pem_private_key(
        sa_info["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = signing_input + b"." + b64url(signature)

    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion.decode(),
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())["access_token"]


def send_push(token, access_token, title, body):
    message = {
        "message": {
            "token": token,
            # Data-only payload so the service worker builds the notification.
            "data": {"title": title, "body": body, "url": "/"},
            "webpush": {
                "headers": {"Urgency": "high"},
                "fcm_options": {"link": "/"},
            },
        }
    }
    data = json.dumps(message).encode()
    req = urllib.request.Request(FCM_ENDPOINT, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    try:
        urllib.request.urlopen(req)
        return True, None
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.read().decode()}"
    except Exception as e:
        return False, str(e)


def main():
    sa_raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa_raw:
        raise SystemExit("FIREBASE_SERVICE_ACCOUNT env var not set")
    sa_info = json.loads(sa_raw)
    access_token = get_access_token(sa_info)

    users = firebase_get("users") or {}
    now_utc = datetime.now(timezone.utc)

    sent = 0
    checked = 0
    for phone, u in users.items():
        if not isinstance(u, dict):
            continue
        r = u.get("reminder")
        if not isinstance(r, dict) or not r.get("enabled") or not r.get("token"):
            continue
        checked += 1

        # User's chosen local time "HH:MM" and their tz offset in minutes
        # (JS getTimezoneOffset semantics: minutes to ADD to local to get UTC,
        # i.e. IST = -330). Convert to a UTC datetime for today in their tz.
        try:
            hh, mm = [int(x) for x in r["time"].split(":")]
        except Exception:
            continue
        tz_off_min = int(r.get("tzOffset", 0))
        user_tz = timezone(timedelta(minutes=-tz_off_min))
        now_local = now_utc.astimezone(user_tz)
        today_str = now_local.strftime("%Y-%m-%d")

        # Already sent today? (dedupe)
        if r.get("lastSent") == today_str:
            continue

        target_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        # Fire if the target time is in the window [now - WINDOW, now].
        delta_min = (now_local - target_local).total_seconds() / 60.0
        if 0 <= delta_min <= WINDOW_MINUTES:
            ok, err = send_push(
                r["token"], access_token,
                "⚽ World Cup Predictor",
                "Time to set your predictions for today!",
            )
            if ok:
                firebase_put(f"users/{phone}/reminder/lastSent", today_str)
                sent += 1
                print(f"  Sent reminder to {phone} (local {now_local.strftime('%H:%M')})")
            else:
                print(f"  FAILED {phone}: {err}")
                # Drop dead tokens so we stop retrying them.
                if err and ("404" in err or "UNREGISTERED" in err or "INVALID_ARGUMENT" in err):
                    firebase_put(f"users/{phone}/reminder/enabled", False)
                    print(f"    disabled dead token for {phone}")

    print(f"Checked {checked} reminder(s), sent {sent}")


if __name__ == "__main__":
    main()
