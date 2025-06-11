import streamlit as st
import requests
import json

# Streamlit page config
st.set_page_config(page_title="Milliman Dashboard Client", layout="wide")
st.title("📬 Milliman Dashboard Tool Invoker")

# 1) Server URL input
def get_base_url():
    return st.sidebar.text_input(
        "FastMCP Server URL", 
        value="http://localhost:8000",
        help="Enter your server's base URL (e.g. http://localhost:8000)"
    )

# 2) Choose an action
action = st.sidebar.radio(
    "Action:",
    options=["get_token", "mcid_search", "submit_medical", "call_all"],
    index=3 if False else 3
)

# 3) JSON payload editor for actions that need it
defaults = {
    "mcid_search": {
        "requestID": "1",
        "processStatus": {"completed":"false","isMemput":"false","errorCode":None,"errorText":None},
        "consumer": [{
            "firstName":"JUNEY","lastName":"TROR","middleName":None,
            "sex":"F","dob":"196971109",
            "addressList":[{"type":"P","zip":None}],
            "id":{"ssn":None}
        }],
        "searchSetting": {"minScore":"100","maxResult":"1"}
    },
    "submit_medical": {
        "requestID":"77554079","firstName":"JUNEY","lastName":"TROR","ssn":"148681406",
        "dateOfBirth":"1978-01-20","gender":"F",
        "zipCodes":["23060","23229","23242"],"callerId":"Milliman-Test16"
    }
}

payload = None
if action in ["mcid_search", "submit_medical"]:
    raw = st.text_area(
        label="JSON payload:",
        value=json.dumps(defaults[action], indent=2),
        height=250
    )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

# 4) Invoke button
if st.button("▶️ Invoke"):
    base_url = get_base_url().rstrip('/')
    if action == "call_all":
        url = f"{base_url}/all"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
        else:
            st.success(f"{resp.status_code} OK")
            st.json(resp.json())
    else:
        url = f"{base_url}/tool/{action}"
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
        else:
            st.success(f"{resp.status_code} OK")
            st.json(resp.json())

# 5) Footer
st.markdown("---")
st.caption("Ensure your FastMCP server is running and reachable before invoking.")
