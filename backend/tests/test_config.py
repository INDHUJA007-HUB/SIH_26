import pytest
from pydantic import ValidationError

from workbench.platform.config import Settings


@pytest.mark.parametrize("environment", ["integration", "staging", "production"])
def test_fixture_auth_cannot_escape_local(environment):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment=environment, auth_mode="fixture")


def test_production_is_explicitly_not_a_phase_one_feature():
    with pytest.raises(ValidationError, match="staging/production"):
        Settings(
            _env_file=None,
            environment="production",
            auth_mode="oidc",
            oidc_jwks_url="https://invalid",
        )


def test_oidc_and_dependency_checks_require_configuration():
    with pytest.raises(ValidationError, match="JWKS"):
        Settings(_env_file=None, auth_mode="oidc", oidc_jwks_url="")
    with pytest.raises(ValidationError, match="DATABASE"):
        Settings(_env_file=None, dependency_checks=True, database_url="")
