from datetime import date, datetime, time
from enum import Enum
from inspect import isclass
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin
from pydantic import BaseModel
from raven_hass import (
    RavenHassClient,
    ENTITY_MODELS,
    HAEntity,
    BaseAttributes,
    Platform,
)
from common.plugin import (
    Resource,
    ResourceProperty,
    ResourceMetadata,
    ResourcePropertyType,
    ResourceResolver,
)


def parse_annotation(annotation: Any) -> ResourcePropertyType:
    origin = get_origin(annotation)
    if origin is UnionType:
        selection = ResourcePropertyType.OBJECT
        for item in get_args(annotation):
            result = parse_annotation(item)
            if result.priority > selection.priority:
                selection = result

        return selection
    elif origin is Literal:
        return ResourcePropertyType.OPTION
    elif origin is list or origin is tuple or annotation is list or annotation is tuple:
        if any(
            [not i in [str, bool, int, float, NoneType] for i in get_args(annotation)]
        ):
            return ResourcePropertyType.OBJECT
        return ResourcePropertyType.LIST
    elif origin is dict or annotation is dict:
        return ResourcePropertyType.OBJECT
    elif issubclass(annotation, Enum):
        return ResourcePropertyType.OPTION
    elif annotation is datetime:
        return ResourcePropertyType.DATETIME
    elif annotation is date:
        return ResourcePropertyType.DATE
    elif annotation is time:
        return ResourcePropertyType.TIME
    elif annotation is bool:
        return ResourcePropertyType.BOOLEAN
    elif annotation is str:
        return ResourcePropertyType.TEXT
    elif annotation is int or annotation is float:
        return ResourcePropertyType.NUMBER
    return ResourcePropertyType.OBJECT


def parse_type(data: Any) -> ResourcePropertyType:
    if type(data) == str:
        if data.lower() in [
            "on",
            "off",
            "yes",
            "no",
            "true",
            "false",
        ]:
            return ResourcePropertyType.BOOLEAN
        try:
            float(data)
            return ResourcePropertyType.NUMBER
        except:
            pass

        try:
            datetime.fromisoformat(data)
            return ResourcePropertyType.DATETIME
        except:
            pass
        return ResourcePropertyType.TEXT
    if type(data) == bool:
        return ResourcePropertyType.BOOLEAN
    if type(data) == float or type(data) == int:
        return ResourcePropertyType.NUMBER
    if type(data) == list:
        return ResourcePropertyType.LIST
    if type(data) == dict:
        return ResourcePropertyType.OBJECT
    if isinstance(data, Enum):
        return ResourcePropertyType.OPTION
    return ResourcePropertyType.TEXT


def deep_parse_fields(data: BaseModel):
    result = {}
    for field, schema in data.model_fields.items():
        if (
            schema.annotation
            and isclass(schema.annotation)
            and issubclass(schema.annotation, BaseModel)
        ):
            result[field] = deep_parse_fields(schema.annotation)
        else:
            value = getattr(data, field) if hasattr(data, field) else None
            if type(value) == str and value.lower() in [
                "on",
                "off",
                "yes",
                "no",
                "true",
                "false",
            ]:
                result[field] = ResourcePropertyType.BOOLEAN
                continue
            if type(value) == str:
                try:
                    float(value)
                    result[field] = ResourcePropertyType.NUMBER
                    continue
                except:
                    pass
            result[field] = parse_annotation(schema.annotation)
    return result


def parse_entity_schema(entity: HAEntity):
    fields = deep_parse_fields(entity)
    properties = {
        "state": parse_type(entity.state),
        **{k: v for k, v in fields["attributes"].items() if k != "state"},
    }
    resource_properties: dict[str, ResourceProperty] = {}
    for key, prop in properties.items():
        if key == "state":
            value = entity.state
        else:
            value = getattr(entity.attributes, key, None)

        if (
            prop == ResourcePropertyType.BOOLEAN
            and type(value) == str
            and value.lower()
            in [
                "on",
                "off",
                "yes",
                "no",
                "true",
                "false",
            ]
        ):
            value = value.lower() in ["on", "yes", "true"]
        elif prop == ResourcePropertyType.NUMBER:
            try:
                value = float(value)
            except:
                pass

        resource_properties[key] = ResourceProperty(
            label=" ".join([i.title() for i in key.split("_")]),
            type=prop,
            value=value,
            hidden=key in BaseAttributes.model_fields.keys() and not key == "state",
        )
    return resource_properties


def resolve_icon(entity: HAEntity) -> str:
    domain: Platform = entity.domain
    match domain:
        case Platform.AIR_QUALITY:
            return "cloud"
        case Platform.ALARM_CONTROL_PANEL:
            return "home-shield"
        case Platform.BINARY_SENSOR:
            return "binary"
        case Platform.BUTTON:
            return "hand-click"
        case Platform.CALENDAR:
            return "calendar"
        case Platform.CAMERA:
            return "camera"
        case Platform.CLIMATE:
            return "temperature"
        case Platform.CONVERSATION:
            return "messages"
        case Platform.COVER:
            return "building-store"
        case Platform.DATE:
            return "calendar"
        case Platform.DATETIME:
            return "calendar-time"
        case Platform.DEVICE_TRACKER:
            return "radar"
        case Platform.EVENT:
            return "exclamation-mark"
        case Platform.FAN:
            return "propeller"
        case Platform.GEO_LOCATION:
            return "map-pin"
        case Platform.HUMIDIFIER:
            return "mist"
        case Platform.IMAGE:
            return "photo"
        case Platform.IMAGE_PROCESSING:
            return "photo-edit"
        case Platform.LAWN_MOWER:
            return "plant"
        case Platform.LIGHT:
            return "bulb"
        case Platform.LOCK:
            return "lock"
        case Platform.MAILBOX:
            return "mailbox"
        case Platform.MEDIA_PLAYER:
            return "music"
        case Platform.NOTIFY:
            return "bell"
        case Platform.NUMBER:
            return "number"
        case Platform.REMOTE:
            return "device-remote"
        case Platform.SCENE:
            return "category"
        case Platform.SELECT:
            return "select"
        case Platform.SENSOR:
            return "photo-sensor-3"
        case Platform.SIREN:
            return "bell-school"
        case Platform.STT:
            return "ear"
        case Platform.SWITCH:
            return "toggle-left"
        case Platform.TEXT:
            return "letter-case"
        case Platform.TIME:
            return "clock"
        case Platform.TODO:
            return "list-details"
        case Platform.TTS:
            return "speakerphone"
        case Platform.VACUUM:
            return "vacuum-cleaner"
        case Platform.VALVE:
            return "droplet"
        case Platform.UPDATE:
            return "refresh-alert"
        case Platform.WAKE_WORD:
            return "speakerphone"
        case Platform.WATER_HEATER:
            return "bath"
        case Platform.WEATHER:
            return "sunset-2"
        case _:
            return "settings-2"


class EntityResolver(ResourceResolver):

    def __init__(self, client: RavenHassClient = None, **kwargs) -> NoneType:
        super().__init__(**kwargs)
        self.client = client

    async def get_one(self, id: str) -> Resource | NoneType:
        entity = await self.client.get_entity(id)
        if entity:
            props: dict = parse_entity_schema(entity)
            return Resource(
                id=entity.entity_id,
                plugin="raven_hass_plugin",
                metadata=ResourceMetadata(
                    display_name=" ".join([i.title() for i in entity.name.split("_")]),
                    category=entity.domain,
                    tags=[entity.domain, "HomeAssistant"],
                    icon=resolve_icon(entity),
                ),
                properties=props,
                state_key="state",
            )
        return None

    async def get_all(self):
        entities = await self.client.get_entities()
        resources: list[Resource] = []
        for entity in entities:
            props: dict = parse_entity_schema(entity)
            resources.append(
                Resource(
                    id=entity.entity_id,
                    plugin="raven_hass_plugin",
                    metadata=ResourceMetadata(
                        display_name=" ".join(
                            [i.title() for i in entity.name.split("_")]
                        ),
                        category=entity.domain,
                        tags=[entity.domain, "HomeAssistant"],
                        icon=resolve_icon(entity),
                    ),
                    properties=props,
                    state_key="state",
                )
            )
        return resources
