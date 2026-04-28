from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Float
from core.database import Base

class Catalog(Base):
    __tablename__ = "catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    holder_id: Mapped[int] = mapped_column(ForeignKey("copyright_holders.id", ondelete="CASCADE"), index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"), index=True)
    
    authors_rights: Mapped[float] = mapped_column(Float, default=0.0)
    related_rights: Mapped[float] = mapped_column(Float, default=0.0)

    holder: Mapped["CopyrightHolder"] = relationship(back_populates="catalogs")
    track: Mapped["Track"] = relationship(back_populates="catalogs")