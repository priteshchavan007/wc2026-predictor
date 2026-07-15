"""Mint a Google OAuth2 access token from a service account.

Shared by the cron scripts so they can authenticate to Firebase. A token minted
here is treated by the Realtime Database as an ADMIN credential — requests
carrying it BYPASS security rules — which is how the cron keeps writing
results/scores/fixtures after those paths are locked to read-only for clients.

Requires the FIREBASE_SERVICE_ACCOUNT env var (the full service-account JSON).
"""
import base64
import json
import time
import urllib.parse
import urllib.request

# Scopes needed to read/write the Realtime Database via REST with an OAuth token.
DB_SCOPES = (
    "https://www.googleapis.com/auth/firebase.database "
    "https://www.googleapis.com/auth/userinfo.email"
)


def get_access_token(sa_info, scope):
    """Mint an OAuth2 access token from the service account via JWT bearer grant."""
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
        "scope": scope,
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


def get_db_token(sa_raw):
    """Return an RTDB admin access token from a raw service-account JSON string,
    or None if no service account was provided (caller falls back to
    unauthenticated requests)."""
    if not sa_raw:
        return None
    return get_access_token(json.loads(sa_raw), DB_SCOPES)
