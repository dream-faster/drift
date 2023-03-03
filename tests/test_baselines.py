from drift.loop import backtest, train
from drift.models.baseline import BaselineNaiveSeasonal
from drift.splitters import ExpandingWindowSplitter
from drift.transformations.columns import OnlyPredictions
from drift.utils.tests import generate_sine_wave_data


def test_baseline_naive_seasonal() -> None:

    X = generate_sine_wave_data(1000)
    y = X.squeeze()

    splitter = ExpandingWindowSplitter(train_window_size=400, step=400)
    transformations = [
        BaselineNaiveSeasonal(seasonal_length=10),
        OnlyPredictions(),
    ]
    transformations_over_time = train(transformations, X, y, splitter)
    _, pred = backtest(transformations_over_time, X, y, splitter)
    assert (pred.squeeze() == y.shift(10)[pred.index]).all()