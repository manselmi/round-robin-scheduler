# vim: set ft=python :

from networkx import Graph, MultiGraph
from networkx.readwrite import node_link_data


def graph_transformer(_, __, event_dict):
    if (graph := event_dict.get("graph")) is None or not isinstance(graph, Graph | MultiGraph):
        return event_dict
    event_dict["graph"] = node_link_data(graph)
    return event_dict
