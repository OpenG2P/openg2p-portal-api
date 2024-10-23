from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class DocumentTagORM(BaseORMModel):
    __tablename__ = "g2p_document_tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
