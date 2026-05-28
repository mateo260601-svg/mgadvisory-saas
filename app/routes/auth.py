import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from app.config import (
    APP_SECRET,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_ALLOWED_DOMAINS,
    GOOGLE_REDIRECT_URI,
    LICENSE_KEY,
)
from app.services.account_service import account_summary, create_trial_account


router = APIRouter(tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES = "openid email profile"
COOKIE_NAME = "mg_google_user"
LICENSE_ACCOUNT = "license:local-demo"


class LoginRequest(BaseModel):
    license_key: str


class RegisterRequest(BaseModel):
    name: str = ""
    email: str
    company: str = ""
    plan: str = "professional"


@router.post("/api/auth/login")
def login(payload: LoginRequest):
    if payload.license_key.strip() != LICENSE_KEY:
        raise HTTPException(status_code=401, detail="Invalid license key")
    return {"ok": True, "token": "local-demo-token", "license": "valid"}


@router.post("/api/auth/register")
def register(payload: RegisterRequest):
    try:
        account = create_trial_account(payload.name, payload.email, payload.company, payload.plan)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    response = JSONResponse(
        {
            "ok": True,
            "user": {
                "email": account["email"],
                "name": account["name"],
                "picture": "",
            },
            "account": account_summary(account["email"]),
        }
    )
    response.set_cookie(
        COOKIE_NAME,
        _sign_payload(
            {
                "email": account["email"],
                "name": account["name"],
                "picture": "",
                "ts": int(time.time()),
            }
        ),
        httponly=True,
        secure=GOOGLE_REDIRECT_URI.startswith("https://"),
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )
    return response


@router.get("/api/auth/google/status")
def google_status():
    configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI)
    return {
        "configured": configured,
        "redirect_uri": GOOGLE_REDIRECT_URI if configured else "",
        "scopes": GOOGLE_SCOPES,
        "domain_restricted": bool(GOOGLE_ALLOWED_DOMAINS),
    }


@router.get("/api/auth/google/url")
def google_login_url():
    _require_google_config()
    state = _sign_payload({"ts": int(time.time()), "nonce": hashlib.sha256(str(time.time()).encode()).hexdigest()[:24]})
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    return {"url": f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"}


@router.get("/auth/callback")
@router.get("/auth/google/callback")
def google_callback(request: Request):
    _require_google_config()
    error = request.query_params.get("error")
    if error:
        return RedirectResponse(url=f"/?google_auth=error&reason={urllib.parse.quote(error)}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return RedirectResponse(url="/?google_auth=error&reason=direct_callback")
    if not _verify_signed_payload(state, max_age_seconds=600):
        return RedirectResponse(url="/?google_auth=error&reason=invalid_state")

    try:
        token_payload = _post_form(
            GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return RedirectResponse(url="/?google_auth=error&reason=token_exchange_failed")

    access_token = token_payload.get("access_token")
    if not access_token:
        return RedirectResponse(url="/?google_auth=error&reason=missing_token")

    try:
        user = _get_json(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return RedirectResponse(url="/?google_auth=error&reason=userinfo_failed")

    email = user.get("email")
    if not email:
        return RedirectResponse(url="/?google_auth=error&reason=missing_email")
    if not _is_allowed_email(email):
        return RedirectResponse(url="/?google_auth=error&reason=email_domain_not_allowed")

    response = RedirectResponse(url="/?google_auth=success")
    response.set_cookie(
        COOKIE_NAME,
        _sign_payload(
            {
                "email": email,
                "name": user.get("name", ""),
                "picture": user.get("picture", ""),
                "ts": int(time.time()),
            }
        ),
        httponly=True,
        secure=GOOGLE_REDIRECT_URI.startswith("https://"),
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )
    return response


@router.get("/api/auth/google/me")
def google_me(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    payload = _verify_signed_payload(cookie, max_age_seconds=7 * 24 * 60 * 60) if cookie else None
    if not payload:
        raise HTTPException(status_code=401, detail="Not signed in with Google")
    return {"ok": True, "user": payload}


@router.get("/api/auth/session")
def session(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    payload = _verify_signed_payload(cookie, max_age_seconds=7 * 24 * 60 * 60) if cookie else None
    if not payload:
        return {"ok": False, "method": None, "user": None}
    return {"ok": True, "method": "google", "user": payload, "account": account_summary(payload.get("email"))}


@router.get("/api/auth/account")
def account_status(request: Request):
    return {"ok": True, "account": account_summary(account_from_request(request))}


def account_from_request(request: Request) -> str:
    cookie = request.cookies.get(COOKIE_NAME)
    payload = _verify_signed_payload(cookie, max_age_seconds=7 * 24 * 60 * 60) if cookie else None
    if payload and payload.get("email"):
        return str(payload["email"]).strip().lower()
    account = request.headers.get("X-MG-Account", "").strip().lower()
    return account or LICENSE_ACCOUNT


@router.post("/api/auth/google/logout")
def google_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


def _require_google_config() -> None:
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI):
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI.",
        )


def _is_allowed_email(email: str) -> bool:
    if not GOOGLE_ALLOWED_DOMAINS:
        return True
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in GOOGLE_ALLOWED_DOMAINS


def _post_form(url: str, data: dict) -> dict:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _sign_payload(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    signature = hmac.new(APP_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _verify_signed_payload(token: str | None, max_age_seconds: int) -> dict | None:
    if not token or "." not in token:
        return None
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(APP_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    ts = int(payload.get("ts", 0))
    if not ts or time.time() - ts > max_age_seconds:
        return None
    return payload
