__version__ = '0.1.0'

# SQLModel throws a warning, which would be fixed by https://github.com/tiangolo/sqlmodel/pull/234
# But the PR has not been merged yet
# The below is a workaround (from https://github.com/urjeetpatel/fastapi-project-template/commit/890e9026715dd81d609e1a4a1b28fdae86f02198#diff-0a1b4fd663181a6b61d569bbd0988104f7b5686c686092668369e03da454aa93)
# from sqlmodel.sql.expression import Select, SelectOfScalar
# SelectOfScalar.inherit_cache = True  # type: ignore
# Select.inherit_cache = True  # type: ignore

from .core import *