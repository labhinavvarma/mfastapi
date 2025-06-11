
# client_app.py
import streamlit as st
import requests, json

st.set_page_config(page_title="Milliman MCP Client", layout="wide")
st.title("📬 Invoke Milliman MCP Tools")

# — Base URL —
base = st.text_input("Server URL", "http://localhost:8000").rstrip("/")

# — Choose tool —
tool = st.selectbox("Tool", ["get_token", "mcid_search", "submit_medical", "all"])

# — JSON editor for POST bodies —
defaults = {
    "mcid_search": { /* your MCID_REQUEST_BODY here */ },
    "submit_medical": { /* your MEDICAL_REQUEST_BODY here */ },
}
payload = None
if tool in defaults:
    raw = st.text_area("JSON payload", value=json.dumps(defaults[tool], indent=2), height=250)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

# — Invoke button —
if st.button("Invoke"):
    url = f"{base}/tool/{tool}"
    try:
        # always POST, even for "all" and "get_token"
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        st.error(f"❌ {e}")
    else:
        st.success(f"✔ {resp.status_code}")
        st.json(resp.json())
