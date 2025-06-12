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

# --- Pydantic Models for Request Bodies ---

class ProcessStatus(BaseModel):
    completed: str
    isMemput: str
    errorCode: Optional[str] = None
    errorText: Optional[str] = None

class Address(BaseModel):
    type: str
    zip: Optional[str] = None

class ID(BaseModel):
    ssn: Optional[str] = None

class Consumer(BaseModel):
    firstName: str
    lastName: str
    middleName: Optional[str] = None
    sex: str
    dob: str
    addressList: List[Address]
    id: ID

class SearchSetting(BaseModel):
    minScore: str
    maxResult: str

class MCIDRequest(BaseModel):
    requestID: str
    processStatus: ProcessStatus
    consumer: List[Consumer]
    searchSetting: SearchSetting

class MedicalRequest(BaseModel):
    requestID: str
    firstName: str
    lastName: str
    ssn: str
    dateOfBirth: str
    gender: str
    zipCodes: List[str]
    callerId: str

class AllDataRequest(BaseModel):
    mcid_request: MCIDRequest
    medical_request: MedicalRequest

# --- Token Configuration ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

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

async def async_submit_medical_request(medical_data: MedicalRequest):
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {'status_code': 500, 'error': 'Access token not found'}
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    payload = json.dumps(medical_data.dict())
    headers = {
        'Authorization': f'{access_token}',
        'content-type': 'application/json'
    }
    
    try:
        response = requests.request("POST", medical_url, headers=headers, data=payload)
        if response.status_code != 200:
            return {'status_code': response.status_code, 'error': response.text}
        return {'status_code': response.status_code}
    except Exception as e:
        return {'status_code': 500, 'error': str(e)}

async def async_mcid_search(mcid_data: MCIDRequest):
    url = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
    headers = {
        'Content-Type': 'application/json',
        'Apiuser': 'MillimanUser'
    }
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=mcid_data.dict())
            return {'status_code': response.status_code, 'body': response.json() if response.content else {}}
        except Exception as e:
            return {'status_code': 500, 'error': str(e)}

# --- Main endpoint ---

@app.post("/all", operation_id="get_all_data", summary="Get all data from Milliman APIs")
async def call_all(request_data: AllDataRequest):
    """
    Call all Milliman APIs with provided request data.
    
    - **mcid_request**: MCID search request data
    - **medical_request**: Medical request data
    """
    try:
        token_task = async_get_token()
        mcid_task = async_mcid_search(request_data.mcid_request)
        medical_task = async_submit_medical_request(request_data.medical_request)
        
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

# --- Optional: Separate endpoints for individual calls ---

@app.post("/mcid", operation_id="mcid_search", summary="MCID Search")
async def mcid_search_endpoint(mcid_data: MCIDRequest):
    """Search MCID with provided data"""
    try:
        result = await async_mcid_search(mcid_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/medical", operation_id="medical_submit", summary="Medical Submit")
async def medical_submit_endpoint(medical_data: MedicalRequest):
    """Submit medical request with provided data"""
    try:
        result = await async_submit_medical_request(medical_data)
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
