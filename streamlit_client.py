import streamlit as st
import requests
import json

st.set_page_config(page_title="Milliman MCP Client", layout="wide")
st.title("📬 Milliman Dashboard Tool Invoker")

# Base URL input
base_url = st.text_input(
    "FastMCP Server URL",
    value="http://localhost:8000",
    help="Enter your FastMCP server base URL (e.g. http://localhost:8000)"
).rstrip("/")

# Tool selector
tool = st.selectbox(
    "Tool to invoke:",
    options=["get_token", "mcid_search", "submit_medical", "all"]
)

# Default payloads for POST tools
defaults = {
    "mcid_search": {
        "requestID": "1",
        "processStatus": {"completed":"false","isMemput":"false","errorCode":None,"errorText":None},
        "consumer":[{"firstName":"JUNEY","lastName":"TROR","middleName":None,"sex":"F","dob":"196971109","addressList":[{"type":"P","zip":None}],"id":{"ssn":None}}],
        "searchSetting":{"minScore":"100","maxResult":"1"}
    },
    "submit_medical": {
        "requestID":"77554079","firstName":"JUNEY","lastName":"TROR","ssn":"148681406",
        "dateOfBirth":"1978-01-20","gender":"F",
        "zipCodes":["23060","23229","23242"],"callerId":"Milliman-Test16"
    }
}

# JSON payload editor
payload = None
if tool in defaults:
    raw = st.text_area(
        "JSON payload:",
        value=json.dumps(defaults[tool], indent=2),
        height=200
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

# Invoke button
if st.button("▶️ Invoke"):
    endpoint = f"{base_url}/tool/{tool}"
    try:
        if tool in ["get_token", "all"]:
            resp = requests.post(endpoint, json={}, timeout=30)
        else:
            resp = requests.post(endpoint, json=payload, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Request failed: {e}")
    else:
        st.success(f"{resp.status_code} OK")
        st.json(resp.json())
