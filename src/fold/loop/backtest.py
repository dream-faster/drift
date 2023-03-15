from typing import Optional

import pandas as pd
from tqdm import tqdm

from fold.utils.pandas import trim_initial_nans_single

from ..all_types import OutOfSamplePredictions, TransformationsOverTime
from ..splitters import Fold, Splitter
from .common import Stage, deepcopy_transformations, recursively_transform


def backtest(
    transformations_over_time: TransformationsOverTime,
    X: pd.DataFrame,
    y: pd.Series,
    splitter: Splitter,
    sample_weights: Optional[pd.Series] = None,
) -> OutOfSamplePredictions:
    """
    Backtest a list of transformations over time.
    Run backtest on a set of TransformationsOverTime and given data.
    Does not mutate or change the transformations in any way, aka you can backtest multiple times.
    """

    assert type(X) is pd.DataFrame, "X must be a pandas DataFrame."
    assert type(y) is pd.Series, "y must be a pandas Series."

    results = [
        __backtest_on_window(
            transformations_over_time,
            split,
            X,
            y,
            sample_weights,
            mutate=False,
        )
        for split in tqdm(splitter.splits(length=len(X)))
    ]
    return pd.concat(results, axis="index")


def _backtest_and_mutate(
    transformations_over_time: TransformationsOverTime,
    X: pd.DataFrame,
    y: pd.Series,
    splitter: Splitter,
    sample_weights: Optional[pd.Series] = None,
) -> OutOfSamplePredictions:
    """
    Backtest a list of transformations over time, and mutates `transformations_over_time` inplace.
    """

    assert type(X) is pd.DataFrame, "X must be a pandas DataFrame."
    assert type(y) is pd.Series, "y must be a pandas Series."

    results = [
        __backtest_on_window(
            transformations_over_time,
            split,
            X,
            y,
            sample_weights,
            mutate=True,
        )
        for split in tqdm(splitter.splits(length=len(X)))
    ]
    return pd.concat(results, axis="index")


def __backtest_on_window(
    transformations_over_time: TransformationsOverTime,
    split: Fold,
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series],
    mutate: bool,
) -> pd.DataFrame:
    current_transformations = [
        transformation_over_time.loc[split.model_index]
        for transformation_over_time in transformations_over_time
    ]
    current_transformations = (
        current_transformations
        if mutate
        else deepcopy_transformations(current_transformations)
    )

    X_test = X.iloc[split.test_window_start : split.test_window_end]
    y_test = y.iloc[split.test_window_start : split.test_window_end]
    sample_weights_test = (
        sample_weights.iloc[split.train_window_start : split.test_window_end]
        if sample_weights is not None
        else None
    )
    X_test = recursively_transform(
        X_test,
        y_test,
        sample_weights_test,
        current_transformations,
        stage=Stage.update,
    )

    return trim_initial_nans_single(X_test)
