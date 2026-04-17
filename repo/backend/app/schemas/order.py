import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OrderCreate(BaseModel):
    property_id: uuid.UUID
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: str = "normal"
    idempotency_key: uuid.UUID
    resident_id: Optional[uuid.UUID] = None  # Required for staff; ignored for resident callers


class OrderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None


class OrderTransitionRequest(BaseModel):
    to_status: str
    notes: Optional[str] = None
    idempotency_key: uuid.UUID


class MilestoneResponse(BaseModel):
    from_status: Optional[str]
    to_status: str
    changed_by: uuid.UUID
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list["OrderResponse"]
    total: int
    page: int
    page_size: int


class OrderResponse(BaseModel):
    id: uuid.UUID
    resident_id: uuid.UUID
    property_id: uuid.UUID
    title: str
    description: Optional[str]
    category: Optional[str]
    priority: str
    status: str
    assigned_to: Optional[uuid.UUID]
    milestones: list[MilestoneResponse] = []
    created_at: datetime
    updated_at: datetime
    version: int

    model_config = {"from_attributes": True}
