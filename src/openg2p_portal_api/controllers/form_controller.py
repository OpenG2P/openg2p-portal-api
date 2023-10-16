from openg2p_fastapi_common.controller import BaseController

from ..config import Settings
from ..models.form import ProgramForm

_config = Settings.get_config()


class FormController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.router.add_api_route(
            "/form/{programid}",
            self.get_program_form,
            responses={200: {"model": ProgramForm}},
            methods=["GET"],
        )

    async def get_program_form(self, programid: int):
        return {"program1": programid}