"""Multi-scenario scoring with weighted decision matrix.

Normalizes metrics across scenarios and produces a weighted composite
score for ranking design alternatives.
"""
from __future__ import annotations


# Metrics where lower values are better
LOWER_IS_BETTER = {"npc", "lcoe", "payback_years", "co2_emissions_kg"}
# Metrics where higher values are better
HIGHER_IS_BETTER = {"irr", "renewable_fraction"}


def normalize_metrics(
    scenarios: list[dict],
    metric_keys: list[str] | None = None,
) -> list[dict]:
    """Min-max normalize metrics across scenarios to 0-1 range.

    For lower-is-better metrics, the best (lowest) value gets 1.0.
    For higher-is-better metrics, the best (highest) value gets 1.0.

    Parameters
    ----------
    scenarios : list[dict]
        Each dict must have the metric keys with numeric values.
    metric_keys : list[str] or None
        Metrics to normalize. Defaults to all known metrics.

    Returns
    -------
    list[dict]
        Same structure with normalized values (0-1).
    """
    if not scenarios:
        return []

    if metric_keys is None:
        metric_keys = list(LOWER_IS_BETTER | HIGHER_IS_BETTER)

    normalized = []
    for s in scenarios:
        entry = {k: v for k, v in s.items() if k not in metric_keys}
        normalized.append(entry)

    for key in metric_keys:
        values = []
        for s in scenarios:
            v = s.get(key)
            if v is not None and v != float("inf"):
                values.append(float(v))
            else:
                values.append(None)

        valid = [v for v in values if v is not None]
        if not valid or len(valid) < 1:
            for i in range(len(scenarios)):
                normalized[i][key] = 0.0
            continue

        min_v = min(valid)
        max_v = max(valid)
        span = max_v - min_v

        for i, v in enumerate(values):
            if v is None:
                normalized[i][key] = 0.0
            elif span == 0:
                normalized[i][key] = 1.0  # All same value
            elif key in LOWER_IS_BETTER:
                # Lower is better: best (min) → 1.0, worst (max) → 0.0
                normalized[i][key] = 1.0 - (v - min_v) / span
            else:
                # Higher is better: best (max) → 1.0, worst (min) → 0.0
                normalized[i][key] = (v - min_v) / span

    return normalized


def score_scenarios(
    scenarios: list[dict],
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """Score and rank scenarios using weighted decision matrix.

    Parameters
    ----------
    scenarios : list[dict]
        Each dict must have metric keys with numeric values plus
        'simulation_id' and optionally 'simulation_name'.
    weights : dict[str, float] or None
        Weight for each metric (will be normalized to sum to 1.0).
        Defaults to equal weights.

    Returns
    -------
    list[dict]
        Sorted by composite score (descending). Each dict includes
        'score', 'rank', and 'normalized' sub-dict.
    """
    if not scenarios:
        return []

    all_metrics = list(LOWER_IS_BETTER | HIGHER_IS_BETTER)
    available = [m for m in all_metrics if any(s.get(m) is not None for s in scenarios)]

    if weights is None:
        weights = {m: 1.0 for m in available}

    # Normalize weights to sum to 1
    total_w = sum(weights.get(m, 0) for m in available)
    if total_w <= 0:
        total_w = 1.0
    norm_weights = {m: weights.get(m, 0) / total_w for m in available}

    # Normalize metrics
    normalized = normalize_metrics(scenarios, available)

    # Compute composite score
    scored = []
    for i, (orig, norm) in enumerate(zip(scenarios, normalized)):
        composite = sum(
            norm.get(m, 0) * norm_weights.get(m, 0)
            for m in available
        )
        scored.append({
            "simulation_id": orig.get("simulation_id", ""),
            "simulation_name": orig.get("simulation_name", f"Scenario {i+1}"),
            "score": round(composite, 4),
            "normalized": {m: round(norm.get(m, 0), 4) for m in available},
            "raw": {m: orig.get(m) for m in available},
        })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Add rank
    for i, s in enumerate(scored):
        s["rank"] = i + 1

    return scored
