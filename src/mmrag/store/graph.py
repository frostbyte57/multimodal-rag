"""Lightweight In-Memory Knowledge Graph."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass
class Triplet:
    subject: str
    predicate: str
    object: str
    chunk_id: str

class GraphStore:
    def __init__(self) -> None:
        self.triplets: list[Triplet] = []
        self.adj: dict[str, set[str]] = defaultdict(set)
        
    def add_triplets(self, triplets: list[Triplet]) -> None:
        for t in triplets:
            self.triplets.append(t)
            s = t.subject.lower()
            o = t.object.lower()
            self.adj[s].add(o)
            self.adj[o].add(s)

    def extract_subgraph(self, keywords: list[str], max_depth: int = 1) -> list[Triplet]:
        """Extract all triplets within max_depth of any keyword."""
        if not self.triplets:
            return []
            
        frontier = set(k.lower() for k in keywords)
        visited = set(frontier)
        
        for _ in range(max_depth):
            next_frontier = set()
            for node in frontier:
                for neighbor in self.adj.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            
        subgraph = []
        for t in self.triplets:
            if t.subject.lower() in visited or t.object.lower() in visited:
                subgraph.append(t)
        return subgraph

    def save(self, path: Path) -> None:
        data = [asdict(t) for t in self.triplets]
        path.write_text(json.dumps(data, indent=2))
        
    @classmethod
    def load(cls, path: Path) -> "GraphStore":
        store = cls()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                triplets = [Triplet(**d) for d in data]
                store.add_triplets(triplets)
            except Exception:
                pass
        return store
