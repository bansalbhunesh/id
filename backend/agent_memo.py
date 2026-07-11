"""Generates a plain-language underwriter memo from a score result.

The public demo stays deterministic by default. Stage 2 can set
`UDYAMPULSE_MEMO_PROVIDER=bedrock` plus a Bedrock model ID to generate the
memo with AWS Bedrock Runtime; any SDK, credential, or model failure falls
back to the deterministic memo so underwriting remains available.
"""
from __future__ import annotations

import json
import os
import re


def _deterministic_memo(score_result: dict) -> str:
    name = score_result["name"]
    grade = score_result["grade"]
    limit = score_result["eligible_limit"]
    reasons = score_result["reasons"]
    trad = score_result["traditional"]

    strengths = [r for r in reasons if r.startswith("Strong")]
    watch_items = [r for r in reasons if r.startswith("Watch")]

    lines = [
        f"{name} scores grade {grade} ({score_result['score']}/100) on alternate-data underwriting, "
        f"suggesting an eligible limit of Rs {limit:,.0f}."
    ]

    if trad["decision"] == "Rejected" and score_result["alternate_data_decision"] == "Approved":
        lines.append(
            f"Traditional bureau-only underwriting would decline this applicant ({trad['reason']}), "
            "but alternate data (GST filing consistency, UPI transaction velocity, low cheque-bounce "
            "rate) shows a creditworthy, active business."
        )

    if strengths:
        lines.append("Strengths: " + "; ".join(s.replace("Strong: ", "") for s in strengths) + ".")
    if watch_items:
        lines.append("Watch items: " + "; ".join(w.replace("Watch: ", "") for w in watch_items) + ".")

    return " ".join(lines)


def _memo_prompt(score_result: dict) -> str:
    profile = score_result["profile"]
    reasons = "; ".join(score_result["reasons"][:5]) or "No extreme reason codes"
    attribution = "; ".join(score_result["ml"]["top_reasons"][:4])
    guardrails = "; ".join(
        f"{item['control']}: {item['status']}" for item in score_result["policy_guardrails"]
    )
    return (
        "Write a concise MSME underwriter memo for IDBI Bank. "
        "Use plain language, preserve the decision facts, avoid unsupported claims, "
        "and end with one practical monitoring condition.\n\n"
        f"Borrower: {score_result['name']}\n"
        f"Sector: {profile['sector']}; District: {profile['district']}; "
        f"Vintage: {profile['vintage_months']} months; "
        f"Bureau history: {profile['has_bureau_history']}\n"
        f"Score: {score_result['score']}/100; Grade: {score_result['grade']}; "
        f"Risk band: {score_result['risk_band']}\n"
        f"Traditional decision: {score_result['traditional']['decision']} "
        f"({score_result['traditional']['reason']})\n"
        f"Alternate-data decision: {score_result['alternate_data_decision']}; "
        f"Eligible limit INR: {score_result['eligible_limit']}\n"
        f"Reason codes: {reasons}\n"
        f"Model attribution: {attribution}\n"
        f"Guardrails: {guardrails}\n"
    )


def _bedrock_payload(model_id: str, prompt: str) -> dict:
    if model_id.startswith("anthropic."):
        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 420,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
        }

    return {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 420,
            "temperature": 0.2,
            "topP": 0.9,
        },
    }


def _extract_bedrock_text(body: dict) -> str | None:
    if isinstance(body.get("content"), list) and body["content"]:
        first = body["content"][0]
        if isinstance(first, dict):
            return first.get("text")
    if isinstance(body.get("results"), list) and body["results"]:
        first = body["results"][0]
        if isinstance(first, dict):
            return first.get("outputText")
    return body.get("outputText") or body.get("generation")


def _bedrock_memo(score_result: dict) -> str | None:
    model_id = os.getenv("BEDROCK_MODEL_ID") or os.getenv("AWS_BEDROCK_MODEL_ID")
    if not model_id:
        return None

    try:
        import boto3  # type: ignore

        region = (
            os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("BEDROCK_REGION")
            or "ap-south-1"
        )
        client = boto3.client("bedrock-runtime", region_name=region)
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(_bedrock_payload(model_id, _memo_prompt(score_result))),
            contentType="application/json",
            accept="application/json",
        )
        raw_body = response["body"].read()
        parsed = json.loads(raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body)
        memo = _extract_bedrock_text(parsed)
        return memo.strip() if memo else None
    except Exception:
        return None


def _memo_matches_known_facts(memo: str, score_result: dict) -> bool:
    """Reject a generative memo that states a limit, score, or grade
    inconsistent with what was actually computed.

    A generative memo is drafted from real facts, but the model can still
    round, mis-restate, or invent a number in prose. This is a lightweight
    guard against exactly that, not a full fact-checker: it only rejects a
    clear numeric contradiction on the figures a memo is most likely to
    restate, and lets everything else through. A false negative here just
    means the deterministic fallback is served instead of a good memo, never
    the reverse.
    """
    expected_limit = float(score_result["eligible_limit"])
    expected_score = int(score_result["score"])
    expected_grade = score_result["grade"]

    for raw in re.findall(r"(?:Rs\.?|₹)\s?([\d,]+(?:\.\d+)?)", memo):
        value = float(raw.replace(",", ""))
        if value > 1000 and abs(value - expected_limit) > max(1.0, expected_limit * 0.01):
            return False

    for raw in re.findall(r"\b(\d{1,3})\s*/\s*100\b", memo):
        if int(raw) != expected_score:
            return False

    grade_match = re.search(r"\bgrade\s+([A-E])\b", memo, re.IGNORECASE)
    if grade_match and grade_match.group(1).upper() != expected_grade:
        return False

    return True


def generate_memo(score_result: dict) -> str:
    fallback = _deterministic_memo(score_result)
    if os.getenv("UDYAMPULSE_MEMO_PROVIDER", "").lower() != "bedrock":
        return fallback
    generated = _bedrock_memo(score_result)
    if generated and _memo_matches_known_facts(generated, score_result):
        return generated
    return fallback
