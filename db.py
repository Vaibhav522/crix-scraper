import os
import enum
import datetime
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy import Text, Integer, DateTime, Enum, text, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase): 
    pass


class FileStatus(enum.Enum):
    zipped = "zipped"
    zipping = "zipping"
    uploaded = "uploaded"
    uploading = "uploading"

class UrlStatus(enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"

class UrlType(enum.Enum):
    scorecard = "scorecard"
    cricketer = "cricketer"
    commentary = "commentary"
    venue = "venue"



class Url(Base):
    __tablename__ = "url"
    url: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[UrlStatus] = mapped_column(Enum(UrlStatus, name="url_queue_status"), nullable=False, server_default="pending", index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url_type: Mapped[UrlType] = mapped_column(Enum(UrlType, name="url_type"), nullable=False, index=True)
    lease_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    last_attempt_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    url_discovered_from: Mapped[str] = mapped_column(Text, nullable=False, server_default="seed")
    
    file_downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    file_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zipped_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uploaded_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_status: Mapped[FileStatus] = mapped_column(Enum(FileStatus, name="file_status"), server_default=None)
    uploaded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    zipped_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    zip_lease_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    upload_lease_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)