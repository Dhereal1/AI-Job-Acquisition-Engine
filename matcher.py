"""
Keyword-based relevance scorer.
Config-driven — edit config/profile.yaml to change behavior.
"""

import re
import yaml
from pathlib import Path
from typing import Tuple

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "profile.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize(text: str) -> str:
    return text.lower()


def extract_matches(text: str, keywords: list) -> list:
    text_lower = normalize(text)
    found = []
    for kw in keywords:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_lower):
            found.append(kw)
    return found


def score_message(text: str, config: dict = None) -> Tuple[int, list, list]:
    """
    Returns: (score, matched_keywords, negative_hits)
    """
    if config is None:
        config = load_config()

    weights = config.get('weights', {})
    kw = config.get('keywords', {})
    neg_kw = config.get('negative_keywords', [])
    roles = config.get('roles', [])

    must_have = kw.get('must_have', [])
    nice_to_have = kw.get('nice_to_have', [])

    must_hits = extract_matches(text, must_have)
    nice_hits = extract_matches(text, nice_to_have)
    neg_hits = extract_matches(text, neg_kw)
    role_hits = extract_matches(text, roles)

    score = 0
    score += len(must_hits) * weights.get('must_have', 6)
    score += len(nice_hits) * weights.get('nice_to_have', 3)
    score += len(role_hits) * weights.get('role_match', 4)
    score += len(neg_hits) * weights.get('negative', -8)

    matched = must_hits + nice_hits
    return max(score, 0), matched, neg_hits


def pick_template(matched_keywords: list, templates_config: dict) -> str:
    """Auto-select the best template based on matched keywords."""
    rules = templates_config.get('template_rules', [])
    matched_lower = [k.lower() for k in matched_keywords]
    for rule in rules:
        for kw in rule.get('keywords', []):
            if kw.lower() in matched_lower:
                return rule['template']
    return 'default'


def build_draft(text: str, matched_keywords: list, profile: dict, templates_config: dict) -> str:
    """Build a proposal/DM draft using template substitution."""
    template_name = pick_template(matched_keywords, templates_config)
    templates = templates_config.get('templates', {})
    template = templates.get(template_name, templates.get('default', ''))

    info = profile.get('your_info', {})
    role_hint = matched_keywords[0] if matched_keywords else 'backend development'

    draft = template.format(
        name=info.get('name', 'Your Name'),
        skills=info.get('skills', ''),
        portfolio=info.get('portfolio', ''),
        timezone=info.get('timezone', 'UTC'),
        availability=info.get('availability', 'immediately'),
        rate_note=info.get('rate_note', ''),
        matched_keywords=', '.join(matched_keywords[:6]) if matched_keywords else 'your stack',
        role_hint=role_hint,
    )
    return draft.strip()


if __name__ == '__main__':
    # Quick test
    sample = """
    Looking for a Python backend developer with FastAPI experience.
    Should know Telegram bots and have some LLM/RAG background.
    Docker and PostgreSQL required. TON experience a plus.
    Junior to mid-level, 2 years experience fine.
    """
    score, matched, negs = score_message(sample)
    print(f"Score: {score}")
    print(f"Matched: {matched}")
    print(f"Negative hits: {negs}")
