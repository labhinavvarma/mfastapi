### server.py
```python
import os
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# --- Configuration (optionally from environment variables) ---
TOKEN_URL = os.getenv("TOKEN_URL", "https://securefed.antheminc.com/as/token.oauth2")
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': os.getenv("CLIENT_ID", 'MILLIMAN'),
    'client_secret': os.getenv("CLIENT_SECRET", 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa')
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
MCID_URL = os.getenv("MCID_URL", "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json")
MEDICAL_URL = os.getenv("MEDICAL_URL", "https://hix-clm-internaltesting-prod.anthem.com/medical")

# Hardcoded request bodies
MCID_REQUEST_BODY = {
    "requestID": "1",
    "processStatus": {"completed": "false", "isMemput": "false", "errorCode": None, "errorText": None},
    "consumer": [{
        "firstName": "JUNEY",
        "lastName": "TROR",
        "middleName": None,
        "sex": "F",
        "dob": "196971109",
        "addressList": [{"type": "P", "zip": None}],
        "id": {"ssn": None}
    }],
    "searchSetting": {"minScore": "100", "maxResult": "1"}
}
MEDICAL_REQUEST_BODY = {
    "requestID": "77554079",
    "firstName": "JUNEY",
    "lastName": "TROR",
    "ssn": "148681406",
    "dateOfBirth": "1978-01-20",
    "gender": "F",
    "zipCodes": ["23060", "23229", "23242"],
    "callerId": "Milliman-Test16"
}

# --- Initialize FastMCP ---
mcp = FastMCP("Milliman Dashboard Tools")

@mcp.tool(name="get_token", description="Fetch OAuth2 access token")
async def get_token_tool() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise HTTPException(status_code=500, detail="Token not found in response")
        return token

@mcp.tool(name="mcid_search", description="Perform MCID external search")
async def mcid_search_tool() -> dict:
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
            json=MCID_REQUEST_BODY
        )
        resp.raise_for_status()
        return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="submit_medical", description="Submit medical eligibility request")
async def submit_medical_tool() -> dict:
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=MEDICAL_REQUEST_BODY
        )
        resp.raise_for_status()
        return {"status_code": resp.status_code, "body": resp.json() if resp.content else {}}

# --- FastAPI application ---
app = FastAPI(title="Milliman MCP Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount MCP router at /mcp
app.mount("/mcp", mcp.app)

# Convenience endpoint to run all tools
@app.get("/all")
async def call_all():
    try:
        token = await get_token_tool()
        mcid = await mcid_search_tool()
        medical = await submit_medical_tool()
        return {"get_token": token, "mcid_search": mcid, "medical_submit": medical}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

This version:
- Loads credentials/URLs from environment if available
- Uses `httpx.AsyncClient` for all external calls (no blocking sync requests)
- Adds `resp.raise_for_status()` and token existence checks
- Mounts the FastMCP router under `/mcp`
- Provides a stable `/all` endpoint that surfaces tool outputs

You can now run:
```bash
pip install fastapi uvicorn httpx mcp-server
uvicorn server:app --reload
```
