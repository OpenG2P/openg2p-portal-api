from typing import Dict, List

from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openg2p_portal_api.models.orm.document_file_orm import DocumentFileORM


class DocumentStoreORM(BaseORMModel):
    __tablename__ = "storage_backend"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    server_env_defaults: Mapped[Dict[str, str]] = mapped_column(JSON, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

    documents: Mapped[List["DocumentFileORM"]] = relationship(
        "DocumentFileORM", back_populates="backend"
    )
