
import streamlit as st
import requests
import json
from datetime import date, datetime
import time
import uuid
import yaml
import asyncio
import urllib3
from contextlib import asynccontextmanager

# Disable SSL warnings for internal environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Page Configuration ---
st.set_page_config(
    page_title="Milliman MCP Client",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Cortex LLM Configuration ---
API_URL = "https://sfassist.edagenaidev.awsdns.internal.das/api/cortex/complete"
API_KEY = "78a799ea-a0f6-11ef-a0ce-15a449f7a8b0"
APP_ID = "edadip"
APLCTN_CD = "edagnai"
MODEL = "llama3.1-70b"
SYS_MSG = "You are a powerful AI assistant specialized in healthcare data analysis. Provide accurate, concise medical insights based on context."

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
    
    .llm-card {
        background-color: #e8f4fd;
        border: 1px solid #bee5eb;
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
    
    .health-trajectory {
        background-color: #f0f8ff;
        border-left: 4px solid #4CAF50;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
    }
    
    .entity-extraction {
        background-color: #fff8dc;
        border-left: 4px solid #FF9800;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Configuration ---
DEFAULT_SERVER_URL = "http://localhost:8000"

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context_window" not in st.session_state:
    st.session_state.context_window = []
if "yaml_models" not in st.session_state:
    st.session_state.yaml_models = {}
if 'mcid_result' not in st.session_state:
    st.session_state.mcid_result = None
if 'medical_result' not in st.session_state:
    st.session_state.medical_result = None
if 'test_result' not in st.session_state:
    st.session_state.test_result = None
if 'health_trajectory' not in st.session_state:
    st.session_state.health_trajectory = None
if 'entity_extraction' not in st.session_state:
    st.session_state.entity_extraction = None

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

def call_cortex_llm(text, context_window=None, debug=False):
    """Call Cortex LLM API with improved error handling"""
    session_id = str(uuid.uuid4())
    
    # Build context if available
    if context_window:
        history = "\n".join(context_window[-5:])
        full_prompt = f"{SYS_MSG}\n{history}\nUser: {text}"
    else:
        full_prompt = f"{SYS_MSG}\nUser: {text}"

    payload = {
        "query": {
            "aplctn_cd": APLCTN_CD,
            "app_id": APP_ID,
            "api_key": API_KEY,
            "method": "cortex",
            "model": MODEL,
            "sys_msg": SYS_MSG,
            "limit_convs": "0",
            "prompt": {
                "messages": [
                    {"role": "user", "content": full_prompt}
                ]
            },
            "app_lvl_prefix": "",
            "user_id": "",
            "session_id": session_id
        }
    }

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "Authorization": f'Snowflake Token="{API_KEY}"'
    }

    if debug:
        st.sidebar.write("**Debug Info:**")
        st.sidebar.write(f"Session ID: {session_id}")
        st.sidebar.write(f"API URL: {API_URL}")
        st.sidebar.json({"payload_structure": list(payload.keys())})

    try:
        response = requests.post(
            API_URL, 
            headers=headers, 
            json=payload, 
            verify=False,
            timeout=30
        )
        
        if debug:
            st.sidebar.write(f"Response Status: {response.status_code}")
            st.sidebar.write(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            raw = response.text
            if debug:
                st.sidebar.write(f"Raw Response Length: {len(raw)}")
                st.sidebar.write(f"Raw Response Preview: {raw[:200]}...")
            
            # Handle different response formats
            if "end_of_stream" in raw:
                answer, _, _ = raw.partition("end_of_stream")
                return answer.strip()
            elif raw.strip():
                return raw.strip()
            else:
                return "❌ Empty response from Cortex API"
        else:
            error_msg = f"❌ Cortex Error {response.status_code}: {response.text}"
            if debug:
                st.sidebar.error(error_msg)
            return error_msg
            
    except requests.exceptions.Timeout:
        error_msg = "❌ Cortex API timeout (30s)"
        if debug:
            st.sidebar.error(error_msg)
        return error_msg
    except requests.exceptions.ConnectionError:
        error_msg = "❌ Cortex API connection error"
        if debug:
            st.sidebar.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"❌ Cortex Exception: {str(e)}"
        if debug:
            st.sidebar.error(error_msg)
        return error_msg

def generate_health_trajectory_prompt(medical_data):
    """Generate prompt for health trajectory analysis"""
    return f"""
    Based on the following medical claims data, provide a comprehensive health trajectory analysis:

    MEDICAL CLAIMS DATA:
    {json.dumps(medical_data, indent=2)}

    Please analyze and provide:
    1. **Current Health Status**: Overall assessment based on claims
    2. **Risk Factors**: Identified health risks and concerns
    3. **Trajectory Prediction**: Likely health progression over next 6-12 months
    4. **Recommendations**: Preventive care and intervention suggestions
    5. **Care Gaps**: Missing or recommended screenings/treatments

    Format your response with clear sections and actionable insights.
    """

def generate_entity_extraction_prompt(medical_data):
    """Generate prompt for entity extraction"""
    return f"""
    Extract and analyze the following health entities from the medical claims data:

    MEDICAL CLAIMS DATA:
    {json.dumps(medical_data, indent=2)}

    Please extract and provide detailed information for these key health entities:

    1. **DIABETES**:
       - Type (Type 1, Type 2, Gestational, etc.)
       - HbA1c levels if available
       - Medications (Insulin, Metformin, etc.)
       - Complications or related conditions

    2. **BLOOD PRESSURE**:
       - Hypertension status (Stage 1, Stage 2, Controlled, etc.)
       - Blood pressure readings if available
       - Medications (ACE inhibitors, Beta blockers, etc.)
       - Related cardiovascular conditions

    3. **SMOKING**:
       - Smoking status (Current, Former, Never)
       - Smoking cessation attempts or programs
       - Related respiratory conditions
       - Tobacco use disorders

    4. **ALCOHOL**:
       - Alcohol use patterns
       - Alcohol-related disorders
       - Liver conditions related to alcohol
       - Treatment or counseling programs

    5. **AGE-RELATED CONDITIONS**:
       - Age-specific health screenings
       - Chronic conditions common for age group
       - Preventive care recommendations
       - Age-related medication considerations

    For each entity, provide:
    - Current status/values
    - Risk level (Low/Medium/High)
    - Clinical significance
    - Recommended actions

    Format as structured JSON with clear categories and values.
    """

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

def display_llm_analysis(title: str, content: str, icon: str, card_class: str):
    """Display LLM analysis results in sidebar"""
    st.sidebar.markdown(f"""
    <div class="{card_class}">
        <h5 style="margin-bottom: 0.5rem;">{icon} {title}</h5>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar.expander(f"📋 View {title}", expanded=False):
        st.markdown(content)

# --- Main Application ---
def main():
    # Header in main area
    st.markdown('<h1 class="main-header">🏥 Milliman MCP Client with AI Analysis</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; font-size: 1.2rem;">Search MCID Database, Submit Medical Requests & Generate Health Insights</p>', unsafe_allow_html=True)
    
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
            submit_ai_analysis = st.form_submit_button("🤖 AI Health Analysis", use_container_width=True)
        
        # === AI ANALYSIS OPTIONS ===
        st.markdown("---")
        st.markdown('<div class="sidebar-header">🤖 AI Analysis Options</div>', unsafe_allow_html=True)
        
        enable_trajectory = st.checkbox("📈 Generate Health Trajectory", value=True)
        enable_entity_extraction = st.checkbox("🔍 Extract Health Entities", value=True)
        
        # === CHATBOT INTERFACE ===
        st.markdown("---")
        st.markdown('<div class="sidebar-header">💬 AI Chatbot</div>', unsafe_allow_html=True)
        
        # Debug mode toggle
        debug_mode = st.checkbox("🔧 Debug Mode", value=False, help="Show detailed API request/response info")
        
        # Chat input form
        with st.form("chat_form", clear_on_submit=True):
            user_query = st.text_input(
                "Ask AI Assistant",
                placeholder="e.g., Analyze the health risks for this patient...",
                help="Ask questions about health analysis, medical data, or general queries"
            )
            chat_submitted = st.form_submit_button("💬 Send Message", use_container_width=True)
        
        # Process chat message
        if chat_submitted and user_query:
            with st.spinner("🤖 AI Assistant is thinking..."):
                # Add user message to context
                st.session_state.context_window.append(f"User: {user_query}")
                
                # Call LLM with debug option
                bot_response = call_cortex_llm(user_query, st.session_state.context_window, debug=debug_mode)
                
                # Add bot response to context
                st.session_state.context_window.append(f"Assistant: {bot_response}")
                
                # Store in messages
                st.session_state.messages.append({"role": "user", "content": user_query})
                st.session_state.messages.append({"role": "assistant", "content": bot_response})
            
            # Show latest response
            st.success("✅ Message sent!")
        
        # Display recent chat messages in sidebar
        if st.session_state.messages:
            st.markdown("**Recent Messages:**")
            # Show last 4 messages (2 exchanges)
            recent_messages = st.session_state.messages[-4:]
            for msg in recent_messages:
                if msg["role"] == "user":
                    st.markdown(f"🧑 **You:** {msg['content'][:50]}...")
                else:
                    st.markdown(f"🤖 **AI:** {msg['content'][:50]}...")
            
            # Button to clear chat history
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.messages = []
                st.session_state.context_window = []
                st.success("Chat history cleared!")
                st.rerun()
        
        # === PROCESS FORM SUBMISSIONS ===
        if submit_mcid or submit_medical or submit_test or submit_both or submit_ai_analysis:
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
                
                if submit_mcid or submit_both or submit_ai_analysis:
                    with st.spinner("Searching MCID database..."):
                        st.session_state.mcid_result = call_endpoint(server_url, "search_mcid", person_data)
                    display_sidebar_response("MCID Search", st.session_state.mcid_result, "🔍")
                
                if submit_medical or submit_both or submit_ai_analysis:
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
                
                # === AI ANALYSIS PROCESSING ===
                if (submit_ai_analysis or submit_both) and st.session_state.medical_result and st.session_state.medical_result.get("success", False):
                    st.markdown("---")
                    st.markdown('<div class="sidebar-header">🤖 AI Health Analysis</div>', unsafe_allow_html=True)
                    
                    medical_data = st.session_state.medical_result.get("response", {})
                    
                    # Generate Health Trajectory
                    if enable_trajectory:
                        with st.spinner("🧠 Generating health trajectory analysis..."):
                            trajectory_prompt = generate_health_trajectory_prompt(medical_data)
                            st.session_state.context_window.append(f"Medical Data Analysis Request: {trajectory_prompt[:100]}...")
                            trajectory_response = call_cortex_llm(trajectory_prompt, st.session_state.context_window, debug=False)
                            st.session_state.health_trajectory = trajectory_response
                            st.session_state.context_window.append(f"Health Trajectory Analysis: {trajectory_response[:100]}...")
                        
                        display_llm_analysis("Health Trajectory", st.session_state.health_trajectory, "📈", "health-trajectory")
                    
                    # Generate Entity Extraction
                    if enable_entity_extraction:
                        with st.spinner("🔍 Extracting health entities..."):
                            entity_prompt = generate_entity_extraction_prompt(medical_data)
                            st.session_state.context_window.append(f"Entity Extraction Request: {entity_prompt[:100]}...")
                            entity_response = call_cortex_llm(entity_prompt, st.session_state.context_window, debug=False)
                            st.session_state.entity_extraction = entity_response
                            st.session_state.context_window.append(f"Entity Extraction Results: {entity_response[:100]}...")
                        
                        display_llm_analysis("Health Entities", st.session_state.entity_extraction, "🔍", "entity-extraction")
                
                # Export results option
                st.markdown("---")
                st.markdown('<div class="sidebar-header">💾 Export Results</div>', unsafe_allow_html=True)
                
                if st.button("📥 Download Complete Results", use_container_width=True):
                    # Prepare export data
                    export_data = {
                        "timestamp": datetime.now().isoformat(),
                        "person_data": person_data,
                        "server_url": server_url,
                        "api_results": {},
                        "ai_analysis": {}
                    }
                    
                    # Add API results
                    if st.session_state.mcid_result:
                        export_data["api_results"]["mcid_search"] = st.session_state.mcid_result
                    if st.session_state.medical_result:
                        export_data["api_results"]["medical_submit"] = st.session_state.medical_result
                    if st.session_state.test_result:
                        export_data["api_results"]["test_connection"] = st.session_state.test_result
                    
                    # Add AI analysis results
                    if st.session_state.health_trajectory:
                        export_data["ai_analysis"]["health_trajectory"] = st.session_state.health_trajectory
                    if st.session_state.entity_extraction:
                        export_data["ai_analysis"]["entity_extraction"] = st.session_state.entity_extraction
                    
                    # Create download
                    json_string = json.dumps(export_data, indent=2, default=str)
                    st.download_button(
                        label="💾 Download JSON File",
                        data=json_string,
                        file_name=f"milliman_ai_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
        
        # === SIDEBAR INFO SECTION ===
        st.markdown("---")
        st.markdown('<div class="sidebar-header">📋 Available Features</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="sidebar-section">
        <strong>🔍 MCID Search</strong><br>
        Search MCID database for person records<br><br>
        <strong>🏥 Medical Submit</strong><br>
        Submit medical request for processing<br><br>
        <strong>🌐 Test Connection</strong><br>
        Test API connectivity to all services<br><br>
        <strong>🤖 AI Health Analysis</strong><br>
        Generate health trajectory and extract entities<br><br>
        <strong>📈 Health Trajectory</strong><br>
        AI-powered health progression analysis<br><br>
        <strong>🔍 Entity Extraction</strong><br>
        Extract: Diabetes, BP, Smoking, Alcohol, Age factors<br><br>
        <strong>💬 AI Chatbot</strong><br>
        Interactive AI assistant for medical queries<br><br>
        <strong>🔧 Debug Mode</strong><br>
        View detailed API request/response information
        </div>
        """, unsafe_allow_html=True)
    
    # === MAIN AREA - Enhanced Dashboard View ===
    st.markdown("---")
    
    # Create a dashboard view in the main area
    col1, col2, col3, col4 = st.columns(4)
    
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
            <div class="dashboard-icon">🤖</div>
            <h3>AI Analysis</h3>
            <p>Generate health trajectory and extract key medical entities</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.health_trajectory or st.session_state.entity_extraction:
            st.success("✅ AI analysis completed")
        elif st.session_state.medical_result and st.session_state.medical_result.get("success", False):
            st.info("💡 Ready for AI analysis")
    
    with col4:
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
    
    # === AI INSIGHTS DASHBOARD ===
    if st.session_state.health_trajectory or st.session_state.entity_extraction:
        st.markdown("---")
        st.markdown('<h2 class="sub-header">🧠 AI Health Insights Dashboard</h2>', unsafe_allow_html=True)
        
        insight_col1, insight_col2 = st.columns(2)
        
        with insight_col1:
            if st.session_state.health_trajectory:
                st.markdown("""
                <div class="health-trajectory">
                    <h4>📈 Health Trajectory Analysis</h4>
                    <p>AI-generated health progression and risk assessment</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("📋 View Health Trajectory", expanded=True):
                    st.markdown(st.session_state.health_trajectory)
        
        with insight_col2:
            if st.session_state.entity_extraction:
                st.markdown("""
                <div class="entity-extraction">
                    <h4>🔍 Health Entity Extraction</h4>
                    <p>Extracted key health indicators: Diabetes, BP, Smoking, Alcohol, Age</p>
                </div>
                """, unsafe_allow_html=True)
                
                with st.expander("📋 View Extracted Entities", expanded=True):
                    st.markdown(st.session_state.entity_extraction)
    
    # === CHATBOT CONVERSATION AREA ===
    if st.session_state.messages:
        st.markdown("---")
        st.markdown('<h2 class="sub-header">💬 AI Assistant Conversation</h2>', unsafe_allow_html=True)
        
        # Create a chat container
        chat_container = st.container()
        
        with chat_container:
            # Display all messages
            for i, message in enumerate(st.session_state.messages):
                if message["role"] == "user":
                    st.markdown(f"""
                    <div style="background-color: #e3f2fd; padding: 10px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #2196f3;">
                        <strong>🧑 You:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background-color: #f1f8e9; padding: 10px; border-radius: 10px; margin: 10px 0; border-left: 4px solid #4caf50;">
                        <strong>🤖 AI Assistant:</strong><br>
                        {message["content"]}
                    </div>
                    """, unsafe_allow_html=True)
        
        # Quick action buttons
        st.markdown("**Quick Actions:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Analyze Current Patient Data"):
                if st.session_state.medical_result and st.session_state.medical_result.get("success", False):
                    quick_query = f"Please analyze this patient's medical data and provide key insights: {json.dumps(st.session_state.medical_result.get('response', {}), indent=2)}"
                    # Process the quick query
                    with st.spinner("Analyzing patient data..."):
                        st.session_state.context_window.append(f"User: {quick_query}")
                        bot_response = call_cortex_llm(quick_query, st.session_state.context_window)
                        st.session_state.context_window.append(f"Assistant: {bot_response}")
                        st.session_state.messages.append({"role": "user", "content": "Analyze current patient data"})
                        st.session_state.messages.append({"role": "assistant", "content": bot_response})
                    st.rerun()
                else:
                    st.warning("⚠️ No patient data available. Please submit medical request first.")
        
        with col2:
            if st.button("🏥 Health Risk Assessment"):
                quick_query = "Provide a comprehensive health risk assessment based on the available patient data, focusing on preventive care recommendations."
                with st.spinner("Generating risk assessment..."):
                    st.session_state.context_window.append(f"User: {quick_query}")
                    bot_response = call_cortex_llm(quick_query, st.session_state.context_window)
                    st.session_state.context_window.append(f"Assistant: {bot_response}")
                    st.session_state.messages.append({"role": "user", "content": "Health risk assessment request"})
                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
                st.rerun()
        
        with col3:
            if st.button("📋 Care Plan Recommendations"):
                quick_query = "Based on the patient analysis, suggest a comprehensive care plan with specific actions, timelines, and monitoring requirements."
                with st.spinner("Creating care plan..."):
                    st.session_state.context_window.append(f"User: {quick_query}")
                    bot_response = call_cortex_llm(quick_query, st.session_state.context_window)
                    st.session_state.context_window.append(f"Assistant: {bot_response}")
                    st.session_state.messages.append({"role": "user", "content": "Care plan recommendations request"})
                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
                st.rerun()
    
    # Summary metrics in main area
    if any([st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result]):
        st.markdown("---")
        st.markdown('<h2 class="sub-header">📈 Session Summary</h2>', unsafe_allow_html=True)
        
        summary_col1, summary_col2, summary_col3, summary_col4, summary_col5, summary_col6 = st.columns(6)
        
        with summary_col1:
            total_requests = sum([1 for result in [st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result] if result is not None])
            st.metric("API Requests", total_requests)
        
        with summary_col2:
            successful_requests = sum([1 for result in [st.session_state.mcid_result, st.session_state.medical_result, st.session_state.test_result] if result and result.get("success", False)])
            st.metric("Successful", successful_requests)
        
        with summary_col3:
            failed_requests = total_requests - successful_requests
            st.metric("Failed", failed_requests)
        
        with summary_col4:
            ai_analysis_count = sum([1 for analysis in [st.session_state.health_trajectory, st.session_state.entity_extraction] if analysis is not None])
            st.metric("AI Analyses", ai_analysis_count)
        
        with summary_col5:
            chat_messages = len([msg for msg in st.session_state.messages if msg.get("role") == "user"])
            st.metric("Chat Messages", chat_messages)
        
        with summary_col6:
            if total_requests > 0:
                success_rate = (successful_requests / total_requests) * 100
                st.metric("Success Rate", f"{success_rate:.1f}%")
            else:
                st.metric("Success Rate", "N/A")

if __name__ == "__main__":
    main()
