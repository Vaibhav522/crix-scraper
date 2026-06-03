import csv
from db import Url, UrlType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert


def read_csv(file_name):
    with open(file_name, "r") as file:
        data = csv.reader(file)

        for i in data:
            print(i)

async def insert_seed_urls(session: AsyncSession, csv_file: str):
    urls = read_csv(csv_file)

    if not urls:
        return 0

    rows = [{"url": url, "url_type": UrlType.scorecard} for url, url_type in urls]

    stmt = pg_insert(Url).values(rows).on_conflict_do_nothing(index_elements=["url"])
    result = await session.execute(stmt)

    await session.commit()
    return result