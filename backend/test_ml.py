from linear_model import FEATURE_NAMES, LinearModel


def test_shapley_contributions_sum_to_prediction_minus_baseline():
    model = LinearModel()
    rows = [
        {name: float(i + j) for j, name in enumerate(FEATURE_NAMES)}
        for i in range(20)
    ]
    targets = [sum(row.values()) for row in rows]
    model.fit(rows, targets)

    sample = rows[5]
    prediction = model.predict(sample)
    contributions = model.shap_contributions(sample)

    assert abs(sum(contributions.values()) - (prediction - model.baseline_prediction)) < 1e-6


def test_recovers_known_linear_relationship():
    model = LinearModel()
    rows = [{name: float((i * 7 + idx) % 11) for idx, name in enumerate(FEATURE_NAMES)} for i in range(50)]
    targets = [2 * row["avg_monthly_inflow"] + 3 * row["cheque_bounce_rate"] + 10 for row in rows]
    model.fit(rows, targets)

    assert abs(model.weights["avg_monthly_inflow"] - 2) < 1e-6
    assert abs(model.weights["cheque_bounce_rate"] - 3) < 1e-6
    assert abs(model.intercept - 10) < 1e-6


def test_explain_returns_pd_estimate_for_sample_profile():
    from ml import explain, model_status
    from feature_bridge import UNIVERSAL_FEATURES
    from sample_data import SAMPLE_PROFILES
    from scoring import score_liquidity, score_discipline, score_momentum, score_leverage, score_digital_footprint

    profile = SAMPLE_PROFILES["ntc_hero"]
    pillars = {
        "liquidity": score_liquidity(profile),
        "discipline": score_discipline(profile),
        "momentum": score_momentum(profile),
        "leverage": score_leverage(profile),
        "digital_footprint": score_digital_footprint(profile),
    }

    result = explain(profile, pillars)
    assert 0 <= result["predicted_score"] <= 100
    assert 0 <= result["pd_estimate"] <= 1
    assert len(result["top_reasons"]) == len(UNIVERSAL_FEATURES)
    assert result["provider"] == model_status()["active_provider"]


def test_model_status_reports_active_provider_contract():
    from ml import model_status

    status = model_status()
    assert status["active_provider"] in {
        "logistic_pd_v1",
        "linear_synthetic_fallback",
        "xgboost",
        "lightgbm",
    }
    assert "explainability" in status
    assert status["fallback"] is None, "committed PD artifact should be loaded by default"
