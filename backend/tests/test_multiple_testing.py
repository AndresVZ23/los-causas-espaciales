from backend.app.statistics.multiple_testing import benjamini_hochberg


def test_benjamini_hochberg_adjustment_is_monotonic_in_rank():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
    assert adjusted == [0.04, 0.05333333333333334, 0.05333333333333334, 0.2]


def test_benjamini_hochberg_preserves_missing_values():
    adjusted = benjamini_hochberg([0.01, None, 0.5])
    assert adjusted == [0.02, None, 0.5]
