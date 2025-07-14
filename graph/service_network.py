from graph.services.service import Service
from graph.services.error_handler_service import ErrorHandlerService
from graph.services.logging_service import LoggingService
from typing import List
import asyncio

class ServiceNetwork:
    def __init__(self):
        self._services: dict[str, Service] = {}
        # publisher_name → event_type → list of subscriber_names
        self._adjacency: dict[str, dict[str, List[str]]] = {}
        self._error_handler: ErrorHandlerService | None = None
        self._error_handler_name: str | None = None
        self._logger: LoggingService | None = None
        self._logger_name: str | None = None

    def add_service(self, name: str, svc: Service):
        self._services[name] = svc
        self._adjacency.setdefault(name, {})  # pre-populate node
        if self._error_handler is not None and name != self._error_handler_name:
            svc.subscribe(self._error_handler, ["error"])
            self._adjacency[name].setdefault("error", []).append(self._error_handler_name)

    def add_ErrorHandling(self, name: str = "error_handler", log_file: str = "errors.log"):
        """Add an :class:`ErrorHandlerService` and subscribe it to all existing services."""
        handler = ErrorHandlerService(log_file=log_file)
        self._error_handler = handler
        self._error_handler_name = name
        self._services[name] = handler
        self._adjacency.setdefault(name, {})
        # Subscribe existing services
        for svc_name, svc in self._services.items():
            if svc_name == name:
                continue
            svc.subscribe(handler, ["error"])
            self._adjacency.setdefault(svc_name, {}).setdefault("error", []).append(name)
        return handler

    def add_Logging(self, name: str = "event_logger", log_file: str = "events.log"):
        """Add a :class:`LoggingService` and mirror existing subscriptions."""
        logger = LoggingService(log_file=log_file)
        self._logger = logger
        self._logger_name = name
        self._services[name] = logger
        self._adjacency.setdefault(name, {})
        for pub, evt_map in self._adjacency.items():
            if pub == name:
                continue
            for evt in evt_map.keys():
                self._services[pub].subscribe(logger, [evt])
                self._adjacency[pub].setdefault(evt, [])
                if name not in self._adjacency[pub][evt]:
                    self._adjacency[pub][evt].append(name)
        return logger

    def connect(self, publisher_name: str, subscriber_name: str, event_types: List[str]):
        self._services[publisher_name].subscribe(self._services[subscriber_name], event_types)
        # Maintain an adjacency mapping for runtime inspection
        for evt in event_types:
            self._adjacency[publisher_name].setdefault(evt, []).append(subscriber_name)

    @property
    def adjacency(self):
        """Adjacency structure: publisher → event_type → subscribers."""
        return self._adjacency

    def to_nx_graph(self):
        """Build and return a NetworkX DiGraph for visualization."""
        import networkx as nx
        G = nx.DiGraph()
        for pub, evt_map in self._adjacency.items():
            for evt, subs in evt_map.items():
                for sub in subs:
                    G.add_edge(pub, sub, event=evt)
        return G

    async def start_all(self):
        await asyncio.gather(*(s.run() for s in self._services.values()))

# python -m graph.service_network
if __name__ == "__main__":
    async def _main():
        from graph.services.computer_media import MicrophoneService, SpeakerService
        network = ServiceNetwork()
        network.add_service("mic", MicrophoneService())
        network.add_service("speak", SpeakerService())
        network.connect("mic", "speak", ["audio_chunk"])
        
        await network.start_all()


    asyncio.run(_main())
