from coderabbit_control.drift import detect_drift


def test_manual_generated_edit_is_reported_as_drift():
    report = detect_drift(
        {".coderabbit.yaml": "expected\n"},
        {".coderabbit.yaml": "edited\n"},
    )
    assert report.has_drift
    assert report.modified == (".coderabbit.yaml",)
    assert report.missing == ()
    assert report.unexpected == ()


def test_drift_report_is_stably_sorted_and_classifies_missing_and_unexpected():
    report = detect_drift(
        {"z": "same", "b": "missing", "a": "old"},
        {"z": "same", "a": "new", "c": "extra"},
    )
    assert report.modified == ("a",)
    assert report.missing == ("b",)
    assert report.unexpected == ("c",)
