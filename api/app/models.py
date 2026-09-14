from sqlalchemy import Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.sql import func

from app.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    ip_address = Column(String(45), nullable=False)
    os = Column(String(50), nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(TIMESTAMP, server_default=func.now())


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    port = Column(Integer)
    status = Column(String(20), nullable=False, default="running")
    created_at = Column(TIMESTAMP, server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="SET NULL"))
    service_id = Column(Integer, ForeignKey("services.id", ondelete="SET NULL"))
    severity = Column(String(20), nullable=False, default="medium")
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(TIMESTAMP, server_default=func.now())
    resolved_at = Column(TIMESTAMP)
