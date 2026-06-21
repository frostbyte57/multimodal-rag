"""Agentic Retrieval components.

Uses an LLM to rewrite and expand user queries to improve recall, and evaluate
retrieval results for iterative querying.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import CONFIG

logger = logging.getLogger(__name__)

def _call_llm(prompt: str, system: str = "", json_format: bool = False, temperature: float = 0.1) -> str:
    """Helper to call Anthropic or Ollama based on configuration."""
    if CONFIG.use_anthropic:
        import anthropic
        client = anthropic.Anthropic(api_key=CONFIG.anthropic_api_key)
        resp = client.messages.create(
            model=CONFIG.generation_model,
            max_tokens=512,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
        
    if CONFIG.use_ollama:
        import urllib.request
        url = f"{CONFIG.ollama_base_url.rstrip('/')}/api/generate"
        payload = {
            "model": CONFIG.ollama_model,
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": temperature}
        }
        if json_format:
            payload["format"] = "json"
            
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result.get("response", "").strip()
            
    raise RuntimeError("No LLM configured (Anthropic or Ollama).")


def expand_query(question: str) -> list[str]:
    """Use the LLM to rewrite and expand the query to improve recall.
    
    Returns the original query plus up to 2 variations (synonyms, 
    acronym expansions, sub-queries). If the LLM call fails or is unconfigured,
    returns just the original question.
    """
    if not (CONFIG.use_anthropic or CONFIG.use_ollama):
        return [question]
    
    try:
        prompt = f"""You are a query expansion module for a retrieval system.
Given the user's question, output a JSON array of 1 to 3 string queries.
The first query must be the original question exactly as written.
The others should be variations that might better match technical documentation (e.g. expanding acronyms, adding synonyms, or breaking down a complex comparative question into sub-queries).
Return ONLY valid JSON array of strings. Do not add markdown blocks or any other text.

Question: {question}
"""
        text = _call_llm(prompt, system="You are a query expansion module. Return ONLY a JSON array of strings.", json_format=True, temperature=0.2)
        
        # Strip potential markdown formatting
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        queries = json.loads(text.strip())
        if isinstance(queries, list) and queries and isinstance(queries[0], str):
            # Ensure the original question is always first
            if queries[0] != question:
                queries.insert(0, question)
            return queries[:3]
            
    except Exception as e:
        logger.warning(f"Query expansion failed, falling back to original query: {e}")
        
    return [question]

def generate_hyde_document(question: str) -> str | None:
    """Generate a Hypothetical Document Embedding (HyDE) string.
    
    Uses the LLM to hallucinate a plausible answer to the question.
    Embedding this hallucinated answer often bridges the semantic gap
    between a short question and a detailed source document.
    """
    if not (CONFIG.use_anthropic or CONFIG.use_ollama):
        return None
        
    try:
        prompt = f"""Please write a plausible, detailed paragraph that answers the following question.
Write it in the style of a technical document or manual.
Do not include any intro/outro like "Here is a paragraph" or "As an AI".
Just output the raw text of the hypothetical document.

Question: {question}
"""
        return _call_llm(prompt, system="You are a technical writer.", json_format=False, temperature=0.3)
    except Exception as e:
        logger.warning(f"HyDE generation failed: {e}")
        
    return None

def extract_keywords(question: str) -> list[str]:
    """Extract key entities from the question for GraphRAG traversal."""
    if not (CONFIG.use_anthropic or CONFIG.use_ollama):
        return [w for w in question.split() if len(w) > 4]
        
    try:
        prompt = f"""Extract 2 to 4 key entities or noun phrases from this question.
Output them as a JSON array of strings. Do not output anything else.

Question: {question}
"""
        text = _call_llm(prompt, system="You are an entity extractor. Return ONLY a JSON array.", json_format=True, temperature=0.1)
        
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
            
        data = json.loads(text.strip())
        if isinstance(data, list):
            return [str(x) for x in data if isinstance(x, str)]
    except Exception as e:
        logger.warning(f"Keyword extraction failed: {e}")
        
    return [w for w in question.split() if len(w) > 4]
