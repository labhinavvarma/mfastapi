import streamlit as st
import requests
import json
from datetime import date, datetime
import time
import pandas as pd

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
        padding: 1.5rem;
        margin: 1rem 0;
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
    
    .json-container {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        max-height: 400px;
        overflow-y: auto;
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

def format_json_response(response_data):
    """Format JSON response for better display"""
    try:
        return json.dumps(response_data, indent=2, ensure_ascii=False)
    except:
        return str(response_data)

def display_response_card(title: str, result: dict, icon: str = "🔄"):
    """Display a response card with formatting"""
    with st.container():
        if result.get("success", False):
            st.markdown(f"""
            <div class="endpoint-card">
                <h4 style="color: #28a745;">{icon} {title}</h4>
                <p><strong>Status:</strong> <span style="color: #28a745;">✅ Success</span></p>
                <p><strong>Status Code:</strong> {result.get('status_code', 'N/A')}</p>
                <p><strong>Execution Time:</strong> {result.get('execution_time', 'N/A'):.2f}s</p>
                <p><strong>URL:</strong> <code>{result.get('url', 'N/A')}</code></p>
            </div>
            """, unsafe_allow_html=True)
            
            # Display response data
            st.markdown("**Response Data:**")
            st.json(result.get("response", {}))
        else:
            st.markdown(f"""
            <div class="endpoint-card">
                <h4 style="color: #dc3545;">{icon} {title}</h4>
                <p><strong>Status:</strong> <span style="color: #dc3545;">❌ Failed</span></p>
                <p><strong>Error:</strong> {result.get('error', 'Unknown error')}</p>
                <p><strong>URL:</strong> <code>{result.get('url', 'N/A')}</code></p>
            </div>
            """, unsafe_allow_html=True)

# --- Main Application ---
def main():
    # Header
    st.markdown('<h1 class="main-header">🏥 Milliman MCP Client</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem;">Connect to Milliman APIs through Model Context Protocol</p>', unsafe_allow_html=True)
    
    # Sidebar Configuration
    with st.sidebar:
        st.markdown('<h2 class="sub-header">⚙️ Configuration</h2>', unsafe_allow_html=True)
        
        server_url = st.text_input(
            "MCP Server URL",
            value=DEFAULT_SERVER_URL,
            help="URL of your running MCP server"
        )
        
        st.markdown("---")
        
        # Test connection button
        if st.button("🔍 Test Server Connection", use_container_width=True):
            with st.spinner("Testing connection..."):
                test_result = call_endpoint(server_url, "get_auth_token", method="GET")
                if test_result.get("success", False):
                    st.success("✅ Server is reachable!")
                else:
                    st.error(f"❌ Connection failed: {test_result.get('error', 'Unknown error')}")
        
        st.markdown("---")
        st.markdown("### 📋 Available Endpoints")
        st.markdown("""
        - **search_mcid** - Search MCID database
        - **submit_medical** - Submit medical request  
        - **get_both** - Get both MCID & Medical data
        - **get_auth_token** - Get authentication token
        - **debug_transforms** - Debug data transformations
        - **test_connection** - Test API connectivity
        """)
    
    # Main Content
    col1, col2 = st.columns([1, 2])
    
    # Input Form
    with col1:
        st.markdown('<h2 class="sub-header">👤 Person Information</h2>', unsafe_allow_html=True)
        
        with st.form("person_form"):
            # Basic Information
            st.markdown("**Basic Information**")
            first_name = st.text_input("First Name", value="JOHN", help="Person's first name")
            last_name = st.text_input("Last Name", value="DOE", help="Person's last name")
            
            # Personal Details
            st.markdown("**Personal Details**")
            ssn = st.text_input("SSN", value="123456789", help="Social Security Number")
            
            col_dob, col_gender = st.columns(2)
            with col_dob:
                date_of_birth = st.date_input(
                    "Date of Birth",
                    value=date(1985, 5, 15),
                    min_value=date(1900, 1, 1),
                    max_value=date.today(),
                    help="Person's date of birth"
                )
            
            with col_gender:
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
            
            # Submit button
            submit_button = st.form_submit_button(
                "🚀 Execute All Endpoints",
                use_container_width=True,
                type="primary"
            )
    
    # Results Area
    with col2:
        st.markdown('<h2 class="sub-header">📊 Results</h2>', unsafe_allow_html=True)
        
        if submit_button:
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
                return
            
            # Display submitted data
            st.markdown("**📝 Submitted Data:**")
            st.json(person_data)
            
            # Execute all endpoints
            st.markdown("---")
            st.markdown("**🔄 Executing All Endpoints...**")
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Define endpoints to call
            endpoints = [
                {"name": "Search MCID", "endpoint": "search_mcid", "icon": "🔍", "data": person_data},
                {"name": "Submit Medical", "endpoint": "submit_medical", "icon": "🏥", "data": person_data},
                {"name": "Get Both APIs", "endpoint": "get_both", "icon": "🔄", "data": person_data},
                {"name": "Get Auth Token", "endpoint": "get_auth_token", "icon": "🔐", "method": "GET"},
                {"name": "Debug Transforms", "endpoint": "debug_transforms", "icon": "🐛", "data": person_data},
                {"name": "Test Connection", "endpoint": "test_connection", "icon": "🌐", "data": person_data}
            ]
            
            results = {}
            total_endpoints = len(endpoints)
            
            # Execute each endpoint
            for i, endpoint_config in enumerate(endpoints):
                status_text.text(f"Executing: {endpoint_config['name']}...")
                progress_bar.progress((i + 1) / total_endpoints)
                
                method = endpoint_config.get("method", "POST")
                data = endpoint_config.get("data", None)
                
                result = call_endpoint(
                    server_url, 
                    endpoint_config["endpoint"], 
                    data=data,
                    method=method
                )
                
                results[endpoint_config["name"]] = {
                    "result": result,
                    "icon": endpoint_config["icon"],
                    "endpoint": endpoint_config["endpoint"]
                }
                
                time.sleep(0.1)  # Small delay for better UX
            
            progress_bar.empty()
            status_text.empty()
            
            # Display results summary
            st.markdown("---")
            st.markdown("**📈 Execution Summary**")
            
            success_count = sum(1 for r in results.values() if r["result"].get("success", False))
            total_count = len(results)
            
            col_metrics1, col_metrics2, col_metrics3 = st.columns(3)
            
            with col_metrics1:
                st.metric("Total Endpoints", total_count)
            with col_metrics2:
                st.metric("Successful", success_count, delta=f"{success_count}/{total_count}")
            with col_metrics3:
                st.metric("Failed", total_count - success_count, delta=f"{total_count - success_count}/{total_count}")
            
            # Display detailed results
            st.markdown("---")
            st.markdown("**📋 Detailed Results**")
            
            # Create tabs for each endpoint
            tab_names = [f"{config['icon']} {name}" for name, config in results.items()]
            tabs = st.tabs(tab_names)
            
            for tab, (name, config) in zip(tabs, results.items()):
                with tab:
                    display_response_card(
                        title=name,
                        result=config["result"],
                        icon=config["icon"]
                    )
            
            # Export results option
            st.markdown("---")
            st.markdown("**💾 Export Results**")
            
            if st.button("📥 Download Results as JSON", use_container_width=True):
                # Prepare export data
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "person_data": person_data,
                    "server_url": server_url,
                    "results": {name: config["result"] for name, config in results.items()}
                }
                
                # Create download
                json_string = json.dumps(export_data, indent=2, default=str)
                st.download_button(
                    label="💾 Download JSON File",
                    data=json_string,
                    file_name=f"milliman_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
