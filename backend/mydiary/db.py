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

# fp = Path(backup_dir).joinpath('database_backup20230930T131940_alembice943e3d13add.db')
# fp.exists()
# url = f"{ncld.url}/remote.php/dav/files/{NEXTCLOUD_USERNAME}/mydiary/db/{fp.name}"
# with fp.open('rb') as f:
# 	r = requests.put(url=url, data=f, auth=ncld.auth)
# r.status_code

# backup_files = Path(rootdir).joinpath('db_backup').glob('*.db')
# backup_files = list(backup_files)

# %%time
# # download from nextcloud and save
# fp_save = Path('.').joinpath(fp.name)
# r = requests.get(url, auth=ncld.auth)
# print(r.status_code)
# fp_save.write_bytes(r.content)

# os.getenv('HOSTNAME')