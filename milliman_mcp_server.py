import json
import asyncio
import httpx
import requests
from mcp.server.fastmcp import tool
from mcp.server.fastmcp.prompts.base import Message

TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

MCID_REQUEST_BODY = {
    "requestID": "1",
    "processStatus": {"completed": "false", "isMemput": "false"},
    "consumer": [{
        "firstName": "JUNEY", "lastName": "TROR", "sex": "F", "dob": "196971109",
        "addressList": [{"type": "P"}], "id": {"ssn": None}
    }],
    "searchSetting": {"minScore": "100", "maxResult": "1"}
}

@tool(name="milliman-api-tool", description="Milliman tool to get token, MCID, and medical data")
async def milliman_tool(input: dict) -> Message:
    try:
        # 1. Token
        token_resp = requests.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # 2. MCID call
        async with httpx.AsyncClient(verify=False) as client:
            mcid_resp = await client.post(
                "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json",
                headers={"Content-Type": "application/json", "Apiuser": "MillimanUser"},
                json=MCID_REQUEST_BODY
            )
            mcid_json = mcid_resp.json()

        # 3. Medical (sync)
        def post_medical():
            return requests.post(
                "https://hix-clm-internaltesting-prod.anthem.com/medical",
                headers={"Authorization": access_token, "content-type": "application/json"},
                data=json.dumps({
                    "requestID": "77554079", "firstName": "JUNEY", "lastName": "TROR",
                    "ssn": "148681406", "dateOfBirth": "1978-01-20", "gender": "F",
                    "zipCodes": ["23060", "23229", "23242"], "callerId": "Milliman-Test16"
                })
            )

        medical_resp = await asyncio.to_thread(post_medical)

        return Message(
            role="tool",
            text=json.dumps({
                "token": bool(access_token),
                "mcid_status": mcid_resp.status_code,
                "mcid_response": mcid_json,
                "medical_status": medical_resp.status_code
            }, indent=2)
        )

    except Exception as e:
        return Message(role="tool", text=f"Error occurred: {str(e)}")
