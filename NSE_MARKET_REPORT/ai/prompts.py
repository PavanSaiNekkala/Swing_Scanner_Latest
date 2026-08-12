"""
ai/prompts.py

Prompt templates for AI summarization and remark generation.
"""

from __future__ import annotations

from typing import Any


###############################################################################
# SUMMARY PROMPT
###############################################################################

def build_summary_prompt(
    stock: dict[str, Any],
) -> str:
    """
    Build the AI prompt for generating a concise stock summary.

    Parameters
    ----------
    stock : dict[str, Any]
        Dictionary containing stock information.

    Returns
    -------
    str
        Prompt for the AI model.
    """

    return f"""
You are an experienced Indian stock market analyst.

Analyze the following stock information.

Symbol:
{stock.get("Symbol", "N/A")}

Company:
{stock.get("Company", "N/A")}

Current Market Price (CMP):
{stock.get("CMP", "N/A")}

1 Day Change:
{stock.get("1 Day Change %", "N/A")}

Open:
{stock.get("Open", "N/A")}

High:
{stock.get("High", "N/A")}

Low:
{stock.get("Low", "N/A")}

Previous Close:
{stock.get("Previous Close", "N/A")}

Volume:
{stock.get("Volume", "N/A")}

Top Headline:
{stock.get("Top Headline", "N/A")}

Recent News:
{stock.get("Recent News", "N/A")}

Prepare a concise summary (3–5 sentences) covering:

1. Price movement and market performance.
2. Technical observations based on OHLC data.
3. Impact of the latest news on the stock.
4. Overall market sentiment.

Guidelines:
- Keep the summary factual and objective.
- Do not invent information.
- Do not provide investment advice.
- Keep the response under 120 words.
""".strip()


###############################################################################
# REMARKS PROMPT
###############################################################################

def build_remarks_prompt(
    stock: dict[str, Any],
) -> str:
    """
    Build the AI prompt for generating final market remarks.

    Parameters
    ----------
    stock : dict[str, Any]
        Stock information.

    Returns
    -------
    str
        Prompt for AI.
    """

    return f"""
You are an experienced Indian stock market analyst.

Analyze the following stock.

Symbol:
{stock.get("Symbol", "N/A")}

Company:
{stock.get("Company", "N/A")}

CMP:
{stock.get("CMP", "N/A")}

1 Day Change:
{stock.get("1 Day Change %", "N/A")}

Open:
{stock.get("Open", "N/A")}

High:
{stock.get("High", "N/A")}

Low:
{stock.get("Low", "N/A")}

Previous Close:
{stock.get("Previous Close", "N/A")}

Volume:
{stock.get("Volume", "N/A")}

Top Headline:
{stock.get("Top Headline", "N/A")}

Recent News:
{stock.get("Recent News", "N/A")}

AI Summary:
{stock.get("AI Summary", "N/A")}

Generate the following:

1. Overall sentiment (Bullish / Bearish / Neutral)
2. Risk level (Low / Medium / High)
3. Strength score (0-100)
4. Final remarks in 2-4 sentences.

Rules:
- Be objective.
- Do not fabricate facts.
- Do not provide buy/sell recommendations.
- Base your response only on the supplied information.
""".strip()