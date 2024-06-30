from contextlib import asynccontextmanager
from raven_hass import RavenHassClient
from .models import HassSettings


@asynccontextmanager
async def hass_lifecycle(settings: HassSettings):
    async with RavenHassClient(settings.hass_instance, settings.hass_token) as client:
        yield client
