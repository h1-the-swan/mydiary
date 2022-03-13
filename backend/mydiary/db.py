import os
from sqlmodel import create_engine, SQLModel, Session, select
from . import models

rootdir = os.path.dirname(os.path.abspath(__file__))
sqlite_file_name = os.path.join(rootdir, "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def create_db_and_tables(engine=engine):
    SQLModel.metadata.create_all(engine)
