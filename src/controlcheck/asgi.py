from __future__ import annotations

from fastapi import FastAPI

from .actions_api import install_action_routes
from .api import create_configured_app
from .governance_api import install_governance_routes
from .reports_api import install_report_routes


def create_asgi_app() -> FastAPI:
    application = create_configured_app()
    install_action_routes(application)
    install_governance_routes(application)
    install_report_routes(application)
    return application


app = create_asgi_app()
