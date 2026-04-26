# ruff: noqa: E501 — long lines below are inside the SYSTEM_PROMPT, not Python.
"""LLM rerank over the pgvector top-K candidates.

`text-embedding-3-small` is good at lexical / semantic similarity but stumbles
on the ambiguous queries Polymarket users actually highlight: "Powell"
(Federal Reserve / kid's wizard / Adam Powell), "Trump" (election / lawsuit /
Truth Social market). The PRD plans LLM rerank as the v0.2 disambiguator;
this module is that v0.2.

Model: `claude-haiku-4-5`. Rerank is a fast judgment task — Opus would cost
~5× more and add ~1s of latency for negligible quality gain on this workload.
The PRD specifically calls Haiku.

Output: structured (Pydantic) so we can't parse it wrong; `pick` is either
1-based candidate index or null for "no candidate is relevant".
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from app.models import Market

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

log = logging.getLogger(__name__)

RERANK_MODEL = "claude-haiku-4-5"
MAX_CANDIDATES = 10


class Reranker(Protocol):
    async def pick(
        self,
        *,
        highlight: str,
        surrounding_context: str | None,
        page_title: str | None,
        candidates: list[Market],
    ) -> Market | None: ...


class RerankChoice(BaseModel):
    """Structured output schema. `pick` is 1-based to match the prompt's
    numbering; `null` means none of the candidates is a defensible match."""

    pick: int | None = Field(
        description=(
            "1-based index of the candidate that best matches the user's "
            "selection, or null if none of the candidates is a defensible match."
        )
    )
    reasoning: str = Field(
        description="One short sentence explaining the choice (or the rejection)."
    )


SYSTEM_PROMPT = """\
You are the rerank component of Speedy, a macOS app that turns highlighted
text into a Polymarket trade. The user highlights a sentence somewhere they're
reading — a news article, a Slack message, a tweet — and we surface the most
relevant Polymarket prediction market at their cursor.

Your job: given the user's highlight and a short list of candidate markets
ranked by raw embedding similarity, pick the one most relevant to what the
user is *trying to find*, or return null if none of them is a defensible
match.

# What "relevant" means

The candidate market should be one the user could actually trade on the
*topic* they highlighted. Not just topical overlap — *the same question*.

- "Powell signaled patience on rate cuts" + market about *Fed cuts in May* →
  strong match. The highlight is direct evidence about the market's resolution.
- "Powell signaled patience on rate cuts" + market about *Powell being
  replaced as Fed Chair* → poor match, despite both being about Powell. The
  user is reading about rate-cut probability, not Powell's job security.
- "Cybertruck deliveries missed estimates" + market about *Tesla earnings
  beat* → weak match. Adjacent topic, but a different question.
- "Cybertruck deliveries missed estimates" + market about *Cybertruck Q2
  deliveries above 45,000* → strong match.

When the user's highlight is short or ambiguous, use the surrounding context
and page title to disambiguate. "Powell" alone is ambiguous; "Powell signaled
patience on rate cuts" plus a page title of "Reuters — Fed minutes" is not.

# When to return null

Return null when:

- None of the candidates is about the same *question* the user highlighted,
  even if they share keywords.
- The highlight is too generic to map to any specific market ("interest
  rates rose", "the market is volatile", "the company reported earnings").
- The candidates are all about a different time horizon than the highlight
  implies.

It is much better to return null than to pick a weak match. The overlay's
fallback UX ("No tradeable market for this selection") is fine; surfacing a
wrong market trains the user to distrust the tool.

# What I will give you

- The user's highlight (required)
- Surrounding context from the page (optional, may be empty)
- The page title (optional, may be empty)
- Up to 10 candidate markets with question, description, and category

# What I want back

- `pick`: the 1-based index of the best candidate, or null
- `reasoning`: one short sentence — why you picked that one, or why none
  of them clears the bar

Be concise. The reasoning is for debugging, not user display.

# Examples

## Example 1: clear match

Highlight: "The Fed is widely expected to cut by 25bp in May"
Page title: "FT — FOMC preview"
Candidates:
1. Will the Fed cut rates at the May 2026 FOMC meeting?
2. Will Jerome Powell be replaced as Fed Chair before 2027?
3. Will the S&P 500 close above 6000 by year-end?

→ {"pick": 1, "reasoning": "Direct match: highlight is about a May Fed cut, candidate 1 resolves on exactly that."}

## Example 2: ambiguous query disambiguated by context

Highlight: "Powell"
Page title: "Bloomberg — Fed minutes signal patience on cuts"
Candidates:
1. Will Powell be replaced as Fed Chair before 2027?
2. Will the Fed cut rates at the May 2026 FOMC meeting?
3. Will Adam Schiff win the California Senate race?

→ {"pick": 2, "reasoning": "Page title clarifies the highlight is about rate-cut probability, not Powell's job."}

## Example 3: no good match

Highlight: "earnings season has been mixed so far"
Candidates:
1. Will Apple's Q2 EPS exceed $2.00?
2. Will Tesla deliver more than 1.8M vehicles in 2026?
3. Will the Fed cut rates at the May 2026 FOMC meeting?

→ {"pick": null, "reasoning": "Highlight is too generic — talks about earnings broadly, not any specific company."}

## Example 4: keyword overlap, wrong question

Highlight: "Tesla's Cybertruck deliveries missed expectations again"
Candidates:
1. Will Tesla beat Q2 earnings estimates?
2. Will the Cybertruck reach 100,000 cumulative deliveries by year-end?
3. Will Elon Musk remain CEO of Tesla through 2026?

→ {"pick": 2, "reasoning": "Highlight is specifically about Cybertruck deliveries; candidate 2 resolves on that, candidate 1 is broader earnings."}
"""


class HaikuReranker(Reranker):
    """Production reranker using Anthropic's Haiku 4.5 with structured output."""

    def __init__(
        self,
        client: AsyncAnthropic | None = None,
        *,
        model: str = RERANK_MODEL,
    ) -> None:
        self._client = client
        self._model = model

    def _ensure_client(self) -> AsyncAnthropic:
        if self._client is not None:
            return self._client
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(api_key=api_key)
        return self._client

    async def pick(
        self,
        *,
        highlight: str,
        surrounding_context: str | None,
        page_title: str | None,
        candidates: list[Market],
    ) -> Market | None:
        if not candidates:
            return None
        bounded = candidates[:MAX_CANDIDATES]
        client = self._ensure_client()

        try:
            response = await client.messages.parse(
                model=self._model,
                max_tokens=300,
                # Cache the system prompt — it's stable across every rerank
                # call. Haiku 4.5 minimum cacheable prefix is 4096 tokens; the
                # SYSTEM_PROMPT above is sized to clear that bar.
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                output_format=RerankChoice,
                messages=[
                    {
                        "role": "user",
                        "content": _format_user_message(
                            highlight=highlight,
                            surrounding_context=surrounding_context,
                            page_title=page_title,
                            candidates=bounded,
                        ),
                    }
                ],
            )
        except Exception:  # noqa: BLE001 — fail open: degrade to top-1 by score
            log.exception("rerank: Haiku call failed; falling back to top-1")
            return bounded[0]

        choice = response.parsed_output
        log.info(
            "rerank: pick=%s reasoning=%s",
            choice.pick,
            choice.reasoning[:120],
        )
        if choice.pick is None:
            return None
        idx = choice.pick - 1
        if 0 <= idx < len(bounded):
            return bounded[idx]
        # Out-of-range pick — treat as no match rather than guess.
        log.warning(
            "rerank: pick=%d out of range (have %d candidates); returning None",
            choice.pick,
            len(bounded),
        )
        return None


def _format_user_message(
    *,
    highlight: str,
    surrounding_context: str | None,
    page_title: str | None,
    candidates: list[Market],
) -> str:
    parts = [f"Highlight: {highlight.strip()}"]
    if surrounding_context and surrounding_context.strip():
        parts.append(f"Surrounding context: {surrounding_context.strip()}")
    if page_title and page_title.strip():
        parts.append(f"Page title: {page_title.strip()}")
    parts.append("")
    parts.append("Candidates:")
    for i, m in enumerate(candidates, start=1):
        parts.append(f"\n{i}. {m.question}")
        if m.category:
            parts.append(f"   Category: {m.category}")
        if m.description:
            # Truncate descriptions — some Polymarket descriptions are 1000+
            # words of resolution criteria. ~400 chars is plenty for rerank.
            desc = m.description.strip().replace("\n", " ")
            if len(desc) > 400:
                desc = desc[:400] + "…"
            parts.append(f"   Description: {desc}")
    return "\n".join(parts)
