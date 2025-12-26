import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

class WebhookMessageIn(BaseModel):
    message_id: str = Field(..., min_length=1, description="Unique identifier for the message")
    sender: str = Field(..., alias="from", description="Sender phone number in E.164 format")
    receiver: str = Field(..., alias="to", description="Receiver phone number in E.164 format")
    ts: datetime = Field(..., description="ISO-8601 UTC timestamp (Z suffix required)")
    text: Optional[str] = Field(None, max_length=4096, description="Optional message text")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('sender', 'receiver')
    @classmethod
    def validate_phone(cls, v: str, info) -> str:
        if not re.match(r"^\+[0-9]+$", v):
            raise ValueError(f"{info.field_name} must be in E.164 format (+[digits]+)")
        return v

    @field_validator('ts')
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo != timezone.utc:
            # Pydantic might parse 'Z' as UTC automatically, 
            # but we ensure it's specifically UTC.
            # If the input string didn't have 'Z' or offset, tzinfo might be None.
            raise ValueError("Timestamp must be in UTC with 'Z' suffix or UTC offset")
        return v

class WebhookResponse(BaseModel):
    status: str = Field("ok")

class MessageOut(BaseModel):
    message_id: str
    sender: str = Field(..., alias="from")
    receiver: str = Field(..., alias="to")
    ts: datetime
    text: Optional[str]

    model_config = ConfigDict(populate_by_name=True)

class MessagesListResponse(BaseModel):
    data: List[MessageOut]
    total: int
    limit: int
    offset: int

class StatsResponse(BaseModel):

    total_messages: int

    senders_count: int

    messages_per_sender: Dict[str, int] # Changed to Dict for simplicity and to match storage.py

    first_message_ts: Optional[str]

    last_message_ts: Optional[str]
