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
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.10, 0.40),
    "gemini-2.5-flash-lite": (0.075, 0.30),
    "gemini-3.0-flash": (0.10, 0.40), # Provisional rates
    "gemini-1.5-flash": (0.10, 0.40),
    "gemini-1.5-pro": (3.50, 10.50),
}

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
    m = model.lower()
    if "/" in m: m = m.split("/")[-1]
    
    rate = _RATES.get(m)
    if not rate:
        for k, v in _RATES.items():
            if k in m:
                rate = v
                break
    
    if not rate:
        rate = _RATES["gemini-2.0-flash"] if "gemini" in m else _RATES["gpt-4o-mini"]
        
    input_rate, output_rate = rate
    
    # ── Expert Pricing: Cache Optimization ──
    # Most providers (Google/Anthropic) bill cached tokens at ~25% of the base input rate.
    cache_rate = input_rate * 0.25
    
    total_input_cost = (input_tokens / 1_000_000 * input_rate) + (cached_tokens / 1_000_000 * cache_rate)
    total_output_cost = (output_tokens / 1_000_000 * output_rate)
    
    return total_input_cost + total_output_cost
