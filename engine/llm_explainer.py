"""
LLM explanation layer.

Takes the raw, machine-oriented reasons a flagged transaction triggered
(e.g. "2195km from last transaction ... implies 170678028 km/h travel")
and asks Claude to turn them into one short sentence a non-technical
fraud reviewer could read and immediately understand.

This layer only runs on transactions that are ALREADY flagged by the
rules/ML layers — it doesn't detect anything itself, it explains what
was already detected. If it fails for any reason (no API key, network
hiccup, timeout), we fall back to the raw reasons so a demo never
breaks because of this layer.
"""

import os
import logging
import time
from dotenv import load_dotenv

from openai import OpenAI
load_dotenv()
# ---------------------------------------------------------------------------
# Logger setup — output goes to uvicorn's stdout so it appears in the
# same terminal as the rest of the engine logs.
# ---------------------------------------------------------------------------
logger = logging.getLogger("llm_explainer")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(name)s] %(levelname)s — %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(_handler)

# ---------------------------------------------------------------------------
# OpenAI client init
# ---------------------------------------------------------------------------
MODEL = "gpt-4o-mini"

client = None
_api_key = os.environ.get("OPENAI_API_KEY")
if _api_key:
    client = OpenAI()
   # logger.info("OpenAI client initialised (model=%s, key=...%s)", MODEL, _api_key[-4:])
else:
    logger.warning("OPENAI_API_KEY not set — LLM explanations disabled, will use fallback")

SYSTEM_PROMPT = (
    "You are an expert Fraud Analyst. You write a short fraud alert explanations for a bank's live "
    "monitoring dashboard. Given the specific facts of a flagged transaction, "
    "write ONE short, plain-English sentence (max ~25 words) a non-technical "
    "reviewer can read in under 3 seconds and immediately understand why it "
    "was flagged. Be concrete and specific to the facts given — mention the "
    "actual cities, amounts, or numbers involved. No preamble, no quotes, "
    "just the sentence."
)


def _fallback_explanation(reasons: list[str]) -> str:
    """Used if the LLM call fails or no API key is configured."""
    return " · ".join(reasons)


async def explain_flag(user_id: str, amount: float, merchant: str, reasons: list[str]) -> str:
    logger.debug(
        "explain_flag called | user=%s  amount=%.2f  merchant=%s  reasons=%s",
        user_id, amount, merchant, reasons,
    )

    if client is None:
        logger.debug("Skipping LLM call — client is None (no API key)")
        return _fallback_explanation(reasons)

    if not reasons:
        logger.debug("Skipping LLM call — reasons list is empty")
        return _fallback_explanation(reasons)

    facts = "\n".join(f"- {r}" for r in reasons)
    user_prompt = (
        f"User: {user_id}\n"
        f"Transaction amount: {amount}\n"
        f"Merchant: {merchant}\n"
        f"Triggered fraud signals:\n{facts}"
    )

    #logger.info("Sending request to OpenAI (model=%s) for user=%s", MODEL, user_id)
    t0 = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=80,
            messages=[{"role": "user", "content": SYSTEM_PROMPT + "\n" + user_prompt}],
        )
        elapsed = time.perf_counter() - t0
        text = response.choices[0].message.content
        logger.info(
            "OpenAI response received in %.2fs | user=%s | explanation=%r",
            elapsed, user_id, text,
        )
        return text or _fallback_explanation(reasons)

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(
            "OpenAI call failed after %.2fs | user=%s | error=%s: %s",
            elapsed, user_id, type(e).__name__, e,
        )
        logger.debug("Falling back to raw reasons: %s", reasons)
        return _fallback_explanation(reasons)
