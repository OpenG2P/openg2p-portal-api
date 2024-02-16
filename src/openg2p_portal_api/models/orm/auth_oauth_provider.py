from typing import List, Optional

import orjson
from openg2p_fastapi_auth.models.login_provider import LoginProviderTypes
from openg2p_fastapi_auth.models.orm.login_provider import LoginProvider
from openg2p_fastapi_auth.models.provider_auth_parameters import (
    OauthClientAssertionType,
    OauthProviderParameters,
)
from openg2p_fastapi_common.context import dbengine
from openg2p_fastapi_common.models import BaseORMModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column


class AuthOauthProviderORM(BaseORMModel):
    __tablename__ = "auth_oauth_provider"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    flow: Mapped[Optional[str]] = mapped_column()
    token_map: Mapped[Optional[str]] = mapped_column()
    client_id: Mapped[Optional[str]] = mapped_column()
    client_secret: Mapped[Optional[str]] = mapped_column()
    auth_endpoint: Mapped[str] = mapped_column()
    validation_endpoint: Mapped[Optional[str]] = mapped_column()
    token_endpoint: Mapped[Optional[str]] = mapped_column()
    jwks_uri: Mapped[Optional[str]] = mapped_column()
    scope: Mapped[Optional[str]] = mapped_column()
    client_authentication_method: Mapped[str] = mapped_column()
    code_verifier: Mapped[Optional[str]] = mapped_column()
    extra_authorize_params: Mapped[Optional[str]] = mapped_column()
    client_private_key: Mapped[Optional[bytes]] = mapped_column()
    g2p_self_service_allowed: Mapped[Optional[bool]] = mapped_column()
    body: Mapped[Optional[str]] = mapped_column()
    g2p_portal_login_image_icon_url: Mapped[Optional[str]] = mapped_column()

    @classmethod
    async def get_by_id(cls, id: int, active=True) -> "AuthOauthProviderORM":
        result = None
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            result = await session.get(cls, id)
            if result.g2p_self_service_allowed != active:
                result = None

        return result

    @classmethod
    async def get_all(cls, active=True) -> List["AuthOauthProviderORM"]:
        response = []
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            stmt = (
                select(cls)
                .where(cls.g2p_self_service_allowed == active)
                .order_by(cls.id.asc())
            )

            result = await session.execute(stmt)

            response = list(result.scalars())
        return response

    @classmethod
    async def get_auth_provider_from_iss(cls, iss: str) -> "AuthOauthProviderORM":
        response = None
        async_session_maker = async_sessionmaker(dbengine.get())
        async with async_session_maker() as session:
            stmt = (
                select(cls)
                .where(
                    and_(
                        cls.g2p_self_service_allowed is True,
                        cls.token_endpoint.ilike(f"%{iss}%"),
                    )
                )
                .order_by(cls.id.asc())
            )

            result = await session.execute(stmt)
            response = result.scalar()
        return response

    def map_auth_provider_to_login_provider(
        self, redirect_uri_base: str = None
    ) -> LoginProvider:
        response_type = "token"
        if self.flow == "id_token":
            response_type = "id_token token"
        elif self.flow == "id_token_code":
            response_type = "code"
        # Only the following type is supported for now
        type = LoginProviderTypes.oauth2_auth_code

        return LoginProvider(
            id=self.id,
            name=self.name,
            type=type,
            # Description not available
            description=self.name,
            login_button_text=self.body or "",
            login_button_image_url=self.g2p_portal_login_image_icon_url or "",
            authorization_parameters=OauthProviderParameters(
                authorize_endpoint=self.auth_endpoint,
                token_endpoint=self.token_endpoint,
                validate_endpoint=self.validation_endpoint,
                jwks_endpoint=self.jwks_uri,
                client_id=self.client_id,
                client_secret=self.client_secret,
                client_assertion_type=OauthClientAssertionType[
                    self.client_authentication_method
                ],
                client_assertion_jwk=self.client_private_key.decode(),
                response_type=response_type,
                redirect_uri=redirect_uri_base.rstrip("/") + "/oauth2/callback",
                scope=self.scope,
                code_verifier=self.code_verifier,
                extra_authorize_parameters=orjson.loads(self.extra_authorize_params),
            ).model_dump(),
            active=self.g2p_self_service_allowed,
        )
