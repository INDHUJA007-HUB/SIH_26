"""Phase 1 authenticated fixture use case, independent of HTTP and storage implementations."""

from workbench.contracts.foundation import Actor, Institution, InstitutionReader
from workbench.platform.errors import AccessDenied


class FoundationInstitutionService:
    def __init__(self, institutions: InstitutionReader) -> None:
        self.institutions = institutions

    def own_fixture(self, actor: Actor) -> Institution:
        institution = self.institutions.get_institution(actor.institution_id)
        if institution is None:
            raise AccessDenied()
        return institution
