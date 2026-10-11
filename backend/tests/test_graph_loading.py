"""The road graph is loaded once and published only when fully prepared."""
import threading
import time

import networkx as nx

from app.services import routing_service as routing_module
from app.services.routing_service import RoutingService


def test_concurrent_cold_requests_load_the_graph_once(monkeypatch, tmp_path):
    graph_file = tmp_path / "g.graphml"
    graph_file.write_text("placeholder")
    calls = {"load": 0}

    def slow_load(path):
        calls["load"] += 1
        time.sleep(0.3)  # widen the race window
        g = nx.MultiDiGraph()
        g.add_edge(1, 2, length=10.0)
        return g

    def add_speeds(g):
        for _, _, d in g.edges(data=True):
            d["speed_kph"] = 30.0
        return g

    def add_times(g):
        for _, _, d in g.edges(data=True):
            d["travel_time"] = 1.2
        return g

    monkeypatch.setattr(routing_module.ox, "load_graphml", slow_load)
    monkeypatch.setattr(routing_module.ox, "add_edge_speeds", add_speeds)
    monkeypatch.setattr(routing_module.ox, "add_edge_travel_times", add_times)

    svc = RoutingService()
    svc.graph_path = str(graph_file)
    seen_partial = []

    def worker():
        assert svc.load_graph() is True
        # Any thread that sees the graph must see it fully prepared.
        if any("travel_time" not in d for _, _, d in svc.G.edges(data=True)):
            seen_partial.append(True)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls["load"] == 1
    assert not seen_partial
    assert svc.edges_count == 1


def test_missing_graph_file_reports_unavailable(tmp_path):
    svc = RoutingService()
    svc.graph_path = str(tmp_path / "absent.graphml")
    assert svc.load_graph() is False
    assert svc.G is None
