"""
CHI Insurance Quote Engine — Lock Screen
==========================================
Shown when trial quota is exhausted.
Professional, persuasive, with clear CTA.
"""

import streamlit as st

from trial_lock import (
    BROKER_NAME, BROKER_COMPANY, BROKER_TEL,
    BROKER_EMAIL, BROKER_WHATSAPP, TRIAL_LIMIT
)


def show_lock_screen():
    """Render the full-page lock screen. Call instead of main content."""

    st.markdown("""
    <style>
    /* Hide Streamlit chrome */
    header[data-testid="stHeader"] { display:none }
    #MainMenu, footer { visibility: hidden }
    .lock-outer {
        display:flex; flex-direction:column; align-items:center;
        justify-content:center; min-height:85vh;
        font-family:'Georgia', serif;
    }
    .lock-card {
        background: linear-gradient(145deg, #0F2638 0%, #1C3F5E 60%, #0F2638 100%);
        border: 1px solid #00B4D840;
        border-radius: 20px;
        padding: 52px 60px;
        max-width: 680px;
        width: 100%;
        text-align: center;
        box-shadow: 0 24px 80px rgba(0,0,0,0.45);
    }
    .lock-icon { font-size: 56px; margin-bottom: 8px; }
    .lock-title {
        font-size: 28px; font-weight: 700;
        color: #FFFFFF; margin: 16px 0 8px;
        letter-spacing: -0.5px;
    }
    .lock-subtitle {
        font-size: 16px; color: #00B4D8;
        font-style: italic; margin-bottom: 28px;
    }
    .lock-body {
        font-size: 15px; color: #C8D8E8;
        line-height: 1.7; margin-bottom: 36px;
    }
    .lock-body strong { color: #F5D679; }
    .lock-divider {
        border: none; border-top: 1px solid #00B4D840;
        margin: 0 0 32px;
    }
    .contact-grid {
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 14px; margin-bottom: 32px;
    }
    .contact-item {
        background: rgba(0,180,216,0.08);
        border: 1px solid #00B4D830;
        border-radius: 12px;
        padding: 18px 16px;
    }
    .contact-label {
        font-size: 10px; text-transform: uppercase;
        letter-spacing: 1.5px; color: #00B4D8;
        margin-bottom: 6px;
    }
    .contact-value {
        font-size: 15px; font-weight: 600;
        color: #FFFFFF;
    }
    .cta-phone {
        display: block;
        background: linear-gradient(135deg, #F59E0B, #FBBF24);
        color: #0F2638 !important;
        font-weight: 700; font-size: 17px;
        padding: 18px 32px; border-radius: 50px;
        text-decoration: none;
        margin-bottom: 14px;
        transition: transform .15s;
    }
    .cta-phone:hover { transform: scale(1.03); }
    .cta-email {
        display: block;
        background: transparent;
        border: 2px solid #00B4D8;
        color: #00B4D8 !important;
        font-weight: 600; font-size: 15px;
        padding: 14px 32px; border-radius: 50px;
        text-decoration: none;
        margin-bottom: 14px;
    }
    .cta-whatsapp {
        display: block;
        background: rgba(37,211,102,0.12);
        border: 2px solid #25D366;
        color: #25D366 !important;
        font-weight: 600; font-size: 15px;
        padding: 14px 32px; border-radius: 50px;
        text-decoration: none;
    }
    .lock-footer {
        font-size: 12px; color: #4A6580;
        margin-top: 28px; font-style: italic;
    }
    .badge {
        display: inline-block;
        background: rgba(245,159,11,0.15);
        border: 1px solid #F59E0B50;
        color: #F5D679;
        font-size: 11px; font-weight: 600;
        padding: 4px 14px; border-radius: 20px;
        letter-spacing: .5px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="lock-outer">
      <div class="lock-card">

        <div class="lock-icon">🔒</div>
        <div class="badge">ΔΟΚΙΜΑΣΤΙΚΗ ΕΚΔΟΣΗ — ΕΛΗΞΕ</div>

        <div class="lock-title">Ευχαριστούμε που δοκιμάσατε<br>το CHI Quote Engine!</div>
        <div class="lock-subtitle">
          Έχετε δημιουργήσει και τις {TRIAL_LIMIT} δωρεάν παρουσιάσεις.
        </div>

        <div class="lock-body">
          Ελπίζουμε ότι είδατε πόσο πολύ
          <strong>εξοικονομεί χρόνο</strong> η εφαρμογή
          και πόσο <strong>επαγγελματικές</strong> είναι οι παρουσιάσεις
          που παράγει.<br><br>
          Για να αποκτήσετε πλήρη πρόσβαση —
          <strong>απεριόριστες παρουσιάσεις</strong>,
          CRM παρακολούθησης πελατών, ανάλυση policy wording
          και 10 θέματα παρουσίασης — επικοινωνήστε μαζί μας.
        </div>

        <hr class="lock-divider">

        <div class="contact-grid">
          <div class="contact-item">
            <div class="contact-label">Σύμβουλος</div>
            <div class="contact-value">{BROKER_NAME}</div>
          </div>
          <div class="contact-item">
            <div class="contact-label">Εταιρεία</div>
            <div class="contact-value">{BROKER_COMPANY}</div>
          </div>
        </div>

        <a class="cta-phone" href="tel:{BROKER_TEL}">
          📞 &nbsp; Καλέστε τώρα &nbsp; {BROKER_TEL}
        </a>
        <a class="cta-whatsapp" href="{BROKER_WHATSAPP}" target="_blank">
          💬 &nbsp; WhatsApp
        </a>
        <a class="cta-email" href="mailto:{BROKER_EMAIL}?subject=Αγορά CHI Quote Engine&body=Γεια σας, θα ήθελα να αγοράσω πλήρη πρόσβαση στο CHI Quote Engine.">
          ✉️ &nbsp; {BROKER_EMAIL}
        </a>

        <div class="lock-footer">
          CHI Insurance Brokers &nbsp;·&nbsp;
          Αυτόματη Σύγκριση & Παρουσίαση Ασφαλιστικών Προσφορών
        </div>

      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


def show_trial_banner():
    """Subtle banner shown during trial — top of every page."""
    status = __import__("trial_lock").get_trial_status()
    remaining = status["remaining"]
    used      = status["count"]

    if remaining <= 2:
        color, icon = "#EF4444", "🔴"
    elif remaining <= 4:
        color, icon = "#F59E0B", "🟡"
    else:
        color, icon = "#10B981", "🟢"

    # Progress bar (used / limit)
    pct = int(used / status["limit"] * 100)

    st.markdown(f"""
    <div style='background:#0F2638;border:1px solid {color}40;
                border-radius:10px;padding:10px 18px;
                margin-bottom:16px;display:flex;
                align-items:center;gap:16px;flex-wrap:wrap'>
      <span style='font-size:13px;color:#94A3B8'>
        {icon} <strong style='color:{color}'>Δοκιμαστική Έκδοση</strong>
        &nbsp;—&nbsp; Απομένουν <strong style='color:#FFFFFF'>{remaining}</strong>
        από {status['limit']} δωρεάν παρουσιάσεις
      </span>
      <div style='flex:1;min-width:120px;background:#1E3A52;
                  border-radius:4px;height:6px;overflow:hidden'>
        <div style='width:{pct}%;background:{color};height:100%;
                    border-radius:4px;transition:width .3s'></div>
      </div>
      <span style='font-size:11px;color:#64748B;white-space:nowrap'>
        Επικοινωνήστε: <strong style='color:#00B4D8'>+30 697 590 0189</strong>
      </span>
    </div>
    """, unsafe_allow_html=True)
