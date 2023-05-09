from sklearn.dummy import DummyRegressor as SklearnDummyRegressor
from sklearn.metrics import mean_squared_error

from fold.composites.optimize import OptimizeGridSearch
from fold.composites.select import SelectBest
from fold.loop import train_backtest
from fold.models.dummy import DummyClassifier, DummyRegressor
from fold.models.sklearn import WrapSKLearnRegressor
from fold.splitters import ExpandingWindowSplitter
from fold.transformations import Difference
from fold.utils.tests import generate_monotonous_data


def test_grid_hpo() -> None:
    X, y = generate_monotonous_data(1000)

    splitter = ExpandingWindowSplitter(initial_train_window=400, step=400)
    pipeline = OptimizeGridSearch(
        pipeline=[
            DummyClassifier(
                predicted_value=1.0,
                predicted_probabilities=[1.0, 2.0],
                all_classes=[1, 2, 3],
                params_to_try=dict(
                    predicted_value=[2.0, 3.0],
                    predicted_probabilities=[[5.0, 6.0], [3.0, 4.0]],
                ),
            ),
            DummyRegressor(
                predicted_value=3.0,
                params_to_try=dict(predicted_value=[22.0, 32.0]),
            ),
            Difference(),
        ],
        scorer=mean_squared_error,
    )

    pred, trained_pipelines = train_backtest(pipeline, X, y, splitter)
    assert len(trained_pipelines[0].iloc[0].param_permutations) > 4


def test_gridsearch_sklearn() -> None:
    X, y = generate_monotonous_data(1000)

    splitter = ExpandingWindowSplitter(initial_train_window=400, step=400)
    pipeline = [
        OptimizeGridSearch(
            pipeline=WrapSKLearnRegressor.from_model(
                SklearnDummyRegressor(strategy="constant", constant=1),
                params_to_try=dict(constant=[1, 2]),
            ),
            scorer=mean_squared_error,
            is_scorer_loss=True,
        )
    ]

    pred, _ = train_backtest(pipeline, X, y, splitter)
    assert (pred.squeeze() == 1).all()


def test_selectbest() -> None:
    X, y = generate_monotonous_data(1000)

    splitter = ExpandingWindowSplitter(initial_train_window=400, step=400)
    pipeline = OptimizeGridSearch(
        pipeline=[
            SelectBest(
                [
                    DummyRegressor(
                        predicted_value=3.0,
                        params_to_try=dict(predicted_value=[22.0, 32.0]),
                    ),
                    DummyRegressor(
                        predicted_value=0.5,
                    ),
                ]
            ),
        ],
        scorer=mean_squared_error,
    )

    pred, _ = train_backtest(pipeline, X, y, splitter)

    assert pred.squeeze()[0] == 0.5