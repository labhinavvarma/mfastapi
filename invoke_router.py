
from fastapi import FastAPI, HTTPException
import httpx
import requests
import json
import asyncio
import time
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, validator
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
    firstName: str
    lastName: str
    ssn: str
    dateOfBirth: str  # Format: YYYY-MM-DD
    gender: str  # M or F
    zipCodes: List[str]
    
    # Allow any field names (case insensitive)
    class Config:
        extra = "ignore"  # Ignore extra fields
        str_strip_whitespace = True  # Strip whitespace from strings
    
    @validator('gender')
    def validate_gender(cls, v):
        if v.upper() not in ['M', 'F']:
            return v  # Accept any value, transform later if needed
        return v.upper()
    
    @validator('zipCodes')
    def validate_zip_codes(cls, v):
        if not v or len(v) == 0:
            return ["00000"]  # Default zip if none provided
        return [str(zip_code) for zip_code in v]  # Convert all to strings

# --- Token Configuration ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

# --- Helper Functions to Transform Data ---

def generate_request_id():
    """Generate a unique request ID"""
    import time
    return str(int(time.time() * 1000))  # Use timestamp in milliseconds

def transform_to_mcid_format(simple_data: SimpleRequest):
    """Transform simple input to MCID format"""
    # Convert date format from YYYY-MM-DD to YYYYMMDD
    dob_formatted = simple_data.dateOfBirth.replace("-", "")
    
    return {
        "requestID": generate_request_id(),
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
    """Transform simple input to Medical format with all potentially required fields"""
    return {
        "requestID": generate_request_id(),
        "firstName": simple_data.firstName,
        "lastName": simple_data.lastName,
        "ssn": simple_data.ssn,
        "dateOfBirth": simple_data.dateOfBirth,
        "gender": simple_data.gender,
        "zipCodes": simple_data.zipCodes,
        "callerId": "Milliman-Test16",
        # Add potentially missing fields
        "middleName": "",
        "addressLine1": "",
        "addressLine2": "",
        "city": "",
        "state": "",
        "country": "US",
        "phoneNumber": "",
        "email": ""
    }

# --- Individual API call functions ---

async def async_get_token():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            try:
                response_body = response.json() if response.content else {}
            except:
                response_body = response.text if response.content else "No content"
            return {'status_code': response.status_code, 'body': response_body}
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
    
    # Fix authorization header - try different formats
    headers = {
        'Authorization': f'Bearer {access_token}',  # Try Bearer format first
        'content-type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.request("POST", medical_url, headers=headers, data=payload)
        
        # Log the request details for debugging
        request_details = {
            'url': medical_url,
            'headers': {k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()},
            'payload': medical_payload
        }
        
        # Handle response body safely
        try:
            if response.content:
                response_body = response.json()
            else:
                response_body = "No content"
        except json.JSONDecodeError:
            response_body = response.text
        except Exception:
            response_body = "Unable to parse response"
        
        return {
            'status_code': response.status_code, 
            'body': response_body,
            'headers': dict(response.headers),
            'request_sent': request_details  # For debugging
        }
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
            
            # Handle response body safely
            try:
                if response.content:
                    response_body = response.json()
                else:
                    response_body = "No content"
            except json.JSONDecodeError:
                response_body = response.text
            except Exception:
                response_body = "Unable to parse response"
            
            return {
                'status_code': response.status_code, 
                'body': response_body,
                'headers': dict(response.headers)
            }
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

# --- Debug endpoint ---
@app.post("/debug", operation_id="debug_transforms", summary="Debug Data Transformations")
async def debug_transforms(request_data: SimpleRequest):
    """
    Debug endpoint to see how data is transformed for each API
    """
    try:
        mcid_format = transform_to_mcid_format(request_data)
        medical_format = transform_to_medical_format(request_data)
        
        return {
            "original_input": request_data.dict(),
            "mcid_transformed": mcid_format,
            "medical_transformed": medical_format
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Alternative medical endpoint with different auth formats ---
@app.post("/medical-alt", operation_id="medical_submit_alt", summary="Medical Submit (Alternative Auth)")
async def medical_submit_alt_endpoint(request_data: SimpleRequest):
    """
    Submit medical request with alternative authorization formats
    """
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {'status_code': 500, 'error': 'Access token not found'}
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(request_data)
    
    # Try different authorization header formats
    auth_formats = [
        f'Bearer {access_token}',
        f'{access_token}',
        f'Token {access_token}',
        f'Basic {access_token}'
    ]
    
    results = []
    
    for auth_format in auth_formats:
        headers = {
            'Authorization': auth_format,
            'content-type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(medical_url, headers=headers, json=medical_payload, timeout=30)
            
            try:
                if response.content:
                    response_body = response.json()
                else:
                    response_body = "No content"
            except:
                response_body = response.text
            
            results.append({
                'auth_format': auth_format.split()[0] if ' ' in auth_format else 'Raw',
                'status_code': response.status_code,
                'body': response_body[:500] if isinstance(response_body, str) else response_body,  # Limit response size
                'headers': dict(response.headers)
            })
            
            # If we get a successful response, break
            if response.status_code == 200:
                break
                
        except Exception as e:
            results.append({
                'auth_format': auth_format.split()[0] if ' ' in auth_format else 'Raw',
                'status_code': 500,
                'error': str(e)
            })
    
    return {
        'results': results,
        'payload_sent': medical_payload
    }

# --- Test with original hardcoded data ---
@app.post("/medical-original", operation_id="medical_original", summary="Medical Submit (Original Hardcoded Data)")
async def medical_original_endpoint():
    """
    Test medical endpoint with the original hardcoded data to verify it works
    """
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {'status_code': 500, 'error': 'Access token not found'}
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    
    # Use the exact original hardcoded payload
    original_payload = {
        "requestID": "77554079",
        "firstName": "JUNEY",
        "lastName": "TROR",
        "ssn": "148681406",
        "dateOfBirth": "1978-01-20",
        "gender": "F",
        "zipCodes": [
            "23060",
            "23229",
            "23242"
        ],
        "callerId": "Milliman-Test16"
    }
    
    headers = {
        'Authorization': f'{access_token}',  # Use original format
        'content-type': 'application/json'
    }
    
    try:
        response = requests.post(medical_url, headers=headers, json=original_payload, timeout=30)
        
        try:
            if response.content:
                response_body = response.json()
            else:
                response_body = "No content"
        except:
            response_body = response.text
        
        return {
            'status_code': response.status_code,
            'body': response_body,
            'headers': dict(response.headers),
            'payload_sent': original_payload
        }
        
    except Exception as e:
        return {'status_code': 500, 'error': str(e)}

# --- Simple test endpoint ---
@app.post("/test", operation_id="test_input", summary="Test Input Reception")
async def test_input(request_data: SimpleRequest):
    """
    Simple test endpoint that just returns what it received
    """
    return {
        "status": "success",
        "message": "Data received successfully",
        "received_data": request_data.dict()
    }

if __name__ == "__main__":
    mcp = FastApiMCP(app, include_operations=["get_all_data", "mcid_search", "medical_submit", "medical_submit_alt", "medical_original", "get_token", "debug_transforms", "test_input"])
    mcp.mount()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
