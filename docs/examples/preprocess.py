from fold.loop import train_evaluate
from fold.splitters import ExpandingWindowSplitter
from fold.transformations.difference import Difference
from fold.transformations.lags import AddLagsX, AddLagsY
from fold.transformations.window import AddWindowFeatures
from fold.utils.dataset import get_preprocessed_dataset

X, y = get_preprocessed_dataset(
    "weather/historical_hourly_la",
    target_col="temperature",
)

splitter = ExpandingWindowSplitter(initial_train_window=0.2, step=0.1)
pipeline = [
    Difference(),
    AddWindowFeatures([("temperature", 14, "mean")]),
    AddLagsX(columns_and_lags=[("temperature", list(range(1, 5)))]),
    AddLagsY([1, 2]),
]


scorecard, prediction, trained_pipelines = train_evaluate(pipeline, X, y, splitter)
