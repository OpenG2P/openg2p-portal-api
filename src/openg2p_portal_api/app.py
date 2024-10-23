# ruff: noqa: E402

import asyncio

from .config import Settings

_config = Settings.get_config()

from openg2p_fastapi_common.app import Initializer

from .controllers.auth_controller import AuthController
from .controllers.discovery_controller import DiscoveryController
from .controllers.document_file_controller import DocumentFileController
from .controllers.form_controller import FormController
from .controllers.oauth_controller import OAuthController
from .controllers.program_controller import ProgramController
from .models.orm.program_registrant_info_orm import ProgramRegistrantInfoDraftORM
from .services.document_file_service import DocumentFileService
from .services.form_service import FormService
from .services.membership_service import MembershipService
from .services.partner_service import PartnerService
from .services.program_service import ProgramService


class Initializer(Initializer):
    def initialize(self, **kwargs):
        super().initialize()
        # Initialize all Services, Controllers, any utils here.
        PartnerService()
        MembershipService()
        ProgramService()
        FormService()
        DocumentFileService()

        DiscoveryController().post_init()
        ProgramController().post_init()
        FormController().post_init()
        DocumentFileController().post_init()
        AuthController().post_init()
        OAuthController().post_init()

    def migrate_database(self, args):
        super().migrate_database(args)

        async def migrate():
            await ProgramRegistrantInfoDraftORM.create_migrate()

        asyncio.run(migrate())
