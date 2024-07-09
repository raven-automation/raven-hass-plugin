from typing import Any
from common.plugin import *
from raven_hass import *

from common.plugin.models.executor import *
from common.plugin.models.executor import Executor
from common.plugin.models.resource import Resource
from iso3166 import countries
from language_tags.tags import registry

registry_mapping = {
    i["Subtag"]: i["Description"][0] if len(i["Description"]) > 0 else i["Subtag"]
    for i in registry
    if "Subtag" in i.keys()
}

PLUGIN = "raven_hass_plugin"


class HassExecutor(ExecutionManager):
    @property
    def client(self) -> RavenHassClient:
        return self.options["client"]

    async def _get_services(self) -> list[Service]:
        return await self.client.get_services()

    def field_to_argument(self, field: ServiceField) -> ExecArguments:
        base = {
            "name": field.id,
            "label": field.name,
            "description": field.description,
            "placeholder": str(field.example) if field.example else None,
            "advanced": field.advanced,
            "required": field.required,
        }

        if field.selector:
            selector = field.selector
            selector_type = field.selector.selector_type

            if selector_type == "constant":
                return ConstantArgument(**base, value=selector.value)
            if selector_type == "boolean":
                return BooleanArgument(**base)
            if selector_type == "number":
                return NumberArgument(
                    **base,
                    min=selector.min,
                    max=selector.max,
                    suffix=selector.unit_of_measurement,
                )
            if selector_type == "duration":
                return DurationArgument(
                    **base, days=selector.enable_day, negatives=selector.allow_negative
                )
            if selector_type == "color_temp":
                if selector.unit == "kelvin":
                    return NumberArgument(
                        **base,
                        min=selector.min,
                        max=selector.max,
                        suffix="K",
                        negatives=False,
                    )
                else:
                    return NumberArgument(
                        **base,
                        min=selector.min_mired,
                        max=selector.max_mired,
                        suffix="Mi",
                        negatives=False,
                    )
            if selector_type == "color_rgb":
                return ColorArgument(**base, format="RGB")
            if selector_type in ["date", "time", "datetime"]:
                return DateTimeArgument(**base, mode=selector_type)
            if selector_type == "entity":
                targets = []
                if selector.include_entities and len(selector.include_entities) > 0:
                    targets.append(ExecutionTarget(id=selector.include_entities))
                if selector.exclude_entities and len(selector.exclude_entities) > 0:
                    targets.append(
                        ExecutionTarget(exclude=True, id=selector.exclude_entities)
                    )
                if selector.filter:
                    if isinstance(selector.filter, EntityFilterSelectorConfig):
                        filters: list[EntityFilterSelectorConfig] = [selector.filter]
                    else:
                        filters: list[EntityFilterSelectorConfig] = selector.filter
                    filter_targets = []
                    for f in filters:
                        filter_targets.append(
                            ExecutionTarget(
                                categories=f.domain,
                                fragment=(
                                    {"attributes": {"device_class": f.device_class}}
                                    if f.device_class
                                    else None
                                ),
                            )
                        )
                    targets.append(filter_targets)

                return ResourceArgument(
                    **base,
                    multiple=selector.multiple,
                    targets=targets if len(targets) > 0 else None,
                )
            if selector_type in [
                "action",
                "condition",
                "location",
                "media",
                "object",
                "target",
                "trigger",
            ]:
                return ObjectArgument(**base)
            if selector_type in [
                "addon",
                "assist_pipeline",
                "backup_location",
                "config_entry",
                "conversation_agent",
                "icon",
                "state",
                "template",
                "theme",
            ]:
                return StringArgument(**base)
            if selector_type == "text":
                if selector.multiline:
                    return StringArgument(**base, multiline=True)
                if selector.type == "password":
                    return StringArgument(**base, password=True)
                return StringArgument(**base)
            if selector_type in ["area", "device", "floor", "label"]:
                if selector.multiple:
                    return ArrayArgument(**base)
                else:
                    return StringArgument(**base)
            if selector_type == "attribute":
                model = ENTITY_MODELS[selector.entity_id.split(".")[0]]
                if model:
                    attr_field = model.model_fields.get("attributes", None)
                    if attr_field and hasattr(attr_field, "annotation"):
                        attr_type = attr_field.annotation
                        if hasattr(attr_type, "model_fields"):
                            options = list(attr_type.model_fields.keys())
                        else:
                            options = []
                    else:
                        options = []
                else:
                    options = []

                return SelectionArgument(**base, options=options)
            if selector_type == "country":
                if selector.countries:
                    options = [
                        {
                            "label": countries.get(i.lower(), i.upper()),
                            "value": i.upper(),
                        }
                        for i in selector.countries
                    ]
                else:
                    options = [
                        {
                            "label": i.name,
                            "value": i.alpha2,
                        }
                        for i in countries
                    ]

                return SelectionArgument(**base, options=options)
            if selector_type == "language":
                if selector.languages:
                    options = [
                        {
                            "label": registry_mapping.get(i.lower(), i),
                            "value": i.lower(),
                        }
                        for i in selector.languages
                    ]
                else:
                    options = [
                        {"label": v, "value": k} for k, v in registry_mapping.items()
                    ]
                return SelectionArgument(**base, options=options)
            if selector_type == "select":
                if len(selector.options) > 0:
                    return SelectionArgument(
                        **base, options=selector.options, multiple=selector.multiple
                    )
                else:
                    return StringArgument(**base)
            return ObjectArgument(**base)

        else:
            return ConstantArgument(**base, value=None)

    def service_to_executor(self, service: Service) -> Executor:
        categories = [service.domain]
        if service.domain.startswith("input_"):
            categories.append(service.domain.split("_")[1])
        return Executor(
            id=f"{PLUGIN}:{service.domain}.{service.service}",
            plugin=PLUGIN,
            export="get_executors",
            name=service.name,
            description=service.description,
            targets=[ExecutionTarget(categories=categories)],
            arguments={k: self.field_to_argument(v) for k, v in service.fields.items()},
        )

    async def get_executors(self, targets: list[Resource]) -> list[Executor]:
        services = await self._get_services()
        executors = [self.service_to_executor(svc) for svc in services]
        return [i for i in executors if i.matches_resources(*targets)]

    async def execute(
        self, executor: Executor, arguments: dict[str, Any], target: Resource
    ) -> None:
        entities = await self.client.get_entities()
        for i in entities:
            if i.entity_id == target.id:
                await i.call_service(executor.id.split(":", maxsplit=1)[1], arguments)
                break
        return None
