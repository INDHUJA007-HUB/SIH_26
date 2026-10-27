"""ASGI entry point."""

from workbench.api.app import create_app

app = create_app()
