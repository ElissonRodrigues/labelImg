import os
import logging
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from alembic.config import Config
from alembic import command

# Global set to track which databases have been migrated in this session
_MIGRATED_DATABASES = set()

# Silence alembic loggers decisively
for logger_name in ["alembic", "alembic.runtime.migration", "sqlalchemy.engine"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)
    logging.getLogger(logger_name).propagate = False

Base = declarative_base()


class Class(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    annotations = relationship("Annotation", back_populates="label_class")

    def __repr__(self):
        return f"<Class(name='{self.name}')>"


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    path = Column(
        String, unique=True, nullable=False
    )  # Stores relative or absolute path depending on project settings
    width = Column(Integer)
    height = Column(Integer)
    depth = Column(Integer)

    annotations = relationship(
        "Annotation", back_populates="image", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Image(path='{self.path}')>"


class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)

    xmin = Column(Integer)
    ymin = Column(Integer)
    xmax = Column(Integer)
    ymax = Column(Integer)

    image = relationship("Image", back_populates="annotations")
    label_class = relationship("Class", back_populates="annotations")

    def __repr__(self):
        return f"<Annotation(image_id={self.image_id}, class_id={self.class_id})>"


class UndoHistory(Base):
    __tablename__ = "undo_history"

    id = Column(Integer, primary_key=True)
    action_type = Column(String, nullable=False)  # CREATE, UPDATE, DELETE
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(Text)  # JSON string or specific format to restore state

    def __repr__(self):
        return f"<UndoHistory(action='{self.action_type}')>"


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(Text)

    def __repr__(self):
        return f"<Setting(key='{self.key}')>"


def get_db_engine(db_path):
    """
    Creates the database engine.
    db_path: Path to the sqlite file (e.g., 'project_statistics.db')
    """
    return create_engine(f"sqlite:///{db_path}")


def apply_migrations(db_path):
    """
    Applies Alembic migrations to the specified database once per session.
    """
    # Normalize path to ensure consistent tracking
    abs_db_path = os.path.abspath(db_path)

    if abs_db_path in _MIGRATED_DATABASES:
        return

    # Path to the alembic.ini file (at the root of the project)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(base_dir, "alembic.ini")

    if not os.path.exists(ini_path):
        return

    alembic_cfg = Config(ini_path)

    # Absolute path to the alembic directory
    alembic_dir = os.path.join(base_dir, "alembic")
    alembic_cfg.set_main_option("script_location", alembic_dir)

    # Set the dynamic database URL
    db_url = f"sqlite:///{abs_db_path}"
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Disable logging configuration during migration to prevent terminal info messages
    alembic_cfg.set_main_option("logging_config", "")

    try:
        # upgrade head will apply all missing migrations
        command.upgrade(alembic_cfg, "head")
        _MIGRATED_DATABASES.add(abs_db_path)
    except Exception as e:
        # Silent handling of common setup issues
        if "already exists" not in str(e):
            # Only log truly unexpected errors
            getattr(logging.getLogger("alembic"), "error")(
                f"Migration error for {os.path.basename(db_path)}: {e}"
            )
        else:
            # Mark as migrated even if it error'd with "already exists"
            # (likely means it was created by Base.metadata.create_all previously)
            _MIGRATED_DATABASES.add(abs_db_path)


def init_db(db_path):
    """
    Initializes the database, creating tables if they don't exist.
    """
    # Run migrations automatically (only once per path)
    apply_migrations(db_path)

    engine = get_db_engine(db_path)
    # create_all is a fallback/safety, migrations should handle it
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
