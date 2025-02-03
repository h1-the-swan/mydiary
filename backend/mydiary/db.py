import os
from datetime import datetime
from sqlmodel import create_engine, SQLModel, Session, select, func, Field
from sqlalchemy import text, inspect
from . import models

rootdir = os.getenv("MYDIARY_ROOTDIR")
if not rootdir:
    rootdir = os.path.dirname(os.path.abspath(__file__))

sqlite_file_name = os.path.join(rootdir, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

backup_dir = os.path.join(rootdir, "db_backup")

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def create_db_and_tables(engine=engine):
    SQLModel.metadata.create_all(engine)


def vacuum_db(engine=engine):
    with Session(engine) as session:
        session.exec(text("VACUUM"))


def get_db_status(more=False):
    table_names = inspect(engine).get_table_names()

    ret = {
        "db_is_initialized": len(table_names) > 0,
    }
    if more is True:
        ret.update(
            {
                "db_table_names": table_names,
            }
        )
    return ret


class MydiaryDatabaseBackup(SQLModel, table=True):
    filename: str = Field(primary_key=True)
    created_at: datetime = Field(index=True)
    alembic_rev: str = Field(index=True)
    hostname: str
    size: int
