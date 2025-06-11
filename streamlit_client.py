import streamlit as st
import requests, json

st.set_page_config(page_title="Milliman Dashboard Client", layout="wide")
st.title("📬 Milliman Dashboard Tool Invoker")

# ——— Inputs ———
base_url = st.text_input("Server URL", "http://localhost:8000")
tool = st.selectbox("Tool", ["get_token", "mcid_search", "submit_medical"])

# default payloads
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

# ——— JSON editor ———
if tool in defaults:
    raw = st.text_area(
        "JSON payload",
        value=json.dumps(defaults[tool], indent=2),
        height=200
    )
else:
    raw = "{}"

if st.button("Invoke"):
    endpoint = f"{base_url.rstrip('/')}/tool/{tool}"
    try:
        payload = json.loads(raw) if tool != "get_token" else None
    except json.JSONDecodeError as e:
        st.error(f"Invalid JSON: {e}")
        st.stop()

    with st.spinner(f"POST {endpoint}"):
        try:
            if tool == "get_token":
                resp = requests.post(endpoint, timeout=30)
            else:
                resp = requests.post(endpoint, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")
        else:
            st.success(f"{resp.status_code} OK")
            st.json(resp.json())
