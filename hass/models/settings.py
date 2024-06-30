from pydantic import BaseModel


class HassSettings(BaseModel):
    hass_instance: str
    hass_token: str
