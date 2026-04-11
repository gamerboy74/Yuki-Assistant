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
    
    # Clean model name (remove vendor prefix if present)
    if "/" in m:
        m = m.split("/")[-1]
    
    # Try exact match, then versioned match
    rate = _RATES.get(m)
    if not rate:
        # Check for model families (e.g., 'gemini-2.0' in 'gemini-2.0-flash-v1')
        for k, v in _RATES.items():
            if k in m:
                rate = v
                break
    
    # Last resort: generic family fallback
    if not rate:
        if "gemini" in m:
            # Default to standard flash rates for any unknown Gemini
            rate = _RATES["gemini-2.0-flash"]
        else:
            rate = _RATES["gpt-4o-mini"]
        
    input_rate, output_rate = rate
    
    cost = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
    return cost
