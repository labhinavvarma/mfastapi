# server.py

import os
import httpx
import asyncio

from fastmcp import FastMCP
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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

# ——— FastMCP tool registry ———
mcp = FastMCP(name="Milliman Dashboard Tools")

@mcp.tool(name="get_token", description="Fetch OAuth2 access token")
async def get_token_tool() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD)
        resp.raise_for_status()
        token = resp.json().get("access_token")
    if not token:
        raise HTTPException(500, "No access_token in response")
    return token

@mcp.tool(name="mcid_search", description="Perform MCID external search; pass your JSON body")
async def mcid_search_tool(body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, "Body must be JSON object")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={
                "Content-Type": "application/json",
                "Apiuser": "MillimanUser"
            },
            json=body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="submit_medical", description="Submit medical eligibility; pass your JSON body")
async def submit_medical_tool(body: dict) -> dict:
    if not isinstance(body, dict):
        raise HTTPException(400, "Body must be JSON object")
    # reuse our get_token tool
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json() if resp.content else {}}


# ——— FastAPI app setup ———
app = FastAPI(
    title="Milliman Dashboard API",
    description="FastMCP tools exposed over HTTP",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

def find_tool(name: str):
    return next((t for t in mcp.tools if t.name == name), None)


# ——— Explicit HTTP endpoints for each tool ———

@app.post("/get_token")
async def http_get_token():
    """
    POST /get_token
    Returns: {"access_token": "..."}
    """
    token = await get_token_tool()
    return {"access_token": token}


@app.post("/mcid_search")
async def http_mcid_search(request: Request):
    """
    POST /mcid_search
    Body: JSON for MCID search
    """
    body = await request.json()
    return await mcid_search_tool(body)


@app.post("/submit_medical")
async def http_submit_medical(request: Request):
    """
    POST /submit_medical
    Body: JSON for medical eligibility
    """
    body = await request.json()
    return await submit_medical_tool(body)


# ——— Generic invoke endpoint ———

@app.post("/tool/{tool_name}")
async def invoke_any(tool_name: str, request: Request):
    """
    POST /tool/{tool_name}
    Body: JSON object (or {} for no-input tools)
    """
    body = await request.json()
    tool = find_tool(tool_name)
    if not tool:
        raise HTTPException(404, f"Tool '{tool_name}' not found")
    result = await tool.invoke(body)
    return {"tool": tool_name, "result": result}


# ——— Convenience /all endpoint ———

MCID_SAMPLE = {
    "requestID": "1",
    "processStatus": {"completed":"false","isMemput":"false","errorCode":None,"errorText":None},
    "consumer":[{"firstName":"JUNEY","lastName":"TROR","middleName":None,"sex":"F","dob":"196971109",
                 "addressList":[{"type":"P","zip":None}],"id":{"ssn":None}}],
    "searchSetting":{"minScore":"100","maxResult":"1"}
}
MEDICAL_SAMPLE = {
    "requestID":"77554079","firstName":"JUNEY","lastName":"TROR","ssn":"148681406",
    "dateOfBirth":"1978-01-20","gender":"F",
    "zipCodes":["23060","23229","23242"],"callerId":"Milliman-Test16"
}

@app.post("/all")
async def run_all():
    """
    POST /all
    Runs get_token, mcid_search and submit_medical with sample bodies.
    """
    token_res = await get_token_tool()
    mcid_res  = await mcid_search_tool(MCID_SAMPLE)
    med_res   = await submit_medical_tool(MEDICAL_SAMPLE)
    return {
        "get_token": token_res,
        "mcid_search": mcid_res,
        "submit_medical": med_res
    }


@app.get("/health")
def health():
    return {"status": "ok"}
