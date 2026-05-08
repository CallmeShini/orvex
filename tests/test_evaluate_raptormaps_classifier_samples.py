from scripts.evaluate_raptormaps_classifier_samples import summarize_evaluation_rows


def test_summarize_evaluation_rows_counts_exact_anomaly_and_confidence() -> None:
    rows = [
        {
            "source_label": "No-Anomaly",
            "predicted_label": "No-Anomaly",
            "exact_match": True,
            "anomaly_binary_match": True,
            "confident": True,
        },
        {
            "source_label": "Hot-Spot",
            "predicted_label": "Offline-Module",
            "exact_match": False,
            "anomaly_binary_match": True,
            "confident": False,
        },
        {
            "source_label": "Soiling",
            "predicted_label": "No-Anomaly",
            "exact_match": False,
            "anomaly_binary_match": False,
            "confident": False,
        },
    ]

    summary = summarize_evaluation_rows(rows)

    assert summary["total"] == 3
    assert summary["exact_matches"] == 1
    assert summary["exact_accuracy"] == 0.333333
    assert summary["anomaly_binary_matches"] == 2
    assert summary["anomaly_binary_accuracy"] == 0.666667
    assert summary["confident_predictions"] == 1
    assert summary["predicted_label_distribution"] == {
        "No-Anomaly": 2,
        "Offline-Module": 1,
    }
