from mmrag.config import CONFIG

# Force the offline, in-process path for the whole test session, independent of
# any saved .mmrag.json on the dev machine. Configuration is no longer env-based.
CONFIG.vector_in_memory = True
CONFIG.anthropic_api_key = None
CONFIG.voyage_api_key = None
