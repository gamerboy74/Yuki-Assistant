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
    "gemini-1.5-flash": (0.10, 0.40),
    "gemini-1.5-pro": (3.50, 10.50),
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the total USD cost for a given model and token count.
    
    Args:
        model: Model identifier (e.g., 'gpt-4o-mini')
        input_tokens: Number of prompt tokens
        output_tokens: Number of completion tokens
        
    Returns:
        float: Total USD cost
    """
    # Normalize model name for lookup
    m = model.lower()
    
    # Try exact match, then substring match
    rate = _RATES.get(m)
    if not rate:
        for k, v in _RATES.items():
            if k in m:
                rate = v
                break
    
    # Fallback to gpt-4o-mini rates if unknown
    if not rate:
        rate = _RATES["gpt-4o-mini"]
        
    input_rate, output_rate = rate
    
    cost = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
    return cost
