"""Feature extraction shape and classifier reproducibility."""

import numpy as np

from commission.classify import FEATURE_NAMES, train_classifier
from commission.episode import run_episode
from shadebus.faults import FAULT_KINDS


def small_dataset(seeds):
    X, y = [], []
    for kind in FAULT_KINDS:
        for seed in seeds:
            ep = run_episode(n_nodes=16, seed=seed, kind=kind, probes=5)
            X.append(ep["features"])
            y.append(ep["label"])
    return np.array(X), np.array(y)


def test_feature_vector_matches_names():
    ep = run_episode(n_nodes=16, seed=0, kind="no_fault", probes=4)
    assert len(ep["features"]) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in ep["features"])


def test_classifier_reproducible_under_seed():
    X, y = small_dataset(range(6))
    preds1 = train_classifier(X, y, seed=3).predict(X)
    preds2 = train_classifier(X, y, seed=3).predict(X)
    assert list(preds1) == list(preds2)


def test_classifier_fits_training_data_reasonably():
    X, y = small_dataset(range(8))
    model = train_classifier(X, y, seed=0)
    acc = (model.predict(X) == y).mean()
    assert acc > 0.85


def test_classifier_generalizes_to_held_out_seeds():
    X_train, y_train = small_dataset(range(8))
    X_test, y_test = small_dataset(range(100, 104))
    model = train_classifier(X_train, y_train, seed=0)
    acc = (model.predict(X_test) == y_test).mean()
    assert acc > 0.6
