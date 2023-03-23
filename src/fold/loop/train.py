from typing import Callable, List, Optional, Tuple, Union

import pandas as pd
from sklearn.base import BaseEstimator

from ..all_types import TransformationsOverTime
from ..composites.base import Composite
from ..models.base import Model
from ..splitters import Fold, SlidingWindowSplitter, Splitter
from ..transformations.base import (
    BlocksOrWrappable,
    DeployableTransformations,
    Transformation,
    Transformations,
)
from ..utils.list import wrap_in_list
from .backend import get_backend_dependent_functions
from .checks import check_types
from .common import deepcopy_transformations, recursively_transform
from .convenience import replace_transformation_if_not_fold_native
from .types import Backend, Stage, TrainMethod


def train(
    transformations: BlocksOrWrappable,
    X: Optional[pd.DataFrame],
    y: pd.Series,
    splitter: Splitter,
    sample_weights: Optional[pd.Series] = None,
    train_method: TrainMethod = TrainMethod.parallel,
    backend: Backend = Backend.no,
    silent: bool = False,
) -> TransformationsOverTime:
    X, y = check_types(X, y)

    if type(splitter) is SlidingWindowSplitter:
        assert train_method == TrainMethod.parallel, (
            "SlidingWindowSplitter is conceptually incompatible with"
            " TrainMethod.sequential"
        )

    transformations = wrap_in_list(transformations)
    transformations = replace_transformation_if_not_fold_native(transformations)

    splits = splitter.splits(length=len(y))
    backend_functions = get_backend_dependent_functions(backend)
    if len(splits) == 0:
        raise ValueError("No splits were generated by the Splitter.")

    if train_method == TrainMethod.parallel_with_search and len(splits) > 1:
        first_batch_index, first_batch_transformations = process_transformations_window(
            X,
            y,
            sample_weights,
            transformations,
            splits[0],
            never_update=True,
            backend=backend,
        )

        rest_idx, rest_transformations = zip(
            *backend_functions.train_transformations(
                process_transformations_window,
                first_batch_transformations,
                X,
                y,
                sample_weights,
                splits[1:],
                False,
                backend,
                silent,
            )
        )
        processed_idx = [first_batch_index] + list(rest_idx)
        processed_transformations = [first_batch_transformations] + list(
            rest_transformations
        )
    elif train_method == TrainMethod.parallel and len(splits) > 1:
        processed_idx, processed_transformations = zip(
            *backend_functions.train_transformations(
                process_transformations_window,
                transformations,
                X,
                y,
                sample_weights,
                splits,
                True,
                backend,
                silent,
            )
        )

    else:
        processed_idx = []
        processed_transformations = []
        processed_transformation = transformations
        for split in splits:
            processed_id, processed_transformation = process_transformations_window(
                X,
                y,
                sample_weights,
                processed_transformation,
                split,
                False,
                backend,
            )
            processed_idx.append(processed_id)
            processed_transformations.append(processed_transformation)

    return [
        pd.Series(
            transformation_over_time,
            index=processed_idx,
            name=transformation_over_time[0].name,
        )
        for transformation_over_time in zip(*processed_transformations)
    ]


def train_for_deployment(
    transformations: List[
        Union[Transformation, Composite, Model, Callable, BaseEstimator]
    ],
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series] = None,
) -> DeployableTransformations:
    X, y = check_types(X, y)

    transformations = wrap_in_list(transformations)
    transformations: Transformations = replace_transformation_if_not_fold_native(
        transformations
    )
    _, transformations = process_transformations_window(
        X,
        y,
        sample_weights,
        transformations,
        Fold(
            order=0,
            model_index=0,
            train_window_start=0,
            train_window_end=None,
            update_window_start=0,
            update_window_end=0,
            test_window_start=0,
            test_window_end=None,
        ),
        True,
        backend=Backend.no,
    )
    return transformations


def process_transformations_window(
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series],
    transformations: List[Union[Transformation, Composite]],
    split: Fold,
    never_update: bool,
    backend: Backend,
) -> Tuple[int, List[Union[Transformation, Composite]]]:
    stage = Stage.inital_fit if (split.order == 0 or never_update) else Stage.update
    window_start = (
        split.update_window_start if stage == Stage.update else split.train_window_start
    )
    window_end = (
        split.update_window_end if stage == Stage.update else split.train_window_end
    )
    X_train = X.iloc[window_start:window_end]
    y_train = y.iloc[window_start:window_end]

    sample_weights_train = (
        sample_weights.iloc[window_start:window_end]
        if sample_weights is not None
        else None
    )

    transformations = deepcopy_transformations(transformations)
    X_train = recursively_transform(
        X_train, y_train, sample_weights_train, transformations, stage, backend
    )

    return split.model_index, transformations
