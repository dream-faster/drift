import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from fold import train_evaluate
from fold.loop import train
from fold.loop.backtesting import backtest
from fold.splitters import ExpandingWindowSplitter
from fold.transformations.lags import AddLagsX, AddLagsY


def test_on_weather_data() -> None:
    df = pd.read_csv("tests/data/weather.csv", index_col=0, parse_dates=True)
    X = df.drop(columns=["temperature"])
    y = df["temperature"]

    splitter = ExpandingWindowSplitter(initial_train_window=0.2, step=0.2)
    pipeline = [
        AddLagsX(columns_and_lags=[("pressure", list(range(1, 3)))]),
        AddLagsY(list(range(1, 10))),
        HistGradientBoostingRegressor(),
    ]

    transformations_over_time = train(pipeline, X, y, splitter)
    backtest(transformations_over_time, X, y, splitter)


def test_train_eval_with_krisi() -> None:
    df = pd.read_csv("tests/data/weather.csv", index_col=0, parse_dates=True)
    X = df.drop(columns=["temperature"])
    y = df["temperature"]

    splitter = ExpandingWindowSplitter(initial_train_window=0.2, step=0.2)
    pipeline = [
        AddLagsX(columns_and_lags=[("pressure", list(range(1, 3)))]),
        AddLagsY(list(range(1, 10))),
        HistGradientBoostingRegressor(),
    ]

    scorecard, pred, trained_transformations_over_time = train_evaluate(
        pipeline, X, y, splitter
    )

    assert len(pred) == len(y)
