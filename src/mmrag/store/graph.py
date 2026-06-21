"""Neo4j Knowledge Graph Store."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from ..config import CONFIG

logger = logging.getLogger(__name__)

@dataclass
class Triplet:
    subject: str
    predicate: str
    object: str
    chunk_id: str

class GraphStore:
    def __init__(self) -> None:
        self.uri = CONFIG.neo4j_uri
        self.user = CONFIG.neo4j_user
        self.password = CONFIG.neo4j_password
        self._driver = None
        
    def _get_driver(self):
        if not self._driver:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            except Exception as e:
                logger.error(f"Failed to connect to Neo4j: {e}")
        return self._driver

    def add_triplets(self, triplets: list[Triplet]) -> None:
        driver = self._get_driver()
        if not driver or not triplets:
            return
            
        query = """
        UNWIND $triplets AS t
        MERGE (s:Entity {name: toLower(t.subject)})
        MERGE (o:Entity {name: toLower(t.object)})
        MERGE (s)-[r:RELATES_TO {type: t.predicate, chunk_id: t.chunk_id}]->(o)
        """
        try:
            with driver.session() as session:
                session.run(query, triplets=[{
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "chunk_id": t.chunk_id
                } for t in triplets])
        except Exception as e:
            logger.error(f"Failed to write triplets to Neo4j: {e}")

    def extract_subgraph(self, keywords: list[str], max_depth: int = 1) -> list[Triplet]:
        """Extract all triplets within max_depth of any keyword using Neo4j Cypher query."""
        driver = self._get_driver()
        if not driver or not keywords:
            return []
            
        query = f"""
        UNWIND $keywords AS kw
        MATCH (s:Entity)-[r:RELATES_TO*1..{max_depth}]-(o:Entity)
        WHERE s.name CONTAINS toLower(kw) OR o.name CONTAINS toLower(kw)
        UNWIND r AS rel
        RETURN startNode(rel).name AS subject,
               rel.type AS predicate,
               endNode(rel).name AS object,
               rel.chunk_id AS chunk_id
        LIMIT 100
        """
        subgraph = []
        try:
            with driver.session() as session:
                result = session.run(query, keywords=keywords)
                seen = set()
                for record in result:
                    t = Triplet(
                        subject=record["subject"],
                        predicate=record["predicate"],
                        object=record["object"],
                        chunk_id=record["chunk_id"],
                    )
                    key = (t.subject, t.predicate, t.object)
                    if key not in seen:
                        seen.add(key)
                        subgraph.append(t)
        except Exception as e:
            logger.error(f"Failed to query subgraph from Neo4j: {e}")
            
        return subgraph
        
    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
