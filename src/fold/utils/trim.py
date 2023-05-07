# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from typing import Optional, Tuple, TypeVar, Union

import numpy as np
import pandas as pd

T = TypeVar("T", pd.Series, Optional[pd.Series])


def trim_initial_nans(
    X: pd.DataFrame, y: pd.Series, sample_weights: T
) -> Tuple[pd.DataFrame, pd.Series, T]:
    # Optimize for speed, if the first value is not NaN, we can save all the subsequent computation
    if not X.iloc[0].isna().any() and (y is None or not np.isnan(y.iloc[0])):
        return X, y, sample_weights
    first_valid_index_X = get_first_valid_index(X)
    first_valid_index_y = get_first_valid_index(y)
    if first_valid_index_X is None or first_valid_index_y is None:
        return (
            pd.DataFrame(),
            pd.Series(),
            pd.Series() if sample_weights is not None else None,
        )
    first_valid_index = max(first_valid_index_X, first_valid_index_y)
    return (
        X.iloc[first_valid_index:],
        y.iloc[first_valid_index:],
        sample_weights[first_valid_index:] if sample_weights is not None else None,
    )


def trim_initial_nans_single(X: pd.DataFrame) -> pd.DataFrame:
    # Optimize for speed, if the first value is not NaN, we can save all the subsequent computation
    if not X.iloc[0].isna().any():
        return X
    first_valid_index = get_first_valid_index(X)
    return X.iloc[first_valid_index:]


def get_first_valid_index(series: Union[pd.Series, pd.DataFrame]) -> int:
    if series.empty:
        return 0
    if isinstance(series, pd.DataFrame):
        return next(
            (
                idx
                for idx, (_, x) in enumerate(series.iterrows())
                if not pd.isna(x).any()
            ),
            None,
        )
    elif isinstance(series, pd.Series):
        return next(
            (idx for idx, (_, x) in enumerate(series.items()) if not pd.isna(x)),
            None,
        )
