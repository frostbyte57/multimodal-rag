"""Graph Entity Extraction."""

from __future__ import annotations

import json
import logging
from ..config import CONFIG
from ..schema import Chunk
from ..store.graph import Triplet

logger = logging.getLogger(__name__)

def extract_triplets(chunk: Chunk) -> list[Triplet]:
    """Use the LLM to extract entity triplets from a chunk."""
    if not (CONFIG.use_anthropic or CONFIG.use_ollama) or not CONFIG.use_graphrag:
        return []
        
    try:
        from ..agent import _call_llm
        
        prompt = f"""Extract key entities and their relationships from the text below.
Output a JSON array of objects with 'subject', 'predicate', and 'object' keys.
Keep entities concise (e.g., "StreamFlow", "Postgres", "Data Pipeline").
Do not output anything except the JSON array.

Text: {chunk.text}
"""
        text = _call_llm(
            prompt, 
            system="You are a knowledge graph extractor. Return ONLY a JSON array.",
            json_format=True,
            temperature=0.1
        )
        
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        data = json.loads(text.strip())
        valid = []
        if isinstance(data, list):
            for t in data:
                if isinstance(t, dict) and "subject" in t and "predicate" in t and "object" in t:
                    valid.append(
                        Triplet(
                            subject=str(t["subject"]),
                            predicate=str(t["predicate"]),
                            object=str(t["object"]),
                            chunk_id=chunk.chunk_id,
                        )
                    )
        return valid
    except Exception as e:
        logger.warning(f"Graph extraction failed for chunk {chunk.chunk_id}: {e}")
        
    return []
