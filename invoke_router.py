from fastapi import FastAPI, HTTPException
import httpx
import requests
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from typing import Optional, List

# FastAPI application for Milliman Dashboard

# FastAPI app initialization
app = FastAPI(
    title="Milliman Dashboard",
    description="The service routes chat messages to various chatbots.",
    version="0.0.1",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Simplified Pydantic Model for Input ---

class SimpleRequest(BaseModel):
    requestID: str
    firstName: str
    lastName: str
    ssn: str
    dateOfBirth: str
    gender: str
    zipCodes: List[str]
    callerId: str = "Milliman-Test16"

class AllDataRequest(BaseModel):
    request_data: SimpleRequest

# --- Token Configuration ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

# --- Helper Functions to Transform Data ---

def transform_to_mcid_format(simple_data: SimpleRequest):
    """Transform simple input to MCID format"""
    # Convert date format from YYYY-MM-DD to YYYYMMDD
    dob_formatted = simple_data.dateOfBirth.replace("-", "")
    
    return {
        "requestID": simple_data.requestID,
        "processStatus": {
            "completed": "false",
            "isMemput": "false",
            "errorCode": None,
            "errorText": None
        },
        "consumer": [
            {
                "firstName": simple_data.firstName,
                "lastName": simple_data.lastName,
                "middleName": None,
                "sex": simple_data.gender,
                "dob": dob_formatted,
                "addressList": [
                    {
                        "type": "P",
                        "zip": simple_data.zipCodes[0] if simple_data.zipCodes else None
                    }
                ],
                "id": {
                    "ssn": simple_data.ssn
                }
            }
        ],
        "searchSetting": {
            "minScore": "100",
            "maxResult": "1"
        }
    }

def transform_to_medical_format(simple_data: SimpleRequest):
    """Transform simple input to Medical format"""
    return {
        "requestID": simple_data.requestID,
        "firstName": simple_data.firstName,
        "lastName": simple_data.lastName,
        "ssn": simple_data.ssn,
        "dateOfBirth": simple_data.dateOfBirth,
        "gender": simple_data.gender,
        "zipCodes": simple_data.zipCodes,
        "callerId": simple_data.callerId
    }

# --- Individual API call functions ---

async def async_get_token():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

def get_access_token_sync():
    try:
        response = requests.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception:
        return None

async def async_submit_medical_request(simple_data: SimpleRequest):
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {'status_code': 500, 'error': 'Access token not found'}
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(simple_data)
    payload = json.dumps(medical_payload)
    headers = {
        'Authorization': f'{access_token}',
        'content-type': 'application/json'
    }
    
    try:
        response = requests.request("POST", medical_url, headers=headers, data=payload)
        if response.status_code != 200:
            return {'status_code': response.status_code, 'error': response.text}
        return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
    except Exception as e:
        return {'status_code': 500, 'error': str(e)}

async def async_mcid_search(simple_data: SimpleRequest):
    url = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
    headers = {
        'Content-Type': 'application/json',
        'Apiuser': 'MillimanUser'
    }
    
    mcid_payload = transform_to_mcid_format(simple_data)
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=mcid_payload)
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

# --- Main endpoint ---

@app.post("/all", operation_id="get_all_data", summary="Get all data from Milliman APIs")
async def call_all(request_data: SimpleRequest):
    """
    Call all Milliman APIs with provided request data.
    
    Uses simplified input format and transforms to required API formats internally.
    """
    try:
        token_task = async_get_token()
        mcid_task = async_mcid_search(request_data)
        medical_task = async_submit_medical_request(request_data)
        
        token_result, mcid_result, medical_result = await asyncio.gather(
            token_task, mcid_task, medical_task
        )
        
        return {
            "get_token": token_result,
            "mcid_search": mcid_result,
            "medical_submit": medical_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Individual endpoints ---

@app.post("/mcid", operation_id="mcid_search", summary="MCID Search")
async def mcid_search_endpoint(request_data: SimpleRequest):
    """
    Search MCID with simplified input data.
    Input is automatically transformed to MCID format.
    """
    try:
        result = await async_mcid_search(request_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/medical", operation_id="medical_submit", summary="Medical Submit")
async def medical_submit_endpoint(request_data: SimpleRequest):
    """
    Submit medical request with simplified input data.
    Input is automatically transformed to Medical API format.
    """
    try:
        result = await async_submit_medical_request(request_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/token", operation_id="get_token", summary="Get Access Token")
async def get_token_endpoint():
    """Get access token"""
    try:
        result = await async_get_token()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    mcp = FastApiMCP(app, include_operations=["get_all_data", "mcid_search", "medical_submit", "get_token"])
    mcp.mount()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
