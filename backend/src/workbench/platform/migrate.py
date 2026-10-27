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


if __name__ == "__main__":
    main()
