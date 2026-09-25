from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime, timezone


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    size = Column(
        Integer,
        nullable=False,
    )

    pages = Column(
        Integer,
        default=0,
        nullable=False,
    )

    chunks = Column(
        Integer,
        default=0,
        nullable=False,
    )

    status = Column(
        String,
        default="indexing",
        nullable=False,
    )

    error = Column(
        String,
        nullable=True,
    )

    uploaded_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )