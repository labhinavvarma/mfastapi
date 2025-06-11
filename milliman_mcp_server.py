### server.py
```python
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
from mcp.server.fastmcp import FastMCP

# --- Configuration Constants ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
MCID_URL = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
MEDICAL_URL = "https://hix-clm-internaltesting-prod.anthem.com/medical"

# --- Initialize FastMCP ---
mcp = FastMCP("MillimanDashboard")
app = mcp.app  # This is a FastAPI instance under the hood

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MCP Tool Definitions ---

@mcp.tool(name="get_token", description="Fetch OAuth2 token from Anthem")
async def get_token() -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        return {"access_token": data.get("access_token")}

@mcp.tool(name="mcid_search", description="Perform MCID search with given JSON body")
async def mcid_search(body: dict) -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(MCID_URL,
                                 headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
                                 json=body)
        return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="medical_submit", description="Submit medical request with given JSON body")
async def medical_submit(body: dict) -> dict:
    token_res = await get_token()
    token = token_res.get("access_token")
    if not token:
        raise Exception("Failed to obtain access token")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body
        )
        if resp.status_code != 200:
            raise Exception(f"Medical request failed: {await resp.text()}")
        return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="call_all", description="Fetch token, then MCID search, then submit medical request")
async def call_all(mcid_body: dict, medical_body: dict) -> dict:
    token_res = await get_token()
    mcid_res = await mcid_search(mcid_body)
    medical_res = await medical_submit(medical_body)
    return {"get_token": token_res, "mcid_search": mcid_res, "medical_submit": medical_res}

# --- FastAPI Endpoint to Invoke Tools ---
@app.post("/invoke/{tool_name}")
async def invoke_tool(tool_name: str, payload: dict):
    tool = next((t for t in mcp.tools if t.name == tool_name), None)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    try:
        result = await tool.invoke(**payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```  

---

### streamlit_app.py
```python
import streamlit as st
import requests
import json

st.set_page_config(page_title="Milliman MCP Client", layout="wide")
st.title("📡 Milliman MCP Client")

# Select operation
tool = st.selectbox("Choose a tool to invoke:", ["get_token", "mcid_search", "medical_submit", "call_all"] )

# Depending on tool, show JSON input areas
if tool in ["mcid_search", "medical_submit"]:
    body_text = st.text_area("Request JSON", value="{}", height=200)
elif tool == "call_all":
    mcid_text = st.text_area("MCID Request JSON", value="{}", height=150)
    medical_text = st.text_area("Medical Request JSON", value="{}", height=150)

if st.button("Invoke"):
    try:
        if tool == "get_token":
            res = requests.post("http://localhost:8000/invoke/get_token", json={})
        elif tool in ["mcid_search", "medical_submit"]:
            data = json.loads(body_text)
            res = requests.post(f"http://localhost:8000/invoke/{tool}", json={"body": data})
        else:  # call_all
            mcid_body = json.loads(mcid_text)
            medical_body = json.loads(medical_text)
            res = requests.post(
                "http://localhost:8000/invoke/call_all",
                json={"mcid_body": mcid_body, "medical_body": medical_body}
            )
        st.subheader("Response")
        st.json(res.json())
    except Exception as e:
        st.error(f"Error invoking tool: {e}")
