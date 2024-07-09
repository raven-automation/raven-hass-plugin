from common.plugin import *
from raven_hass import RavenHassClient


class HassExecutor(ExecutionManager):
    @property
    def client(self) -> RavenHassClient:
        return self.options["client"]
