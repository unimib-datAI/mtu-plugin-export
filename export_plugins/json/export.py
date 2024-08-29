import os
from graph import GraphWrapper
from rdflib import Graph
import time

"""Export Module"""
import abc


class Export(abc.ABC):
    """Export Interface"""

    @abc.abstractmethod
    def export(self, graph: Graph):
        """export function"""
        pass

class JSONLDExport(Export):
    """JSON-LD Export"""

    def export(self, graph: Graph):
        graph.serialize(destination=f"{os.path.dirname(os.path.realpath(__file__))}/output/kg.json", format="json-ld")


graph_wrapper = GraphWrapper()
graph_wrapper.build_kg()
export: Export = JSONLDExport().export(graph_wrapper.get_graph())
