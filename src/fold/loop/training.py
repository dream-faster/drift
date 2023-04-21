# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from typing import List, Optional, Tuple, Union

import pandas as pd

from ..base import (
    Composite,
    DeployablePipeline,
    Pipeline,
    TrainedPipelines,
    Transformation,
)
from ..splitters import Fold, SlidingWindowSplitter, Splitter
from ..utils.list import wrap_in_list
from .backend import get_backend_dependent_functions
from .checks import check_types
from .common import deepcopy_pipelines, recursively_transform
from .convenience import replace_transformation_if_not_fold_native
from .types import Backend, Stage, TrainMethod


def train(
    pipeline: Pipeline,
    X: Optional[pd.DataFrame],
    y: pd.Series,
    splitter: Splitter,
    sample_weights: Optional[pd.Series] = None,
    train_method: Union[TrainMethod, str] = TrainMethod.parallel,
    backend: Union[Backend, str] = Backend.no,
    silent: bool = False,
) -> TrainedPipelines:
    """
    Trains a pipeline on a given dataset, for all folds returned by the Splitter.

    Parameters
    ----------
    pipeline: Pipeline
        The pipeline to be fitted.
    X: Optional[pd.DataFrame]
        Exogenous Data.
    y: pd.Series
        Endogenous Data (Target).
    splitter: Splitter
        Defines how the folds should be constructed.
    train_method : TrainMethod, str = TrainMethod.parallel
        The training methodology, by default `parallel`.
    backend: str, Backend = Backend.no
        The library/service to use for parallelization / distributed computing, by default `no`.
    sample_weights: Optional[pd.Series] = None
        Weights assigned to each sample/timestamp, that are passed into models that support it, by default None.
    silent: bool = False
        Wether the pipeline should print to the console, by default False.

    Returns
    -------
    TrainedPipelines
        The fitted pipelines, for all folds.
    """
    X, y = check_types(X, y)
    train_method = TrainMethod.from_str(train_method)
    backend = Backend.from_str(backend)

    if isinstance(splitter, SlidingWindowSplitter):
        assert train_method == TrainMethod.parallel, (
            "SlidingWindowSplitter is conceptually incompatible with"
            " TrainMethod.sequential"
        )

    pipeline = wrap_in_list(pipeline)
    pipeline = replace_transformation_if_not_fold_native(pipeline)

    splits = splitter.splits(length=len(y))
    backend_functions = get_backend_dependent_functions(backend)
    if len(splits) == 0:
        raise ValueError("No splits were generated by the Splitter.")

    if train_method == TrainMethod.parallel_with_search and len(splits) > 1:
        first_batch_index, first_batch_transformations = process_pipeline_window(
            X,
            y,
            sample_weights,
            pipeline,
            splits[0],
            never_update=True,
            backend=backend,
        )

        rest_idx, rest_transformations = zip(
            *backend_functions.train_transformations(
                process_pipeline_window,
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
        processed_pipelines = [first_batch_transformations] + list(rest_transformations)
    elif train_method == TrainMethod.parallel and len(splits) > 1:
        processed_idx, processed_pipelines = zip(
            *backend_functions.train_transformations(
                process_pipeline_window,
                pipeline,
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
        processed_pipelines = []
        processed_pipeline = pipeline
        for split in splits:
            processed_id, processed_pipeline = process_pipeline_window(
                X,
                y,
                sample_weights,
                processed_pipeline,
                split,
                False,
                backend,
            )
            processed_idx.append(processed_id)
            processed_pipelines.append(processed_pipeline)

    return [
        pd.Series(
            transformation_over_time,
            index=processed_idx,
            name=transformation_over_time[0].name,
        )
        for transformation_over_time in zip(*processed_pipelines)
    ]


def train_for_deployment(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series] = None,
) -> DeployablePipeline:
    X, y = check_types(X, y)

    pipeline = wrap_in_list(pipeline)
    pipeline = replace_transformation_if_not_fold_native(pipeline)
    _, transformations = process_pipeline_window(
        X,
        y,
        sample_weights,
        pipeline,
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


def process_pipeline_window(
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

    transformations = deepcopy_pipelines(transformations)
    X_train = recursively_transform(
        X_train, y_train, sample_weights_train, transformations, stage, backend
    )

    return split.model_index, transformations
