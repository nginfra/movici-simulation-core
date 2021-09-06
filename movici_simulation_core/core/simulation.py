import typing as t

from movici_simulation_core.core.plugins import Service, Plugin


class Simulation:
    services: t.Dict[str, t.Type[Service]]
    config: dict

    def __init__(self):
        ...

    def run(self):
        """
        starts up services from config and auto_use using ServiceRunner. Collects service addresses
        starts up models from config with service addresses for discovery using ModelRunner
        tracks models and services, terminates when necessary (question: when do we terminate
        everything and when does the orchestrator take over?)
        """
        ...

    def start_service(self, service: t.Type[Service]):
        ...

    def use(self, plugin: t.Type[Plugin]):
        plugin.install(self)

    def register_service(self, name, service, auto_use=False):
        ...

    def register_model_type(self, name, model, adapter_class=None):
        ...


class ServiceRunner:
    """
    Provides logic for:
        - Creating a Pipe that the Service can use to announce its port
        - Creating a Process (daemon=True) that runs Service. Using a wrapping function this will
          - create the service
          - create a (router) socket
          - announce the port
          - run the Service
          - raise exception on failure
        - Returning the process object for management purposes
        - Also returning the address/port somehow (ServiceInfo object?)
        - Raising an exception if it fails to announce the port in time
    """

    def start(self):
        ...
