from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Index
from core.database import Base
from typing import List, Optional

class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    isrc: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    artist: Mapped[Optional[str]] = mapped_column(String(500))
    authors: Mapped[Optional[str]] = mapped_column(String(1000))
    composer: Mapped[Optional[str]] = mapped_column(String(500))
    lyricist: Mapped[Optional[str]] = mapped_column(String(500))
    album_name: Mapped[Optional[str]] = mapped_column(String(500))

    catalogs: Mapped[List["Catalog"]] = relationship(back_populates="track")