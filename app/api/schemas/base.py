from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class LoginRequest(BaseModel):
    user_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


class ActionRequest(BaseModel):
    action: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CycleRequest(BaseModel):
    mode: str = Field(default="mock", description="'real' or 'mock'")
    job_type: str = Field(default="morning", description="morning, midday, evening, or event")
