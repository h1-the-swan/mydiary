import os
from datetime import datetime
from sqlmodel import create_engine, SQLModel, Session, select, func, Field
from . import models

rootdir = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(rootdir, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

backup_dir = os.path.join(rootdir, "db_backup")

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def create_db_and_tables(engine=engine):
    SQLModel.metadata.create_all(engine)


class MydiaryDatabaseBackup(SQLModel, table=True):
    filename: str = Field(primary_key=True)
    created_at: datetime = Field(index=True)
    alembic_rev: str = Field(index=True)
    hostname: str
    size: int