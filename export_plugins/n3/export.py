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

class NOTATION3Export(Export):
    """NTRIPLES Export"""

    def export(self, graph: Graph):
        graph.serialize(destination=f"{os.path.dirname(os.path.realpath(__file__))}/output/kg.n3", format="n3")


graph_wrapper = GraphWrapper()
graph_wrapper.build_kg()
export: Export = NOTATION3Export().export(graph_wrapper.get_graph())
