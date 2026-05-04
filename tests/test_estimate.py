from doc_preprocessor.estimate import TokenEstimator


def test_estimate_ceil_len_div_4():
    assert TokenEstimator.estimate("") == 0
    assert TokenEstimator.estimate("a") == 1
    assert TokenEstimator.estimate("abcd") == 1
    assert TokenEstimator.estimate("abcde") == 2
