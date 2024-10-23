from typing import Annotated

from fastapi import Depends
from openg2p_fastapi_common.controller import BaseController
from openg2p_fastapi_common.errors.http_exceptions import (
    BadRequestError,
    UnauthorizedError,
)

from ..config import Settings
from ..dependencies import JwtBearerAuth
from ..models.credentials import AuthCredentials
from ..models.form import ProgramForm, ProgramRegistrantInfo
from ..services.form_service import FormService
from ..services.program_service import ProgramService

_config = Settings.get_config()


class FormController(BaseController):
    """
    FormController handles operations related to form management for programs.
    """

    def __init__(self, **kwargs):
        """
        Initializes the FormController with necessary components and configurations.
        """
        super().__init__(**kwargs)
        self._form_service = FormService.get_component()
        self._program_service = ProgramService.get_component()

        self.router.prefix += "/form"
        self.router.tags += ["portal"]

        self.router.add_api_route(
            "/{programid}",
            self.get_program_form,
            responses={200: {"model": ProgramForm}},
            methods=["GET"],
        )

        self.router.add_api_route(
            "/{programid}",
            self.create_or_update_form_draft,
            responses={200: {"model": ProgramForm}},
            methods=["PUT"],
        )

        self.router.add_api_route(
            "/{programid}/submit",
            self.submit_form,
            responses={200: {"model": ProgramForm}},
            methods=["POST"],
        )

    @property
    def form_service(self):
        """
        Provides access to the form service component.
        """
        if not self._form_service:
            self._form_service = FormService.get_component()
        return self._form_service

    @property
    def program_service(self):
        """
        Provides access to the form service component.
        """
        if not self._program_service:
            self._program_service = ProgramService.get_component()
        return self._program_service

    async def get_program_form(
        self, programid: int, auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())]
    ):
        """
        Retrieves the form for a specified program.

        Args:

            programid (int): The ID of the program whose form is to be retrieved.

            auth (AuthCredentials): Authentication credentials, obtained via JWT Bearer Auth.

        Returns:

            ProgramForm: The form associated with the specified program.
        """
        if not auth.partner_id:
            raise UnauthorizedError(
                message="Unauthorized. Partner Not Found in Registry."
            )
        return await self.form_service.get_program_form(programid, auth.partner_id)

    async def create_or_update_form_draft(
        self,
        programid: int,
        programreginfo: ProgramRegistrantInfo,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
    ):
        """
        Creates or updates a draft of a form for a specified program.

        Args:

            programid (int): The ID of the program for which the form draft is to be created or updated.

            programreginfo (ProgramRegistrantInfo): Information to be filled in the form.

            auth (AuthCredentials): Authentication credentials, obtained via JWT Bearer Auth.

        Returns:

            ProgramForm: The created or updated form draft.
        """
        if not auth.partner_id:
            raise UnauthorizedError(
                message="Unauthorized. Partner Not Found in Registry."
            )

        return await self.form_service.create_form_draft(
            programid, programreginfo, auth.partner_id
        )

    async def submit_form(
        self,
        programid: int,
        programreginfo: ProgramRegistrantInfo,
        auth: Annotated[AuthCredentials, Depends(JwtBearerAuth())],
    ):
        """
        Submits a form for a specified program.

        Args:

            programid (int): The ID of the program for which the form is submitted.

            programreginfo (ProgramRegistrantInfo): Information to be submitted in the form.

            auth (AuthCredentials): Authentication credentials, obtained via JWT Bearer Auth.

        Returns:

            ProgramForm: The submitted form.
        """
        if not auth.partner_id:
            raise UnauthorizedError(
                message="Unauthorized. Partner Not Found in Registry."
            )

        program = await self.program_service.get_program_by_id_service(
            programid, auth.partner_id
        )

        if not program.is_portal_form_mapped:
            raise BadRequestError(
                message="Form submission is not allowed. Portal form is not mapped to this program."
            )

        return await self.form_service.submit_application_form(
            programid, programreginfo, auth.partner_id
        )
