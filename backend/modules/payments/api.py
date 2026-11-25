from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from backend.core.auth import get_current_user
from backend.core.db import get_db
import logging

router = APIRouter(prefix="/api/payments", tags=["payments"])
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_receipt(
    game_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    user_id = user.get("id")
    db = get_db()

    try:
        # Validate file size or type if needed
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024: # 10MB limit
            raise HTTPException(status_code=400, detail="File too large")

        # Upload file to Supabase storage bucket 'receipts' or save reference
        # For demonstration, store file name / path
        file_path = f"receipts/{game_id}_{user_id}_{file.filename}"
        
        try:
            db.storage.from_("receipts").upload(file_path, contents, file_options={"content-type": file.content_type})
            public_url = db.storage.from_("receipts").get_public_url(file_path)
        except Exception as storage_err:
            logger.warning(f"Storage upload warning (bucket might not exist yet): {storage_err}")
            public_url = f"https://supabase.storage.local/{file_path}"

        # Upsert payment record
        db.table("payments").upsert({
            "game_id": game_id,
            "user_id": user_id,
            "receipt_url": public_url,
            "status": "pending"
        }, on_conflict="game_id,user_id").execute()

        return {"success": True, "receipt_url": public_url}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error uploading receipt for user {user_id}, game {game_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
