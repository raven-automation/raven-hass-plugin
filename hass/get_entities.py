from raven_hass import RavenHassClient


async def get_entities(client: RavenHassClient = None, **kwargs):
    return await client.get_entities()
