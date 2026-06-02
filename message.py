import asyncio
import datetime
import json
import os
import shutil
import urllib.error
import urllib.request
from typing import Optional

from sqlalchemy import desc, func, select

from db import AsyncSessionLocal, Bucket, Url, UrlStatus
from settings import ARCHIVAL_PATH, ZIPPED_PATH

from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def _enum_value(value):
    return getattr(value, "value", str(value))


def _format_count(value):
    return f"{int(value or 0):,}"


def _format_percent(done, total):
    if not total:
        return "0.00%"
    return f"{(done / total) * 100:.2f}%"


def _dir_size(path):
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _format_bytes(size):
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024


async def collect_worker_snapshot(uploaded_bucket_id: Optional[str] = None, uploaded_object_name: Optional[str] = None):
    now = datetime.datetime.now(datetime.timezone.utc)
    one_hour_ago = now - datetime.timedelta(hours=1)

    async with AsyncSessionLocal() as session:
        url_rows = await session.execute(select(Url.status, func.count()).group_by(Url.status))
        bucket_rows = await session.execute(select(Bucket.status, func.count()).group_by(Bucket.status))
        total_urls = await session.scalar(select(func.count()).select_from(Url))
        completed_urls = await session.scalar(select(func.count()).select_from(Url).where(Url.status == UrlStatus.completed))
        failed_urls = await session.scalar(select(func.count()).select_from(Url).where(Url.status == UrlStatus.failed))
        running_urls = await session.scalar(select(func.count()).select_from(Url).where(Url.status == UrlStatus.in_progress))
        pending_urls = await session.scalar(select(func.count()).select_from(Url).where(Url.status == UrlStatus.pending))
        stale_leases = await session.scalar(select(func.count()).select_from(Url).where(Url.status == UrlStatus.in_progress, Url.lease_until < now))
        completed_last_hour = await session.scalar(select(func.count()).select_from(Url).where(Url.completed_at >= one_hour_ago))
        latest_bucket = await session.scalar(select(Bucket).order_by(desc(Bucket.uploaded_at)).limit(1))
        error_rows = await session.execute(select(Url.last_error, func.count()).where(Url.last_error.is_not(None)).group_by(Url.last_error).order_by(desc(func.count())).limit(5))

    url_counts = {_enum_value(status): count for status, count in url_rows.all()}
    bucket_counts = {_enum_value(status): count for status, count in bucket_rows.all()}
    disk_total, disk_used, disk_free = shutil.disk_usage(ARCHIVAL_PATH)

    return {
        "timestamp": now.isoformat(),
        "uploaded_bucket_id": uploaded_bucket_id,
        "uploaded_object_name": uploaded_object_name,
        "total_urls": total_urls or 0,
        "completed_urls": completed_urls or 0,
        "pending_urls": pending_urls or 0,
        "running_urls": running_urls or 0,
        "failed_urls": failed_urls or 0,
        "stale_leases": stale_leases or 0,
        "completed_last_hour": completed_last_hour or 0,
        "url_counts": url_counts,
        "bucket_counts": bucket_counts,
        "latest_uploaded_bucket": latest_bucket.bucket_id if latest_bucket else None,
        "latest_uploaded_at": latest_bucket.uploaded_at.isoformat() if latest_bucket and latest_bucket.uploaded_at else None,
        "archival_size": _dir_size(ARCHIVAL_PATH),
        "zipped_size": _dir_size(ZIPPED_PATH),
        "disk_total": disk_total,
        "disk_used": disk_used,
        "disk_free": disk_free,
        "top_errors": [{"error": error or "unknown", "count": count} for error, count in error_rows.all()],
    }


def build_discord_payload(snapshot):
    total = snapshot["total_urls"]
    completed = snapshot["completed_urls"]
    title = "Crix scraper upload completed" if snapshot.get("uploaded_bucket_id") else "Crix scraper worker snapshot"

    fields = [
        {"name": "Uploaded bucket", "value": snapshot.get("uploaded_bucket_id") or "No upload event attached", "inline": False},
        {"name": "Backblaze object", "value": snapshot.get("uploaded_object_name") or "Not provided", "inline": False},
        {"name": "Progress", "value": f"{_format_count(completed)} / {_format_count(total)} ({_format_percent(completed, total)})", "inline": True},
        {"name": "Last hour", "value": f"{_format_count(snapshot['completed_last_hour'])} completed", "inline": True},
        {"name": "Pending", "value": _format_count(snapshot["pending_urls"]), "inline": True},
        {"name": "In progress", "value": _format_count(snapshot["running_urls"]), "inline": True},
        {"name": "Failed", "value": _format_count(snapshot["failed_urls"]), "inline": True},
        {"name": "Stale leases", "value": _format_count(snapshot["stale_leases"]), "inline": True},
        {"name": "URL status", "value": "\n".join(f"{key}: {_format_count(value)}" for key, value in sorted(snapshot["url_counts"].items())) or "No URL rows", "inline": True},
        {"name": "Bucket status", "value": "\n".join(f"{key}: {_format_count(value)}" for key, value in sorted(snapshot["bucket_counts"].items())) or "No bucket rows", "inline": True},
        {"name": "Local storage", "value": f"raw: {_format_bytes(snapshot['archival_size'])}\nzipped: {_format_bytes(snapshot['zipped_size'])}\nfree: {_format_bytes(snapshot['disk_free'])}", "inline": True},
    ]

    if snapshot["top_errors"]:
        fields.append({"name": "Top errors", "value": "\n".join(f"{_format_count(item['count'])}: {item['error'][:180]}" for item in snapshot["top_errors"]), "inline": False})

    return {
        "username": "crix-scraper",
        "embeds": [{
            "title": title,
            "description": "Durable Postgres snapshot after bucket upload.",
            "color": 0x2ECC71 if not snapshot["failed_urls"] else 0xF1C40F,
            "fields": fields,
            "timestamp": snapshot["timestamp"],
        }],
    }


def _post_webhook_sync(webhook_url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json", "User-Agent": "crix-scraper"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord webhook failed with HTTP {exc.code}: {body}") from exc


async def send_worker_snapshot(uploaded_bucket_id: Optional[str] = None, uploaded_object_name: Optional[str] = None, webhook_url: Optional[str] = None):
    target_url = webhook_url or DISCORD_WEBHOOK_URL
    if not target_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not configured")

    snapshot = await collect_worker_snapshot(uploaded_bucket_id=uploaded_bucket_id, uploaded_object_name=uploaded_object_name)
    payload = build_discord_payload(snapshot)
    return await asyncio.to_thread(_post_webhook_sync, target_url, payload)

