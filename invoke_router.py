#!/usr/bin/env python3
"""
Milliman MCP Server
A Model Context Protocol server for Milliman API integrations (MCID and Medical)
"""

import httpx
import requests
import json
import asyncio
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, validator
from typing import List, Dict, Any

# --- FastAPI Application ---
app = FastAPI(
    title="Milliman MCP Server",
    description="Model Context Protocol server for Milliman API integrations",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class PersonRequest(BaseModel):
    firstName: str
    lastName: str
    ssn: str
    dateOfBirth: str  # Format: YYYY-MM-DD
    gender: str  # M or F
    zipCodes: List[str]
    
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

# --- Configuration ---
TOKEN_URL = "https://securefed.antheminc.com/as/token.oauth2"
TOKEN_PAYLOAD = {
    'grant_type': 'client_credentials',
    'client_id': 'MILLIMAN',
    'client_secret': 'qCZpW9ixf7KTQh5Ws5YmUUqcO6JRfz0GsITmFS87RHLOls8fh0pv8TcyVEVmWRQa'
}
TOKEN_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

# --- Helper Functions ---
def generate_request_id():
    """Generate a unique request ID"""
    return str(int(time.time() * 1000))  # Use timestamp in milliseconds

def get_access_token_sync():
    """Get access token synchronously"""
    try:
        response = requests.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
        response.raise_for_status()
        return response.json().get("access_token")
    except Exception:
        return None

def transform_to_mcid_format(person_data: PersonRequest):
    """Transform person data to MCID API format"""
    # Convert date format from YYYY-MM-DD to YYYYMMDD
    dob_formatted = person_data.dateOfBirth.replace("-", "")
    
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
                "firstName": person_data.firstName,
                "lastName": person_data.lastName,
                "middleName": None,
                "sex": person_data.gender,
                "dob": dob_formatted,
                "addressList": [
                    {
                        "type": "P",
                        "zip": person_data.zipCodes[0] if person_data.zipCodes else None
                    }
                ],
                "id": {
                    "ssn": person_data.ssn
                }
            }
        ],
        "searchSetting": {
            "minScore": "100",
            "maxResult": "1"
        }
    }

def transform_to_medical_format(person_data: PersonRequest):
    """Transform person data to Medical API format"""
    return {
        "requestID": generate_request_id(),
        "firstName": person_data.firstName,
        "lastName": person_data.lastName,
        "ssn": person_data.ssn,
        "dateOfBirth": person_data.dateOfBirth,
        "gender": person_data.gender,
        "zipCodes": person_data.zipCodes,
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

# --- Core API Functions ---
async def async_get_token():
    """Get authentication token"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(TOKEN_URL, data=TOKEN_PAYLOAD, headers=TOKEN_HEADERS)
            try:
                response_body = response.json() if response.content else {}
            except:
                response_body = response.text if response.content else "No content"
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code, 
                'data': response_body
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 500, 
                'error': str(e)
            }

async def async_mcid_search(person_data: PersonRequest):
    """Search MCID database"""
    url = "https://mcid-app-prod.anthem.com:443/MCIDExternalService/V2/extSearchService/json"
    headers = {
        'Content-Type': 'application/json',
        'Apiuser': 'MillimanUser'
    }
    
    mcid_payload = transform_to_mcid_format(person_data)
    
    async with httpx.AsyncClient(verify=False) as client:
        try:
            response = await client.post(url, headers=headers, json=mcid_payload, timeout=30)
            
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
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'data': response_body,
                'request_id': mcid_payload.get('requestID')
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 500,
                'error': str(e),
                'request_id': mcid_payload.get('requestID')
            }

async def async_submit_medical_request(person_data: PersonRequest):
    """Submit medical information request"""
    access_token = await asyncio.to_thread(get_access_token_sync)
    if not access_token:
        return {
            'success': False,
            'status_code': 500,
            'error': 'Access token not found'
        }
    
    medical_url = 'https://hix-clm-internaltesting-prod.anthem.com/medical'
    medical_payload = transform_to_medical_format(person_data)
    
    # Try different authorization header formats
    auth_formats = [
        f'Bearer {access_token}',
        f'{access_token}',
        f'Token {access_token}'
    ]
    
    for auth_format in auth_formats:
        headers = {
            'Authorization': auth_format,
            'content-type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.post(medical_url, headers=headers, json=medical_payload, timeout=30)
            
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
            
            result = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'data': response_body,
                'request_id': medical_payload.get('requestID'),
                'auth_format_used': auth_format.split()[0] if ' ' in auth_format else 'Raw'
            }
            
            # If successful, return immediately
            if response.status_code == 200:
                return result
            
            # If this is the last format and still not successful, return the result
            if auth_format == auth_formats[-1]:
                return result
                
        except Exception as e:
            # If this is the last format, return error
            if auth_format == auth_formats[-1]:
                return {
                    'success': False,
                    'status_code': 500,
                    'error': str(e),
                    'request_id': medical_payload.get('requestID')
                }
            continue

# --- MCP Tool Endpoints ---

@app.post("/search_mcid", operation_id="search_mcid", summary="Search MCID database for person")
async def search_mcid(person_data: PersonRequest) -> Dict[str, Any]:
    """
    Search the MCID (Member Consumer ID) database for a person.
    
    This tool searches Milliman's MCID database to find member information
    based on the provided person details.
    
    Args:
        person_data: Person information including:
            - firstName: Person's first name
            - lastName: Person's last name  
            - ssn: Social Security Number
            - dateOfBirth: Date in YYYY-MM-DD format
            - gender: "M" or "F"
            - zipCodes: Array of zip code strings
        
    Returns:
        MCID search results including status and member information
    """
    try:
        result = await async_mcid_search(person_data)
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@app.post("/submit_medical", operation_id="submit_medical", summary="Submit medical information request")
async def submit_medical(person_data: PersonRequest) -> Dict[str, Any]:
    """
    Submit a medical information request for a person.
    
    This tool submits a request to Milliman's medical API to retrieve
    or process medical information for the specified person.
    
    Args:
        person_data: Person information including:
            - firstName: Person's first name
            - lastName: Person's last name
            - ssn: Social Security Number  
            - dateOfBirth: Date in YYYY-MM-DD format
            - gender: "M" or "F"
            - zipCodes: Array of zip code strings
        
    Returns:
        Medical submission results including status and response data
    """
    try:
        result = await async_submit_medical_request(person_data)
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

@app.post("/get_both", operation_id="get_both", summary="Get both MCID and Medical data")
async def get_both(person_data: PersonRequest) -> Dict[str, Any]:
    """
    Retrieve both MCID and Medical information for a person in parallel.
    
    This tool efficiently retrieves data from both Milliman APIs simultaneously,
    providing comprehensive person information from both systems.
    
    Args:
        person_data: Person information including:
            - firstName: Person's first name
            - lastName: Person's last name
            - ssn: Social Security Number
            - dateOfBirth: Date in YYYY-MM-DD format  
            - gender: "M" or "F"
            - zipCodes: Array of zip code strings
        
    Returns:
        Combined results from both MCID search and Medical submission
    """
    try:
        # Run both operations in parallel
        mcid_task = async_mcid_search(person_data)
        medical_task = async_submit_medical_request(person_data)
        
        mcid_result, medical_result = await asyncio.gather(mcid_task, medical_task)
        
        return {
            "success": mcid_result.get('success', False) or medical_result.get('success', False),
            "mcid_search": mcid_result,
            "medical_submit": medical_result,
            "timestamp": int(time.time())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": int(time.time())
        }

@app.get("/get_auth_token", operation_id="get_auth_token", summary="Get authentication token")
async def get_auth_token() -> Dict[str, Any]:
    """
    Get an authentication token for Milliman services.
    
    This tool retrieves an authentication token that can be used
    for debugging or testing purposes with Milliman APIs.
    
    Returns:
        Token information and status
    """
    try:
        result = await async_get_token()
        return result
    except Exception as e:
        return {
            'success': False,
            'status_code': 500,
            'error': str(e)
        }

# --- Additional Utility Endpoints ---

@app.post("/debug_transforms", operation_id="debug_transforms", summary="Debug data transformations")
async def debug_transforms(person_data: PersonRequest) -> Dict[str, Any]:
    """
    Debug endpoint to see how person data is transformed for each API.
    
    This tool shows how the input data gets transformed for both
    MCID and Medical API formats, useful for debugging.
    
    Args:
        person_data: Person information to transform
        
    Returns:
        Original input and transformed formats for both APIs
    """
    try:
        mcid_format = transform_to_mcid_format(person_data)
        medical_format = transform_to_medical_format(person_data)
        
        return {
            "success": True,
            "original_input": person_data.dict(),
            "mcid_transformed": mcid_format,
            "medical_transformed": medical_format
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/test_connection", operation_id="test_connection", summary="Test API connectivity")
async def test_connection(person_data: PersonRequest) -> Dict[str, Any]:
    """
    Test connectivity to Milliman APIs without processing data.
    
    This tool verifies that the APIs are reachable and responding,
    useful for health checks and troubleshooting.
    
    Args:
        person_data: Person information (used for test requests)
        
    Returns:
        Connection status for each API endpoint
    """
    try:
        # Test token endpoint
        token_result = await async_get_token()
        
        # Test MCID endpoint (with timeout)
        mcid_test = await async_mcid_search(person_data)
        
        # Test Medical endpoint (with timeout)  
        medical_test = await async_submit_medical_request(person_data)
        
        return {
            "success": True,
            "token_api": {
                "reachable": token_result.get('success', False),
                "status": token_result.get('status_code', 'unknown')
            },
            "mcid_api": {
                "reachable": mcid_test.get('status_code', 0) != 500,
                "status": mcid_test.get('status_code', 'unknown')
            },
            "medical_api": {
                "reachable": medical_test.get('status_code', 0) != 500,
                "status": medical_test.get('status_code', 'unknown')
            },
            "timestamp": int(time.time())
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": int(time.time())
        }

# --- MCP Server Setup ---
def create_mcp_server():
    """Create and configure the MCP server"""
    mcp = FastApiMCP(
        app,
        include_operations=[
            "search_mcid",           # Core: Search MCID database
            "submit_medical",        # Core: Submit medical request  
            "get_both",             # Core: Get both MCID and Medical data
            "get_auth_token",       # Utility: Get authentication token
            "debug_transforms",     # Debug: See data transformations
            "test_connection"       # Debug: Test API connectivity
        ]
    )
    return mcp

# --- Main Execution ---
if __name__ == "__main__":
    print("🏥 Starting Milliman MCP Server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API docs available at: http://localhost:8000/docs")
    print("🔧 MCP schema available at: http://localhost:8000/openapi.json")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Create and mount MCP server
    mcp = create_mcp_server()
    mcp.mount()
    
    # Start the server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
