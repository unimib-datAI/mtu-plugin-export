import os
import json
import requests
from tqdm import tqdm
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import FOAF, XSD, RDF, RDFS
from literal_checker import LiteralRecognizer

PREFIX_WIKIDATA_OBJECT = "https://www.wikidata.org/wiki"
PREFIX_WIKIDATA_PROPERTY = "https://www.wikidata.org/wiki/Property:"


class GraphWrapper():
    """Graph Wrapper"""

    def __init__(self) -> None:
        self.graph: Graph = Graph()
        self.graph.bind("foaf", FOAF)
        self.graph_builder: GraphBuilder = GraphBuilder(self.graph)
        self.annotated_tables: list[dict] = self.load_annotated_table()

    def load_annotated_table(self):
        """Load the annotated dataset"""
        annotated_tables = []
        file_path = f"{os.path.dirname(os.path.realpath(__file__))}/input.json"
        file_open = open(file_path, encoding="utf-8")
        data = json.load(file_open)
        annotated_tables.append(data)

        return annotated_tables

    def build_kg(self):
        """Build Kg from annotated tables"""
        self.graph_builder.build_graph(annotated_tables=self.annotated_tables)
        self.graph = self.graph_builder.graph

    def get_annotated_dataset(self) -> list[dict]:
        """Return annotations"""
        return self.annotated_tables

    def get_graph(self) -> Graph:
        """get current graph instance"""
        return self.graph


class GraphBuilder():
    """Graph Builder"""

    def __init__(self, graph: Graph) -> None:
        self.graph: Graph = graph
        self._invalid_uri_chars = '<>" {}|\\^`'
        self.literal_checker = LiteralRecognizer()

    def is_valid_uri(self, uri: str) -> bool:
        """check url validity"""
        for c in self._invalid_uri_chars:
            if c in uri:
                return False
        return True

    def create_cpa_dict(self, cpa: list[dict]) -> dict[str, str]:
        """create property dictionary"""
        property_dict: dict[str: str] = {}
        for prop in cpa:
            source = prop.get("idSourceColumn", None)
            destination = prop.get("idTargetColumn", None)
            predicates = prop.get("predicates", None)
            predicate = predicates[0] if len(predicates) > 0 else None

            if None in [source, destination, predicate]:
                continue

            predicate_name: str = predicate["name"]
            if predicate_name is None:
                continue
            property_dict[f"{source}_{destination}"] = {
                "id": predicate["id"],
                "source": source,
                "destination": destination,
                "name": predicate_name if predicate_name is not None else "",
                "name_fixed": "_".join(predicate_name.split(" "))
            }
        return property_dict

    def create_cta_dict(self, cta: list[dict]) -> dict[str, str]:
        """create types dictionary"""
        types_dict: dict[str: str] = {}
        for current_type in cta:
            column_id: int = current_type.get("idColumn", None)
            type_annotations = current_type.get("types", None)

            if None in [column_id, type_annotations]:
                continue

            for ct in type_annotations:
                type_name: str = ct["name"]
                if type_name is None:
                    continue
                types_dict[str(column_id)] = {
                    "id": ct["id"],
                    "column": column_id,
                    "name": type_name,
                    "name_fixed": "_".join(type_name.split(" "))
                }

        return types_dict

    def create_cea_dict(self, cea: list[dict]) -> dict[str, str]:
        """create cea dictionary"""
        entities_dict: dict[str: str] = {}
        for entity in cea:
            column_id = entity.get("idColumn", None)
            row_id = entity.get("idRow", None)
            candidate_entites = entity.get("entities", None)

            if None in [column_id, row_id, candidate_entites] or len(candidate_entites) < 1:
                continue

            annotated_entity: dict = candidate_entites[0]
            name: str = annotated_entity.get("name", "")
            types = annotated_entity.get("types", [])
            entities_dict[f"{row_id}_{column_id}"] = {
                "id": annotated_entity.get("id", ""),
                "name": name,
                "name_fixed": "_".join(name.split(" ")),
                "types": [{"id": ct["id"], "name": ct["name"], "name_fixed": "_".join(ct["name"].split(" "))} for ct in types if ct["id"] != "" and ct["name"] is not None],
                "description": annotated_entity.get("description", ""),
                "score": annotated_entity.get("score", 0)
            }

        return entities_dict

    def parse_annotations(self, table_dictionary: dict):
        """parse annotations"""
        header = table_dictionary.get("header", None)
        rows = table_dictionary.get("rows", None)
        semantic_annotations: dict = table_dictionary.get(
            "semanticAnnotations", None)
        metadata = table_dictionary.get("metadata", None)
        cpa = semantic_annotations.get("cpa", None)
        cta = semantic_annotations.get("cta", None)
        cea = semantic_annotations.get("cea", None)

        if None in [header, rows, metadata, cpa, cta, cea]:
            return None

        return [header, rows, metadata, cpa, cta, cea]

    def create_metadata_dict(self, metadata: dict[str, list[dict[str, str]]]) -> dict[str, str]:
        """metadata dictionary"""
        metadata_dict: dict = {}
        for col_type in metadata["column"]:
            col_id = col_type.get("idColumn", None)
            tag = col_type.get("tag", None)

            if None in [col_id, tag]:
                continue

            metadata_dict[str(col_id)] = tag

        return metadata_dict

    def literal_mapper(self, literal: str) -> URIRef:
        """Map literals to XSD type"""
        literal_type = self.literal_checker.check_literal(literal)
        if literal_type == "DATE":
            return XSD.date
        elif literal_type == "DATETIME":
            return XSD.dateTime
        elif literal_type == "TIME":
            return XSD.time
        elif literal_type == "URL":
            return XSD.anyURI
        elif literal_type == "EMAIL":
            return XSD.string
        elif literal_type == "FLOAT":
            return XSD.float
        elif literal_type == "INTEGER":
            return XSD.integer
        else:
            return XSD.string

    def build_graph(self, annotated_tables: list[dict]):
        """Build Graph from annotations"""
        for annotated_table in tqdm(annotated_tables):
            parsed_data = self.parse_annotations(annotated_table["data"])
            if parsed_data is None:
                continue
            [_, rows, metadata, cpa, cta, cea] = parsed_data
            props_dict = self.create_cpa_dict(cpa=cpa)
            types_dict = self.create_cta_dict(cta=cta)
            entities_dict = self.create_cea_dict(cea=cea)
            metadata_dict = self.create_metadata_dict(metadata=metadata)
            # entities
            for _, value in entities_dict.items():
                qid = URIRef(f"{PREFIX_WIKIDATA_OBJECT}/{value['id']}")
                name = Literal(value["name"], datatype=XSD.string)
                self.graph.add((qid, RDFS.label, name))
            # types
            for _, value in types_dict.items():
                qid = URIRef(f"{PREFIX_WIKIDATA_OBJECT}/{value['id']}")
                name = Literal(value["name"], datatype=XSD.string)
                self.graph.add((qid, RDFS.label, name))
            # props
            for _, value in props_dict.items():
                qid = URIRef(f"{PREFIX_WIKIDATA_PROPERTY}{value['id']}")
                name = Literal(value["name"], datatype=XSD.string)
                self.graph.add((qid, RDFS.label, name))
            for row_id, row in enumerate(rows):
                for i, _ in enumerate(row["data"]):
                    for j, cell_j in enumerate(row["data"]):
                        if j > i:
                            # create representation of cells
                            name_j: str = "_".join(cell_j.split(" "))
                            # create node names
                            metadata_j = metadata_dict.get(str(j), None)
                            if f"{row_id}_{i}" not in entities_dict:
                                continue
                            node_i = URIRef(
                                f"{PREFIX_WIKIDATA_OBJECT}/{entities_dict[f'{row_id}_{i}']['id']}")
                            if metadata_j != "LIT" and f"{row_id}_{j}" not in entities_dict:
                                continue
                            node_j = URIRef(
                                f"{PREFIX_WIKIDATA_OBJECT}/{entities_dict[f'{row_id}_{j}']['id']}") if metadata_j != "LIT" else Literal(name_j, datatype=self.literal_mapper(name_j))
                            # check relation
                            if f"{i}_{j}" in props_dict:
                                wikidata_relation_id = props_dict[f"{i}_{j}"]["id"]
                                relation_name = props_dict[f"{i}_{j}"]["id"]
                                relation = URIRef(
                                    f"{PREFIX_WIKIDATA_PROPERTY}/{relation_name}")
                                if self.is_valid_uri(f"{PREFIX_WIKIDATA_PROPERTY}{wikidata_relation_id}") and self.is_valid_uri(node_i) and self.is_valid_uri(node_j):
                                    self.graph.add((node_i, relation, node_j))

                            # check types
                            if str(i) in types_dict:
                                wikidata_type_id = types_dict[str(i)]["id"]
                                ontology = URIRef(
                                    f"{PREFIX_WIKIDATA_OBJECT}/{wikidata_type_id}")
                                if self.is_valid_uri(ontology):
                                    self.graph.add(
                                        (node_i, RDF.type, ontology))
                            if str(j) in types_dict:
                                wikidata_type_id = types_dict[str(j)]["id"]
                                ontology = URIRef(
                                    f"{PREFIX_WIKIDATA_OBJECT}/{wikidata_type_id}")
                                if self.is_valid_uri(ontology):
                                    self.graph.add(
                                        (node_j, RDF.type, ontology))

