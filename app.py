import os
import httpx
from fastapi import HTTPException
from fastmcp import FastMCP

# ——— FastMCP setup ———
mcp = FastMCP(name="Milliman Dashboard Tools")

# ——— Configuration ———
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
    ),
}
MCID_URL = os.getenv(
    "MCID_URL",
    "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
)
MEDICAL_URL = os.getenv(
    "MEDICAL_URL",
    "https://hix-clm-internaltesting-prod.anthem.com/medical"
)

# ——— Tools ———

@mcp.tool(
    name="get_token",
    description="Fetch OAuth2 access token (no input)."
)
async def get_token_tool() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD)
        resp.raise_for_status()
        data = resp.json()
    token = data.get("access_token")
    if not token:
        raise HTTPException(status_code=500, detail="No access_token in response")
    return token

@mcp.tool(
    name="mcid_search",
    description="Perform MCID search; pass full MCID JSON body.",
)
async def mcid_search_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Body must be JSON object")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={
                "Content-Type": "application/json",
                "Apiuser": "MillimanUser"
            },
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(
    name="submit_medical",
    description="Submit medical‐eligibility request; pass full medical JSON body.",
)
async def submit_medical_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Body must be JSON object")
    # get token internally
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json() if resp.content else {}}


# ——— Run server ———
if __name__ == "__main__":
    # This serves:
    #  • POST /tool/{tool_name}
    #  • GET /prompt/{prompt_name}  (if you add prompts later)
    #  • SSE on  /messages
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000"))
    )
