import re
import logging
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/design-extract/public', tags=['design-extract', 'public'])

_db: Optional[AsyncIOMotorDatabase] = None


def set_db(database: AsyncIOMotorDatabase):
    global _db
    _db = database


class PublicExtractRequest(BaseModel):
    url: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    source: str = Field(default='public-page')

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if '@' not in v:
            raise ValueError('Email must contain @')
        return v


@router.get('/_/health')
async def health():
    return {'ok': True}


@router.get('/sample')
async def sample():
    return {
        'ok': True,
        'sample': True,
        'url': 'https://stripe.com',
        'colors': ['#635BFF', '#0A2540', '#425466', '#FFFFFF', '#F6F9FC'],
        'fonts': ['Söhne', 'sohne-var', '-apple-system'],
        'headline_count': 7,
        'meta_description': 'Online payment processing for internet businesses.'
    }


@router.post('/run')
async def run(body: PublicExtractRequest):
    if _db is None:
        raise HTTPException(status_code=500, detail='Database not initialized')

    collection = _db['design_extract_public_captures']

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    count = await collection.count_documents({
        'email': body.email,
        'captured_at': {'$gte': twenty_four_hours_ago.isoformat()}
    })

    if count >= 3:
        logger.warning(f'Rate limit exceeded for email={body.email}')
        raise HTTPException(status_code=429, detail='Daily limit reached (3/day for this email).')

    colors = []
    fonts = []
    headline_count = 0
    meta_description = ''

    try:
        from services.design_extract_service import run_extraction
        logger.info(f'Using design_extract_service for url={body.url}')
        result = await run_extraction(body.url)
        colors = result.get('colors', [])
        fonts = result.get('fonts', [])
        headline_count = result.get('headline_count', 0)
        meta_description = result.get('meta_description', '')
    except (ImportError, Exception) as e:
        logger.warning(f'Falling back to stub extraction: {e}')
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(body.url)
                html = response.text

                color_pattern = re.compile(r'#[0-9a-fA-F]{6}')
                color_matches = color_pattern.findall(html)
                colors = list(dict.fromkeys(color_matches))[:6]

                font_pattern = re.compile(r'font-family\s*:\s*([^;}]+)', re.IGNORECASE)
                font_matches = font_pattern.findall(html)
                all_fonts = []
                for match in font_matches:
                    parts = [f.strip().strip('"').strip("'") for f in match.split(',')]
                    all_fonts.extend(parts)
                fonts = list(dict.fromkeys(all_fonts))[:5]

                h1_count = len(re.findall(r'<h1[^>]*>', html, re.IGNORECASE))
                h2_count = len(re.findall(r'<h2[^>]*>', html, re.IGNORECASE))
                h3_count = len(re.findall(r'<h3[^>]*>', html, re.IGNORECASE))
                headline_count = h1_count + h2_count + h3_count

                meta_desc_pattern = re.compile(
                    r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
                    re.IGNORECASE | re.DOTALL
                )
                meta_match = meta_desc_pattern.search(html)
                if meta_match:
                    meta_description = meta_match.group(1).strip()

        except Exception as ex:
            logger.error(f'Stub extraction failed for url={body.url}: {ex}')

    extraction_id = str(uuid4())
    capture_doc = {
        'extraction_id': extraction_id,
        'email': body.email,
        'url': body.url,
        'source': body.source,
        'captured_at': datetime.now(timezone.utc).isoformat(),
        'colors': colors,
        'fonts': fonts,
        'headline_count': headline_count,
        'meta_description': meta_description
    }

    await collection.insert_one(capture_doc)
    logger.info(f'Captured extraction_id={extraction_id} for email={body.email}')

    return {
        'ok': True,
        'extraction_id': extraction_id,
        'colors': colors,
        'fonts': fonts,
        'headline_count': headline_count,
        'meta_description': meta_description
    }