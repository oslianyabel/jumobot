import databases
import sqlalchemy

from chatbot.core.config import config

metadata = sqlalchemy.MetaData()

post_table = sqlalchemy.Table(
    "threads",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("body", sqlalchemy.String),
)

engine = sqlalchemy.create_engine(config.DATABASE_URL)

metadata.create_all(engine)

database = databases.Database(
    config.DATABASE_URL, force_rollback=config.DB_FORCE_ROLL_BACK
)