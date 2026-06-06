import csv
import asyncio
from db import Url, UrlType
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy import Text, Integer, DateTime, Enum, text, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = create_async_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)



def read_csv(file_name):
    with open(file_name, "r") as file:
        data = csv.reader(file)
        url = []

        for i in data:
            url.append(i[0])
        
        return url

async def insert_seed_urls(session: AsyncSession, csv_file: str):
    urls = read_csv(csv_file)

    if not urls:
        return 0
    

    rows = [{"url": url, "url_type": UrlType.scorecard} for url in urls]

    stmt = pg_insert(Url).values(rows).on_conflict_do_nothing(index_elements=["url"])
    result = await session.execute(stmt)

    await session.commit()
    print(f"inserted, {len(urls)}")


async def transfer(batch_size: int = 5000):
    csv_file = input("Enter csv file to transfer: ")
    
    if csv_file:
        data = read_csv(csv_file)

        if not data:
            print("Empty file")
            return False
        
        async with AsyncSessionLocal() as session:
            for i in range(0, len(data), batch_size):
                batch_data = data[i, i+batch_size]
                rows = [{"url": url, "url_type": UrlType.scorecard} for url in batch_data]
                stmt = pg_insert(Url).values(rows).on_conflict_do_nothing(index_elements=["url"])
                await session.execute(stmt)
                await session.commit()
                print(f"Inserted -> {i}-{len(batch_size)}")


async def transfer():
    csv_file = input("Enter csv file to transfer: ")
    
    if csv_file:
        async with AsyncSessionLocal() as session:
            await insert_seed_urls(session=session, csv_file=csv_file)



if __name__ == "__main__":
    # This block ONLY runs if etl.py is executed directly, 
    # NOT when imported by main.py
    asyncio.run(transfer())