import streamlit as st
import requests

st.set_page_config(page_title="Milliman MCP Client", layout="centered")
st.title("🏥 MCID + Medical Claims Submission")

API_URL = "http://localhost:8000/tool/invoke"

with st.form("submit_form"):
    fname = st.text_input("First Name", value="JUNEY")
    lname = st.text_input("Last Name", value="TROR")
    gender = st.selectbox("Gender", ["F", "M"])
    dob = st.text_input("Date of Birth (YYYY-MM-DD)", value="1978-01-20")
    ssn = st.text_input("SSN", value="148681406")
    zipcodes = st.text_input("ZIP Codes (comma-separated)", value="23060,23229,23242")

    submitted = st.form_submit_button("Submit")

if submitted:
    data = {
        "mcid_payload": {
            "requestID": "1",
            "consumer": [{
                "firstName": fname,
                "lastName": lname,
                "sex": gender,
                "dob": dob.replace("-", ""),
                "addressList": [{"type": "P", "zip": None}],
                "id": {"ssn": ssn}
            }],
            "searchSetting": {
                "minScore": "100",
                "maxResult": "1"
            }
        },
        "medical_payload": {
            "requestID": "REQ001",
            "firstName": fname,
            "lastName": lname,
            "ssn": ssn,
            "dateOfBirth": dob,
            "gender": gender,
            "zipCodes": [z.strip() for z in zipcodes.split(",")],
            "callerId": "Milliman-Streamlit"
        }
    }

    with st.spinner("Calling MCP server..."):
        response = requests.post(API_URL, json={"tool": "submit_requests", "input": data})
        result = response.json()
        st.success("✅ Response received!")

        st.subheader("MCID Response")
        st.json(result["content"]["mcid_response"])

        st.subheader("Medical Claims Response")
        st.json(result["content"]["medical_response"])
