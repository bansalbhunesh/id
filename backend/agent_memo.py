"""Generates a plain-language underwriter memo from a score result.

The public demo stays deterministic by default. Stage 2 can set
`UDYAMPULSE_MEMO_PROVIDER=bedrock` plus a Bedrock model ID to generate the
memo with AWS Bedrock Runtime; any SDK, credential, or model failure falls
back to the deterministic memo so underwriting remains available.
"""
from __future__ import annotations

import json
import os


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


def generate_memo(score_result: dict) -> str:
    fallback = _deterministic_memo(score_result)
    if os.getenv("UDYAMPULSE_MEMO_PROVIDER", "").lower() != "bedrock":
        return fallback
    return _bedrock_memo(score_result) or fallback
