
import streamlit as st
import requests
import json
from datetime import date, datetime
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="Milliman MCP Client",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for better styling ---
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .sub-header {
        font-size: 1.5rem;
        color: #333;
        margin-bottom: 1rem;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    
    .sidebar-header {
        font-size: 1.2rem;
        color: #1f77b4;
        margin-bottom: 0.5rem;
        font-weight: bold;
    }
    
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .endpoint-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    
    .dashboard-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    .dashboard-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
    
    .sidebar-section {
        background-color: #f8f9fa;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration ---
DEFAULT_SERVER_URL = "http://localhost:8000"

# --- Helper Functions ---
def call_endpoint(server_url: str, endpoint: str, data: dict = None, method: str = "POST"):
    """Call an MCP server endpoint"""
    try:
        url = f"{server_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        else:
            response = requests.post(url, json=data, timeout=30)
        
        return {
            "success": True,
            "status_code": response.status_code,
            "response": response.json() if response.content else {},
            "url": url,
            "execution_time": response.elapsed.total_seconds()
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout (30s)",
            "url": url if 'url' in locals() else "Unknown"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Connection error - Is the MCP server running?",
            "url": url if 'url' in locals() else "Unknown"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url if 'url' in locals() else "Unknown"
        }

def display_sidebar_response(title: str, result: dict, icon: str = "🔄"):
    """Display a response card in sidebar with compact formatting"""
    if result.get("success", False):
        st.sidebar.markdown(f"""
        <div class="endpoint-card">
            <h5 style="color: #28a745; margin-bottom: 0.5rem;">{icon} {title}</h5>
            <p style="margin: 0.2rem 0;"><strong>Status:</strong> <span style="color: #28a745;">✅ Success</span></p>
            <p style="margin: 0.2rem 0;"><strong>Code:</strong> {result.get('status_code', 'N/A')}</p>
            <p style="margin: 0.2rem 0;"><strong>Time:</strong> {result.get('execution_time', 'N/A'):.2f}s</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Display response data in sidebar
        with st.sidebar.expander(f"📄 {title} Response Data", expanded=False):
            st.json(result.get("response", {}))
    else:
        st.sidebar.markdown(f"""
        <div class="endpoint-card">
            <h5 style="color: #dc3545; margin-bottom: 0.5rem;">{icon} {title}</h5>
            <p style="margin: 0.2rem 0;"><strong>Status:</strong> <span style="color: #dc3545;">❌ Failed</span></p>
            <p style="margin: 0.2rem 0;"><strong>Error:</strong> {result.get('error', 'Unknown error')}</p>
        </div>
        """, unsafe_allow_html=True)

# --- Main Application ---
def main():
    # Header in main area
    st.markdown('<h1 class="main-header">🏥 Milliman MCP Client</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem;">Search MCID Database and Submit Medical Requests</p>', unsafe_allow_html=True)
    
    # Initialize session state for results
    if 'mcid_result' not in st.session_state:
        st.session_state.mcid_result = None
    if 'medical_result' not in st.session_state:
        st.session_state.medical_result = None
    if 'test_result' not in st.session_state:
        st.session_state.test_result = None
    
    # === SIDEBAR - All inputs and outputs ===
    with st.sidebar:
        st.markdown('<div class="sidebar-header">⚙️ Configuration</div>', unsafe_allow_html=True)
        
        # Server Configuration
        with st.container():
            server_url = st.text_input(
                "MCP Server URL",
                value=DEFAULT_SERVER_URL,
                help="URL of your running MCP server"
            )
            
            # Test connection button
            if st.button("🔍 Test Server Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    test_result = call_endpoint(server_url, "", method="GET")
                    if test_result.get("success", False):
                        st.success("✅ Server is reachable!")
                    else:
                        st.error(f"❌ Connection failed: {test_result.get('error', 'Unknown error')}")
        
        st.markdown("---")
        
        # === INPUT FORM IN SIDEBAR ===
        st.markdown('<div class="sidebar-header">👤 Person Information</div>', unsafe_allow_html=True)
        
        with st.form("person_form_sidebar"):
            # Basic Information
            st.markdown("**Basic Information**")
            first_name = st.text_input("First Name", value="JOHN", help="Person's first name")
            last_name = st.text_input("Last Name", value="DOE", help="Person's last name")
            
            # Personal Details
            st.markdown("**Personal Details**")
            ssn = st.text_input("SSN", value="123456789", help="Social Security Number")
            
            date_of_birth = st.date_input(
                "Date of Birth",
                value=date(1985, 5, 15),
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                help="Person's date of birth"
            )
            
            gender = st.selectbox(
                "Gender",
                options=["M", "F"],
                index=0,
                help="Person's gender"
            )
            
            # Address Information
            st.markdown("**Address Information**")
            zip_codes_input = st.text_input(
                "Zip Codes",
                value="10001, 10002",
                help="Comma-separated list of zip codes"
            )
            
            # Submit buttons
            st.markdown("**Actions**")
            submit_mcid = st.form_submit_button("🔍 Search MCID", use_container_width=True, type="primary")
            submit_medical = st.form_submit_button("🏥 Submit Medical", use_container_width=True)
            submit_test = st.form_submit_button("🌐 Test Connection", use_container_width=True)
            submit_both = st.form_submit_button("🚀 Execute Both", use_container_width=True)
        
        # === PROCESS FORM SUBMISSIONS ===
        if submit_mcid or submit_medical or submit_test or submit_both:
            # Prepare data
            zip_codes = [zip_code.strip() for zip_code in zip_codes_input.split(",") if zip_code.strip()]
            
            person_data = {
                "firstName": first_name.strip(),
                "lastName": last_name.strip(),
                "ssn": ssn.strip(),
                "dateOfBirth": date_of_birth.strftime("%Y-%m-%d"),
                "gender": gender,
                "zipCodes": zip_codes
            }
            
            # Validate data
            if not all([first_name.strip(), last_name.strip(), ssn.strip(), zip_codes]):
                st.error("❌ Please fill in all required fields")
            else:
                # Display submitted data in sidebar
                st.markdown("---")
                st.markdown('<div class="sidebar-header">📝 Submitted Data</div>', unsafe_allow_html=True)
                with st.expander("View Submitted Data", expanded=False):
                    st.json(person_data)
                
                # Execute endpoints based on button clicked
                st.markdown("---")
                st.markdown('<div class="sidebar-header">📊 API Results</div>', unsafe_allow_html=True)
                
                if submit_mcid or submit_both:
                    with st.spinner("Searching MCID database..."):
                        st.session_state.mcid_result = call_endpoint(server_url, "search_mcid", person_data)
                    display_sidebar_response("MCID Search", st.session_state.mcid_result, "🔍")
                
                if submit_medical or submit_both:
                    with st.spinner("Submitting medical request..."):
                        st.session_state.medical_result = call_endpoint(server_url, "submit_medical", person_data)
                    display_sidebar_response("Medical Submission", st.session_state.medical_result, "🏥")
                
                if submit_test:
                    with st.spinner("Testing all API connections..."):
                        st.session_state.test_result = call_endpoint(server_url, "test_connection", person_data)
                    display_sidebar_response("API Connectivity Test", st.session_state.test_result, "🌐")
                    
                    # Display detailed connectivity results
                    if st.session_state.test_result.get("success", False) and "response" in st.session_state.test_result:
                        response_data = st.session_state.test_result["response"]
                        if "token_api" in response_data:
                            with st.expander("🔍 Connection Details", expanded=False):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    token_status = "✅" if response_data["token_api"].get("reachable", False) else "❌"
                                    st.metric("Token", token_status, delta=response_data["token_api"].get("status", "Unknown"))
                                with col2:
                                    mcid_status = "✅" if response_data["mcid_api"].get("reachable", False) else "❌"
                                    st.metric("MCID", mcid_status, delta=response_data["mcid_api"].get("status", "Unknown"))
                                with col3:
                                    medical_status = "✅" if response_data["medical_api"].get("reachable", False) else "❌"
                                    st.metric("Medical", medical_status, delta=response_data["medical_api"].get("status", "Unknown"))
                
                # Export results option
                st.markdown("---")
                st.markdown('<div class="sidebar-header">💾 Export Results</div>', unsafe_allow_html=True)
                
                if st.button("📥 Download Results as JSON", use_container_width=True):
                    # Prepare export data
                    export_data = {
                        "timestamp": datetime.now().isoformat(),
                        "person_data": person_data,
                        "server_url": server_url,
                        "results": {}
                    }
                    
                    # Add results based on what was executed
                    if st.session_state.mcid_result:
                        export_data["results"]["mcid_search"] = st.session_state.mcid_result
                    if st.session_state.medical_result:
                        export_data["results"]["medical_submit"] = st.session_state.medical_result
                    if st.session_state.test_result:
                        export_data["results"]["test_connection"] = st.session_state.test_result
                    
                    # Create download
                    json_string = json.dumps(export_data, indent=2, default=str)
                    st.download_button(
                        label="💾 Download JSON File",
                        data=json_string,
                        file_name=f"milliman_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        
        # === SIDEBAR INFO SECTION ===
        st.markdown("---")
        st.markdown('<div class="sidebar-header">📋 Available Endpoints</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="sidebar-section">
        <strong>🔍 search_mcid</strong><br>
        Search MCID database for person records<br><br>
        <strong>🏥 submit_medical</strong><br>
        Submit medical request for processing<br><br>
        <strong>🌐 test_connection</strong><br>
        Test API connectivity to all services
        </div>
        """, unsafe_allow_html=True)
    
    # === MAIN AREA - Dashboard View ===
    st.markdown("---")
    
    # Create a dashboard view in the main area
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-icon">🔍</div>
            <h3>MCID Search</h3>
            <p>Search the MCID database for person records and medical identifiers</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.mcid_result:
            if st.session_state.mcid_result.get("success", False):
                st.success("✅ Last MCID search successful")
            else:
                st.error("❌ Last MCID search failed")
    
    with col2:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-icon">🏥</div>
            <h3>Medical Submission</h3>
            <p>Submit medical requests and healthcare-related documentation</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.medical_result:
            if st.session_state.medical_result.get("success", False):
                st.success("✅ Last medical submission successful")
            else:
                st.error("❌ Last medical submission failed")
    
    with col3:
        st.markdown("""
        <div class="dashboard-card">
            <div class="dashboard-icon">🌐</div>
            <h3>API Testing</h3>
            <p>Test connectivity and verify all backend services are operational</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.test_result:
            if st.session_state.test_result.get("success", False):
                st.success("✅ Last connectivity test successful")
            else:
                st.error("❌ Last connectivity test failed")
    
    # Summary metrics in main area
    if any([st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result]):
        st.markdown("---")
        st.markdown('<h2 class="sub-header">📈 Session Summary</h2>', unsafe_allow_html=True)
        
        summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
        
        with summary_col1:
            total_requests = sum([1 for result in [st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result] if result is not None])
            st.metric("Total Requests", total_requests)
        
        with summary_col2:
            successful_requests = sum([1 for result in [st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result] if result and result.get("success", False)])
            st.metric("Successful", successful_requests)
        
        with summary_col3:
            failed_requests = total_requests - successful_requests
            st.metric("Failed", failed_requests)
        
        with summary_col4:
            if total_requests > 0:
                success_rate = (successful_requests / total_requests) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")
            else:
                st.metric("Success Rate", "N/A")

if __name__ == "__main__":
    main()
