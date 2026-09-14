from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ServerBase(BaseModel):
    name: str
    ip_address: str
    os: str
    role: str
    status: str = "active"


class ServerCreate(ServerBase):
    pass


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    os: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class ServerOut(ServerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class ServiceBase(BaseModel):
    name: str
    server_id: int
    port: Optional[int] = None
    status: str = "running"


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    server_id: Optional[int] = None
    port: Optional[int] = None
    status: Optional[str] = None


class ServiceOut(ServiceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


class IncidentBase(BaseModel):
    title: str
    description: Optional[str] = None
    server_id: Optional[int] = None
    service_id: Optional[int] = None
    severity: str = "medium"
    status: str = "open"


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    server_id: Optional[int] = None
    service_id: Optional[int] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None


class IncidentOut(IncidentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    resolved_at: Optional[datetime] = None


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
