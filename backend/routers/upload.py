"""
router: upload.py
Mount at: /api/upload
Proxies file uploads to Cloudinary using existing CLOUDINARY_* env vars.

Add to server.py:
    from routers.upload import router as upload_router
    app.include_router(upload_router, prefix="/api")
"""

import os
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["upload"])

# Cloudinary is configured from env vars — already set in your k8s secrets:
#   CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)


async def get_current_user_from_request(request: Request):
    """Get current user from request - compatible with server.py auth system"""
    import jwt
    from motor.motor_asyncio import AsyncIOMotorClient
    from bson import ObjectId
    
    JWT_SECRET = os.environ.get("JWT_SECRET") or "dev-secret-key-change-in-production"
    
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        
        # Get user from database
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME", "reroots")
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            # Try ObjectId
            try:
                user = await db.users.find_one({"_id": ObjectId(user_id)})
            except:
                pass
        
        return user
    except Exception as e:
        return None


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    public_id: str = Form(default=""),
    folder: str = Form(default="reroots/products"),
):
    """
    Upload a product image to Cloudinary.
    Only accessible to authenticated admin users.

    Returns:
        { url: str, public_id: str, width: int, height: int }
    """
    # Get current user
    current_user = await get_current_user_from_request(request)
    
    # Restrict to admin/founder role
    if not current_user or current_user.get("role", "customer") not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Validate mime type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use JPEG, PNG, or WEBP.",
        )

    # 5 MB limit
    MAX_SIZE = 5 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 5 MB limit")

    try:
        upload_opts = {
            "folder": folder,
            "resource_type": "image",
            "transformation": [
                # Auto-optimize: convert to WebP, max 1200px wide, quality auto
                {"width": 1200, "crop": "limit", "quality": "auto", "fetch_format": "auto"}
            ],
        }
        if public_id:
            upload_opts["public_id"] = public_id
            upload_opts["overwrite"] = True

        result = cloudinary.uploader.upload(contents, **upload_opts)

        return JSONResponse({
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "width": result.get("width"),
            "height": result.get("height"),
            "format": result.get("format"),
        })

    except cloudinary.exceptions.Error as e:
        raise HTTPException(status_code=500, detail=f"Cloudinary error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
