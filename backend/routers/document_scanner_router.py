"""
ReRoots AI Document Scanner Router
OCR and data extraction from documents, lab reports, invoices
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import base64
import json

router = APIRouter(prefix="/api/document-scanner", tags=["document-scanner"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


class ScanDocumentRequest(BaseModel):
    image_base64: str
    document_type: str = "general"  # invoice, lab_report, certificate, id, receipt


@router.post("/scan")
async def scan_document(data: ScanDocumentRequest):
    """Scan and extract data from document image using GPT Vision"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Document scanning service not configured")
        
        import secrets
        scan_id = f"scan_{secrets.token_hex(8)}"
        
        # Choose extraction prompt based on document type
        extraction_prompts = {
            "invoice": """Extract all data from this invoice:
- Invoice number, date, due date
- Vendor/seller details (name, address, contact)
- Customer/buyer details
- Line items (description, quantity, unit price, total)
- Subtotal, taxes, discounts, total
- Payment terms and methods""",
            
            "lab_report": """Extract all data from this lab report/certificate:
- Lab name and accreditation
- Report/certificate number
- Test date and report date
- Sample/product details
- Test results (parameters, values, units, limits)
- Pass/fail status
- Certifications and approvals""",
            
            "certificate": """Extract all data from this certificate:
- Certificate type and number
- Issuing authority/organization
- Issue date and expiry date
- Certified entity/product
- Scope of certification
- Compliance standards""",
            
            "receipt": """Extract all data from this receipt:
- Store/vendor name and location
- Transaction date and time
- Items purchased (name, quantity, price)
- Subtotal, taxes, discounts
- Total amount
- Payment method
- Receipt/transaction number""",
            
            "general": """Extract all relevant text and data from this document.
Identify document type, key fields, dates, numbers, and any important information."""
        }
        
        prompt = extraction_prompts.get(data.document_type, extraction_prompts["general"])
        
        chat = LlmChat(
            api_key=api_key,
            session_id=scan_id,
            system_message=f"""You are a document scanning AI for a skincare company.
Extract structured data from document images accurately.
{prompt}

Respond in valid JSON format with extracted fields."""
        ).with_model("openai", "gpt-5.2")
        
        image_content = ImageContent(image_base64=data.image_base64)
        
        response = await chat.send_message(UserMessage(
            text="Please scan and extract all data from this document.",
            image_contents=[image_content]
        ))
        
        # Parse JSON response
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            
            extracted_data = json.loads(response.strip())
        except:
            extracted_data = {"raw_text": response, "parse_error": True}
        
        # Store scan result
        await db.document_scans.insert_one({
            "scan_id": scan_id,
            "document_type": data.document_type,
            "extracted_data": extracted_data,
            "scanned_at": datetime.now(timezone.utc)
        })
        
        return {
            "scan_id": scan_id,
            "document_type": data.document_type,
            "extracted_data": extracted_data,
            "confidence": 0.9 if not extracted_data.get("parse_error") else 0.5
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document scan failed: {str(e)}")


@router.post("/scan/upload")
async def scan_document_upload(
    file: UploadFile = File(...),
    document_type: str = Form("general")
):
    """Scan document from uploaded file"""
    # Validate file type
    if not file.content_type.startswith("image/") and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be an image or PDF")
    
    # Read and encode file
    file_bytes = await file.read()
    image_base64 = base64.b64encode(file_bytes).decode("utf-8")
    
    return await scan_document(ScanDocumentRequest(
        image_base64=image_base64,
        document_type=document_type
    ))


@router.post("/extract-table")
async def extract_table(data: ScanDocumentRequest):
    """Extract tabular data from document"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Service not configured")
        
        import secrets
        chat = LlmChat(
            api_key=api_key,
            session_id=f"table_{secrets.token_hex(6)}",
            system_message="""Extract all tables from this document.
Convert each table to a structured format.
Respond in JSON:
{
  "tables": [
    {
      "table_name": "string",
      "headers": ["col1", "col2"],
      "rows": [["val1", "val2"], ["val3", "val4"]]
    }
  ],
  "total_tables": number
}"""
        ).with_model("openai", "gpt-5.2")
        
        image_content = ImageContent(image_base64=data.image_base64)
        
        response = await chat.send_message(UserMessage(
            text="Extract all tables from this document image.",
            image_contents=[image_content]
        ))
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            return json.loads(response.strip())
        except:
            return {"tables": [], "error": "Failed to parse tables"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Table extraction failed: {str(e)}")


@router.get("/history")
async def get_scan_history(limit: int = 20):
    """Get document scan history"""
    scans = await db.document_scans.find(
        {},
        {"_id": 0}
    ).sort("scanned_at", -1).limit(limit).to_list(limit)
    
    return {"scans": scans}


@router.get("/{scan_id}")
async def get_scan(scan_id: str):
    """Get a specific scan result"""
    scan = await db.document_scans.find_one(
        {"scan_id": scan_id},
        {"_id": 0}
    )
    
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return {"scan": scan}
