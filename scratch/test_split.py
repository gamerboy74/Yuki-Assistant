import re

def smart_split(text, buffer):
    buffer += text
    # Split on .!? followed by whitespace, but NOT if the dot is surrounded by digits
    # Also split on newlines.
    
    sentences = []
    # We use a pattern that finds a sentence end: . ! or ? 
    # Must NOT be preceded by a digit and followed by a digit (decimal guard)
    # Must be followed by whitespace OR be at the very end of the string (if specifically allowed)
    
    # Simple heuristic: Split on [.!?] only if followed by space or newline
    # and not part of a decimal number.
    
    while True:
        # Regex: find first occurrence of [.!?] followed by whitespace
        # or find a newline
        match = re.search(r'([.!?](?:\s+|$))|(\n)', buffer)
        if not match:
            break
            
        end_idx = match.end()
        sentence = buffer[:end_idx].strip()
        
        # Guard: if sentence ends in a decimal dot (e.g. "... 28."), check if next is digit
        # But wait, match found a SPACE. So "28. " is a sentence end. "28.6" is NOT.
        
        sentences.append(sentence)
        buffer = buffer[end_idx:]
    
    return sentences, buffer

# Test cases
test_buffer = ""
chunks = ["Mumbai mein ", "abhi 28.", "6°C hai. ", "SpaceX ke head", "lines: unhone $5.", "23 billion loss ", "kiya. \nAgla ", "sawal?"]

all_sentences = []
for chunk in chunks:
    sents, test_buffer = smart_split(chunk, test_buffer)
    all_sentences.extend(sents)
    print(f"Chunk: {repr(chunk)} -> Sentences: {sents}")

print(f"Final Buffer: {repr(test_buffer)}")
print(f"All: {all_sentences}")
