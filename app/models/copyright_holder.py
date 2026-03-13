from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from core.database import Base
from typing import List

class CopyrightHolder(Base):
    __tablename__ = "copyright_holders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    catalogs: Mapped[List["Catalog"]] = relationship(back_populates="holder")