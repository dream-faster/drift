from __future__ import annotations

from copy import deepcopy
from typing import Callable, List, Optional, Tuple

import pandas as pd

from ..composites.base import Composite
from ..models.base import Model
from ..transformations.base import Transformation, Transformations
from ..utils.checks import is_prediction
from ..utils.pandas import trim_initial_nans
from .backend.ray import (
    process_primary_child_transformations as _process_primary_child_transformations_ray,
)
from .backend.ray import (
    process_secondary_child_transformations as _process_secondary_child_transformations_ray,
)
from .backend.sequential import (
    process_primary_child_transformations as _process_primary_child_transformations_sequential,
)
from .backend.sequential import (
    process_secondary_child_transformations as _process_secondary_child_transformations_sequential,
)
from .types import Backend, Stage


def recursively_transform(
    X: pd.DataFrame,
    y: Optional[pd.Series],
    sample_weights: Optional[pd.Series],
    transformations: Transformations,
    stage: Stage,
    backend: Backend,
) -> pd.DataFrame:
    """
    The main function to transform (and fit or update) a pipline of transformations.
    `stage` is used to determine whether to run the inner loop for online models.
    """
    if y is not None and len(X) != len(y):
        y = y[X.index]

    if isinstance(transformations, List):
        for transformation in transformations:
            X = recursively_transform(
                X, y, sample_weights, transformation, stage, backend
            )
        return X

    elif isinstance(transformations, Composite):
        composite: Composite = transformations
        # TODO: here we have the potential to parallelize/distribute training of child transformations
        composite.before_fit(X)
        primary_transformations = composite.get_child_transformations_primary()
        process_func = __get_process_primary_function(backend)
        results_primary = process_func(
            process_primary_child_transform,
            enumerate(primary_transformations),
            composite,
            X,
            y,
            sample_weights,
            stage,
            backend,
        )

        if composite.properties.primary_only_single_pipeline:
            assert len(results_primary) == 1, ValueError(
                "Expected single output from primary transformations, got"
                f" {len(results_primary)} instead."
            )
        if composite.properties.primary_requires_predictions:
            assert is_prediction(results_primary[0]), ValueError(
                "Expected predictions from primary transformations, but got something"
                " else."
            )

        secondary_transformations = composite.get_child_transformations_secondary()
        if secondary_transformations is None:
            return composite.postprocess_result_primary(results_primary, y)
        else:
            process_func = __get_process_secondary_function(backend)
            results_secondary = process_func(
                process_secondary_child_transform,
                enumerate(secondary_transformations),
                composite,
                X,
                y,
                sample_weights,
                results_primary,
                stage,
                backend,
            )

            if composite.properties.secondary_only_single_pipeline:
                assert len(results_secondary) == 1, ValueError(
                    "Expected single output from secondary transformations, got"
                    f" {len(results_secondary)} instead."
                )
            if composite.properties.secondary_requires_predictions:
                assert is_prediction(results_secondary[0]), ValueError(
                    "Expected predictions from secondary transformations, but got"
                    " something else."
                )

            return composite.postprocess_result_secondary(
                results_primary, results_secondary, y
            )

    elif isinstance(transformations, Transformation) or isinstance(
        transformations, Model
    ):
        if len(X) == 0:
            return pd.DataFrame()

        # If the transformation needs to be "online", and we're in the update stage, we need to run the inner loop.
        if (
            transformations.properties.mode == Transformation.Properties.Mode.online
            and stage in [Stage.update, Stage.update_online_only]
        ):
            # We need to run the inference & fit loop on each row, sequentially (one-by-one).
            # This is so the transformation can update its parameters after each sample.

            def transform_row(
                X_row: pd.DataFrame, y_row: Optional[pd.Series], sample_weights_row
            ):
                X_row_with_memory, y_row_with_memory = _preprocess_X_y_with_memory(
                    transformations, X_row, y_row
                )
                result = transformations.transform(X_row_with_memory, in_sample=False)
                if y_row is not None:
                    transformations.update(
                        X_row_with_memory, y_row_with_memory, sample_weights_row
                    )
                    _postprocess_X_y_into_memory(
                        transformations, X_row_with_memory, y_row_with_memory, False
                    )
                return result.loc[X_row.index]

            return pd.concat(
                [
                    transform_row(
                        X.loc[index:index],
                        y.loc[index:index] if y is not None else None,
                        sample_weights.loc[index]
                        if sample_weights is not None
                        else None,
                    )
                    for index in X.index
                ],
                axis="index",
            )

        # or the model is "mini-batch" updating or we're in initial_fit stage
        else:
            X, y = trim_initial_nans(X, y)
            X_with_memory, y_with_memory = _preprocess_X_y_with_memory(
                transformations, X, y
            )
            # The order is:
            # 1. fit (if we're in the initial_fit stage)
            if stage == Stage.inital_fit:
                transformations.fit(X_with_memory, y_with_memory, sample_weights)
                _postprocess_X_y_into_memory(
                    transformations,
                    X_with_memory,
                    y_with_memory,
                    in_sample=stage == Stage.inital_fit,
                )
            # 2. transform (inference)
            X_with_memory, y_with_memory = _preprocess_X_y_with_memory(
                transformations, X, y
            )
            return_value = transformations.transform(
                X_with_memory, in_sample=stage == Stage.inital_fit
            )
            # 3. update (if we're in the update stage)
            if stage == Stage.update:
                transformations.update(X_with_memory, y_with_memory, sample_weights)
                _postprocess_X_y_into_memory(transformations, X, y, False)
            return return_value.loc[X.index]

    else:
        raise ValueError(
            f"{transformations} is not a Fold Transformation, but of type"
            f" {type(transformations)}"
        )


def __get_process_primary_function(backend: Backend) -> Callable:
    if backend == Backend.ray:
        return _process_primary_child_transformations_ray
    else:
        return _process_primary_child_transformations_sequential


def __get_process_secondary_function(backend: Backend) -> Callable:
    if backend == Backend.ray:
        return _process_secondary_child_transformations_ray
    else:
        return _process_secondary_child_transformations_sequential


def process_primary_child_transform(
    composite: Composite,
    index: int,
    child_transform: Transformations,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    sample_weights: Optional[pd.Series],
    stage: Stage,
    backend: Backend,
) -> pd.DataFrame:
    X, y = composite.preprocess_primary(X, index, y, fit=stage.is_fit_or_update())
    return recursively_transform(X, y, sample_weights, child_transform, stage, backend)


def process_secondary_child_transform(
    composite: Composite,
    index: int,
    child_transform: Transformations,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    sample_weights: Optional[pd.Series],
    results_primary: List[pd.DataFrame],
    stage: Stage,
    backend: Backend,
) -> pd.DataFrame:
    X, y = composite.preprocess_secondary(
        X, y, results_primary, index, fit=stage.is_fit_or_update()
    )
    return recursively_transform(X, y, sample_weights, child_transform, stage, backend)


def deepcopy_transformations(transformation: Transformations) -> Transformations:
    if isinstance(transformation, List):
        return [deepcopy_transformations(t) for t in transformation]
    elif isinstance(transformation, Composite):
        return transformation.clone(deepcopy_transformations)
    else:
        return deepcopy(transformation)


def _preprocess_X_y_with_memory(
    transformation: Transformation, X: pd.DataFrame, y: Optional[pd.Series]
) -> Tuple[pd.DataFrame, pd.Series]:
    if transformation._state is None or transformation.properties.memory_size is None:
        return X, y
    memory_X, memory_y = transformation._state.memory_X, transformation._state.memory_y
    non_overlapping_indices = ~memory_X.index.isin(X.index)
    memory_X, memory_y = (
        memory_X[non_overlapping_indices],
        memory_y[non_overlapping_indices],
    )
    if len(memory_X) == 0:
        return X, y
    assert len(memory_X) == len(memory_y)
    if y is None:
        return pd.concat([memory_X, X], axis="index"), y
    else:
        memory_y.name = y.name
        return pd.concat([memory_X, X], axis="index"), pd.concat(
            [memory_y, y], axis="index"
        )


def _postprocess_X_y_into_memory(
    transformation: Transformation,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    in_sample: bool,
) -> None:
    # don't update the transformation if we're in inference mode (y is None)
    if transformation.properties.memory_size is None or y is None:
        return

    window_size = (
        len(X)
        if transformation.properties.memory_size == 0
        else transformation.properties.memory_size
    )
    if in_sample:
        # store the whole training X and y
        transformation._state = Transformation.State(
            memory_X=X,
            memory_y=y,
        )
    elif transformation.properties.memory_size < len(X):
        memory_X, memory_y = (
            transformation._state.memory_X,
            transformation._state.memory_y,
        )
        memory_y.name = y.name
        #  memory requirement is greater than the current batch, so we use the previous memory as well
        transformation._state = Transformation.State(
            memory_X=pd.concat([memory_X, X], axis="index").iloc[-window_size:],
            memory_y=pd.concat([memory_y, y], axis="index").iloc[-window_size:],
        )
    else:
        transformation._state = Transformation.State(
            memory_X=X.iloc[-window_size:],
            memory_y=y.iloc[-window_size:],
        )
