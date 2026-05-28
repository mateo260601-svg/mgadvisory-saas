from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.config import DATA_DIR


ACCOUNTS_PATH = DATA_DIR / "accounts" / "accounts.json"
PLAN_CATALOG = {
    "starter": {
        "name": "Starter",
        "monthly_price": 490,
        "currency": "EUR",
        "project_limit": 3,
        "seat_limit": 1,
        "features": ["Google SSO", "BP Builder", "Excel export"],
    },
    "professional": {
        "name": "Professional",
        "monthly_price": 1490,
        "currency": "EUR",
        "project_limit": 15,
        "seat_limit": 5,
        "features": ["Claude extraction", "BP + debt model", "PPTX outputs", "Priority support"],
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": None,
        "currency": "EUR",
        "project_limit": 999,
        "seat_limit": 50,
        "features": ["Custom templates", "Team onboarding", "Private deployment option"],
    },
}


def create_trial_account(name: str, email: str, company: str, plan: str) -> dict[str, Any]:
    email = normalize_email(email)
    if not email:
        raise ValueError("A valid professional email is required.")
    plan_key = plan if plan in PLAN_CATALOG else "professional"
    accounts = _load_accounts()
    existing = accounts.get(email, {})
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=14)
    account = {
        "email": email,
        "name": clean_text(name) or existing.get("name") or email.split("@", 1)[0],
        "company": clean_text(company) or existing.get("company") or "",
        "plan": plan_key,
        "status": existing.get("status") or "trialing",
        "billing_status": existing.get("billing_status") or "trial_required",
        "trial_started_at": existing.get("trial_started_at") or now.isoformat(),
        "trial_ends_at": existing.get("trial_ends_at") or trial_end.isoformat(),
        "created_at": existing.get("created_at") or now.isoformat(),
        "updated_at": now.isoformat(),
        "stripe_customer_id": existing.get("stripe_customer_id") or "",
        "stripe_subscription_id": existing.get("stripe_subscription_id") or "",
        "checkout_ready": False,
    }
    accounts[email] = account
    _save_accounts(accounts)
    return account


def get_account(email: str | None) -> dict[str, Any] | None:
    email = normalize_email(email or "")
    if not email:
        return None
    return _load_accounts().get(email)


def account_summary(email: str | None) -> dict[str, Any]:
    account = get_account(email)
    if not account:
        return {
            "status": "license",
            "billing_status": "not_configured",
            "plan": "demo",
            "plan_name": "Demo",
            "trial_days_left": None,
            "checkout_ready": False,
            "plans": PLAN_CATALOG,
        }
    plan = PLAN_CATALOG.get(account.get("plan"), PLAN_CATALOG["professional"])
    trial_days_left = None
    try:
        end = datetime.fromisoformat(account["trial_ends_at"])
        trial_days_left = max(0, (end - datetime.now(timezone.utc)).days)
    except Exception:
        pass
    return {
        **account,
        "plan_name": plan["name"],
        "plan_details": plan,
        "trial_days_left": trial_days_left,
        "plans": PLAN_CATALOG,
    }


def normalize_email(email: str) -> str:
    email = str(email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return ""
    return email


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:120]


def _load_accounts() -> dict[str, Any]:
    if not ACCOUNTS_PATH.exists():
        return {}
    try:
        return json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_accounts(accounts: dict[str, Any]) -> None:
    ACCOUNTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(ACCOUNTS_PATH) + ".tmp")
    tmp.write_text(json.dumps(accounts, indent=2), encoding="utf-8")
    tmp.replace(ACCOUNTS_PATH)
