import numpy as np
import pandas as pd
from scripts.forecast_benchmark import features, fit_predict


def test_price_features_cannot_see_the_forecast_day_or_future():
    y = np.arange(24*14, dtype=float)
    times = pd.Series(pd.date_range("2019-04-01", periods=len(y), freq="h", tz="UTC"))
    original = features(y, times)
    changed = y.copy()
    changed[240:] = -10000
    altered = features(changed, times)
    np.testing.assert_array_equal(original[240-168:264-168], altered[240-168:264-168])


def test_ridge_scaling_and_weights_do_not_fit_test_rows():
    rng = np.random.default_rng(13)
    x, y = rng.normal(size=(200, 3)), rng.normal(size=200)
    original = fit_predict(x, y, 100, 1)
    x[100:] *= 1000
    y[100:] = 10000
    changed = fit_predict(x, y, 100, 1)
    np.testing.assert_array_equal(original[:100], changed[:100])
