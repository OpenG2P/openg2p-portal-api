from typing import Annotated, List

from fastapi import Depends
from openg2p_fastapi_auth.controllers.auth_controller import AuthController
from openg2p_fastapi_auth.models.orm.login_provider import LoginProvider
from openg2p_fastapi_common.errors.http_exceptions import UnauthorizedError
from sqlalchemy.exc import IntegrityError

from ..config import Settings
from ..dependencies import JwtBearerAuth
from ..models.credentials import AuthCredentials
from ..models.orm.auth_oauth_provider import AuthOauthProviderORM
from ..models.orm.partner_orm import (
    BankORM,
    PartnerBankORM,
    PartnerORM,
    PartnerPhoneNoORM,
)
from ..models.orm.reg_id_orm import RegIDORM, RegIDTypeORM
from ..models.profile import GetProfile, UpdateProfile
from ..services.partner_service import PartnerService

_config = Settings.get_config()


class AuthController(AuthController):
    """
    AuthController handles authentication and profile management operations.
    """

    def __init__(self, **kwargs):
        """
        Initializes the AuthController with necessary components and configurations.
        """
        super().__init__(**kwargs)
        self._partner_service = PartnerService.get_component()

        self.router.add_api_route(
            "/profile",
            self.get_profile,
            responses={200: {"model": GetProfile}},
            methods=["GET"],
        )
        self.router.add_api_route(
            "/profile",
            self.update_profile,
            methods=["PUT"],
        )

    @property
    def partner_service(self):
        """
        Provides access to the partner service component.
        """
        if not self._partner_service:
            self._partner_service = PartnerService.get_component()
        return self._partner_service

    async def get_profile(
        self,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
        online: bool = True,
    ):
        """
        Retrieves the profile of the authenticated user.

        Args:

            auth (AuthCredentials): Authentication credentials, obtained via JWT Bearer Auth.

            online (bool, optional): Indicates whether to fetch the profile online. Defaults to True.

        Returns:

            Profile: The profile of the authenticated user.
        """

        if not auth.partner_id:
            raise UnauthorizedError(
                message="Unauthorized. Partner Not Found in Registry."
            )

        partner_data = await PartnerORM.get_partner_data(auth.partner_id)
        partner_ids_data = await RegIDORM.get_all_partner_ids(partner_data.id)
        partner_bank_data = await PartnerBankORM.get_partner_banks(partner_data.id)
        partner_phone_data = await PartnerPhoneNoORM.get_partner_phone_details(
            partner_data.id
        )

        partner_ids = []
        for reg_id in partner_ids_data:
            partner_id = {
                "id_type": None,
                "value": reg_id.value,
                "expiry_date": reg_id.expiry_date,
            }

            id_type_name = await RegIDTypeORM.get_id_type_name(reg_id.id_type)

            if id_type_name:
                partner_id["id_type"] = id_type_name.name

            partner_ids.append(partner_id)

        partner_bank_accounts = []
        for bank in partner_bank_data:
            partner_bank = {
                "bank_name": None,
                "acc_number": bank.acc_number,
            }

            bank = await BankORM.get_by_id(bank.bank_id)

            if bank:
                partner_bank["bank_name"] = bank.name

            partner_bank_accounts.append(partner_bank)

        partner_phone_numbers = []
        for phone in partner_phone_data:
            partner_phone_numbers.append(
                {
                    "phone_no": phone.phone_no,
                    "date_collected": phone.date_collected,
                }
            )

        return GetProfile(
            id=partner_data.id,
            ids=partner_ids,
            email=partner_data.email,
            gender=partner_data.gender,
            address=partner_data.address,
            bank_ids=partner_bank_accounts,
            addl_name=partner_data.addl_name,
            given_name=partner_data.given_name,
            family_name=partner_data.family_name,
            birthdate=partner_data.birthdate,
            phone_numbers=partner_phone_numbers,
            birth_place=partner_data.birth_place,
        )

    async def update_profile(
        self,
        userdata: UpdateProfile,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
    ):
        """
        Updates the profile of the authenticated user.

        Args:

            userdata (Profile): The new data for the user's profile.

            auth (AuthCredentials): Authentication credentials, obtained via JWT Bearer Auth.

        Returns:

            Confirmation or updated profile data after the update.
        """
        try:
            await self.partner_service.update_partner_info(
                auth.partner_id, userdata.model_dump(exclude={"id"})
            )
        except IntegrityError:
            return "Could not add to registrant to program!!"
        return "Updated the partner info"

    async def get_login_providers_db(self) -> List[LoginProvider]:
        return [
            ap.map_auth_provider_to_login_provider()
            for ap in await AuthOauthProviderORM.get_all()
        ]

    async def get_login_provider_db_by_id(self, id: int) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_by_id(id)
        return ap.map_auth_provider_to_login_provider() if ap else None

    async def get_login_provider_db_by_iss(self, iss: str) -> LoginProvider:
        ap = await AuthOauthProviderORM.get_auth_provider_from_iss(iss)
        return ap.map_auth_provider_to_login_provider() if ap else None
