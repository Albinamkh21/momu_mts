from __future__ import annotations

import uuid
import decimal
from typing import Optional
from pydantic import BaseModel, Field


# ─── Step 1: Track basics ────────────────────────────────────────────────────

class DraftStep1(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    isrc: Optional[str] = Field(None, max_length=20)
    duration: Optional[str] = Field(None, max_length=20)
    explicit: Optional[bool] = False
    resource_reference: Optional[str] = None
    label_id: Optional[int] = None  # saved in TrackLabel
    label_own_code: Optional[str] = Field(None, max_length=50)  # saved directly on Track


# ─── Step 2: Release ─────────────────────────────────────────────────────────

class DraftNewRelease(BaseModel):
    title: str = Field(..., min_length=1)
    upc: Optional[str] = Field(None, max_length=20)
    release_date: Optional[str] = None  # ISO date string
    label_id: Optional[int] = None


class DraftStep2(BaseModel):
    release_id: Optional[int] = None        # existing release
    new_release: Optional[DraftNewRelease] = None  # or create new


# ─── Step 3: Contributors ─────────────────────────────────────────────────────

class DraftContributor(BaseModel):
    person_id: Optional[int] = None         # None = create new
    full_name: str = Field(..., min_length=1)
    role: str = Field(..., pattern=r'^(artist_name|composer|lyricist)$')


class DraftStep3(BaseModel):
    contributors: list[DraftContributor] = []


# ─── Step 4: Rights ──────────────────────────────────────────────────────────

class DraftRight(BaseModel):
    right_holder_id: int
    right_category_id: int
    right_usage_type_id: int
    contract_id: Optional[int] = None
    share_percentage: decimal.Decimal = Field(..., ge=0, le=100)
    region_id: Optional[int] = None


class DraftStep4(BaseModel):
    rights: list[DraftRight] = []


# ─── Full payload ─────────────────────────────────────────────────────────────

class DraftPayload(BaseModel):
    step1: Optional[DraftStep1] = None
    step2: Optional[DraftStep2] = None
    step3: Optional[DraftStep3] = None
    step4: Optional[DraftStep4] = None


# ─── Request / Response ───────────────────────────────────────────────────────

class DraftCreateRequest(BaseModel):
    user_id: Optional[int] = None


class DraftPatchRequest(BaseModel):
    """Partial update: only the keys present in the request are merged."""
    step1: Optional[DraftStep1] = None
    step2: Optional[DraftStep2] = None
    step3: Optional[DraftStep3] = None
    step4: Optional[DraftStep4] = None


class DraftResponse(BaseModel):
    id: uuid.UUID
    user_id: Optional[int]
    status: str
    payload: dict
    track_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ActivationResult(BaseModel):
    track_id: int
    message: str
