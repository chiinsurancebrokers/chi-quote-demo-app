"""
CHI Insurance Brokers — Αυτόματη Δημιουργία Παρουσίασης
Εκκίνηση: streamlit run app.py
"""

import hashlib
import time
from datetime import datetime

import streamlit as st

from config import BROKER_DEFAULTS, INTER_FILE_DELAY
from extraction import compute_score, compute_premium_efficiency, extract_insurance_data
from analysis import generate_recommendation_analysis
from terms_analyzer import analyze_terms_pdf
from language_profiles import detect_pdf_language, detect_client_language, get_profile
from pptx_builder import generate_pptx
from email_gate import (
    show_registration_gate, show_trial_banner,
    increment_quote, is_locked, remaining_quotes
)
from lock_screen import show_lock_screen
from greek_insurers import detect_comparison_mode, NOT_AVAILABLE_IN_GREEK, GREEK_SPECIFIC_FIELDS, is_greek_insurer, localize_insurance_data


st.set_page_config(
    page_title="CHI Insurance — Παρουσιάσεις",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    # ── GLOBAL STYLES ────────────────────────────────────────────────
    st.markdown("""
    <style>
    .main { background: #F4F9FF; }
    .stButton > button {
        background: #1C3F5E; color: white; border-radius: 8px;
        font-weight: bold; padding: 0.6em 2em; border: none;
    }
    .stButton > button:hover { background: #00B4D8; }
    div[data-testid="stFileUploader"] {
        border: 2px dashed #00B4D8; border-radius: 8px; padding: 1em;
    }
    </style>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 5])
    with c1:
        st.markdown("# 🛡️")
    with c2:
        st.markdown("## CHI Insurance Brokers")
        st.markdown("*Αυτόματη Δημιουργία Παρουσιάσεων Ασφάλισης*")
    st.divider()

    # ── GATE 1: Registration (email) ─────────────────────────────────
    show_registration_gate()   # blocks until user submits email

    # ── GATE 2: Lock screen if quota exhausted ───────────────────────
    if is_locked():
        show_lock_screen()     # st.stop() inside

    show_trial_banner()

    # ── TOP-LEVEL NAVIGATION ─────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 📌 Σελίδα")
        page = st.radio(
            "nav", ["🏠 Quote Engine"],
            label_visibility="collapsed"
        )

    # ── SIDEBAR ──────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Ρυθμίσεις")

        # API key — prefer secrets, fall back to text input
        _secret_key = (
            st.secrets.get("Claude_API_Key")
            or st.secrets.get("ANTHROPIC_API_KEY")
            or st.secrets.get("claude_api_key")
            or ""
        )
        if _secret_key:
            api_key = _secret_key
            st.success("🔑 API Key φορτώθηκε αυτόματα", icon="✅")
        else:
            api_key = st.text_input(
                "🔑 Claude API Key", type="password",
                help="Ή πρόσθεσέ το στο Secrets ως: Claude_API_Key = 'sk-ant-...'"
            )

        st.markdown("---")
        st.markdown("### 🖼️ Λογότυπο")
        logo_file  = st.file_uploader(
            "Ανέβασε λογότυπο (PNG / JPG)",
            type=["png", "jpg", "jpeg"],
            help="Προαιρετικό. Εμφανίζεται στην κεντρική σελίδα της παρουσίασης."
        )
        logo_bytes = logo_file.read() if logo_file else None

        st.markdown("---")
        st.markdown("### 🎨 Θέμα Παρουσίασης")

        from themes import list_themes
        all_themes = list_themes()

        # Visual swatch preview using HTML
        swatch_html = "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px'>"
        for tk, td in all_themes:
            colors = td.get("preview", ["#1C3F5E","#00B4D8","#F59E0B","#F4F9FF"])
            dots   = "".join(
                f"<span style='display:inline-block;width:14px;height:14px;"
                f"border-radius:50%;background:{c};border:1px solid #ccc'></span>"
                for c in colors
            )
            swatch_html += (
                f"<div style='display:flex;align-items:center;gap:4px;"
                f"font-size:11px;color:#444'>{td['emoji']} {dots}</div>"
            )
        swatch_html += "</div>"
        st.markdown(swatch_html, unsafe_allow_html=True)

        theme_options = {f"{td['emoji']} {td['name']}": tk for tk, td in all_themes}
        selected_label = st.selectbox(
            "Επίλεξε θέμα",
            list(theme_options.keys()),
            help="Το θέμα επηρεάζει τα χρώματα όλων των slides — εξώφυλλο, πίνακες, ανάλυση"
        )
        selected_theme = theme_options[selected_label]
        # Show description of selected theme
        sel_theme_data = dict(all_themes)[selected_theme]
        st.caption(f"_{sel_theme_data['description']}_")
        broker_name  = st.text_input("Όνομα",    value=BROKER_DEFAULTS["name"])
        broker_tel   = st.text_input("Τηλέφωνο", value=BROKER_DEFAULTS["tel"])
        broker_email = st.text_input("Email",     value=BROKER_DEFAULTS["email"])

        st.markdown("---")
        st.markdown("### 👥 Στοιχεία Πελάτη")
        client_name  = st.text_input("Ονοματεπώνυμο *", placeholder="π.χ. Φιλοξενίδης Σταύρος")
        client_email = st.text_input("Email πελάτη",   placeholder="stavros@example.com")
        client_phone = st.text_input("Τηλέφωνο",       placeholder="+30 69X XXX XXXX")

        # Language of the output (analysis + PPTX)
        st.markdown("**🌐 Γλώσσα Παρουσίασης**")
        lang_choice = st.selectbox(
            "Γλώσσα εξόδου",
            ["Ελληνικά (GR)", "English (EN)"],
            help="Επιλέξτε βάσει εθνικότητας του πελάτη. "
                 "Αυτόματη ανίχνευση από τα PDF αν αφεθεί default."
        )
        client_lang = "el" if "GR" in lang_choice else "en"

        st.markdown("**Μέλη:**")
        n_members = st.number_input("Αριθμός μελών", 1, 6, 2)
        members = []
        for i in range(n_members):
            mc1, mc2 = st.columns(2)
            with mc1:
                age = st.number_input(
                    f"Ηλικία #{i + 1}", 0, 99,
                    30 if i == 0 else 17, key=f"age_{i}"
                )
            with mc2:
                role = st.selectbox(
                    "Ρόλος",
                    ["Κύρια Ασφαλισμένη", "Κύριος Ασφαλισμένος",
                     "Εξαρτώμενο Μέλος", "Σύζυγος"],
                    key=f"role_{i}"
                )
            members.append({"age": age, "role": role})

    # ── PDF UPLOAD ───────────────────────────────────────────────────
    st.markdown("### 📄 Φόρτωσε τις Ασφαλιστικές Προσφορές (PDF)")
    st.info("Φόρτωσε 2–4 PDF προσφορές. Το Claude θα εξάγει αυτόματα όλα τα στοιχεία.", icon="ℹ️")

    uploaded_files = st.file_uploader(
        "Επίλεξε PDF αρχεία", type="pdf", accept_multiple_files=True,
        help="Ανέβασε τις προσφορές Generali, Morgan Price, NOW Health κ.λπ."
    )

    # ── TERMS / POLICY WORDING UPLOAD ───────────────────────────────
    st.markdown("### 📑 Policy Wording / Όροι Συμβολαίου (προαιρετικό)")
    st.info(
        "Ανέβασε τους **Γενικούς Όρους** κάθε ασφαλιστικής για ανάλυση κρίσιμων εξαιρέσεων "
        "από το πραγματικό policy wording. Το σύστημα σκανάρει μόνο τις σχετικές σελίδες "
        "για να αποφύγει πρόβλημα tokens σε πολυσέλιδα κείμενα.",
        icon="📜"
    )
    terms_files = st.file_uploader(
        "Ανέβασε Terms PDFs (Γενικοί Όροι)", type="pdf", accept_multiple_files=True,
        key="terms_uploader",
        help="Π.χ. 'Generali_Terms.pdf', 'MorganPrice_PolicyWording.pdf'. "
             "Ονόμασε τα αρχεία με το όνομα της ασφαλιστικής για auto-match."
    )

    if not uploaded_files:
        st.markdown("---")
        st.markdown("#### Πώς λειτουργεί:")
        h1, h2, h3 = st.columns(3)
        with h1:
            st.markdown("**1️⃣ Ανέβασε PDFs**\nΌλες οι προσφορές που θέλεις να συγκρίνεις")
        with h2:
            st.markdown("**2️⃣ Claude τα αναλύει**\nΕξάγει αυτόματα κεφάλαια, απαλλαγές, καλύψεις")
        with h3:
            st.markdown("**3️⃣ Download PPTX**\nΈτοιμη παρουσίαση με το brand σου")
        return

    # ── SESSION STATE INIT ───────────────────────────────────────────
    if "proposals"      not in st.session_state: st.session_state.proposals      = {}
    if "pdf_cache"      not in st.session_state: st.session_state.pdf_cache      = {}
    if "terms_results"  not in st.session_state: st.session_state.terms_results  = {}
    if "detected_lang"  not in st.session_state: st.session_state.detected_lang  = client_lang

    # ── EXTRACTION ───────────────────────────────────────────────────
    if st.button("🤖 Ανάλυση με Claude API", type="primary", disabled=not api_key):
        if not api_key:
            st.error("Χρειάζεσαι Claude API key!")
            return

        progress = st.progress(0, text="Αρχικοποίηση...")
        st.session_state.proposals = {}
        total = len(uploaded_files)

        # Auto-detect language from first PDF
        detected_lang = client_lang

        for idx, uf in enumerate(uploaded_files):
            progress.progress(idx / total, text=f"Ανάλυση {idx + 1}/{total}: {uf.name}...")
            try:
                pdf_bytes = uf.read()
                pdf_hash  = hashlib.md5(pdf_bytes).hexdigest()

                # Auto-detect language from PDF text (first file wins)
                if idx == 0 and client_lang == "el":
                    try:
                        import fitz as _fitz
                        _doc = _fitz.open(stream=pdf_bytes, filetype="pdf")
                        _sample = " ".join(
                            _doc[i].get_text() for i in range(min(3, len(_doc)))
                        )
                        _doc.close()
                        detected_lang = detect_pdf_language(_sample)
                    except Exception:
                        detected_lang = client_lang
                st.session_state.detected_lang = detected_lang

                if pdf_hash in st.session_state.pdf_cache:
                    # Return cached result — no API call needed
                    data = st.session_state.pdf_cache[pdf_hash]
                    st.success(f"⚡ {uf.name} — φορτώθηκε από cache")
                else:
                    data = extract_insurance_data(pdf_bytes, api_key, filename=uf.name)
                    # Μεταφράζει "Not Covered" → "Δεν Καλύπτεται" κλπ για ελληνικές
                    if is_greek_insurer(data.get("insurer")):
                        localize_insurance_data(data)
                    st.session_state.pdf_cache[pdf_hash] = data
                    st.success(
                        f"✅ {uf.name} → {data.get('insurer', '')} {data.get('plan_name', '')}"
                    )

                st.session_state.proposals[uf.name] = data

            except Exception as e:
                st.error(f"❌ Σφάλμα στο {uf.name}: {e}")

            if idx < total - 1:
                time.sleep(INTER_FILE_DELAY)

        progress.progress(1.0, text="✅ Ολοκληρώθηκε!")

    # ── TERMS / WORDING ANALYSIS ─────────────────────────────────────
    if st.session_state.get("proposals") and terms_files:
        st.markdown("---")
        st.markdown("### 📑 Ανάλυση Policy Wording (Όροι Συμβολαίου)")
        st.caption(
            f"Βρέθηκαν {len(terms_files)} αρχεία όρων. "
            "Το σύστημα σκανάρει μόνο τις σελίδες με εξαιρέσεις "
            f"(max {6} chunks × 3 500 χαρακτήρες ανά ασφαλιστική)."
        )

        if st.button("🔬 Ανάλυση Εξαιρέσεων από Policy Wording", type="secondary",
                     disabled=not api_key):
            st.session_state.terms_results = {}
            active_lang = st.session_state.get("detected_lang", client_lang)

            for tf in terms_files:
                # Try to match terms file to an extracted insurer
                tf_bytes  = tf.read()
                tf_name   = tf.name.lower()

                # Best-effort insurer name from filename
                matched_insurer = tf.name.replace(".pdf","").replace("_"," ").strip()
                for prop in st.session_state.proposals.values():
                    ins = (prop.get("insurer") or "").lower()
                    if ins and ins[:6] in tf_name:
                        matched_insurer = prop.get("insurer", matched_insurer)
                        break

                with st.spinner(f"Ανάλυση όρων: {matched_insurer}…"):
                    try:
                        result = analyze_terms_pdf(
                            pdf_bytes=tf_bytes,
                            insurer=matched_insurer,
                            api_key=api_key,
                            lang=active_lang,
                            filename=tf.name,
                        )
                        st.session_state.terms_results[matched_insurer] = result

                        crit = result["critical_count"]
                        high = result["high_count"]
                        if crit > 0:
                            st.error(
                                f"🚨 {matched_insurer}: {crit} ΚΡΙΣΙΜΕΣ + {high} HIGH εξαιρέσεις "
                                f"(από {result['pages_selected']} σελίδες / "
                                f"{result['chunks_analyzed']} chunks)"
                            )
                        elif high > 0:
                            st.warning(
                                f"⚠️ {matched_insurer}: {high} HIGH εξαιρέσεις "
                                f"({result['pages_selected']} σελίδες)"
                            )
                        else:
                            st.success(
                                f"✅ {matched_insurer}: Δεν εντοπίστηκαν κρίσιμες εξαιρέσεις "
                                f"({result['pages_selected']} σελίδες)"
                            )
                    except Exception as e:
                        st.error(f"❌ Σφάλμα στους όρους {tf.name}: {e}")

        # Display terms results
        terms_data = st.session_state.get("terms_results", {})
        if terms_data:
            for insurer_name, tdata in terms_data.items():
                with st.expander(
                    f"📋 {insurer_name} — "
                    f"{tdata['critical_count']} κρίσιμες / "
                    f"{tdata['high_count']} high εξαιρέσεις "
                    f"({tdata['pages_selected']}/{tdata['pages_scanned']} σελίδες)",
                    expanded=tdata["critical_count"] > 0
                ):
                    if tdata.get("summary_flags"):
                        st.markdown("**Σύνοψη Risk Flags:**")
                        for flag in tdata["summary_flags"]:
                            st.markdown(f"- {flag}")

                    if tdata.get("exclusions"):
                        sev_colors = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡"}
                        st.markdown("**Λεπτομέρειες Εξαιρέσεων:**")
                        for exc in tdata["exclusions"]:
                            sev = exc.get("severity","MEDIUM")
                            st.markdown(
                                f"{sev_colors.get(sev,'⚪')} **{exc.get('description','')}**"
                            )
                            if exc.get("exact_wording"):
                                st.caption(f"Wording: *\"{exc['exact_wording']}\"*")
                            if exc.get("limit_value"):
                                st.caption(f"Όριο: {exc['limit_value']}")
                            st.markdown("---")

                    if tdata.get("ambiguous_clauses"):
                        st.markdown("**Αμφίσημοι Όροι:**")
                        for clause in tdata["ambiguous_clauses"]:
                            st.markdown(f"- ⚠️ {clause}")

    # ── DISPLAY & EDIT EXTRACTED DATA ───────────────────────────────
    if st.session_state.get("proposals"):
        proposals_list = list(st.session_state.proposals.values())
        file_names     = list(st.session_state.proposals.keys())

        # ── Detect Greek vs International mode ───────────────────────
        comp_mode = detect_comparison_mode(proposals_list)
        # Store in session so downstream widgets can use it
        st.session_state["comp_mode"] = comp_mode

        if comp_mode == "greek_only":
            st.info(
                "🇬🇷 **Ελληνική αγορά** — Εμφανίζονται οι καλύψεις που πράγματι "
                "παρέχουν οι ελληνικές ασφαλιστικές. Πεδία όπως εξωνοσοκομειακή "
                "ελεύθερου δικτύου, πλήρης οδοντιατρική, ψυχολογική εκτός νοσηλείας "
                "και MRI/CT/PET εκτός νοσηλείας **δεν ισχύουν** στην ελληνική αγορά.",
                icon="ℹ️"
            )
            with st.expander("📋 Τι ΔΕΝ καλύπτουν οι ελληνικές ασφαλιστικές", expanded=False):
                for item in NOT_AVAILABLE_IN_GREEK:
                    st.markdown(f"**❌ {item['label']}**")
                    st.caption(item["reason"])
        elif comp_mode == "mixed":
            st.warning(
                "⚡ **Μεικτή σύγκριση** — Ελληνικές + Διεθνείς εταιρείες. "
                "Ορισμένα πεδία (εξωνοσοκομειακή ελεύθερου δικτύου, πλήρης οδοντιατρική "
                "κλπ) ισχύουν **μόνο για τις διεθνείς**. "
                "Η βαθμολογία ελληνικών εταιρειών χρησιμοποιεί προσαρμοσμένα βάρη.",
                icon="⚠️"
            )
        else:
            st.success("🌍 Διεθνής σύγκριση — χρησιμοποιούνται πλήρη διεθνή κριτήρια.", icon="✅")

        st.markdown("---")
        st.markdown("### 📊 Εξαχθέντα Στοιχεία")

        # Βαθμολογία κάλυψης — πολυδιάστατη, προσαρμοσμένη για ελληνικές/διεθνείς
        st.markdown("#### 📊 Βαθμολογία Κάλυψης")
        st.caption(
            "Βαθμολογία Κάλυψης = ποιότητα παροχών. "
            "Για ελληνικές εταιρείες χρησιμοποιούνται ελληνικά βάρη (check-up, ER, αποκατάσταση). "
            "Η τελική πρόταση λαμβάνει υπόψη και premium, κεφάλαιο, και εξωνοσοκομειακό τύπο."
        )

        score_cols = st.columns(len(proposals_list))
        _comp_mode = st.session_state.get("comp_mode", "greek_only")
        for col, prop in zip(score_cols, proposals_list):
            md      = prop.get("_multidim") or {}
            sc      = compute_score(prop, mode=_comp_mode)
            eff     = compute_premium_efficiency(prop, mode=_comp_mode)
            emoji   = "🟢" if sc >= 7 else ("🟡" if sc >= 5 else "🔴")
            safety  = prop.get("_safety_rating", 9.0)
            s_emoji = "✅" if safety >= 8 else ("⚠️" if safety >= 5 else "🚨")
            otype   = str(prop.get("outpatient_type") or "").lower()
            ctype   = str(prop.get("company_type") or "").lower()
            with col:
                st.metric(
                    label=f"{prop.get('insurer','?')} — {prop.get('plan_name','?')[:18]}",
                    value=f"{sc} / 10",
                    delta=f"{emoji} Κάλυψη  {s_emoji} Safety {safety}/10",
                )
                if eff:
                    st.caption(f"💰 Αξία: {eff} σκορ/€1000 ασφαλίστρου")
                # ── Outpatient type message — mode-aware ──
                if ctype == "greek" or _comp_mode == "greek_only":
                    # For Greek companies hospital_procedures is NORMAL — no warning
                    if otype == "hospital_procedures":
                        st.info(
                            "🏥 **Ειδικές διαγνωστικές** σε συμβεβλημένα νοσοκομεία "
                            "(γαστρο/κολονο/βιοψία κλπ) — τυπική κάλυψη ελληνικής αγοράς",
                            icon="ℹ️"
                        )
                    elif otype == "general":
                        st.success("✅ Γενική εξωνοσοκομειακή κάλυψη")
                else:
                    # International context — show warning for hospital_procedures
                    if otype == "hospital_procedures":
                        st.warning(
                            "⚠️ **Εξωνοσοκομειακά:** Μόνο επεμβατικές/ενδοσκοπικές "
                            "σε συμβεβλημένα νοσοκομεία — ΟΧΙ γενική εξωνοσοκομειακή κάλυψη",
                            icon="🏥"
                        )
                    elif otype == "general":
                        st.success("✅ Γενική εξωνοσοκομειακή κάλυψη (ιατρεία, εξετάσεις)")
                flags = prop.get("_risk_flags", [])
                if flags:
                    with st.expander(f"🚩 {len(flags)} Risk Flag(s)", expanded=False):
                        for flag in flags:
                            st.markdown(f"- {flag}")

        # Editable tabs — one per proposal
        edited_proposals = []
        tabs = st.tabs([
            f"📋 {p.get('insurer', '?')} — {p.get('plan_name', '?')[:20]}"
            for p in proposals_list
        ])

        for tab, prop, fname in zip(tabs, proposals_list, file_names):
            with tab:
                _mode = st.session_state.get("comp_mode", "greek_only")
                _is_greek_tab = (
                    _mode == "greek_only"
                    or str(prop.get("company_type") or "").lower() == "greek"
                )
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("**📌 Βασικά Στοιχεία**")
                    prop["insurer"]        = st.text_input("Ασφαλιστική",       prop.get("insurer", ""),                  key=f"ins_{fname}")
                    prop["plan_name"]      = st.text_input("Πλάνο",             prop.get("plan_name", ""),                key=f"plan_{fname}")
                    prop["annual_premium"] = st.text_input("Ετήσιο Ασφάλιστρο", str(prop.get("annual_premium", "")),      key=f"prem_{fname}")
                    prop["currency"]       = st.selectbox("Νόμισμα",            ["EUR", "USD", "GBP"],
                                                          index=["EUR","USD","GBP"].index(prop.get("currency","EUR") or "EUR"),
                                                          key=f"cur_{fname}")
                    prop["deductible"]     = st.text_input("Απαλλαγή",          prop.get("deductible", ""),               key=f"ded_{fname}")
                    if _is_greek_tab:
                        prop["deductible_public"] = st.text_input(
                            "Απαλλαγή Δημόσιο",  str(prop.get("deductible_public") or "0"),
                            key=f"ded_pub_{fname}", help="Συνήθως €0 στα ελληνικά προγράμματα"
                        )
                        prop["deductible_ods"] = st.text_input(
                            "Απαλλαγή ODS",       str(prop.get("deductible_ods") or ""),
                            key=f"ded_ods_{fname}", help="Εκπιπτόμενο για χειρουργεία ημέρας χωρίς διανυκτέρευση"
                        )
                    prop["max_coverage"]   = st.text_input("Μέγιστο Κεφάλαιο",  str(prop.get("max_coverage", "")),        key=f"maxcov_{fname}")
                    prop["geography"]      = st.text_input("Γεωγραφία",          prop.get("geography", ""),                key=f"geo_{fname}")
                    prop["hospital_class"] = st.text_input("Θέση Νοσηλείας",    prop.get("hospital_class", ""),           key=f"hosp_{fname}")
                    prop["waiting_period"] = st.text_input("Αναμονή",            prop.get("waiting_period", ""),           key=f"wait_{fname}")
                    prop["preexisting"]    = st.text_input("Προϋπ. Παθήσεις",   prop.get("preexisting", ""),              key=f"preex_{fname}")

                with col2:
                    st.markdown("**✅ Καλύψεις**")
                    prop["inpatient"]               = st.text_input("Νοσηλεία",              prop.get("inpatient", ""),               key=f"inp_{fname}")
                    prop["outpatient_limit"]         = st.text_input("Εξωνοσοκ. Όριο",       str(prop.get("outpatient_limit", "")),   key=f"outp_{fname}")
                    prop["outpatient_pct"]           = st.text_input("Εξωνοσοκ. %",           str(prop.get("outpatient_pct") or ""),   key=f"outpct_{fname}")
                    # Outpatient type
                    otype_options = ["hospital_procedures", "general", "not_covered"]
                    current_otype = prop.get("outpatient_type") or "not_covered"
                    if current_otype not in otype_options:
                        current_otype = "not_covered"
                    prop["outpatient_type"] = st.selectbox(
                        "Τύπος Εξωνοσοκ.",
                        otype_options,
                        index=otype_options.index(current_otype),
                        key=f"otype_{fname}",
                        help="hospital_procedures = επεμβατικές/ενδοσκοπικές σε συμβεβλημένα (ΤΥΠΙΚΟ για ελληνικές) | general = ελεύθερο δίκτυο (μόνο διεθνείς)"
                    )
                    prop["outpatient_note"]          = st.text_input("Εξωνοσοκ. Σημείωση",   prop.get("outpatient_note") or "",      key=f"outnote_{fname}")

                    if _is_greek_tab:
                        st.markdown("**🏥 Επείγοντα & Ειδικές Διαγν. (Ελληνική αγορά)**")
                        prop["emergency_er_limit"] = st.text_input(
                            "Επείγοντα ΤΕΠ — Όριο/περιστατικό",
                            str(prop.get("emergency_er_limit") or ""),
                            key=f"er_lim_{fname}"
                        )
                        prop["emergency_er_copay"] = st.text_input(
                            "Επείγοντα — Συμμετοχή (%)",
                            str(prop.get("emergency_er_copay") or ""),
                            key=f"er_cop_{fname}"
                        )
                        prop["emergency_er_incidents"] = st.text_input(
                            "Επείγοντα — Μέγιστα/έτος",
                            str(prop.get("emergency_er_incidents") or ""),
                            key=f"er_inc_{fname}"
                        )
                        prop["specific_diagnostics_limit"] = st.text_input(
                            "Ειδικές Διαγν. χωρίς νοσ. — Όριο",
                            str(prop.get("specific_diagnostics_limit") or ""),
                            key=f"diag_lim_{fname}",
                            help="Γαστροσκόπηση, κολονοσκόπηση, κυστεοσκόπηση, βιοψία κλπ"
                        )
                        prop["specific_diagnostics_copay"] = st.text_input(
                            "Ειδικές Διαγν. — Συμμετοχή (%)",
                            str(prop.get("specific_diagnostics_copay") or ""),
                            key=f"diag_cop_{fname}"
                        )
                        prop["second_opinion"] = st.text_input(
                            "Δεύτερη Ιατρική Γνώμη",
                            prop.get("second_opinion") or "",
                            key=f"sec_op_{fname}"
                        )
                        prop["zero_deductible_serious"] = st.text_input(
                            "Μηδενισμός εκπ. — Σοβαρές ασθένειες",
                            prop.get("zero_deductible_serious") or "",
                            key=f"zero_ded_{fname}"
                        )
                    else:
                        prop["mri_ct_pet"]               = st.text_input("MRI / CT / PET",        prop.get("mri_ct_pet", ""),              key=f"mri_{fname}")

                    prop["cancer"]                   = st.text_input("Καρκίνος",               prop.get("cancer", ""),                  key=f"can_{fname}")
                    prop["physiotherapy"]            = st.text_input("Φυσιοθεραπεία",          prop.get("physiotherapy", ""),           key=f"physio_{fname}")
                    prop["chronic_conditions"]       = st.text_input("Χρόνιες Παθήσεις",      prop.get("chronic_conditions", ""),      key=f"chron_{fname}")
                    prop["evacuation_repatriation"]  = st.text_input("Εκκένωση / Μεταφορά",  prop.get("evacuation_repatriation", ""), key=f"evac_{fname}")
                    prop["psychiatric_inpatient"]    = st.text_input("Ψυχ. Νοσηλεία (εντός νοσ.)",  prop.get("psychiatric_inpatient", ""),   key=f"psyin_{fname}")
                    if _is_greek_tab:
                        prop["psychiatric_post_hosp"] = st.text_input(
                            "Ψυχολ. Υποστήριξη μετά νοσ.",
                            prop.get("psychiatric_post_hosp") or "",
                            key=f"psy_post_{fname}",
                            help="π.χ. Generali: 10 συνεδρίες μόνο μετά νοσηλεία"
                        )
                    else:
                        prop["psychiatric_outpatient"]   = st.text_input("Ψυχ. Εξωτερικά",       prop.get("psychiatric_outpatient", ""),  key=f"psyout_{fname}")

                with col3:
                    st.markdown("**➕ Πρόσθετα & Παρατηρήσεις**")
                    if _is_greek_tab:
                        prop["rehabilitation_limit"] = st.text_input(
                            "Αποκατάσταση / Κέντρα — Όριο",
                            str(prop.get("rehabilitation_limit") or ""),
                            key=f"rehab_{fname}"
                        )
                        prop["home_nursing"] = st.text_input("Νοσηλεία Κατ' Οίκον — Όριο", prop.get("home_nursing", ""), key=f"homenur_{fname}")
                        prop["maternity_allowance"] = st.text_input(
                            "Επίδομα Τοκετού",
                            str(prop.get("maternity_allowance") or ""),
                            key=f"mat_{fname}"
                        )
                        prop["annual_checkup_count"] = st.text_input(
                            "Ετήσιες Προλ. Εξετάσεις (αριθμός)",
                            str(prop.get("annual_checkup_count") or ""),
                            key=f"checkup_{fname}"
                        )
                        prop["telemedicine"] = st.text_input(
                            "Τηλεϊατρική",
                            prop.get("telemedicine") or "",
                            key=f"tele_{fname}"
                        )
                        prop["accident_outpatient_limit"] = st.text_input(
                            "Ατύχημα εκτός νοσ. — Όριο",
                            str(prop.get("accident_outpatient_limit") or ""),
                            key=f"acc_lim_{fname}"
                        )
                        prop["accident_outpatient_copay"] = st.text_input(
                            "Ατύχημα εκτός νοσ. — Συμμ. (%)",
                            str(prop.get("accident_outpatient_copay") or ""),
                            key=f"acc_cop_{fname}"
                        )
                        prop["dental_network_discount"] = st.text_input(
                            "Οδοντ. Εκπτώσεις Δικτύου",
                            prop.get("dental_network_discount") or "",
                            key=f"dent_disc_{fname}",
                            help="ΟΧΙ κάλυψη θεραπείας — μόνο εκπτώσεις δικτύου"
                        )
                        prop["wellness_screening"] = st.text_input("Προληπτικός Έλεγχος",     prop.get("wellness_screening", ""), key=f"well_{fname}")
                    else:
                        prop["dental_emergency"]   = st.text_input("Οδοντ. Έκτακτη",         prop.get("dental_emergency", ""),   key=f"dent_{fname}")
                        prop["wellness_screening"] = st.text_input("Προληπτικός Έλεγχος",     prop.get("wellness_screening", ""), key=f"well_{fname}")
                        prop["cancer_screening"]   = st.text_input("Έλεγχος Καρκίνου",        prop.get("cancer_screening", ""),   key=f"canscr_{fname}")
                        prop["organ_transplant"]   = st.text_input("Μεταμόσχευση Οργάνου",    prop.get("organ_transplant", ""),   key=f"organ_{fname}")
                        prop["hospice_care"]       = st.text_input("Ανακουφιστική Φροντίδα",  prop.get("hospice_care", ""),       key=f"hosp2_{fname}")
                        prop["home_nursing"]       = st.text_input("Νοσηλεία Κατ' Οίκον",    prop.get("home_nursing", ""),       key=f"homenur_{fname}")

                    st.markdown("**💳 Τρόπος Πληρωμής**")
                    freq_options = ["Μηνιαία", "Τριμηνιαία", "Εξαμηνιαία", "Ετήσια"]
                    current_freq = prop.get("payment_frequency") or "Ετήσια"
                    if current_freq not in freq_options:
                        current_freq = "Ετήσια"
                    prop["payment_frequency"] = st.selectbox(
                        "Συχνότητα πληρωμής",
                        freq_options,
                        index=freq_options.index(current_freq),
                        key=f"freq_{fname}",
                        help="Επιλέξτε πώς θα εμφανίζεται το ασφάλιστρο στην παρουσίαση. Το ετήσιο κεφάλαιο διαιρείται αυτόματα."
                    )

                    st.markdown("**📝 Παρατηρήσεις**")
                    notes_raw  = prop.get("key_notes") or []
                    notes_str  = "\n".join(notes_raw) if isinstance(notes_raw, list) else str(notes_raw)
                    edited_notes = st.text_area(
                        "Μία παρατήρηση ανά γραμμή",
                        notes_str, height=150, key=f"notes_{fname}"
                    )
                    prop["key_notes"] = [
                        n.strip() for n in edited_notes.splitlines() if n.strip()
                    ]

                edited_proposals.append(prop)

        # ── RECOMMENDED CHOICE ───────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🎯 Επιλογή Πρότασης")
        insurer_labels = [
            f"{p.get('insurer', '')} — {p.get('plan_name', '')} "
            f"({p.get('currency','€')}{p.get('annual_premium', '—')})"
            for p in edited_proposals
        ]
        rec_idx = st.selectbox(
            "Ποια πρόταση να εμφανίζεται ως **ΠΡΟΤΕΙΝΟΜΕΝΗ**;",
            range(len(insurer_labels)),
            format_func=lambda i: insurer_labels[i],
        )

        # ── Score contradiction warning ───────────────────────────────
        # If recommended plan has LOWER score than another, show explanation
        if len(edited_proposals) > 1:
            _cmode = st.session_state.get("comp_mode", "greek_only")
            all_scores  = [(compute_score(p, mode=_cmode), i, p.get("insurer","?")) for i, p in enumerate(edited_proposals)]
            best_score, best_idx, best_ins = max(all_scores, key=lambda x: x[0])
            rec_score   = compute_score(edited_proposals[rec_idx], mode=_cmode)

            if best_idx != rec_idx and best_score > rec_score:
                rec_ins = edited_proposals[rec_idx].get("insurer","?")
                # Explain the contradiction proactively
                reasons = []
                rec = edited_proposals[rec_idx]
                alt = edited_proposals[best_idx]

                # Check max_coverage advantage
                try:
                    rec_mc = int(str(rec.get("max_coverage") or 0).replace(",",""))
                    alt_mc = int(str(alt.get("max_coverage") or 0).replace(",",""))
                    if rec_mc > alt_mc:
                        reasons.append(f"υψηλότερο ανώτατο κεφάλαιο ({rec_mc:,} vs {alt_mc:,}€)")
                except Exception:
                    pass

                # Check premium advantage
                try:
                    rec_pr = float(str(rec.get("annual_premium") or 0).replace(",",""))
                    alt_pr = float(str(alt.get("annual_premium") or 0).replace(",",""))
                    if rec_pr < alt_pr:
                        reasons.append(f"χαμηλότερο ασφάλιστρο ({rec_pr:,.0f} vs {alt_pr:,.0f}€)")
                except Exception:
                    pass

                # Check outpatient type (real outpatient > hospital_procedures)
                rec_otype = str(rec.get("outpatient_type") or "").lower()
                alt_otype = str(alt.get("outpatient_type") or "").lower()
                if rec_otype == "general" and alt_otype != "general":
                    reasons.append("πραγματική γενική εξωνοσοκομειακή κάλυψη")

                reason_str = " · ".join(reasons) if reasons else "client-specific λόγους"
                st.info(
                    f"ℹ️ **Σημείωση σκορ:** Η {best_ins} έχει υψηλότερη βαθμολογία κάλυψης "
                    f"({best_score}/10 vs {rec_score}/10 της {rec_ins}), αλλά προτείνεται "
                    f"η {rec_ins} λόγω: **{reason_str}**. "
                    f"Η ανάλυση Claude θα εξηγήσει αναλυτικά την επιλογή.",
                    icon="📊"
                )

        # ── AI ANALYSIS ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🧠 Ανάλυση & Αιτιολόγηση Πρότασης")
        st.info(
            "Το Claude αναλύει τις προσφορές και παράγει μια εξατομικευμένη "
            "αιτιολόγηση — την ίδια λογική που χρησιμοποιεί ένας έμπειρος "
            "σύμβουλος για να εξηγήσει την επιλογή στον πελάτη. "
            "Η ανάλυση ενσωματώνεται και στην PPTX παρουσίαση.",
            icon="💡"
        )

        if "analysis_result" not in st.session_state:
            st.session_state.analysis_result = None

        if st.button("🔍 Δημιούργησε Ανάλυση Πρότασης", type="secondary", disabled=not api_key):
            if not client_name:
                st.warning("Συμπλήρωσε το όνομα του πελάτη στο sidebar!")
            else:
                with st.spinner("Δημιουργία ανάλυσης με Claude..."):
                    try:
                        st.session_state.analysis_result = generate_recommendation_analysis(
                            proposals=edited_proposals,
                            recommended_idx=rec_idx,
                            client_name=client_name,
                            client_members=members,
                            api_key=api_key,
                            lang=st.session_state.get("detected_lang", client_lang),
                            terms_results=st.session_state.get("terms_results", {}),
                        )
                        st.success("✅ Ανάλυση ολοκληρώθηκε!")
                    except Exception as e:
                        st.error(f"❌ Σφάλμα ανάλυσης: {e}")

        analysis = st.session_state.get("analysis_result")
        if analysis:
            st.markdown(
                f"""
                <div style='background:#1C3F5E;border-radius:10px;
                            padding:1.2em 1.6em;margin-bottom:1em'>
                  <p style='color:#F59E0B;font-size:1.2em;
                             font-weight:700;margin:0'>
                    {analysis.get("headline", "")}
                  </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.markdown("#### 📝 Αιτιολόγηση Πρότασης")
            st.markdown(analysis.get("main_rationale", ""))

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### ✅ Βασικοί Λόγοι Επιλογής")
                for reason in analysis.get("key_reasons", []):
                    st.markdown(f"- {reason}")
                st.markdown("#### 🎯 Κριτήρια Απόφασης")
                for factor in analysis.get("decision_factors", []):
                    st.markdown(f"- {factor}")

            with col_b:
                st.markdown("#### 📊 Αξιολόγηση Προσφορών")
                tag_colors = {
                    "ΑΡΙΣΤΟ": "#27AE60", "ΚΑΛΟ": "#00B4D8",
                    "ΜΕΣΑΙΟ": "#E67E22", "ΠΕΡΙΟΡΙΣΜΕΝΟ": "#E74C3C",
                }
                for v in analysis.get("plan_verdicts", []):
                    color = tag_colors.get(v.get("tag", ""), "#666")
                    st.markdown(
                        f"""
                        <div style='border-left:4px solid {color};
                                    background:#F4F9FF;border-radius:4px;
                                    padding:0.6em 1em;margin-bottom:0.5em'>
                          <strong>{v.get('insurer','')} — {v.get('plan','')}</strong>
                          <span style='background:{color};color:white;
                                       border-radius:4px;padding:2px 8px;
                                       font-size:0.75em;margin-left:8px'>
                            {v.get('tag','')}
                          </span><br/>
                          <span style='color:#444;font-size:0.9em'>
                            {v.get('verdict','')}
                          </span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                if analysis.get("key_concerns"):
                    st.markdown("#### ⚠️ Σημεία Προσοχής")
                    for concern in analysis.get("key_concerns", []):
                        st.markdown(f"- {concern}")

        # ── GENERATE ─────────────────────────────────────────────────
        st.markdown("---")
        if st.button("🎨 Δημιουργία Παρουσίασης PPTX", type="primary"):
            if not client_name:
                st.warning("Συμπλήρωσε το όνομα του πελάτη στο sidebar!")
                return

            with st.spinner("Δημιουργία παρουσίασης..."):
                try:
                    pptx_bytes = generate_pptx(
                        client_name=client_name,
                        client_members=members,
                        proposals=edited_proposals,
                        recommended_idx=rec_idx,
                        broker_name=broker_name,
                        broker_tel=broker_tel,
                        broker_email=broker_email,
                        logo_bytes=logo_bytes,
                        analysis=st.session_state.get("analysis_result"),
                        lang=st.session_state.get("detected_lang", client_lang),
                        terms_results=st.session_state.get("terms_results", {}),
                        theme=selected_theme,
                    )
                    fname_out = (
                        f"{client_name.replace(' ', '_')}_Insurance_"
                        f"{datetime.now().strftime('%Y%m')}.pptx"
                    )
                    st.download_button(
                        label="⬇️ Download Παρουσίαση",
                        data=pptx_bytes,
                        file_name=fname_out,
                        mime=(
                            "application/vnd.openxmlformats-officedocument"
                            ".presentationml.presentation"
                        ),
                    )
                    st.success(f"✅ Η παρουσίαση '{fname_out}' είναι έτοιμη!")

                    # ── Increment trial counter (server-side, per email) ──
                    status    = increment_quote()
                    remaining = remaining_quotes()
                    if remaining == 0:
                        st.warning(
                            "🔒 Αυτή ήταν η τελευταία δωρεάν παρουσίαση. "
                            "Κατεβάστε το αρχείο και επικοινωνήστε μαζί μας "
                            "για πλήρη πρόσβαση.",
                            icon="🔔"
                        )
                    elif remaining <= 2:
                        st.info(
                            f"⏳ Απομένουν **{remaining}** παρουσιάσεις. "
                            "Καλέστε +30 697 590 0189 για την πλήρη έκδοση.",
                            icon="💡"
                        )

                except Exception as e:
                    st.error(f"Σφάλμα: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    elif uploaded_files and not st.session_state.get("proposals"):
        st.info("👆 Πάτα 'Ανάλυση με Claude API' για να εξαχθούν τα στοιχεία από τα PDFs.")


if __name__ == "__main__":
    main()
