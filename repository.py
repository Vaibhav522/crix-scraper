import datetime
from settings import MAX_ATTEMPTS
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from db import Url, UrlStatus, UrlType, FileStatus


async def claim_next_url(session: AsyncSession, lease_seconds: int = 900):
    now = datetime.datetime.now(datetime.timezone.utc)
    lease_until = now + datetime.timedelta(seconds=lease_seconds)

    stmt = (
        select(Url)
        .where(or_(Url.status == UrlStatus.pending, (Url.status == UrlStatus.in_progress) & (Url.lease_until < now) & (Url.attempt_count < MAX_ATTEMPTS)))
        .order_by(Url.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    result = await session.execute(stmt)
    url = result.scalar_one_or_none()

    if not url:
        return None

    url.status = UrlStatus.in_progress
    url.lease_until = lease_until
    url.last_attempt_at = now
    url.attempt_count += 1

    await session.commit()
    await session.refresh(url)
    return url


async def mark_url_completed(session: AsyncSession, url: str, file_name: str):
    stmt = (
        update(Url)
        .where(Url.url == url)
        .values(
            status=UrlStatus.completed,
            file_name=file_name,
            lease_until=None,
            last_error=None,
            file_downloaded=True,
            completed_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    await session.execute(stmt)
    await session.commit()


async def mark_url_failed(session: AsyncSession, url: str, error: str, max_attempts: int = MAX_ATTEMPTS):
    result = await session.execute(select(Url).where(Url.url == url).with_for_update())
    row = result.scalar_one_or_none()

    if not row:
        return None

    row.last_error = error
    row.lease_until = None
    row.status = UrlStatus.failed if row.attempt_count >= max_attempts else UrlStatus.pending

    await session.commit()
    return row.status


async def claim_file_for_zipping(session: AsyncSession, lease_seconds: int = 1800):
    now = datetime.datetime.now(datetime.timezone.utc)
    lease_until = now + datetime.timedelta(seconds=lease_seconds)

    stmt = (select(Url)
        .where(
            or_(
                Url.file_downloaded == True,
                (Url.file_status == FileStatus.zipping) & (Url.zip_lease_until < now),
            )
        )
        .order_by(Url.completed_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    result = await session.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        return None

    file.file_status = FileStatus.zipping
    file.zip_lease_until = lease_until
    await session.commit()
    await session.refresh(file)
    return file


async def mark_file_zipped(session: AsyncSession, file_name: str, zipped_name: str):
    stmt = (
        update(Url)
        .where(Url.file_name == file_name)
        .values(
            zipped_name= zipped_name,
            file_status=FileStatus.zipped,
            zipped_at=datetime.datetime.now(datetime.timezone.utc),
            zip_lease_until=None,
        )
    )
    await session.execute(stmt)
    await session.commit()


async def claim_file_for_upload(session: AsyncSession, lease_seconds: int = 1800):
    now = datetime.datetime.now(datetime.timezone.utc)
    lease_until = now + datetime.timedelta(seconds=lease_seconds)

    stmt = (
        select(Url)
        .where(
            or_(
                Url.file_status == FileStatus.zipped,
                (Url.file_status == FileStatus.uploading) & (Url.upload_lease_until < now),
            )
        )
        .order_by(Url.zipped_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    result = await session.execute(stmt)
    file = result.scalar_one_or_none()

    if not file:
        return None

    file.file_status = FileStatus.uploading
    file.upload_lease_until = lease_until
    await session.commit()
    await session.refresh(file)
    return file


async def mark_file_uploaded(session: AsyncSession, file_name: str, uploaded_id: str):
    stmt = (
        update(Url)
        .where(Url.file_name == file_name)
        .values(
            file_status=FileStatus.uploaded,
            uploaded_at=datetime.datetime.now(datetime.timezone.utc),
            upload_lease_until=None,
            uploaded_file_id=uploaded_id
        )
    )
    await session.execute(stmt)
    await session.commit()



async def complete_scorecard(session: AsyncSession, url: str, file_name: str, discovered_urls: list[tuple[str, UrlType]]):
    if discovered_urls:
        rows = [{"url": item_url, "url_type": item_type, "url_discovered_from": url} for item_url, item_type in discovered_urls]
        stmt = pg_insert(Url).values(rows).on_conflict_do_nothing(index_elements=["url"])
        await session.execute(stmt)

    stmt = (
        update(Url)
        .where(Url.url == url)
        .values(
            status=UrlStatus.completed,
            file_name=file_name,
            lease_until=None,
            last_error=None,
            file_downloaded=True,
            completed_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )

    await session.execute(stmt)
    await session.commit()