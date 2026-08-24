"""Labeled fault episode evaluation: ML classifier vs rule baseline.

Generates seeded labeled episodes across all fault kinds, splits them
into train and test with no seed overlap between classes, trains the
decision tree on the train split, and scores both the classifier and the
rule baseline on the same held out test split. Writes results/eval.json
and results/confusion_matrix.json.

Usage:
    .venv/bin/python eval/run_eval.py --per-class 50 --seed 7
"""

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split

from commission.classify import FEATURE_NAMES, train_classifier
from commission.episode import run_episode
from shadebus.faults import FAULT_KINDS

NODE_CHOICES = [24, 32, 40, 48]


def generate_episodes(per_class, probes, seed):
    rng = random.Random("eval:%d" % seed)
    episodes = []
    for kind in FAULT_KINDS:
        for i in range(per_class):
            ep_seed = seed * 100000 + i
            n_nodes = rng.choice(NODE_CHOICES)
            episodes.append(run_episode(n_nodes=n_nodes, seed=ep_seed, kind=kind, probes=probes))
    return episodes


def per_type_metrics(y_true, y_pred):
    prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=FAULT_KINDS, zero_division=0
    )
    return {
        kind: {
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1": round(float(f), 4),
            "support": int(s),
        }
        for kind, p, r, f, s in zip(FAULT_KINDS, prec, rec, f1, support)
    }


def macro(metrics):
    keys = ("precision", "recall", "f1")
    return {k: round(sum(m[k] for m in metrics.values()) / len(metrics), 4) for k in keys}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-class", type=int, default=50)
    parser.add_argument("--probes", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--test-size", type=float, default=0.3)
    parser.add_argument("--out", default="results")
    args = parser.parse_args()

    t0 = time.perf_counter()
    episodes = generate_episodes(args.per_class, args.probes, args.seed)
    gen_time = time.perf_counter() - t0

    X = np.array([ep["features"] for ep in episodes])
    y = np.array([ep["label"] for ep in episodes])
    rule = np.array([ep["rule_kind"] for ep in episodes])

    idx = np.arange(len(episodes))
    train_idx, test_idx = train_test_split(
        idx, test_size=args.test_size, random_state=args.seed, stratify=y
    )

    model = train_classifier(X[train_idx], y[train_idx], seed=args.seed)
    pred_test = model.predict(X[test_idx])

    y_test = y[test_idx]
    rule_test = rule[test_idx]

    clf_metrics = per_type_metrics(y_test, pred_test)
    rule_metrics = per_type_metrics(y_test, rule_test)
    clf_cm = confusion_matrix(y_test, pred_test, labels=FAULT_KINDS)
    rule_cm = confusion_matrix(y_test, rule_test, labels=FAULT_KINDS)

    result = {
        "config": {
            "per_class": args.per_class,
            "episodes_total": len(episodes),
            "probes_per_node": args.probes,
            "seed": args.seed,
            "test_size": args.test_size,
            "node_count_choices": NODE_CHOICES,
            "feature_names": FEATURE_NAMES,
            "model": "DecisionTreeClassifier(max_depth=6)",
        },
        "honesty": {
            "synthetic_bus": True,
            "invented_protocol": True,
            "injected_faults": True,
            "note": "All episodes are simulated and seeded; no real hardware involved.",
        },
        "generation_wall_s": round(gen_time, 2),
        "train_episodes": int(len(train_idx)),
        "test_episodes": int(len(test_idx)),
        "classifier": {
            "per_type": clf_metrics,
            "macro": macro(clf_metrics),
            "accuracy": round(float((pred_test == y_test).mean()), 4),
        },
        "rule_baseline": {
            "per_type": rule_metrics,
            "macro": macro(rule_metrics),
            "accuracy": round(float((rule_test == y_test).mean()), 4),
        },
    }

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "eval.json"), "w") as fh:
        json.dump(result, fh, indent=2)
    with open(os.path.join(args.out, "confusion_matrix.json"), "w") as fh:
        json.dump(
            {
                "labels": FAULT_KINDS,
                "rows_are_true_labels": True,
                "classifier": clf_cm.tolist(),
                "rule_baseline": rule_cm.tolist(),
            },
            fh,
            indent=2,
        )

    print("episodes: %d (train %d / test %d), generated in %.1fs" % (
        len(episodes), len(train_idx), len(test_idx), gen_time))
    print("classifier accuracy: %.4f  macro F1: %.4f" % (
        result["classifier"]["accuracy"], result["classifier"]["macro"]["f1"]))
    print("rule baseline accuracy: %.4f  macro F1: %.4f" % (
        result["rule_baseline"]["accuracy"], result["rule_baseline"]["macro"]["f1"]))
    for kind in FAULT_KINDS:
        c = clf_metrics[kind]
        r = rule_metrics[kind]
        print("  %-20s clf P %.2f R %.2f F1 %.2f | rule P %.2f R %.2f F1 %.2f" % (
            kind, c["precision"], c["recall"], c["f1"],
            r["precision"], r["recall"], r["f1"]))


if __name__ == "__main__":
    main()
