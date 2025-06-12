import streamlit as st
import requests

# Page configuration
st.set_page_config(
    page_title="Milliman MCP Client", 
    page_icon="📡", 
    layout="wide"
)

# Sidebar for server URL configuration
with st.sidebar:
    st.header("Server Configuration")
    server_url = st.text_input(
        "MCP Server Base URL", 
        value="http://localhost:8000",
        help="Enter the base URL of your Milliman MCP server"
    ).rstrip("/")

# Main form for person details
st.title("📡 Milliman MCP Streamlit Client")
st.subheader("Enter Person Details and Execute All MCP Endpoints")

with st.form("person_form"):
    col1, col2 = st.columns(2)
    with col1:
        first_name = st.text_input("First Name", placeholder="John")
        last_name = st.text_input("Last Name", placeholder="Doe")
        ssn = st.text_input("SSN", placeholder="123-45-6789")
    with col2:
        date_of_birth = st.date_input("Date of Birth")
        gender = st.selectbox("Gender", ["M", "F", "Other"] )
        zip_codes_str = st.text_input(
            "Zip Codes (comma separated)", 
            placeholder="12345, 67890"
        )
    submitted = st.form_submit_button("Run All Endpoints")

if submitted:
    # Prepare payload
    person_data = {
        "firstName": first_name.strip(),
        "lastName": last_name.strip(),
        "ssn": ssn.strip(),
        "dateOfBirth": date_of_birth.strftime("%Y-%m-%d"),
        "gender": gender if gender in ["M", "F"] else gender[0],
        "zipCodes": [z.strip() for z in zip_codes_str.split(",") if z.strip()]
    }

    # Define MCP endpoints to call
    endpoints = {
        "Search MCID": "/tool/search_mcid",
        "Submit Medical": "/tool/submit_medical",
        "Get Both": "/tool/get_both",
        "Get Auth Token": "/tool/get_auth_token",
        "Debug Transforms": "/tool/debug_transforms",
        "Test Connection": "/tool/test_connection"
    }

    # Display raw JSON responses
    for title, path in endpoints.items():
        st.markdown(f"### {title}")
        try:
            with st.spinner(f"Calling {title}..."):
                url = server_url + path
                if "get_auth_token" in path or title == "Get Auth Token":
                    resp = requests.get(url, timeout=30)
                else:
                    resp = requests.post(url, json=person_data, timeout=30)
                resp.raise_for_status()
                st.json(resp.json())
        except Exception as e:
            st.error(f"Error calling {title}: {e}")

# Instructions
st.markdown(
    "---\n"
    "**How to run:** Save this file as `streamlit_client.py` and run:\n"
    "```
"
    "pip install streamlit requests\n"
    "streamlit run streamlit_client.py
"
    "```"
)

