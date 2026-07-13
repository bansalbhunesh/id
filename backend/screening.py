"""Negative-registry screening -- advisory surface, decision path untouched.

Public negative registries (MCA strike-off CINs, SEBI debarred entities, the
RBI alert list, GST non-genuine-taxpayer lists) are a real fraud signal that
alternate-data scoring alone cannot see. This module ships the *governed
shape* of that pillar: a registry schema, an advisory check endpoint, and the
routing policy a bank would actually accept -- an exact-ID hit can only force
human review (never an automated decline across domains, consistent with
apply_decision_policy), and a name-only hit is advisory because common names
collide.

Every row shipped in this repository is a clearly-labelled SAMPLE
(`is_sample: true`, reserved test identifiers): the registries' terms don't
allow vendoring their data here, so honest fixtures beat quietly scraped
rows. Loading the real public lists is a documented deployment step, not a
code change -- replace SAMPLE_REGISTRY with the downloaded rows and the
policy below applies unchanged. Wiring hits into the live decision path is
deliberately a prototype-phase item; on this deployment the check is a view.
"""

# Reserved/test identifiers only -- these match no real business.
SAMPLE_REGISTRY = [
    {
        "list_name": "MCA strike-off (sample row)",
        "id_type": "cin",
        "id_value": "U00000MH2020PTC000000",
        "source": "data.gov.in MCA struck-off companies dataset",
        "as_of": "2026-07-13",
        "is_sample": True,
    },
    {
        "list_name": "SEBI debarred entities (sample row)",
        "id_type": "pan",
        "id_value": "ZZZPZ0000Z",
        "source": "sebi.gov.in debarred entities list",
        "as_of": "2026-07-13",
        "is_sample": True,
    },
    {
        "list_name": "GST non-genuine taxpayer (sample row)",
        "id_type": "gstin",
        "id_value": "27ZZZZZ0000Z9Z9",
        "source": "state GST non-genuine taxpayer publications",
        "as_of": "2026-07-13",
        "is_sample": True,
    },
    {
        "list_name": "RBI alert list (sample row)",
        "id_type": "name",
        "id_value": "Sample Flagged Entity Pvt Ltd",
        "source": "rbi.org.in alert list",
        "as_of": "2026-07-13",
        "is_sample": True,
    },
]

_EXACT_ID_TYPES = {"gstin", "pan", "cin"}


def screen(name: str, gstin: str | None = None, pan: str | None = None,
           cin: str | None = None) -> dict:
    """Advisory screening verdict for one applicant.

    exact_id_hit  -> routing_advice "mandatory_human_review" (hard flag; the
                     policy engine never auto-declines on a registry alone)
    name_only_hit -> "advisory_manual_disposition" (common-name collisions
                     must not gate credit)
    clear         -> "no_registry_objection"
    """
    supplied = {"gstin": gstin, "pan": pan, "cin": cin}
    hits = []
    for row in SAMPLE_REGISTRY:
        if row["id_type"] in _EXACT_ID_TYPES:
            value = supplied.get(row["id_type"])
            if value and value.strip().upper() == row["id_value"].upper():
                hits.append({**row, "match_kind": "exact_id"})
        elif row["id_type"] == "name" and name:
            if name.strip().lower() == row["id_value"].lower():
                hits.append({**row, "match_kind": "name_only"})
    exact = [h for h in hits if h["match_kind"] == "exact_id"]
    if exact:
        advice = "mandatory_human_review"
        rationale = (
            "Exact registered-identifier match on a negative registry. Policy "
            "forces human review with the hit attached; an automated decline "
            "on registry data alone is deliberately not allowed."
        )
    elif hits:
        advice = "advisory_manual_disposition"
        rationale = (
            "Name-only match. Common names collide, so this is surfaced for "
            "manual disposition and never gates the decision by itself."
        )
    else:
        advice = "no_registry_objection"
        rationale = "No match in the loaded registries."
    return {
        "screened": {"name": name, **{k: v for k, v in supplied.items() if v}},
        "registries_loaded": sorted({row["list_name"] for row in SAMPLE_REGISTRY}),
        "sample_data_only": all(row["is_sample"] for row in SAMPLE_REGISTRY),
        "hits": hits,
        "routing_advice": advice,
        "rationale": rationale,
        "truth_boundary": (
            "All shipped rows are labelled samples with reserved identifiers; "
            "real public lists load at deployment via the documented step. "
            "This endpoint is advisory -- it is not wired into the live "
            "decision path on this deployment."
        ),
    }
