import copy

import numpy as np
import pytest

import profile_features as pf
import profile_model as pm


def simulated(n=300, seed=194, effects=None, style=.8):
    rng = np.random.default_rng(seed)
    y = np.tile([1, 0], n)
    shared = rng.normal(size=2 * n)
    X = style * shared[:, None] + np.sqrt(1 - style ** 2) * rng.normal(size=(2 * n, 26))
    for j, effect in (effects or {0: 1.}).items():
        X[:, j] += effect * y
    rows = []
    for i, x in enumerate(X):
        features = {fid: {"value": float(v), "rate": float(np.exp(v / 5)), "k": 1., "n": 10., "fired": []}
                    for fid, v in zip(pf.IDS, x)}
        features["F26"]["observed"] = float(np.exp(x[-1] / 5))
        rows.append({"id": str(i), "pair": str(i // 2), "source": "ai" if y[i] else "human", "genre": "G1",
                     "origin": "synthetic", "features": features})
    return rows


def test_null_shared_style_cannot_pass_h1_without_other_rate_differences():
    # Strong shared style once let unscreened models cancel noise with unrelated tells
    for seed in (194, 195, 196):
        dev = simulated(300, seed)
        heldout = simulated(300, seed + 100)
        profile, single = pm.fit(dev), pm.best_single(dev)
        assert profile["active"] == ["F1"]
        fitted = {"models": {"profile": profile, "B1": single}}
        result = pm.evaluate(heldout, fitted, repeats=300)
        assert result["H1"]["passed"] is False
        assert result["H2"]["tested"] is False
        assert result["qualifies"] is False
        assert result["H1"]["delta_ci"] == [0., 0.]


def test_positive_multifeature_control_h1_and_h2():
    effects = {j: (-.8 if j == 20 else .8) for j in range(12)}
    dev, heldout = simulated(300, 40, effects, style=.1), simulated(300, 41, effects, style=.1)
    models = {"profile": pm.fit(dev), "B1": pm.best_single(dev), "weak": pm.fit(dev, pm.weak_features(dev)),
              "best_weak": pm.best_single(dev, pm.weak_features(dev))}
    result = pm.evaluate(heldout, {"models": models}, repeats=300)
    assert result["H1"]["passed"] and result["H2"]["passed"] and result["qualifies"]
    assert result["H1"]["delta_ci"][0] > 0


def test_empty_profile_and_sparse_features_do_not_fallback_to_strongest():
    dev = simulated(20, effects={0: 100})
    for i, row in enumerate(dev):
        row["features"]["F1"]["k"] = int(i < 9)
        for fid in pf.IDS[1:]:
            row["features"][fid]["value"] = 0.
    fit = pm.fit(dev)
    assert "F1" in fit["sparse"] and fit["active"] == []
    assert fit["weights"] == [0.] * 26


def test_direction_measured_on_pairs_and_pair_order_not_row_order():
    rows = simulated(100, effects={0: 1., 1: -1.})
    model = pm.fit_fixed(rows, 1.)
    assert model["weights"][0] > 0 and model["weights"][1] < 0
    rng = np.random.default_rng(3)
    shuffled = [rows[i] for i in rng.permutation(len(rows))]
    other = pm.fit_fixed(shuffled, 1.)
    assert other["weights"] == pytest.approx(model["weights"])
    assert all(w * t >= -1e-8 for w, t in zip(model["weights"], model["screen_t"]))


def test_grouped_cv_preprocessing_and_screening_only_see_training_pairs(monkeypatch):
    dev = simulated(25)
    real = pm.fit_fixed
    calls = []
    def inspect(rows, *args, **kwargs):
        pairs = pm.paired_indices(rows)
        calls.append(len(pairs))
        assert all(len({rows[i]["pair"] for i in pair}) == 1 for pair in pairs)
        return real(rows, *args, **kwargs)
    monkeypatch.setattr(pm, "fit_fixed", inspect)
    model = pm.fit(dev)
    assert calls.count(20) == 30 and calls[-1] == 25
    assert model["flag_line"] == np.quantile(np.array(model["oof"])[1::2], .9)


def test_nonapplicable_imputes_human_transformed_mean_and_weak_set_uses_raw_rates():
    dev = simulated(30)
    for i, row in enumerate(dev):
        row["features"]["F13"]["value"] = None if i % 7 == 0 else row["features"]["F13"]["value"]
        row["features"]["F2"]["rate"] = 1 if row["source"] == "human" else 2
        row["features"]["F3"]["rate"] = 2 if row["source"] == "human" else 1
    model = pm.fit(dev)
    missing = copy.deepcopy(dev)
    for r in missing:
        r["features"]["F13"]["value"] = None
    Z = pm.standardized(missing, model)
    assert np.allclose(Z[:, 12], (model["human_mean"][12] - model["mean"][12]) / model["sd"][12])
    assert "F2" not in pm.weak_features(dev) and "F3" not in pm.weak_features(dev)


def test_auc_ties_and_pair_bootstrap_are_deterministic_and_joint():
    rows = simulated(12)
    y = np.array([int(r["source"] == "ai") for r in rows])
    s = np.array([float(i) for i in range(len(rows))])
    assert pm.auc(np.zeros(len(rows)), y) == .5
    assert pm.pair_bootstrap(rows, s, s) == [0., 0.]
    assert pm.pair_bootstrap(rows, s) == pm.pair_bootstrap(rows, s)
    with pytest.raises(ValueError, match="pair"):
        pm.paired_indices(rows[:-1])
