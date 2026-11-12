"""Registered paired, screened additive model (calibration only; requires numpy)."""
import math

import numpy as np

from profile_features import GROUPS, IDS, NAMES

SEED = 194
PENALTIES = (.3, 1., 3., 10., 30., 100.)
SCREEN_T = 3.2


def paired_indices(rows):
    pairs = {}
    for i, r in enumerate(rows):
        if r["source"] not in {"ai", "human"}:
            raise ValueError("source must be ai or human")
        side = pairs.setdefault(r["pair"], {})
        if r["source"] in side:
            raise ValueError("duplicate side in pair")
        side[r["source"]] = i
    if not pairs or any(set(p) != {"ai", "human"} for p in pairs.values()):
        raise ValueError("each pair needs exactly one AI and one human page")
    return np.array([[p["ai"], p["human"]] for _, p in sorted(pairs.items())])


def arrays(rows):
    paired_indices(rows)
    return (np.array([[r["features"][fid]["value"] if r["features"][fid]["value"] is not None else np.nan
                       for fid in IDS] for r in rows], float),
            np.array([int(r["source"] == "ai") for r in rows]))


def auc(scores, y):
    scores, y = np.asarray(scores), np.asarray(y)
    if not np.isfinite(scores).all() or not 0 < y.sum() < len(y):
        raise ValueError("AUC needs finite scores and both classes")
    _, inv, count = np.unique(scores, return_inverse=True, return_counts=True)
    ranks = (np.cumsum(count) - (count - 1) / 2)[inv]
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def pair_bootstrap(rows, scores, other=None, repeats=2000, seed=SEED):
    """The same sampled pairs supply both instruments and both sides."""
    ix = paired_indices(rows)
    y = np.array([int(r["source"] == "ai") for r in rows])
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repeats):
        take = ix[rng.integers(len(ix), size=len(ix))].ravel()
        value = auc(np.asarray(scores)[take], y[take])
        if other is not None:
            value -= auc(np.asarray(other)[take], y[take])
        values.append(value)
    return [float(v) for v in np.percentile(values, [2.5, 97.5])]


def preprocessing(rows):
    X, y = arrays(rows)
    human = []
    for j in range(len(IDS)):
        vals = X[y == 0, j]
        human.append(float(np.mean(vals[np.isfinite(vals)])) if np.isfinite(vals).any() else 0.)
    human = np.array(human)
    X = np.where(np.isfinite(X), X, human)
    mean, sd = X.mean(0), X.std(0)
    sd = np.where(sd > 1e-12, sd, 1.)
    return (X - mean) / sd, y, human, mean, sd


def standardized(rows, model):
    X, _ = arrays(rows)
    X = np.where(np.isfinite(X), X, model["human_mean"])
    return (X - model["mean"]) / model["sd"]


def matvec(matrix, vector):
    return np.einsum("ij,j->i", matrix, vector)


def ridge(Z, y, penalty):
    X = np.column_stack([np.ones(len(y)), Z])
    w = np.zeros(X.shape[1])
    P = np.eye(X.shape[1]) * penalty
    P[0, 0] = 0
    for _ in range(100):
        s = np.clip(matvec(X, w), -35, 35)
        p = 1 / (1 + np.exp(-s))
        gradient = matvec(X.T, p - y) + matvec(P, w)
        hessian = np.einsum("ni,n,nj->ij", X, p * (1 - p), X) + P
        step = np.linalg.solve(hessian, gradient)
        w -= step
        if abs(step).max() < 1e-8:
            return w
    raise ValueError("ridge did not converge")


def fit_fixed(rows, penalty, columns=None, unconstrained=False):
    Z, y, human, mean, sd = preprocessing(rows)
    ix = paired_indices(rows)
    d = Z[ix[:, 0]] - Z[ix[:, 1]]
    spread = d.std(0, ddof=1) / math.sqrt(len(ix))
    t = np.divide(d.mean(0), spread, out=np.zeros(len(IDS)), where=spread > 1e-12)
    t[(spread <= 1e-12) & (abs(d.mean(0)) > 1e-12)] = np.sign(d.mean(0)[(spread <= 1e-12) & (abs(d.mean(0)) > 1e-12)]) * 1e12
    sparse = np.array([sum((r["features"][fid]["k"] or 0) != 0 for r in rows) < 10 for fid in IDS])
    allowed = IDS if columns is None else columns
    active = [j for j, fid in enumerate(IDS) if fid in allowed and not sparse[j]
              and (unconstrained or abs(t[j]) >= SCREEN_T)]
    while active:
        w = ridge(Z[:, active], y, penalty)
        oriented = w[1:] * np.sign(t[active])
        if unconstrained or min(oriented) >= -1e-10:
            break
        active.pop(int(np.argmin(oriented)))
    weights = np.zeros(len(IDS))
    if active:
        weights[active] = w[1:]
        intercept = float(w[0])
    else:
        intercept = 0.
    return {"weights": weights.tolist(), "intercept": intercept, "human_mean": human.tolist(),
            "mean": mean.tolist(), "sd": sd.tolist(), "penalty": penalty,
            "active": [IDS[j] for j in active], "screen_t": t.tolist(),
            "sparse": [fid for fid, drop in zip(IDS, sparse) if drop]}


def scores(rows, model):
    return model["intercept"] + matvec(standardized(rows, model), model["weights"])


def fit(rows, columns=None, unconstrained=False):
    ix = paired_indices(rows)
    if len(ix) < 5:
        raise ValueError("five-fold fitting requires at least five dev pairs")
    order = np.random.default_rng(SEED).permutation(len(ix))
    folds = [ix[order[k::5]].ravel() for k in range(5)]
    y = np.array([int(r["source"] == "ai") for r in rows])
    candidates = []
    for penalty in PENALTIES:
        oof = np.empty(len(rows))
        for val in folds:
            take = set(val.tolist())
            train = [r for i, r in enumerate(rows) if i not in take]
            model = fit_fixed(train, penalty, columns, unconstrained)
            oof[val] = scores([rows[i] for i in val], model)
        loss = float(np.mean(np.logaddexp(0, oof) - y * oof))
        candidates.append((loss, penalty, oof))
    _, penalty, oof = min(candidates, key=lambda c: (c[0], c[1]))
    model = fit_fixed(rows, penalty, columns, unconstrained)
    model.update(flag_line=float(np.quantile(oof[y == 0], .9)), oof=oof.tolist(),
                 oof_auc=auc(oof, y), cv_logloss={str(p): loss for loss, p, _ in candidates})
    return model


def best_single(rows, columns=None):
    X, y, human, mean, sd = preprocessing(rows)
    choices = []
    for j, fid in enumerate(IDS):
        if columns is not None and fid not in columns:
            continue
        a = auc(X[:, j], y)
        sign = 1 if a >= .5 else -1
        choices.append((max(a, 1 - a), -j, sign))
    if not choices:
        return None
    a, negj, sign = max(choices)
    j = -negj
    weights = [0.] * len(IDS); weights[j] = float(sign)
    s = X[:, j] * sign
    return {"feature": IDS[j], "active": [IDS[j]], "dev_auc": a, "weights": weights, "intercept": 0.,
            "human_mean": human.tolist(), "mean": mean.tolist(), "sd": sd.tolist(),
            "flag_line": float(np.quantile(s[y == 0], .9))}


def weak_features(rows):
    out = []
    for fid in IDS:
        means = {}
        for side in ("ai", "human"):
            vals = [(r["features"][fid].get("observed") if fid == "F26" else r["features"][fid]["rate"])
                    for r in rows if r["source"] == side]
            vals = [v for v in vals if v is not None]
            means[side] = np.mean(vals) if vals else 0
        if means["human"] and .5 < means["ai"] / means["human"] < 2.:
            out.append(fid)
    return out


def fit_all(dev):
    weak = weak_features(dev)
    models = {"profile": fit(dev), "B1": best_single(dev), "B2": best_single(dev, ["F1"]),
              "B3": fit(dev, IDS[15:25]), "B5": fit(dev, IDS[:15] + ["F26"]),
              "unconstrained": fit(dev, unconstrained=True), "weak": fit(dev, weak),
              "best_weak": best_single(dev, weak)}
    medians = {fid: {side: (float(np.median(vals)) if (vals := [r["features"][fid]["rate"] for r in dev
               if r["source"] == side and r["features"][fid]["rate"] is not None]) else None)
               for side in ("human", "ai")} for fid in IDS}
    return {"models": models, "weak_features": weak, "medians": medians}


def load_score(rows):
    return np.array([100 * sum(r["features"][fid]["k"] for fid in IDS[:12]) /
                     (12 * r["features"]["F1"]["n"]) for r in rows]) * 12


def evaluate(heldout, fitted, repeats=2000):
    y = np.array([int(r["source"] == "ai") for r in heldout])
    instruments = {name: scores(heldout, model) for name, model in fitted["models"].items() if model is not None}
    instruments["B4"] = load_score(heldout)
    report = {}
    for name, values in instruments.items():
        report[name] = {"auc": auc(values, y), "ci": pair_bootstrap(heldout, values, repeats=repeats),
                        "scores": values.tolist()}
        model = fitted["models"].get(name)
        if model:
            report[name]["flag_rates"] = {side: float(np.mean(values[y == label] >= model["flag_line"]))
                                          for side, label in (("ai", 1), ("human", 0))}
    delta = pair_bootstrap(heldout, instruments["profile"], instruments["B1"], repeats)
    h1 = bool(fitted["models"]["profile"]["active"] and delta[0] > 0)
    h2 = {"tested": h1, "passed": False}
    if h1 and "best_weak" in instruments:
        weak_delta = pair_bootstrap(heldout, instruments["weak"], instruments["best_weak"], repeats)
        h2.update(delta_ci=weak_delta, passed=bool(fitted["models"]["weak"]["active"] and
                  report["weak"]["ci"][0] > .5 and weak_delta[0] > 0))
    return {"H1": {"passed": h1, "delta_ci": delta}, "H2": h2,
            "qualifies": bool(h1 and report["profile"]["ci"][0] >= .70), "instruments": report}


def diagnostics(dev, heldout, fitted, weight_repeats=1000, permutations=50):
    """Predeclared descriptions, never model selection or promotion gates."""
    model = fitted["models"]["profile"]
    rng = np.random.default_rng(SEED)
    ix = paired_indices(dev)
    weights, entered = [], []
    for _ in range(weight_repeats):
        sample = []
        for newpair, p in enumerate(rng.integers(len(ix), size=len(ix))):
            sample += [dict(dev[i], pair=str(newpair)) for i in ix[p]]
        refit = fit_fixed(sample, model["penalty"])
        weights.append(refit["weights"])
        entered.append([abs(t) >= SCREEN_T and fid not in refit["sparse"] for fid, t in zip(IDS, refit["screen_t"])])
    weight_ci = np.percentile(weights, [2.5, 97.5], axis=0).T.tolist()
    y = np.array([int(r["source"] == "ai") for r in heldout])
    Z = standardized(heldout, model)
    base = auc(scores(heldout, model), y)
    groups = {**{fid: [fid] for fid in IDS}, **GROUPS}
    importance = {}
    for name, members in groups.items():
        columns = [IDS.index(fid) for fid in members]
        drops = []
        for _ in range(permutations):
            shuffled = Z.copy()
            shuffled[:, columns] = Z[rng.permutation(len(Z))][:, columns]
            drops.append(base - auc(model["intercept"] + matvec(shuffled, model["weights"]), y))
        minus = fit(dev, [fid for fid in IDS if fid not in members])
        importance[name] = {"permutation_auc_drop": float(np.mean(drops)),
                            "dev_drop_auc": model["oof_auc"] - minus["oof_auc"]}
    by_genre, left_out = {}, {}
    for genre in sorted({r["genre"] for r in heldout}):
        rows = [r for r in heldout if r["genre"] == genre]
        s = scores(rows, model)
        by_genre[genre] = {"auc": auc(s, np.array([r["source"] == "ai" for r in rows])),
                           "ci": pair_bootstrap(rows, s)}
    for origin in sorted({r["origin"] for r in heldout}):
        test = [r for r in heldout if r["origin"] == origin]
        train = [r for r in dev if r["origin"] != origin]
        if len(paired_indices(test)) >= 30 and len(train) >= 10:
            refit = fit(train)
            s = scores(test, refit)
            left_out[origin] = {"auc": auc(s, np.array([r["source"] == "ai" for r in test])),
                                "ci": pair_bootstrap(test, s)}
    # Holm tests use paired sign-flip randomisation; bootstrap intervals describe magnitudes
    X, _ = arrays(heldout)
    X = np.where(np.isfinite(X), X, model["human_mean"])
    hx = paired_indices(heldout)
    differences = X[hx[:, 0]] - X[hx[:, 1]]
    signs = rng.choice([-1, 1], size=(10000, len(hx)))
    null = abs(np.einsum("bn,nj->bj", signs, differences) / len(hx))
    pvals = (1 + (null >= abs(differences.mean(0))).sum(0)) / 10001
    adjusted, running = {}, 0.
    for rank, j in enumerate(np.argsort(pvals)):
        running = max(running, min(1., float(pvals[j] * (26 - rank))))
        adjusted[IDS[j]] = running
    draws = np.array([differences[rng.integers(len(hx), size=len(hx))].mean(0) for _ in range(2000)])
    signals = {fid: {"difference": float(differences[:, j].mean()),
                     "ci": np.percentile(draws[:, j], [2.5, 97.5]).tolist(),
                     "holm_p": adjusted[fid], "different": adjusted[fid] < .05} for j, fid in enumerate(IDS)}
    return {"weight_ci": dict(zip(IDS, weight_ci)), "screening_frequency": dict(zip(IDS, np.mean(entered, axis=0).tolist())),
            "importance": importance, "by_genre": by_genre, "leave_one_source_out": left_out,
            "signals": signals, "signal_count": sum(v["different"] for v in signals.values())}
