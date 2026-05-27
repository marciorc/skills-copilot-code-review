"""
Announcement endpoints backed by MongoDB.
"""

from datetime import date
from uuid import uuid4
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from pymongo import ReturnDocument

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementPayload(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    message: str = Field(min_length=8, max_length=280)
    start_date: Optional[date] = None
    expires_on: date

    @field_validator("title", "message")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_dates(self) -> "AnnouncementPayload":
        if self.start_date and self.start_date >= self.expires_on:
            raise ValueError("Start date must be before expiration date")
        return self


def _serialize_announcement(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": document["_id"],
        "title": document["title"],
        "message": document["message"],
        "start_date": document.get("start_date"),
        "expires_on": document["expires_on"],
        "created_by": document.get("created_by")
    }


def _require_authenticated_user(username: Optional[str]) -> Dict[str, Any]:
    if not username:
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def list_active_announcements() -> List[Dict[str, Any]]:
    """Return only announcements visible today on the public site."""
    today = date.today().isoformat()
    documents = announcements_collection.find(
        {
            "expires_on": {"$gte": today},
            "$or": [
                {"start_date": None},
                {"start_date": {"$exists": False}},
                {"start_date": {"$lte": today}}
            ]
        }
    ).sort([("expires_on", 1), ("title", 1)])

    return [_serialize_announcement(document) for document in documents]


@router.get("/manage", response_model=List[Dict[str, Any]])
def list_all_announcements(username: str = Query(...)) -> List[Dict[str, Any]]:
    """Return all announcements for authenticated management screens."""
    _require_authenticated_user(username)
    documents = announcements_collection.find({}).sort([("expires_on", 1), ("title", 1)])
    return [_serialize_announcement(document) for document in documents]


@router.post("", response_model=Dict[str, Any], status_code=201)
@router.post("/", response_model=Dict[str, Any], status_code=201)
def create_announcement(
    payload: AnnouncementPayload,
    username: str = Query(...)
) -> Dict[str, Any]:
    """Create a new announcement. Authentication required."""
    teacher = _require_authenticated_user(username)

    document = {
        "_id": uuid4().hex,
        "title": payload.title,
        "message": payload.message,
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "expires_on": payload.expires_on.isoformat(),
        "created_by": teacher["_id"]
    }

    announcements_collection.insert_one(document)
    return _serialize_announcement(document)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    payload: AnnouncementPayload,
    username: str = Query(...)
) -> Dict[str, Any]:
    """Update an existing announcement. Authentication required."""
    teacher = _require_authenticated_user(username)

    result = announcements_collection.find_one_and_update(
        {"_id": announcement_id},
        {
            "$set": {
                "title": payload.title,
                "message": payload.message,
                "start_date": payload.start_date.isoformat() if payload.start_date else None,
                "expires_on": payload.expires_on.isoformat()
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if not result:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return _serialize_announcement(result)


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(announcement_id: str, username: str = Query(...)) -> Dict[str, str]:
    """Delete an announcement. Authentication required."""
    _require_authenticated_user(username)
    result = announcements_collection.delete_one({"_id": announcement_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}