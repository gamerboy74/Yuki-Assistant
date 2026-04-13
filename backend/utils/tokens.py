"""
backend/utils/tokens.py — Token cost calculation and model rates.

Pricing as of April 2026 (per 1,000,000 tokens):
- OpenAI gpt-4o-mini:  $0.15 / $0.60
- Gemini 2.0 Flash:    $0.10 / $0.40
- Gemini 2.0 Flash Lite: $0.075 / $0.30
- Others (fallback):   $0.15 / $0.60 (OpenAI Mini rates)
"""

# Rate table: (input_price_per_1m, output_price_per_1m)
_RATES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (5.00, 15.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3": (10.00, 40.00),
    "o4-mini": (1.10, 4.40),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-3.0-flash": (0.10, 0.40),
    "gemini-3.0-pro": (1.25, 10.00),
    "gemini-3.1-flash": (0.05, 0.20),
    "gemini-3.1-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.10, 0.40),
    "gemini-1.5-pro": (3.50, 10.50),
}
from backend.utils.logger import get_logger
logger = get_logger(__name__)

def calculate_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    """
    Calculate the total USD cost for a given model and token count.
    Handles context caching for Gemini/OpenAI models if provided.
    
    Args:
        model: Model identifier
        input_tokens: Regular prompt tokens
        output_tokens: Completion tokens
        cached_tokens: Tokens retrieved from context cache (billed lower)
    """
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0
    cached_tokens = cached_tokens or 0
    
    m = model.lower()
    if "/" in m: m = m.split("/")[-1]
    
    rate = _RATES.get(m)
    if not rate:
        for k, v in _RATES.items():
            if k in m:
                rate = v
                break
    
    if not rate:
        logger.warning(f"[TOKENS] Unknown model '{model}', using default rate.")
        rate = _RATES["gemini-2.0-flash"] if "gemini" in m else _RATES["gpt-4o-mini"]
        
    input_rate, output_rate = rate
    
    # ── Expert Pricing: Cache Optimization ──
    # Different providers have different cache discount rates.
    CACHE_DISCOUNT = {
        "openai": 0.50,   # OpenAI: 50% of base input rate
        "gemini": 0.25,   # Google: 25% of base input rate
    }
    
    # Determine the provider based on the model string
    provider = "openai" if any(k in m for k in ["gpt", "o1", "o3", "o4"]) else "gemini"
    cache_discount = CACHE_DISCOUNT.get(provider, 0.50) # Default to 50% if unknown
    cache_rate = input_rate * cache_discount
    
    total_input_cost = (input_tokens / 1_000_000 * input_rate) + (cached_tokens / 1_000_000 * cache_rate)
    total_output_cost = (output_tokens / 1_000_000 * output_rate)
    
    return total_input_cost + total_output_cost
