# app/endpoints/common/course_public.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.deps import get_db
from schemas.partner.course import CoursePage
from crud.partner import course as crud_course

router = APIRouter()

@router.get("", response_model=CoursePage, summary="전체 코스조회")
def list_public_courses(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    rows, total = crud_course.list_courses(
        db=db,
        org_id=None,  # ← 전체 org 대상
        status=status,
        search=search,
        limit=limit,
        offset=offset,
    )

    page = offset // limit + 1 if limit > 0 else 1

    return {
        "total": total,
        "items": rows,
        "page": page,
        "size": limit,
    }



from pydantic import BaseModel
import requests

class SMSRequest(BaseModel):
    to: str
    message: str

@router.post("/sms", summary="sms테스트")
def send_sms(data: SMSRequest):

    API_KEY = "8936a01db6367d0494a386c1b48a5977be6289db118465eb"

    url = "https://api.smsmobileapi.com/sendsms/"
    payload = {
        "recipients": data.to,
        "message": data.message,
        "apikey": API_KEY
    }

    response = requests.post(url, data=payload)


    try:
        return response.json()
    except:
        return {"status": response.status_code, "response": response.text}