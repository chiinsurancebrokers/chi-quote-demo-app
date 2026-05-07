# CHI Insurance Quote Engine — Demo Version

Δοκιμαστική έκδοση με όριο 7 δωρεάν παρουσιάσεων.

## Εκκίνηση

```bash
pip install -r requirements.txt
streamlit run app.py
```

Χρειάζεται Anthropic API key — βάλε στο `.streamlit/secrets.toml`:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

## Deploy (Streamlit Community Cloud — δωρεάν)

1. Push σε GitHub repo
2. Πήγαινε στο share.streamlit.io
3. Σύνδεσε το repo → Deploy
4. Βάλε το API key στα Secrets του Streamlit Cloud

Η εφαρμογή κλειδώνει μετά από 7 παρουσιάσεις και δείχνει
οθόνη επικοινωνίας για αγορά.

## Αλλαγή ορίου

Στο `trial_lock.py` → αλλαγή `TRIAL_LIMIT = 7`
