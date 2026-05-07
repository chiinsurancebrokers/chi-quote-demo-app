"""
CHI Insurance Brokers — Email Templates
========================================
Ready-made email templates for follow-up reminders in Greek and English.
"""

from datetime import date


BROKER_SIGNATURE_EL = """
---
{broker_name}
CHI Insurance Brokers
📞 {broker_tel}
✉️  {broker_email}
🌐 www.chiinsurancebrokers.com
"""

BROKER_SIGNATURE_EN = """
---
{broker_name}
CHI Insurance Brokers
📞 {broker_tel}
✉️  {broker_email}
🌐 www.chiinsurancebrokers.com
"""


TEMPLATES = {

    # ─── GREEK TEMPLATES ─────────────────────────────────────────────

    "el_first_followup": {
        "label":   "1η Υπενθύμιση (EL)",
        "subject": "Υπενθύμιση: Η Πρότασή μας για Ασφάλιση Υγείας — {applicant_name}",
        "body": """\
Αγαπητέ/ή {applicant_name},

Ελπίζω να είστε καλά.

Σας έχω αποστείλει πρόσφατα μια αναλυτική σύγκριση ασφαλιστικών προτάσεων \
και θα ήθελα να ελέγξω αν είχατε την ευκαιρία να την εξετάσετε.

Η κορυφαία πρότασή μας για εσάς είναι το πλάνο **{recommended_plan}** \
της **{recommended_insurer}**, με ετήσιο ασφάλιστρο **{recommended_premium:.2f} {currency}**.

Θα χαρώ να απαντήσω σε οποιαδήποτε ερώτηση ή να κλείσουμε μια σύντομη συνάντηση.

Με εκτίμηση,
{signature}
""",
    },

    "el_second_followup": {
        "label":   "2η Υπενθύμιση (EL)",
        "subject": "Τελευταία υπενθύμιση: Πρόταση Ασφάλισης Υγείας",
        "body": """\
Αγαπητέ/ή {applicant_name},

Σας στέλνω αυτό το τελευταίο μήνυμα σχετικά με την πρόταση ασφάλισης υγείας \
που σας έχουμε ετοιμάσει.

Καταλαβαίνω ότι η επιλογή ασφαλιστικού πλάνου απαιτεί χρόνο και σκέψη. \
Αν έχετε οποιεσδήποτε ερωτήσεις ή θέλετε να συζητήσουμε τις επιλογές σας, \
είμαι στη διάθεσή σας.

Η πρόταση **{recommended_plan}** της **{recommended_insurer}** \
παραμένει ανοιχτή και θα χαρώ να σας βοηθήσω να προχωρήσετε.

Με εκτίμηση,
{signature}
""",
    },

    "el_renewal": {
        "label":   "Ανανέωση Συμβολαίου (EL)",
        "subject": "Ανανέωση Ασφαλιστηρίου — {applicant_name} | Λήξη: {renewal_date}",
        "body": """\
Αγαπητέ/ή {applicant_name},

Σας ενημερώνω ότι το ασφαλιστήριό σας ({insurer} — {plan}) \
λήγει στις **{renewal_date}**.

Θα ήθελα να επικοινωνήσουμε για να εξετάσουμε:
✓ Ανανέωση με τους ίδιους όρους
✓ Νέες προσφορές από την αγορά (έχουν αλλάξει τιμές και παροχές)
✓ Οποιεσδήποτε αλλαγές στις ανάγκες σας

Παρακαλώ επικοινωνήστε μαζί μου για να κλείσουμε ραντεβού.

Με εκτίμηση,
{signature}
""",
    },

    "el_quote_sent": {
        "label":   "Αποστολή Προσφοράς (EL)",
        "subject": "Συγκριτική Ανάλυση Ασφαλιστικών Προτάσεων — {applicant_name}",
        "body": """\
Αγαπητέ/ή {applicant_name},

Σε συνέχεια της συνομιλίας μας, σας αποστέλλω την αναλυτική σύγκριση \
ασφαλιστικών προτάσεων που έχουμε ετοιμάσει ειδικά για εσάς.

📊 Έχουμε συγκρίνει: {insurers}
⭐ Κορυφαία πρότασή μας: **{recommended_plan}** — {recommended_insurer}
   Ετήσιο ασφάλιστρο: **{recommended_premium:.2f} {currency}**

Θα χαρώ να σας εξηγήσω γιατί αυτή η πρόταση ταιριάζει καλύτερα \
στις ανάγκες σας και να απαντήσω σε οποιεσδήποτε ερωτήσεις.

Με εκτίμηση,
{signature}
""",
    },

    # ─── ENGLISH TEMPLATES ───────────────────────────────────────────

    "en_first_followup": {
        "label":   "1st Follow-up (EN)",
        "subject": "Follow-up: Your Health Insurance Quote — {applicant_name}",
        "body": """\
Dear {applicant_name},

I hope you are well.

I wanted to follow up on the health insurance comparison I recently sent you \
and check whether you had the chance to review it.

Our top recommendation for you is the **{recommended_plan}** plan \
by **{recommended_insurer}**, with an annual premium of **{recommended_premium:.2f} {currency}**.

I would be happy to answer any questions or schedule a brief call at your convenience.

Kind regards,
{signature}
""",
    },

    "en_second_followup": {
        "label":   "2nd Follow-up (EN)",
        "subject": "Final follow-up: Health Insurance Proposal",
        "body": """\
Dear {applicant_name},

I am reaching out one final time regarding the health insurance proposal \
we prepared for you.

I understand that choosing a health insurance plan requires careful consideration. \
Please do not hesitate to reach out if you have any questions or \
would like to revisit the options.

The **{recommended_plan}** plan by **{recommended_insurer}** \
remains available and I would be glad to assist you in moving forward.

Kind regards,
{signature}
""",
    },

    "en_renewal": {
        "label":   "Policy Renewal (EN)",
        "subject": "Policy Renewal Notice — {applicant_name} | Expires: {renewal_date}",
        "body": """\
Dear {applicant_name},

This is a reminder that your insurance policy ({insurer} — {plan}) \
is due for renewal on **{renewal_date}**.

I would like to connect with you to discuss:
✓ Renewal on the same terms
✓ New market quotes (premiums and benefits have changed)
✓ Any updates to your coverage needs

Please reach out so we can schedule a convenient time to speak.

Kind regards,
{signature}
""",
    },
}


def build_email(
    template_key: str,
    applicant: dict,
    quote: dict = None,
    contract: dict = None,
    broker_name: str = "Ιατρόπουλος Χρήστος",
    broker_tel: str = "+30 697 590 0189",
    broker_email: str = "info@chiinsurancebrokers.com",
    lang: str = "el",
) -> dict:
    """
    Fill a template with actual data.
    Returns {"subject": str, "body": str}.
    """
    tmpl = TEMPLATES.get(template_key, TEMPLATES["el_first_followup"])
    sig_tmpl = BROKER_SIGNATURE_EL if lang == "el" else BROKER_SIGNATURE_EN
    signature = sig_tmpl.format(
        broker_name=broker_name, broker_tel=broker_tel, broker_email=broker_email
    )

    q = quote or {}
    c = contract or {}
    insurers_str = " · ".join(q.get("insurers", [])) if q.get("insurers") else "—"

    ctx = {
        "applicant_name":      applicant.get("name", ""),
        "recommended_insurer": q.get("recommended_insurer") or c.get("insurer") or "—",
        "recommended_plan":    q.get("recommended_plan")    or c.get("plan")    or "—",
        "recommended_premium": float(q.get("recommended_premium") or c.get("annual_premium") or 0),
        "currency":            q.get("currency") or c.get("currency") or "EUR",
        "insurers":            insurers_str,
        "insurer":             c.get("insurer", "—"),
        "plan":                c.get("plan", "—"),
        "renewal_date":        c.get("renewal_date", "—"),
        "signature":           signature,
    }

    subject = tmpl["subject"].format(**ctx)
    body    = tmpl["body"].format(**ctx)
    return {"subject": subject, "body": body}


def get_template_options(lang: str = "el") -> list[tuple[str, str]]:
    """Return list of (template_key, label) for the given language."""
    prefix = f"{lang}_"
    return [(k, v["label"]) for k, v in TEMPLATES.items() if k.startswith(prefix)]
