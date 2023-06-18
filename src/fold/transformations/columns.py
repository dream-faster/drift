# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from __future__ import annotations

from typing import Callable, List, Optional, Tuple, Union

import pandas as pd

from ..base import Artifact, Transformation, Tunable, fit_noop
from ..utils.checks import check_get_columns
from ..utils.list import wrap_in_list


class SelectColumns(Transformation, Tunable):
    """
    Selects a single or multiple columns, drops the rest.

    Parameters
    ----------

    columns : Union[List[str], str]
        The column or columns to select (dropping the rest).


    """

    properties = Transformation.Properties(requires_X=True)

    def __init__(
        self,
        columns: Union[List[str], str],
        name: Optional[str] = None,
        params_to_try: Optional[dict] = None,
    ) -> None:
        self.columns: List[str] = wrap_in_list(columns)
        self.params_to_try = params_to_try
        self.name = name or f"SelectColumns-{columns}"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        return X[self.columns], None

    fit = fit_noop
    update = fit


class DropColumns(Transformation, Tunable):
    """
    Drops a single or multiple columns.

    Parameters
    ----------

    columns : List[str], str
        The column or columns to drop.

    """

    properties = Transformation.Properties(requires_X=True)

    def __init__(
        self,
        columns: Union[List[str], str],
        name: Optional[str] = None,
        params_to_try: Optional[dict] = None,
    ) -> None:
        self.columns = wrap_in_list(columns)
        self.params_to_try = params_to_try
        self.name = name or f"DropColumns-{columns}"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        return X.drop(columns=check_get_columns(self.columns, X)), None

    fit = fit_noop
    update = fit


class RenameColumns(Transformation):
    """
    Renames columns.

    Parameters
    ----------

    columns_mapper : dict
        A dictionary containing the old column names as keys and the new column names as values.

    Examples
    --------

    ```pycon
    >>> from fold.loop import train_backtest
    >>> from fold.splitters import SlidingWindowSplitter
    >>> from fold.transformations import RenameColumns
    >>> from fold.utils.tests import generate_sine_wave_data
    >>> X, y  = generate_sine_wave_data()
    >>> splitter = SlidingWindowSplitter(train_window=0.5, step=0.2)
    >>> pipeline = RenameColumns({"sine": "sine_renamed"})
    >>> preds, trained_pipeline = train_backtest(pipeline, X, y, splitter)
    >>> preds.head()
                         sine_renamed
    2021-12-31 15:40:00       -0.0000
    2021-12-31 15:41:00        0.0126
    2021-12-31 15:42:00        0.0251
    2021-12-31 15:43:00        0.0377
    2021-12-31 15:44:00        0.0502

    ```
    """

    properties = Transformation.Properties(requires_X=True)

    def __init__(self, columns_mapper: dict) -> None:
        self.columns_mapper = columns_mapper
        self.name = "RenameColumns"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        return X.rename(columns=self.columns_mapper), None

    fit = fit_noop
    update = fit


class OnlyPredictions(Transformation):
    """
    Drops all columns except the output model(s)' predictions.

    Examples
    --------
    ```pycon
    >>> from fold.loop import train_backtest
    >>> from fold.splitters import SlidingWindowSplitter
    >>> from fold.transformations import OnlyProbabilities
    >>> from fold.models.dummy import DummyClassifier
    >>> from fold.utils.tests import generate_sine_wave_data
    >>> X, y  = generate_sine_wave_data()
    >>> splitter = SlidingWindowSplitter(train_window=0.5, step=0.2)
    >>> pipeline = [DummyClassifier(1, [0, 1], [0.5, 0.5]), OnlyPredictions()]
    >>> preds, trained_pipeline = train_backtest(pipeline, X, y, splitter)
    >>> preds.head()
                         predictions_DummyClassifier
    2021-12-31 15:40:00                            1
    2021-12-31 15:41:00                            1
    2021-12-31 15:42:00                            1
    2021-12-31 15:43:00                            1
    2021-12-31 15:44:00                            1

    ```
    """

    properties = Transformation.Properties(requires_X=True)

    def __init__(self) -> None:
        self.name = "OnlyPredictions"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        return (
            X.drop(
                columns=[col for col in X.columns if not col.startswith("predictions_")]
            ),
            None,
        )

    fit = fit_noop
    update = fit


class OnlyProbabilities(Transformation):
    """
    Drops all columns except the output model(s)' probabilities.

    Examples
    --------
    ```pycon
    >>> from fold.loop import train_backtest
    >>> from fold.splitters import SlidingWindowSplitter
    >>> from fold.transformations import OnlyProbabilities
    >>> from fold.models.dummy import DummyClassifier
    >>> from fold.utils.tests import generate_sine_wave_data
    >>> X, y  = generate_sine_wave_data()
    >>> splitter = SlidingWindowSplitter(train_window=0.5, step=0.2)
    >>> pipeline = [DummyClassifier(1, [0, 1], [0.5, 0.5]), OnlyProbabilities()]
    >>> preds, trained_pipeline = train_backtest(pipeline, X, y, splitter)
    >>> preds.head()
                         probabilities_DummyClassifier_0  probabilities_DummyClassifier_1
    2021-12-31 15:40:00                              0.5                              0.5
    2021-12-31 15:41:00                              0.5                              0.5
    2021-12-31 15:42:00                              0.5                              0.5
    2021-12-31 15:43:00                              0.5                              0.5
    2021-12-31 15:44:00                              0.5                              0.5

    ```
    """

    properties = Transformation.Properties(requires_X=True)

    def __init__(self) -> None:
        self.name = "OnlyProbabilities"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        return (
            X.drop(
                columns=[
                    col for col in X.columns if not col.startswith("probabilities_")
                ]
            ),
            None,
        )

    fit = fit_noop
    update = fit


ColumnOrColumns = Union[str, List[str]]
ColumnFunction = Tuple[ColumnOrColumns, Callable]


class FunctionOnColumns(Transformation, Tunable):
    """
    Applies a function to one or more columns.

    Parameters
    ----------
    column_func
        A tuple of a column or list of columns and a function to apply to them.
    name
        Name of the transformation.
    params_to_try
        Dictionary of parameters to try when tuning.

    Examples
    --------
    ```pycon
    >>> from fold.loop import train_backtest
    >>> from fold.splitters import SlidingWindowSplitter
    >>> from fold.transformations import FunctionOnColumns
    >>> from fold.models.dummy import DummyClassifier
    >>> from fold.utils.tests import generate_sine_wave_data
    >>> X, y  = generate_sine_wave_data()
    >>> splitter = SlidingWindowSplitter(train_window=0.5, step=0.2)
    >>> def squared(x):
            return x ** 2
    >>> pipeline = FunctionOnColumns([("sine", squared)])
    >>> preds, trained_pipeline = train_backtest(pipeline, X, y, splitter)
    >>> preds.head()
                               sine     sine_squared
    2021-12-31 15:40:00       -0.0000   0.0000
    2021-12-31 15:41:00        0.0126   0.0159
    2021-12-31 15:42:00        0.0251   0.0006
    2021-12-31 15:43:00        0.0377   0.0014
    2021-12-31 15:44:00        0.0502   0.0025

    ```


    """

    def __init__(
        self,
        column_func: Union[ColumnFunction, List[ColumnFunction]],
        name: Optional[str] = None,
        params_to_try: Optional[dict] = None,
    ) -> None:
        self.column_func = [
            (wrap_in_list(column), function)
            for column, function in wrap_in_list(column_func)
        ]
        self.properties = Transformation.Properties(requires_X=True)
        self.params_to_try = params_to_try
        self.name = name or f"FunctionOnColumns_{self.column_func}"

    def transform(
        self, X: pd.DataFrame, in_sample: bool
    ) -> Tuple[pd.DataFrame, Optional[Artifact]]:
        X_function_applied = pd.DataFrame([], index=X.index)
        for columns, function in self.column_func:
            function_name = (
                function.__name__ if function.__name__ != "<lambda>" else "transformed"
            )

            if columns[0] == "all":
                columns = X.columns

            X_function_applied = pd.concat(
                [
                    X_function_applied,
                    function(X[columns].add_suffix(f"_{function_name}")),
                ],
                axis="columns",
            )
        return pd.concat([X, X_function_applied], axis="columns"), None

    fit = fit_noop
    update = fit
