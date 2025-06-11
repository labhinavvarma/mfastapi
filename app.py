import os
import httpx
from fastmcp import FastMCP
from fastapi import HTTPException

# ——— Configuration ———
TOKEN_URL = os.getenv(
    "TOKEN_URL",
    "https://securefed.antheminc.com/as/token.oauth2"
)
TOKEN_PAYLOAD = {
    "grant_type": "client_credentials",
    "client_id": os.getenv("CLIENT_ID", "MILLIMAN"),
    "client_secret": os.getenv(
        "CLIENT_SECRET",
        "qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa"
    )
}
MCID_URL = os.getenv(
    "MCID_URL",
    "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
)
MEDICAL_URL = os.getenv(
    "MEDICAL_URL",
    "https://hix-clm-internaltesting-prod.anthem.com/medical"
)

# ——— FastMCP instance ———
mcp = FastMCP(name="Milliman Dashboard Tools")

# ——— Tools ———
@mcp.tool(name="get_token", description="Fetch OAuth2 access token")
async def get_token_tool() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD)
        resp.raise_for_status()
        token = resp.json().get("access_token")
    if not token:
        raise HTTPException(500, "No access_token in response")
    return token

@mcp.tool(name="mcid_search", description="Perform MCID search; pass your JSON body")
async def mcid_search_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(400, "Body must be JSON object")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="submit_medical", description="Submit medical eligibility; pass your JSON body")
async def submit_medical_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(400, "Body must be JSON object")
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json() if resp.content else {}}

# ——— Convenience /all tool ———
MCID_SAMPLE = {
    "requestID": "1",
    "processStatus": {"completed":"false","isMemput":"false","errorCode":None,"errorText":None},
    "consumer":[{"firstName":"JUNEY","lastName":"TROR","middleName":None,"sex":"F","dob":"19691109",
                 "addressList":[{"type":"P","zip":None}],"id":{"ssn":None}}],
    "searchSetting":{"minScore":"100","maxResult":"1"}
}
MEDICAL_SAMPLE = {
    "requestID":"77554079","firstName":"JUNEY","lastName":"TROR","ssn":"148681406",
    "dateOfBirth":"1978-01-20","gender":"F",
    "zipCodes":["23060","23229","23242"],"callerId":"Milliman-Test16"
}

@mcp.tool(name="all", description="Run get_token, mcid_search and submit_medical with defaults")
async def all_tool() -> dict:
    token_res = await get_token_tool()
    mcid_res  = await mcid_search_tool(MCID_SAMPLE)
    med_res   = await submit_medical_tool(MEDICAL_SAMPLE)
    return {"get_token": token_res, "mcid_search": mcid_res, "submit_medical": med_res}

# ——— Run the server ———
if __name__ == "__main__":  # Fixed the syntax error
    # This blocks and keeps the server alive.
    print("🚀 Starting FastMCP Server...")
    print("📍 Server will be available at: http://0.0.0.0:8000")
    print("🔧 Available tools: get_token, mcid_search, submit_medical, all")
    print("📡 Transport: SSE (Server-Sent Events)")
    print("🌐 Endpoints:")
    print("   • Tool calls: POST /tool/{name}")
    print("   • SSE stream: /messages")
    
    mcp.run(
        transport="sse",        # HTTP POST /tool/{name} & SSE /messages
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000"))
    )
