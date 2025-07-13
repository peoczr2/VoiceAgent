from graph.services.service import Service
from typing import List
import asyncio

class ServiceNetwork:
    def __init__(self):
        self._services: dict[str, Service] = {}
        # publisher_name → event_type → list of subscriber_names
        self._adjacency: dict[str, dict[str, List[str]]] = {}  

    def add_service(self, name: str, svc: Service):
        self._services[name] = svc
        self._adjacency.setdefault(name, {})  # pre-populate node

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
