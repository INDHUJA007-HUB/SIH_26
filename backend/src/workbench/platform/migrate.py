"""Run reviewed migrations and local-only generated login setup before API startup."""

from alembic import command
from alembic.config import Config

from workbench.platform.config import PROJECT_ROOT, Settings
from workbench.platform.domain_bootstrap import configure_roles, seed_domain


def main() -> None:
    command.upgrade(Config(str(PROJECT_ROOT / "backend/alembic.ini")), "head")
    settings = Settings()
    configure_roles(settings)
    seed_domain(settings)
    from workbench.adapters.rule_registry_service import RuleRegistryService
    from workbench.platform.database import build_engine

    owner_engine = build_engine(settings.database_url.get_secret_value())
    try:
        RuleRegistryService(owner_engine).seed_default_rules()
    finally:
        owner_engine.dispose()


if __name__ == "__main__":
    main()
