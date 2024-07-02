from datetime import date, datetime, time
from enum import Enum
from inspect import isclass
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin
from pydantic import BaseModel
from raven_hass import RavenHassClient, ENTITY_MODELS, HAEntity, BaseAttributes
from common.plugin import (
    Resource,
    ResourceProperty,
    ResourceMetadata,
    ResourcePropertyType,
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
            result[field] = parse_annotation(schema.annotation)

    return result


def parse_entity_schema(entity: HAEntity):
    fields = deep_parse_fields(entity)
    properties = {"state": fields["state"], **fields["attributes"]}
    resource_properties: dict[str, ResourceProperty] = {}
    for key, prop in properties.items():
        if key == "state":
            value = entity.state
        else:
            value = getattr(entity.attributes, key, None)

        resource_properties[key] = ResourceProperty(
            label=" ".join([i.title() for i in key.split("_")]),
            type=prop,
            value=value,
            hidden=key in BaseAttributes.model_fields.keys(),
        )
    return resource_properties


async def get_entities(client: RavenHassClient = None, **kwargs):
    entities = await client.get_entities()
    resources: list[Resource] = []
    for entity in entities:
        props: dict = parse_entity_schema(entity)
        resources.append(
            Resource(
                id=entity.entity_id,
                plugin="raven_hass_plugin",
                metadata=ResourceMetadata(
                    display_name=" ".join([i.title() for i in entity.name.split("_")]),
                    category=entity.domain,
                    tags=[entity.domain, "HomeAssistant"],
                ),
                properties=props,
                state_key="state",
            )
        )
    return resources
