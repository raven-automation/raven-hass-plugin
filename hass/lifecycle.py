from contextlib import asynccontextmanager
import logging
from typing import Any, Callable
from raven_hass import RavenHassClient, WSEvent
from .models import HassSettings


@asynccontextmanager
async def hass_lifecycle(settings: HassSettings):
    async with RavenHassClient(
        settings["hass_instance"], settings["hass_token"]
    ) as client:
        yield client


async def handle_hass_events(
    emit: Callable[[str, dict[str, Any], list[str] | str], None],
    client: RavenHassClient = None,
):
    async for ev in client.subscribe_events("state_changed"):
        event = ev.event["data"]
        if "entity_id" in event.keys():
            emit(
                "resource.update",
                {"entity_id": event["entity_id"]},
                scopes=["resources.all.*", "resources.plugin.raven_hass_plugin.*"],
            )
