# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from ...base import Artifact, Extras, Transformation, X
from ...utils.dataframe import concat_on_columns, concat_on_index
from ..memory import postprocess_X_y_into_memory_, preprocess_X_y_with_memory


def _process_with_inner_loop(
    transformation: Transformation,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    extras: Extras,
    artifacts: Artifact,
) -> Tuple[Transformation, X, Artifact]:
    if len(X) == 0:
        return (pd.DataFrame(), pd.DataFrame())

    # We need to run the inference & fit loop on each row, sequentially (one-by-one).
    # This is so the transformation can update its parameters after each sample.

    def transform_row(
        X_row: pd.DataFrame,
        y_row: Optional[pd.Series],
        extras_row: Extras,
    ):
        (
            X_row_with_memory,
            y_row_with_memory,
            sample_weights_row_with_memory,
        ) = preprocess_X_y_with_memory(
            transformation, X_row, y_row, extras_row.sample_weights, in_sample=False
        )
        result, _ = transformation.transform(X_row_with_memory, in_sample=False)
        if y_row is not None:
            artifact = transformation.update(
                X_row_with_memory, y_row_with_memory, sample_weights_row_with_memory
            )
            _ = concat_on_columns([artifact, artifacts])
            postprocess_X_y_into_memory_(
                transformation,
                X_row_with_memory,
                y_row_with_memory,
                sample_weights_row_with_memory,
                False,
            )
        return result.loc[X_row.index]

    return (
        transformation,
        concat_on_index(
            [
                transform_row(
                    X.loc[index:index],
                    y.loc[index:index] if y is not None else None,
                    extras.loc(index),
                )
                for index in X.index
            ]
        ),
        pd.DataFrame(),
    )