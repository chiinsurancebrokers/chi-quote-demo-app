"""
CHI Insurance Quote Engine — Email Gate & Trial System
=======================================================
Per-email trial tracking stored in SQLite.
Each email gets TRIAL_LIMIT free quotes — tracked on the SERVER,
so clearing cookies / incognito / new device does NOT reset the counter.

Flow:
  1. User opens app → sees registration screen (name + email)
  2. If email is new → created with 0 quotes used
  3. If email exists and not locked → continues from where they left off
  4. After TRIAL_LIMIT quotes → lock screen with contact CTA
  5. Admin can see all registrations in the Streamlit Cloud logs
     or by reading the SQLite file directly
"""

import re
import sqlite3
import streamlit as st
from datetime import datetime
from pathlib import Path

# ─── CONFIG ──────────────────────────────────────────────────────────
TRIAL_LIMIT     = 7

BROKER_NAME     = "Ιατρόπουλος Χρήστος"
BROKER_COMPANY  = "CHI Insurance Brokers"
BROKER_TEL      = "+30 697 590 0189"
BROKER_EMAIL    = "info@chiinsurancebrokers.com"
BROKER_WHATSAPP = "https://wa.me/306975900189"

DB_PATH = Path(__file__).parent / ".email_gate.db"


# ─── DATABASE ────────────────────────────────────────────────────────

def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("""
        CREATE TABLE IF NOT EXISTS trial_users (
            email       TEXT PRIMARY KEY,
            name        TEXT,
            company     TEXT,
            phone       TEXT,
            quotes_used INTEGER DEFAULT 0,
            locked      INTEGER DEFAULT 0,
            registered_at TEXT,
            last_active   TEXT,
            notified_at   TEXT
        )
    """)
    con.commit()
    return con


def _get_user(email: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM trial_users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
    return dict(row) if row else None


def _create_user(email: str, name: str, company: str = "", phone: str = "") -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            """INSERT OR IGNORE INTO trial_users
               (email, name, company, phone, quotes_used, locked, registered_at, last_active)
               VALUES (?, ?, ?, ?, 0, 0, ?, ?)""",
            (email.lower().strip(), name, company, phone, now, now)
        )
    return _get_user(email)


def _increment(email: str) -> dict:
    now = datetime.now().isoformat(timespec="seconds")
    with _conn() as con:
        con.execute(
            """UPDATE trial_users
               SET quotes_used = quotes_used + 1,
                   last_active  = ?,
                   locked       = CASE WHEN quotes_used + 1 >= ? THEN 1 ELSE 0 END
               WHERE email = ?""",
            (now, TRIAL_LIMIT, email.lower().strip())
        )
    return _get_user(email)


def get_all_registrations() -> list[dict]:
    """Admin view — all trial users."""
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trial_users ORDER BY registered_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ─── VALIDATION ──────────────────────────────────────────────────────

def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()))


# ─── STREAMLIT SESSION HELPERS ───────────────────────────────────────

def get_session_user() -> dict | None:
    return st.session_state.get("_gate_user")


def set_session_user(user: dict):
    st.session_state["_gate_user"] = user


def increment_quote() -> dict:
    """Call after every successful PPTX generation."""
    user = get_session_user()
    if not user:
        return {}
    updated = _increment(user["email"])
    set_session_user(updated)
    return updated


def is_locked() -> bool:
    user = get_session_user()
    if not user:
        return False
    return bool(user.get("locked")) or user.get("quotes_used", 0) >= TRIAL_LIMIT


def remaining_quotes() -> int:
    user = get_session_user()
    if not user:
        return 0
    return max(0, TRIAL_LIMIT - user.get("quotes_used", 0))


# ─── REGISTRATION SCREEN ─────────────────────────────────────────────

def show_registration_gate():
    """
    Full-page registration form shown before the app.
    Returns only after the user has successfully registered / logged in.
    If already registered (session), returns immediately.
    """
    # Already logged in this session
    if get_session_user():
        user = get_session_user()
        # Re-check DB for latest count (handles multi-tab)
        fresh = _get_user(user["email"])
        if fresh:
            set_session_user(fresh)
        return

    st.markdown("""
    <style>
    header[data-testid="stHeader"]{display:none}
    #MainMenu,footer{visibility:hidden}
    .gate-wrap{
        display:flex;align-items:center;justify-content:center;
        min-height:90vh;
    }
    .gate-card{
        background:linear-gradient(160deg,#0F2638 0%,#1C3F5E 100%);
        border:1px solid #00B4D840;border-radius:20px;
        padding:48px 52px;max-width:520px;width:100%;
        box-shadow:0 20px 60px rgba(0,0,0,.4);
    }
    .gate-logo{font-size:40px;text-align:center;margin-bottom:4px}
    .gate-title{
        font-size:24px;font-weight:700;color:#fff;
        text-align:center;margin:12px 0 6px;font-family:Georgia,serif
    }
    .gate-sub{
        font-size:14px;color:#00B4D8;text-align:center;
        font-style:italic;margin-bottom:28px
    }
    .gate-features{
        background:rgba(0,180,216,0.07);border:1px solid #00B4D820;
        border-radius:12px;padding:16px 20px;margin-bottom:28px
    }
    .gate-feature{
        font-size:13px;color:#C8D8E8;padding:4px 0;
    }
    .gate-feature span{color:#00B4D8;margin-right:8px}
    .gate-footer{
        font-size:11px;color:#4A6580;text-align:center;
        margin-top:20px;font-style:italic
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="gate-wrap">
      <div class="gate-card">
        <div class="gate-logo">🛡️</div>
        <div class="gate-title">CHI Insurance Quote Engine</div>
        <div class="gate-sub">Δωρεάν δοκιμή — 7 παρουσιάσεις χωρίς χρέωση</div>
        <div class="gate-features">
          <div class="gate-feature"><span>✓</span>Αυτόματη ανάλυση PDF προσφορών με AI</div>
          <div class="gate-feature"><span>✓</span>Έτοιμη PPTX παρουσίαση σε 2 λεπτά</div>
          <div class="gate-feature"><span>✓</span>Bilingual (ελληνικά & αγγλικά)</div>
          <div class="gate-feature"><span>✓</span>10 επαγγελματικά θέματα παρουσίασης</div>
          <div class="gate-feature"><span>✓</span>Ανάλυση εξαιρέσεων από policy wording</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Form — rendered below the card HTML (Streamlit limitation)
    st.markdown("### 📋 Συμπλήρωσε τα στοιχεία σου για να ξεκινήσεις")

    with st.form("gate_form", clear_on_submit=False):
        name    = st.text_input("Ονοματεπώνυμο *", placeholder="Παπαδόπουλος Νίκος")
        email   = st.text_input("Email *",          placeholder="nikos@insurance.gr")
        company = st.text_input("Εταιρεία / Γραφείο", placeholder="Παπαδόπουλος Insurance")
        phone   = st.text_input("Τηλέφωνο",          placeholder="+30 69X XXX XXXX")

        st.caption(
            "Τα στοιχεία σου χρησιμοποιούνται μόνο για να παρακολουθούμε τη δοκιμαστική "
            "περίοδο. Δεν αποστέλλονται σε τρίτους."
        )
        submitted = st.form_submit_button(
            "🚀 Ξεκίνα τη Δωρεάν Δοκιμή",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        # Validation
        if not name.strip():
            st.error("Το ονοματεπώνυμο είναι υποχρεωτικό.")
            st.stop()
        if not email.strip() or not _valid_email(email):
            st.error("Βάλε έγκυρο email.")
            st.stop()

        # Check existing user
        existing = _get_user(email)
        if existing:
            if existing["locked"]:
                # Already exhausted — go straight to lock screen
                set_session_user(existing)
                st.rerun()
            else:
                used = existing["quotes_used"]
                left = TRIAL_LIMIT - used
                set_session_user(existing)
                st.success(
                    f"Καλώς ήρθες πάλι, **{existing['name']}**! "
                    f"Έχεις χρησιμοποιήσει {used}/{TRIAL_LIMIT} παρουσιάσεις. "
                    f"Απομένουν **{left}**."
                )
                st.rerun()
        else:
            # New user
            user = _create_user(email, name.strip(), company.strip(), phone.strip())
            set_session_user(user)
            st.success(f"Καλώς ήρθες, **{name.strip()}**! Έχεις **{TRIAL_LIMIT}** δωρεάν παρουσιάσεις.")
            st.rerun()

    st.stop()   # Block the rest of the app until registration complete


# ─── TRIAL BANNER ────────────────────────────────────────────────────

def show_trial_banner():
    """Progress bar shown at top of every page after login."""
    user = get_session_user()
    if not user:
        return

    used      = user.get("quotes_used", 0)
    remaining = max(0, TRIAL_LIMIT - used)
    pct       = int(used / TRIAL_LIMIT * 100)

    if remaining <= 2:
        color, icon = "#EF4444", "🔴"
    elif remaining <= 4:
        color, icon = "#F59E0B", "🟡"
    else:
        color, icon = "#10B981", "🟢"

    st.markdown(f"""
    <div style='background:#0F2638;border:1px solid {color}40;
                border-radius:10px;padding:10px 18px;margin-bottom:16px;
                display:flex;align-items:center;gap:16px;flex-wrap:wrap'>
      <span style='font-size:13px;color:#94A3B8'>
        {icon} <strong style='color:{color}'>Δοκιμαστική Έκδοση</strong>
        &nbsp;·&nbsp;
        <span style='color:#fff'>{user.get("name","")}</span>
        &nbsp;—&nbsp; Απομένουν
        <strong style='color:#fff'>{remaining}</strong> από {TRIAL_LIMIT} παρουσιάσεις
      </span>
      <div style='flex:1;min-width:120px;background:#1E3A52;
                  border-radius:4px;height:6px;overflow:hidden'>
        <div style='width:{pct}%;background:{color};height:100%;
                    border-radius:4px'></div>
      </div>
      <span style='font-size:11px;color:#64748B;white-space:nowrap'>
        📞 <strong style='color:#00B4D8'>{BROKER_TEL}</strong>
      </span>
    </div>
    """, unsafe_allow_html=True)
