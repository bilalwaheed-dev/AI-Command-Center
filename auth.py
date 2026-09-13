"""Authentication module for AI Command Center.
Provides Bearer token generation, persistence, and request verification for workers and APIs.
"""
from __future__ import annotations

import functools
import hmac
import os
import secrets
from pathlib import Path
from typing import Callable, Optional
from flask import jsonify, request

from config import DATA_DIR

TOKEN_FILE = DATA_DIR / "auth_token.secret"
ENV_FILE = Path(__file__).resolve().parent / ".env"


def get_or_create_auth_token() -> str:
    """Retrieve existing auth token or generate and persist a new local secret."""
    # 1. Environment variable override
    env_token = os.getenv("COMMAND_CENTER_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    # 2. Existing secret file
    if TOKEN_FILE.exists():
        try:
            token = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception:
            pass

    # 3. Generate new secure development token
    token = f"cc_tok_{secrets.token_urlsafe(24)}"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        TOKEN_FILE.write_text(token, encoding="utf-8")
        # On POSIX, set 0600 permissions
        if hasattr(os, "chmod"):
            try:
                os.chmod(TOKEN_FILE, 0o600)
            except Exception:
                pass
    except Exception as e:
        print(f"Warning: could not write {TOKEN_FILE}: {e}")

    # Also append/write to .env for local tooling
    try:
        if not ENV_FILE.exists() or "COMMAND_CENTER_TOKEN" not in ENV_FILE.read_text(encoding="utf-8"):
            with open(ENV_FILE, "a", encoding="utf-8") as f:
                f.write(f"\nCOMMAND_CENTER_TOKEN={token}\n")
    except Exception:
        pass

    return token


def rotate_auth_token() -> str:
    """Generate and persist a new Bearer token, replacing any existing secret."""
    new_token = f"cc_tok_{secrets.token_urlsafe(24)}"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(new_token, encoding="utf-8")
    if hasattr(os, "chmod"):
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except Exception:
            pass

    # Update .env
    lines = []
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                if not line.startswith("COMMAND_CENTER_TOKEN="):
                    lines.append(line)
        except Exception:
            pass
    lines.append(f"COMMAND_CENTER_TOKEN={new_token}")
    try:
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass

    os.environ["COMMAND_CENTER_TOKEN"] = new_token
    global ACTIVE_AUTH_TOKEN
    ACTIVE_AUTH_TOKEN = new_token
    return new_token


ACTIVE_AUTH_TOKEN = get_or_create_auth_token()


def validate_token(provided_token: Optional[str]) -> bool:
    """Validate a provided token in constant time."""
    if not provided_token:
        return False
    current_token = get_or_create_auth_token()
    return hmac.compare_digest(provided_token.strip(), current_token.strip())


def extract_token_from_request() -> Optional[str]:
    """Extract token from Authorization header, X-Worker-Token, or query parameter."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    x_token = request.headers.get("X-Worker-Token", "")
    if x_token.strip():
        return x_token.strip()

    # Fallback to query parameter (e.g. for browser testing or SSE)
    query_token = request.args.get("token", "")
    if query_token.strip():
        return query_token.strip()

    return None


def require_auth(func: Callable) -> Callable:
    """Decorator to enforce Bearer token authentication on API routes."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Allow disabling auth via environment if explicitly requested
        auth_enabled = os.getenv("COMMAND_CENTER_AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
        if not auth_enabled:
            return func(*args, **kwargs)

        token = extract_token_from_request()
        if not token or not validate_token(token):
            return jsonify({
                "error": "Unauthorized: Invalid or missing Bearer token",
                "hint": "Pass 'Authorization: Bearer <token>' header"
            }), 401

        return func(*args, **kwargs)
    return wrapper
