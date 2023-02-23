from drift.loop import backtest, train
from drift.models.random import RandomClassifier
from drift.splitters import ExpandingWindowSplitter
from drift.transformations.columns import OnlyPredictions
from drift.utils.tests import generate_all_zeros


def test_random_classifier() -> None:

    X = generate_all_zeros(1000)
    y = X.squeeze()

    splitter = ExpandingWindowSplitter(train_window_size=400, step=400)
    transformations = [RandomClassifier(all_classes=[0, 1]), OnlyPredictions()]
    transformations_over_time = train(transformations, X, y, splitter)
    _, pred = backtest(transformations_over_time, X, y, splitter)
    assert pred.squeeze().sum() > 1