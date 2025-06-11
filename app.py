import os
import httpx
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

# ——— FastMCP instance ———
mcp = FastMCP(name="Milliman Dashboard Tools")

# ——— Tool definitions ———
@mcp.tool(name="get_token", description="Fetch OAuth2 access token")
async def get_token_tool() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD)
        resp.raise_for_status()
        token = resp.json().get("access_token")
    if not token:
        raise HTTPException(status_code=500, detail="No access_token in response")
    return token

@mcp.tool(name="mcid_search", description="Perform MCID search; pass JSON body")
async def mcid_search_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Body must be JSON object")
    async with httpx.AsyncClient(verify=False) as client:
        resp = await client.post(
            MCID_URL,
            headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json()}

@mcp.tool(name="submit_medical", description="Submit medical eligibility; pass JSON body")
async def submit_medical_tool(request_body: dict) -> dict:
    if not isinstance(request_body, dict):
        raise HTTPException(status_code=400, detail="Body must be JSON object")
    token = await get_token_tool()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            MEDICAL_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=request_body
        )
        resp.raise_for_status()
    return {"status_code": resp.status_code, "body": resp.json() if resp.content else {}}

# ——— FastAPI app setup ———
app = FastAPI(
    title="Milliman Dashboard API",
    description="FastMCP tools exposed via FastAPI",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ——— Explicit HTTP endpoints for each tool ———
@app.post("/get_token")
async def http_get_token():
    """POST /get_token → returns {access_token} """
    token = await get_token_tool()
    return {"access_token": token}

@app.post("/mcid_search")
async def http_mcid_search(request: Request):
    """POST /mcid_search → accepts JSON body for MCID search"""
    body = await request.json()
    return await mcid_search_tool(body)

@app.post("/submit_medical")
async def http_submit_medical(request: Request):
    """POST /submit_medical → accepts JSON body for medical eligibility"""
    body = await request.json()
    return await submit_medical_tool(body)

# ——— Generic invoke endpoint ———
def find_tool(name: str):
    return next((t for t in mcp.tools if t.name == name), None)

@app.post("/tool/{tool_name}")
async def invoke_tool(tool_name: str, request: Request):
    payload = await request.json()
    tool = find_tool(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    result = await tool.invoke(payload)
    return {"tool": tool_name, "result": result}

# ——— Convenience /all endpoint ———
MCID_SAMPLE = {
    "requestID": "1",
    "processStatus": {"completed":"false","isMemput":"false","errorCode":None,"errorText":None},
    "consumer":[{"firstName":"JUNEY","lastName":"TROR","middleName":None,"sex":"F","dob":"196971109","addressList":[{"type":"P","zip":None}],"id":{"ssn":None}}],
    "searchSetting":{"minScore":"100","maxResult":"1"}
}
MEDICAL_SAMPLE = {
    "requestID":"77554079","firstName":"JUNEY","lastName":"TROR","ssn":"148681406",
    "dateOfBirth":"1978-01-20","gender":"F",
    "zipCodes":["23060","23229","23242"],"callerId":"Milliman-Test16"
}

@app.post("/all")
async def run_all():
    get_token_res = await get_token_tool()
    mcid_res = await mcid_search_tool(MCID_SAMPLE)
    medical_res = await submit_medical_tool(MEDICAL_SAMPLE)
    return {"get_token": get_token_res, "mcid_search": mcid_res, "submit_medical": medical_res}

@app.get("/health")
def health():
    return {"status": "ok"}

# ——— Run the server ———
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
