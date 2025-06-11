### server.py
```python
import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

# --- Configuration (optionally from environment variables) ---
TOKEN_URL = os.getenv(
    "TOKEN_URL",
    "https://securefed.antheminc.com/as/token.oauth2"
)
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': os.getenv("CLIENT_ID", 'MILLIMAN'),
    'client_secret': os.getenv(
        "CLIENT_SECRET",
        'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
    )
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}
MCID_URL = os.getenv(
    "MCID_URL",
    "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
)
MEDICAL_URL = os.getenv(
    "MEDICAL_URL",
    "https://hix-clm-internaltesting-prod.anthem.com/medical"
)

# --- Initialize FastMCP ---
mcp = FastMCP("Milliman Dashboard Tools")

@mcp.tool(name="get_token", description="Fetch OAuth2 access token")
async def get_token_tool() -> str:
    """No input required; returns an access token string."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    token = data.get("access_token")
    if not token:
        raise HTTPException(status_code=500, detail="Token not found in response")
    return token

@mcp.tool(name="mcid_search", description="Perform MCID external search")
async def mcid_search_tool(request_body: dict) -> dict:
    """
    Expects a JSON body with MCID search parameters from the client.
    Returns status code and response body.
    """
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="MCID request body must be a JSON object")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
            json=request_body
        )
        resp.raise_for_status()
        return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="submit_medical", description="Submit medical eligibility request")
async def submit_medical_tool(request_body: dict) -> dict:
    """
    Expects a JSON body with medical request parameters from the client.
    Obtains an OAuth token internally.
    Returns status code and response body.
    """
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Medical request body must be a JSON object")
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=request_body
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

# Mount the FastMCP router under /mcp
app.mount("/mcp", mcp.app)

# If executed directly, start Uvicorn
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
```
