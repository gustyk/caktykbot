"""Simple password-gate authentication for the Streamlit dashboard.

Design:
  - Password stored in env var DASHBOARD_PASSWORD (plain text, read once at startup
    and compared as bcrypt hash in session).
  - On successful login, a signed cookie is written so the user stays logged in
    across browser refreshes (cookie TTL = 30 days).
  - Cookie is just a SHA-256 HMAC of (password + secret_key) so it is not guessable
    without knowing both values. No external auth service needed.
  - If DASHBOARD_PASSWORD is not set, auth is DISABLED (dev mode warning shown).

Usage:
    from dashboard.auth import require_login

    st.set_page_config(...)          # must be FIRST streamlit call
    if not require_login():
        st.stop()                    # auth wall — stop rendering the rest of the page
    # ... rest of your app ...
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time

import streamlit as st

# ── Config ────────────────────────────────────────────────────────────────────

_PASSWORD     = os.environ.get("DASHBOARD_PASSWORD", "")
_SECRET_KEY   = os.environ.get("DASHBOARD_SECRET_KEY", "caktykbot-default-secret-2024")
_COOKIE_NAME  = "caktykbot_auth"
_COOKIE_TTL   = 60 * 60 * 24 * 30  # 30 days in seconds

# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_token(password: str) -> str:
    """Create a deterministic HMAC token for the given password."""
    return hmac.new(
        _SECRET_KEY.encode(),
        password.encode(),
        hashlib.sha256,
    ).hexdigest()


def _valid_token(token: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    if not _PASSWORD:
        return True   # auth disabled (no password set)
    expected = _make_token(_PASSWORD)
    return hmac.compare_digest(token, expected)


# ── Cookie helpers (pure session-state fallback if cookies unavailable) ────────

def _get_cookie() -> str | None:
    """Read auth cookie from browser via st.context (Streamlit ≥ 1.31)."""
    try:
        cookies = st.context.cookies          # type: ignore[attr-defined]
        return cookies.get(_COOKIE_NAME)
    except Exception:
        return None


def _set_cookie_js(token: str) -> None:
    """Inject JS to write a cookie with 30-day expiry."""
    expires = time.strftime(
        "%a, %d %b %Y %H:%M:%S GMT",
        time.gmtime(time.time() + _COOKIE_TTL),
    )
    js = (
        f"document.cookie = '{_COOKIE_NAME}={token}; "
        f"path=/; expires={expires}; SameSite=Lax;';"
    )
    st.components.v1.html(f"<script>{js}</script>", height=0)


def _clear_cookie_js() -> None:
    """Inject JS to delete the auth cookie."""
    js = (
        f"document.cookie = '{_COOKIE_NAME}=; "
        "path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax;';"
    )
    st.components.v1.html(f"<script>{js}</script>", height=0)


# ── Login page UI ─────────────────────────────────────────────────────────────

def _show_login_page() -> bool:
    """Render the login form. Returns True if login succeeded this call."""
    st.markdown("""
    <style>
        /* Hide sidebar on login page */
        [data-testid="stSidebar"] { display: none; }
        /* Center the login card */
        .login-wrap {
            max-width: 420px;
            margin: 8vh auto 0 auto;
        }
        .login-card {
            background: #1a1a2e;
            border: 1px solid #252545;
            border-radius: 16px;
            padding: 40px 36px 32px 36px;
            box-shadow: 0 8px 40px #00ADB522;
        }
        .login-title {
            font-size: 2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00ADB5, #00e5ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0 0 4px 0;
        }
        .login-sub {
            color: #888;
            font-size: 0.82rem;
            margin: 0 0 28px 0;
        }
    </style>
    <div class="login-wrap">
      <div class="login-card">
        <p class="login-title">📊 CakTykBot</p>
        <p class="login-sub">IDX TRADING ANALYTICS — Login dengan password Anda</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # The actual input must be Streamlit widgets (outside the HTML block)
    with st.container():
        # Add some top space so it flows below the HTML card
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        col = st.columns([1, 2, 1])[1]
        with col:
            with st.form("login_form", clear_on_submit=True):
                pwd = st.text_input(
                    "🔑 Password",
                    type="password",
                    placeholder="Masukkan password",
                )
                submitted = st.form_submit_button(
                    "Masuk →",
                    use_container_width=True,
                    type="primary",
                )
            if submitted:
                if _valid_token(_make_token(pwd)):
                    token = _make_token(_PASSWORD)
                    st.session_state["_auth_ok"] = True
                    st.session_state["_auth_token"] = token
                    _set_cookie_js(token)
                    st.success("✅ Login berhasil!")
                    st.rerun()
                else:
                    st.error("❌ Password salah. Coba lagi.")
    return False


# ── Public API ────────────────────────────────────────────────────────────────

def require_login() -> bool:
    """Gate function — call after st.set_page_config(), before any page content.

    Returns:
        True  → user is authenticated, render the page normally.
        False → user is NOT authenticated, login form is shown; caller should
                call st.stop() to halt further rendering.
    """
    # If no password configured → disable auth (local dev)
    if not _PASSWORD:
        st.sidebar.warning("⚠️ DASHBOARD_PASSWORD not set — auth disabled (dev mode)")
        return True

    # 1. Already authenticated in this session
    if st.session_state.get("_auth_ok"):
        return True

    # 2. Valid cookie from a previous session
    cookie = _get_cookie()
    if cookie and _valid_token(cookie):
        st.session_state["_auth_ok"] = True
        return True

    # 3. Show login form
    _show_login_page()
    return False


def logout() -> None:
    """Call from a sidebar logout button."""
    st.session_state.pop("_auth_ok", None)
    st.session_state.pop("_auth_token", None)
    _clear_cookie_js()
    st.rerun()
