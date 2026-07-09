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


def test_explain_returns_reasons_for_sample_profile():
    from ml import explain, model_status
    from sample_data import SAMPLE_PROFILES

    result = explain(SAMPLE_PROFILES["ntc_hero"])
    assert 0 <= result["predicted_score"] <= 100
    assert len(result["top_reasons"]) == 4
    assert len(result["shap_contributions"]) == len(FEATURE_NAMES)
    assert result["provider"] == model_status()["active_provider"]


def test_model_status_reports_active_fallback_contract():
    from ml import model_status

    status = model_status()
    assert status["active_provider"] in {"linear", "xgboost", "lightgbm"}
    assert status["records"] > 0
    assert "explainability" in status
