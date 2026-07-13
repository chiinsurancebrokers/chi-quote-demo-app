"""
CHI Insurance Brokers — PDF Data Extraction & Coverage Scoring
Uses Claude to parse insurance PDFs into structured JSON,
then computes a weighted coverage quality score (0–10).

Smart extraction:
  - Αν το PDF έχει > 6 σελίδες ή > 60 KB, εξάγει κείμενο με PyMuPDF
    και κρατά μόνο τις σελίδες με ασφαλιστικά δεδομένα (scoring).
  - Στέλνει κείμενο αντί για binary PDF → πολύ λιγότερα tokens.
  - Fallback σε binary PDF για μικρά/απλά αρχεία.
"""

import base64
import json
import re
import time

import anthropic
import streamlit as st

try:
    import fitz  # PyMuPDF
    _PYMUPDF_OK = True
except ImportError:
    _PYMUPDF_OK = False

from config import MODEL, MAX_RETRIES, RETRY_WAIT_BASE
from exclusions_detector import detect_exclusions, compute_multidim_score


# ─── ΣΤΑΘΕΡΕΣ SMART EXTRACTION ──────────────────────────────────────

# Λέξεις-κλειδιά που δείχνουν χρήσιμη ασφαλιστική σελίδα
_HIGH_VALUE = [
    "ασφάλιστρο", "ασφαλίστρου", "ασφαλίστρων", "ασφαλίστρα",
    "κάλυψη", "κάλυψης", "καλύψεις", "καλύπτεται", "καλύπτονται",
    "παροχές", "παροχή", "παροχών",
    "απαλλαγή", "απαλλαγής",
    "νοσηλεία", "νοσηλείας",
    "ετήσιο", "ετήσιος", "ετήσια",
    "ανώτατο όριο", "ανώτατο",
    "χημειοθεραπεία", "ακτινοθεραπεία",
    "εξωνοσοκομειακ", "εξωτερικ",
    "διαγνωστικ", "φυσιοθεραπεί",
    "premium", "deductible", "coverage",
    "πλάνο", "πρόγραμμα",
    # Πεδία τιμολόγησης / ασφαλίστρου
    "ανάλυση ασφαλίστρων", "βασικά στοιχεία προγράμματος",
    "συνολικό καθαρό", "σύνολο δόσης", "σύνολο πρώτης δόσης",
    "καθαρό ασφάλιστρο", "ετήσιο καθαρό", "δικαίωμα",
    "συχνότητα πληρωμής", "τρόπος πληρωμής",
    "full health", "full επείγοντα",
]

# Λέξεις που μειώνουν αξία σελίδας
_LOW_VALUE = [
    "INTERNAL",
    "εναλλακτικής επίλυσης διαφορών",
    "φερεγγυότητα",
    "ν. 4364", "ν. 2496",
    "νόμος 4364",
    "εναντίωσ",
    "υπαναχώρησ",
    "τράπεζα της ελλάδος",
    "ερωτηματολόγιο αναγκών",   # Τελευταία σελίδα με ναι/όχι
    # Νομικές σελίδες 3-5 από προσυμβατική (5ψήφιες σελίδες)
    "σελίδα 3 από 5",
    "σελίδα 4 από 5",
    "σελίδα 5 από 5",
    "σελίδα 3 από 4",
    "σελίδα 4 από 4",
]

# Όρια για smart extraction
_SIZE_THRESHOLD_BYTES = 60_000   # > 60 KB → χρήση text extraction
_PAGE_THRESHOLD       = 6        # > 6 σελίδες → χρήση text extraction
_MAX_CHARS_TO_CLAUDE  = 16_000   # Μέγιστοι χαρακτήρες προς Claude


# ─── ΒΑΘΜΟΛΟΓΗΣΗ ΣΕΛΙΔΑΣ ────────────────────────────────────────────

def _score_page(text: str) -> int:
    """Βαθμολογεί μια σελίδα ως προς τη χρησιμότητά της (0–100)."""
    t = text.lower()
    score = 0
    for kw in _HIGH_VALUE:
        if kw.lower() in t:
            score += 5
    for kw in _LOW_VALUE:
        if kw.lower() in t:
            score -= 15
    return max(0, score)


# ─── SMART PDF → TEXT ────────────────────────────────────────────────

def smart_pdf_to_text(pdf_bytes: bytes, filename: str = "") -> str | None:
    """
    Εξάγει κείμενο από τις πιο σχετικές σελίδες του PDF.

    Επιστρέφει:
      - str  : το συμπιεσμένο κείμενο αν η εξαγωγή πέτυχε
      - None : αν πρέπει να σταλεί ολόκληρο το PDF binary
    """
    if not _PYMUPDF_OK:
        return None

    needs_smart = (
        len(pdf_bytes) > _SIZE_THRESHOLD_BYTES
        or _quick_page_count(pdf_bytes) > _PAGE_THRESHOLD
    )
    if not needs_smart:
        return None   # Μικρό PDF — στείλε binary κανονικά

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(doc)

        # Βαθμολόγησε κάθε σελίδα
        scored = []
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            sc   = _score_page(text)
            scored.append((i + 1, sc, text))   # (αρ. σελίδας, score, κείμενο)

        doc.close()

        # ── Επιλογή σελίδων ──
        # 1. Πάντα κράτα τις πρώτες 2 σελίδες (εξώφυλλο + βασικά)
        must_keep = {1, 2}
        selected_pages = []
        total_chars    = 0

        # Πρώτα must_keep (με σειρά)
        for pg, sc, tx in scored:
            if pg in must_keep and tx:
                selected_pages.append((pg, tx))
                total_chars += len(tx)

        # Μετά υπόλοιπες με score > 0 (ταξινομημένες κατά score φθίνον)
        rest = [(pg, sc, tx) for pg, sc, tx in scored if pg not in must_keep and sc > 0]
        rest.sort(key=lambda x: -x[1])

        for pg, sc, tx in rest:
            if total_chars + len(tx) > _MAX_CHARS_TO_CLAUDE:
                continue   # Παράλειψε αν είναι πολύ μεγάλη
            selected_pages.append((pg, tx))
            total_chars += len(tx)

        # Τελική ταξινόμηση κατά αριθμό σελίδας
        selected_pages.sort(key=lambda x: x[0])

        if not selected_pages:
            return None   # Δεν εξαχθηκε τίποτα χρήσιμο

        kept    = [pg for pg, _ in selected_pages]
        skipped = total - len(kept)

        header = (
            f"=== ΑΣΦΑΛΙΣΤΙΚΗ ΠΡΟΣΦΟΡΑ: {filename} ===\n"
            f"[Εξαγωγή {len(kept)}/{total} σελίδων — {skipped} νομικές σελίδες παραλείφθηκαν]\n\n"
        )
        body = "\n\n---\n\n".join(
            f"[ΣΕΛΙΔΑ {pg}]\n{tx}" for pg, tx in selected_pages
        )

        return header + body

    except Exception:
        return None   # Fallback σε binary


def _quick_page_count(pdf_bytes: bytes) -> int:
    """Μετράει γρήγορα τις σελίδες χωρίς πλήρες parse."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        n   = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


# ─── EXTRACTION PROMPT ──────────────────────────────────────────────
# FIX: insured_members is now an empty array — no hardcoded example ages.
# Claude will populate it only if the PDF contains member information.

EXTRACT_PROMPT = """
Διάβασε αυτή την ασφαλιστική προσφορά και εξάγαγε τα παρακάτω στοιχεία σε JSON.
Απάντησε ΜΟΝΟ με valid JSON, χωρίς markdown backticks ή οποιοδήποτε άλλο κείμενο.

{
  "insurer": "Όνομα ασφαλιστικής (π.χ. Generali, Morgan Price, NOW Health, ERGO, AXA, Εθνική)",
  "plan_name": "Ακριβές όνομα πλάνου (π.χ. Evolution Standard, Foundation, Full Health)",
  "annual_premium": "Ετήσιο ασφάλιστρο — μόνο αριθμός χωρίς σύμβολο (π.χ. 2626)",
  "currency": "EUR ή USD ή GBP",
  "deductible": "Απαλλαγή — μόνο αριθμός (π.χ. 500)",
  "max_coverage": "Μέγιστο κεφάλαιο ανά έτος — μόνο αριθμός (π.χ. 500000)",
  "geography": "Γεωγραφική κάλυψη (π.χ. Ευρώπη, Παγκόσμια εκτός ΗΠΑ, Ελλάδα και Εξωτερικό)",
  "hospital_class": "Θέση νοσηλείας (π.χ. Α, Β, Standard Room)",

  "inpatient": "Full Refund ή ποσοστό ή Not Covered",

  "outpatient_type": "ΚΡΙΣΙΜΟ ΠΕΔΙΟ — Καθόρισε με ακρίβεια τον τύπο εξωνοσοκομειακής κάλυψης:
    - 'general': καλύπτει ΓΕΝΙΚΑ εξωνοσοκομειακά (ιατρεία, εξετάσεις, lab, ειδικούς εκτός νοσοκομείου)
    - 'hospital_procedures': καλύπτει ΜΟΝΟ επεμβατικές/ενδοσκοπικές πράξεις σε συμβεβλημένα νοσοκομεία ως εξωτερικοί ασθενείς — ΟΧΙ γενικές επισκέψεις/εξετάσεις
    - 'not_covered': δεν καλύπτει εξωνοσοκομειακά
    Διαβάζοντας το PDF: αν αναφέρει 'εξωνοσοκομειακές επεμβάσεις/πράξεις σε συμβεβλημένα' ή 'day surgery outpatient' → 'hospital_procedures'. Αν αναφέρει 'ιατρείο', 'εξετάσεις', 'εξωτερικοί ασθενείς γενικά' → 'general'.",
  "outpatient_limit": "Ανώτατο όριο εξωνοσοκομειακών — μόνο αριθμός ή null αν δεν υπάρχει ή Not Covered",
  "outpatient_pct": "Ποσοστό κάλυψης εξωνοσοκομειακών — μόνο αριθμός ή null",
  "outpatient_note": "Σύντομη περιγραφή ΤΙ ακριβώς καλύπτει (π.χ. 'Ενδοσκοπικές/επεμβατικές σε συμβεβλημένα νοσοκομεία' ή 'Γενικά εξωνοσοκομειακά έως €X' ή null)",

  "mri_ct_pet": "Full Refund ή Not Covered ή σύντομη περιγραφή — ΠΡΟΣΟΧΗ: MRI/CT/PET που γίνεται νοσοκομειακά ΔΕΝ είναι εξωνοσοκομειακό",
  "cancer": "Full Refund ή Not Covered ή σύντομη περιγραφή",
  "physiotherapy": "Ποσό ή Full Refund ή Not Covered",
  "chronic_conditions": "Full Refund ή Not Covered ή περιγραφή",
  "evacuation_repatriation": "Full Refund ή Not Covered ή ποσό",
  "dental_emergency": "Full Refund ή Not Covered ή ποσό",
  "wellness_screening": "Ποσό ή Not Covered (π.χ. 300)",
  "cancer_screening": "Ποσό ή Not Covered (π.χ. 1000)",
  "organ_transplant": "Ποσό ή Full Refund ή Not Covered",
  "hospice_care": "Full Refund ή Not Covered ή περιγραφή",
  "psychiatric_inpatient": "Περιγραφή ή Not Covered (π.χ. 100 ημέρες/lifetime)",
  "psychiatric_outpatient": "Περιγραφή ή Not Covered",
  "home_nursing": "Περιγραφή ή Not Covered",

  "company_type": "ΚΡΙΣΙΜΟ: 'greek' αν είναι ελληνική ασφαλιστική (Generali Hellas, Εθνική, Groupama, Interamerican, Eurolife, ERGO Hellas κλπ). 'international' αν είναι expat/global insurer (Morgan Price, NOW Health, Cigna, Bupa, AXA Global κλπ).",

  "deductible_public": "Εκπιπτόμενο σε δημόσιο νοσοκομείο — μόνο αριθμός (συνήθως 0) ή null",
  "deductible_ods": "Εκπιπτόμενο για χειρουργεία ημέρας χωρίς διανυκτέρευση (ODS) — μόνο αριθμός ή null",
  "emergency_er_limit": "Κάλυψη επειγόντων εξωτερικών ιατρείων — ανώτατο ποσό ανά περιστατικό (μόνο αριθμός) ή null",
  "emergency_er_copay": "Ποσοστό συμμετοχής στα επείγοντα — μόνο αριθμός (π.χ. 10) ή null",
  "emergency_er_incidents": "Μέγιστα επείγοντα περιστατικά ανά έτος — μόνο αριθμός ή null",
  "specific_diagnostics_limit": "Ειδικές διαγνωστικές χωρίς νοσηλεία (γαστροσκόπηση, κολονοσκόπηση, κυστεοσκόπηση, βιοψία) — ανώτατο ποσό/έτος μόνο αριθμός ή null",
  "specific_diagnostics_copay": "Συμμετοχή στις ειδικές διαγνωστικές — μόνο αριθμός ή null",
  "second_opinion": "Δεύτερη ιατρική γνώμη — σύντομη περιγραφή (π.χ. '13 ασθένειες, 2x/ασθένεια') ή Not Covered",
  "zero_deductible_serious": "Μηδενισμός εκπιπτόμενου για σοβαρές ασθένειες — περιγραφή ή Not Covered",
  "rehabilitation_limit": "Κέντρα αποκατάστασης/αποθεραπείας — ανώτατο ποσό (μόνο αριθμός) ή null",
  "maternity_allowance": "Επίδομα τοκετού — ποσό (μόνο αριθμός, χαμηλότερο εάν κλιμακωτό) ή null",
  "annual_checkup_count": "Αριθμός εξετάσεων ετήσιου προληπτικού ελέγχου — μόνο αριθμός ή null",
  "telemedicine": "Τηλεϊατρική — σύντομη περιγραφή ή Not Covered",
  "accident_outpatient_limit": "Ατύχημα εκτός νοσοκομείου (ιατροφαρμακευτικά) — ανώτατο ποσό μόνο αριθμός ή null",
  "accident_outpatient_copay": "Συμμετοχή ατυχήματος εκτός νοσ. — μόνο αριθμός ή null",
  "dental_network_discount": "Οδοντιατρικές εκπτώσεις δικτύου — σύντομη περιγραφή ή Not Covered. ΣΗΜΑΝΤΙΚΟ: ΟΧΙ κάλυψη θεραπείας.",
  "psychiatric_post_hosp": "Ψυχολογική υποστήριξη ΜΕΤΑ νοσηλεία — περιγραφή ή Not Covered",

  "waiting_period": "Αναμονή για παθήσεις (π.χ. Άμεση ή 6 μήνες ή 24 μήνες)",
  "preexisting": "Κάλυψη προϋπαρχουσών παθήσεων (π.χ. Άμεση MHD ή μετά 12 μήνες ή Όχι)",
  "payment_frequency": "Μηνιαία ή Τριμηνιαία ή Εξαμηνιαία ή Ετήσια",

  "insured_members": [],

  "key_notes": ["σύντομη παρατήρηση 1", "σύντομη παρατήρηση 2"]
}

Κανόνες:
- Αν κάποιο πεδίο δεν βρεθεί στο PDF, βάλε null.
- outpatient_type ΚΡΙΣΙΜΟ: 'hospital_procedures' αν καλύπτει μόνο ειδικές εξετάσεις/επεμβάσεις σε συμβεβλημένα νοσοκομεία. 'general' αν καλύπτει ιατρεία, εξετάσεις, ειδικούς εκτός νοσοκομείου.
- company_type: Generali Hellas/Εθνική/Groupama/Interamerican/Eurolife/ERGO = 'greek'. Morgan Price/NOW Health/Cigna/Bupa/AXA International = 'international'.
- Για ελληνικές (company_type='greek'): mri_ct_pet εκτός νοσηλείας = 'Δεν Καλύπτεται'. psychiatric_outpatient = 'Δεν Καλύπτεται'.
- Για ελληνικές εταιρείες χρησιμοποίησε ΕΛΛΗΝΙΚΑ για τιμές κάλυψης: 'Δεν Καλύπτεται' αντί 'Not Covered', 'Πλήρης Κάλυψη' αντί 'Full Refund', 'Καλύπτεται' αντί 'Covered'.
- Για διεθνείς εταιρείες χρησιμοποίησε ΑΓΓΛΙΚΑ: 'Not Covered', 'Full Refund', 'Covered'.
- Μην εφεύρεις πληροφορίες που δεν υπάρχουν στο PDF.
- key_notes: 2-4 σημαντικές παρατηρήσεις που βρίσκονται στο κείμενο.
"""


# ─── PDF EXTRACTION ─────────────────────────────────────────────────

def extract_insurance_data(pdf_bytes: bytes, api_key: str, filename: str = "") -> dict:
    """
    Εξάγει ασφαλιστικά δεδομένα από PDF με Claude.

    Για μεγάλα PDFs (> 6 σελίδες ή > 60 KB): εξάγει έξυπνα μόνο
    τις σχετικές σελίδες ως κείμενο — πολύ λιγότερα tokens.
    Για μικρά PDFs: στέλνει το binary απευθείας.
    """
    client = anthropic.Anthropic(api_key=api_key)

    # ── Απόφαση: text extraction ή binary PDF ──
    extracted_text = smart_pdf_to_text(pdf_bytes, filename)

    if extracted_text:
        # Έξυπνη εξαγωγή — στέλνει μόνο το κείμενο
        pages_kept = extracted_text.count("[ΣΕΛΙΔΑ ")
        st.info(
            f"📄 «{filename}»: μεγάλο PDF — "
            f"εξαγωγή {pages_kept} σελίδων (νομικά κείμενα παραλείφθηκαν)",
            icon="✂️"
        )
        user_content = [
            {"type": "text", "text": extracted_text},
            {"type": "text", "text": EXTRACT_PROMPT},
        ]
    else:
        # Μικρό PDF — στείλε binary
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
        user_content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": pdf_b64,
                },
            },
            {"type": "text", "text": EXTRACT_PROMPT},
        ]

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": user_content,
                }],
            )
            raw = response.content[0].text.strip()
            # Robust JSON extraction: strip code fences, then find the outermost {...}
            raw = re.sub(r"```json|```", "", raw).strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                raw = m.group(0)
            data = json.loads(raw)

            # ── Exclusions & safety analysis (from PythonProject5) ──
            # Use the full extracted text (or raw PDF text if available)
            text_for_exclusions = extracted_text or ""
            exc = detect_exclusions(text_for_exclusions, insurer=data.get("insurer", filename))
            data["_exclusions"]    = exc
            data["_safety_rating"] = exc["safety_rating"]
            data["_risk_flags"]    = exc["risk_flags"]
            data["_multidim"]      = compute_multidim_score(data)

            return data

        except anthropic.RateLimitError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                wait  = RETRY_WAIT_BASE * (2 ** attempt)   # 10s → 20s → 40s
                label = f" ({filename})" if filename else ""
                st.warning(
                    f"⏳ Rate limit{label} — αναμονή {wait}s "
                    f"(απόπειρα {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Rate limit μετά από {MAX_RETRIES} απόπειρες. "
                    "Δοκίμασε ξανά σε λίγο ή μείωσε τον αριθμό PDFs."
                ) from e

        except anthropic.APIStatusError as e:
            raise RuntimeError(
                f"Claude API σφάλμα: {e.status_code} — {e.message}"
            ) from e

        except json.JSONDecodeError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                label = f" ({filename})" if filename else ""
                st.warning(
                    f"⚠️ Μη-έγκυρο JSON{label} — επανάληψη "
                    f"(απόπειρα {attempt + 1}/{MAX_RETRIES})..."
                )
                time.sleep(2)
            else:
                raise RuntimeError(
                    "Το Claude επέστρεψε μη-έγκυρο JSON μετά από πολλαπλές απόπειρες. "
                    "Δοκίμασε ξανά ή έλεγξε το PDF."
                ) from e

    raise RuntimeError("Αποτυχία εξαγωγής δεδομένων.") from last_error


# ─── COVERAGE SCORE ─────────────────────────────────────────────────

def compute_score(prop: dict, mode: str = "auto") -> float:
    """
    Return a weighted coverage quality score from 0.0 to 10.0.

    mode:
      "auto"         — auto-detect from prop['company_type']
      "greek_only"   — Greek market weights (removes intl-only fields,
                       adds Greek-specific fields to scoring)
      "mixed" / "international_only" — original international weights

    Greek vs International differences in scoring:
      - MRI/CT/PET outpatient: not scored for Greek (always Not Covered)
      - psychiatric_outpatient: not scored for Greek (not in market)
      - outpatient 'hospital_procedures': treated as NORMAL for Greek
        (all Greek companies have this — it's not a downgrade)
      - Greek-specific fields added: checkup, emergency_er, rehab,
        accident_outpatient
    """

    def covered(field: str) -> bool:
        v = prop.get(field)
        if v is None:
            return False
        s = str(v).strip()
        return s not in ("", "null", "None", "—", "Δεν Καλύπτεται") and \
               "Not Covered" not in s and "Δεν Καλύπτεται" not in s

    # ── Determine effective mode ──────────────────────────────────────
    if mode == "auto":
        ctype = str(prop.get("company_type") or "").lower()
        if ctype == "greek":
            mode = "greek_only"
        elif ctype == "international":
            mode = "international_only"
        else:
            mode = "greek_only"   # conservative default for unknown

    is_greek = mode == "greek_only"

    if is_greek:
        # ── GREEK weights: MRI/psych_out removed, greek-specific added ──
        weights = {
            "inpatient":              20,
            "cancer":                 15,
            "chronic_conditions":      6,   # reduced (ambiguous in Greek context)
            "evacuation_repatriation": 5,
            "max_coverage":           12,
            "outpatient_limit":        5,   # hospital_procedures = normal → less penalty
            # Greek-specific benefits
            "emergency_er_limit":      5,   # ER coverage at affiliated hospitals
            "specific_diagnostics_limit": 4, # gastro/colono/biopsy
            "rehabilitation_limit":    4,
            "annual_checkup_count":    4,
            "accident_outpatient_limit": 3,
            "home_nursing":            3,
            "maternity_allowance":     3,
            "second_opinion":          2,
            "telemedicine":            2,
            "zero_deductible_serious": 2,
            "physiotherapy":           3,
            "wellness_screening":      2,
        }

        score = 0.0

        # Binary standard fields (minus intl-only)
        for field in ["inpatient", "cancer", "chronic_conditions",
                      "evacuation_repatriation", "physiotherapy",
                      "wellness_screening", "home_nursing"]:
            if covered(field):
                score += weights[field]

        # Greek-specific binary fields
        for field in ["second_opinion", "telemedicine", "zero_deductible_serious"]:
            if covered(field):
                score += weights.get(field, 0)

        # Greek-specific numeric fields
        for field, thresholds in [
            ("emergency_er_limit",       [(500, 1.0), (200, 0.6)]),
            ("specific_diagnostics_limit",[(1000, 1.0), (500, 0.6)]),
            ("rehabilitation_limit",      [(10000, 1.0), (5000, 0.7)]),
            ("accident_outpatient_limit", [(1000, 1.0), (500, 0.6)]),
            ("maternity_allowance",       [(1500, 1.0), (500, 0.5)]),
        ]:
            v_raw = prop.get(field)
            if v_raw and str(v_raw).strip() not in ("", "null", "None", "Not Covered"):
                try:
                    v = int(str(v_raw).replace(",", ""))
                    for threshold, mult in thresholds:
                        if v >= threshold:
                            score += weights.get(field, 0) * mult
                            break
                except (ValueError, TypeError):
                    score += weights.get(field, 0) * 0.5

        # Annual checkup
        ck = prop.get("annual_checkup_count")
        if ck and str(ck).strip() not in ("", "null", "None"):
            try:
                n = int(str(ck))
                if n >= 20:   score += weights["annual_checkup_count"]
                elif n >= 10: score += weights["annual_checkup_count"] * 0.7
                elif n > 0:   score += weights["annual_checkup_count"] * 0.4
            except (ValueError, TypeError):
                score += weights["annual_checkup_count"] * 0.5

        # ── Outpatient for Greek: 'hospital_procedures' = NORMAL, not a downgrade
        ol    = prop.get("outpatient_limit")
        otype = str(prop.get("outpatient_type") or "").lower().strip()
        if otype in ("hospital_procedures", "general") and ol:
            if str(ol).strip() not in ("Not Covered", "null", "None", ""):
                try:
                    v = int(str(ol).replace(",", ""))
                    if   v >= 1000: score += weights["outpatient_limit"]
                    elif v > 0:     score += weights["outpatient_limit"] * 0.6
                except (ValueError, TypeError):
                    score += weights["outpatient_limit"] * 0.5

        # Max coverage
        mc = prop.get("max_coverage")
        if mc:
            try:
                v = int(str(mc).replace(",", ""))
                if   v >= 1_500_000: score += weights["max_coverage"]
                elif v >= 1_000_000: score += weights["max_coverage"] * 0.85
                elif v >=   750_000: score += weights["max_coverage"] * 0.75
                elif v >=   500_000: score += weights["max_coverage"] * 0.60
            except (ValueError, TypeError):
                pass

    else:
        # ── INTERNATIONAL weights (original logic, unchanged) ──────────
        weights = {
            "inpatient":              20,
            "cancer":                 15,
            "mri_ct_pet":              8,
            "chronic_conditions":      8,
            "evacuation_repatriation": 6,
            "max_coverage":           12,
            "outpatient_limit":        8,
            "physiotherapy":           5,
            "psychiatric_outpatient":  3,
            "dental_emergency":        4,
            "wellness_screening":      3,
            "cancer_screening":        3,
            "organ_transplant":        3,
            "hospice_care":            2,
        }

        score = 0.0

        binary = [
            "inpatient", "cancer", "mri_ct_pet", "chronic_conditions",
            "evacuation_repatriation", "physiotherapy", "psychiatric_outpatient",
            "dental_emergency", "wellness_screening", "cancer_screening",
            "organ_transplant", "hospice_care",
        ]
        for field in binary:
            if covered(field):
                score += weights[field]

        # Outpatient — type-aware (original logic)
        ol    = prop.get("outpatient_limit")
        otype = str(prop.get("outpatient_type") or "").lower().strip()
        outpatient_multiplier = 0.0
        if otype == "general":
            outpatient_multiplier = 1.0
        elif otype == "hospital_procedures":
            outpatient_multiplier = 0.30
        if outpatient_multiplier > 0 and ol and str(ol).strip() not in ("Not Covered", "null", "None", ""):
            try:
                v = int(str(ol).replace(",", ""))
                if   v >= 5_000: score += weights["outpatient_limit"] * outpatient_multiplier
                elif v >= 2_000: score += weights["outpatient_limit"] * outpatient_multiplier * 0.7
                elif v >  0:     score += weights["outpatient_limit"] * outpatient_multiplier * 0.4
            except (ValueError, TypeError):
                score += weights["outpatient_limit"] * outpatient_multiplier * 0.5

        # Max coverage (original)
        mc = prop.get("max_coverage")
        if mc:
            try:
                v = int(str(mc).replace(",", ""))
                if   v >= 1_500_000: score += weights["max_coverage"]
                elif v >= 1_000_000: score += weights["max_coverage"] * 0.85
                elif v >=   500_000: score += weights["max_coverage"] * 0.65
                elif v >=   250_000: score += weights["max_coverage"] * 0.40
            except (ValueError, TypeError):
                pass

    total_weight = sum(weights.values())
    return round((score / total_weight) * 10, 1)


def compute_premium_efficiency(prop: dict, mode: str = "auto") -> float:
    """
    Value metric: coverage score per €1000 of annual premium.
    Higher = better value for money.
    Shown in UI as extra context — NOT part of coverage score.
    """
    score   = compute_score(prop, mode=mode)
    premium = prop.get("annual_premium")
    if not premium:
        return 0.0
    try:
        p = float(str(premium).replace(",", ""))
        return round(score / (p / 1000), 2) if p > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0
