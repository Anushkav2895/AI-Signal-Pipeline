from rapidfuzz import process, fuzz

CANONICAL_SEED_LIST = [
    "OpenAI", "Anthropic", "Google DeepMind", "Mistral AI", "Cohere",
    "Stability AI", "Hugging Face", "Scale AI", "Perplexity AI", "Runway",
    "Character.AI", "Inflection AI", "Adept AI", "Together AI", "Databricks",
    "Weights & Biases", "LangChain", "Pinecone", "Chroma", "Replicate",
    "ElevenLabs", "Midjourney", "Synthesia", "Jasper", "Writer",
    "Glean", "Sierra", "Harvey", "Cursor", "Cognition Labs",
    "Vercel", "Modal", "Fireworks AI", "Groq", "Cerebras",
    "SambaNova", "Lambda Labs", "CoreWeave", "Voltage Park", "Crusoe Energy",
    "AI21 Labs", "Contextual AI", "Imbue", "Reka AI", "01.AI",
    "Moonshot AI", "Zhipu AI", "DeepSeek", "xAI", "Suno",
]

MATCH_THRESHOLD = 85


def canonicalize(raw_name: str) -> tuple[str, bool]:
    if not raw_name or not raw_name.strip():
        return raw_name, False

    result = process.extractOne(
        raw_name, CANONICAL_SEED_LIST, scorer=fuzz.WRatio, score_cutoff=MATCH_THRESHOLD
    )
    if result:
        matched_name, score, _ = result
        return matched_name, True

    return raw_name.strip(), False


def build_mapping_log(raw_names: list[str]) -> list[dict]:
    log = []
    seen = set()
    for raw in raw_names:
        key = raw.strip().lower()
        if key in seen:
            continue
        seen.add(key)

        canonical, matched = canonicalize(raw)
        log.append({
            "raw_name": raw,
            "canonical_name": canonical if matched else raw,
            "matched": matched,
        })
    return log


if __name__ == "__main__":
    test_names = [
        "OpenAI", "OpenAI, Inc.", "Open AI", "open-ai",
        "Anthropic PBC", "anthropic.com", "DeepMind (Google)",
        "SomeRandomStartupXYZ", "Mistral", "mistral ai",
    ]
    for name in test_names:
        canonical, matched = canonicalize(name)
        status = "MATCHED" if matched else "no match (kept as-is)"
        print(f"'{name}' -> '{canonical}'  [{status}]")