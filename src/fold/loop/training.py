# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from typing import Optional, Union

import pandas as pd

from ..base import DeployablePipeline, Pipeline, TrainedPipelines
from ..splitters import Fold, SlidingWindowSplitter, Splitter
from ..utils.dataframe import concat_on_index
from ..utils.list import wrap_in_list
from .backend import get_backend_dependent_functions
from .checks import check_types
from .common import _sequential_train_on_window, _train_on_window
from .types import Backend, TrainMethod
from .utils import _extract_trained_pipelines
from .wrap import wrap_transformation_if_needed


def train(
    pipeline: Pipeline,
    X: Optional[pd.DataFrame],
    y: pd.Series,
    splitter: Splitter,
    sample_weights: Optional[pd.Series] = None,
    train_method: Union[TrainMethod, str] = TrainMethod.parallel,
    backend: Union[Backend, str] = Backend.no,
    silent: bool = False,
    return_artifacts: bool = False,
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
        assert train_method != TrainMethod.sequential, (
            "SlidingWindowSplitter is conceptually incompatible with"
            " TrainMethod.sequential"
        )

    pipeline = wrap_in_list(pipeline)
    pipeline = wrap_transformation_if_needed(pipeline)

    splits = splitter.splits(length=len(y))
    backend_functions = get_backend_dependent_functions(backend)
    if len(splits) == 0:
        raise ValueError("No splits were generated by the Splitter.")

    if train_method == TrainMethod.parallel_with_search and len(splits) > 1:
        (
            first_batch_index,
            first_batch_transformations,
            first_batch_artifacts,
        ) = _train_on_window(
            X,
            y,
            sample_weights,
            pipeline,
            splits[0],
            never_update=True,
            backend=backend,
        )

        rest_idx, rest_transformations, rest_artifacts = zip(
            *backend_functions.train_transformations(
                _train_on_window,
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
        processed_artifacts = [first_batch_artifacts] + list(rest_artifacts)

    elif train_method == TrainMethod.parallel and len(splits) > 1:
        processed_idx, processed_pipelines, processed_artifacts = zip(
            *backend_functions.train_transformations(
                _train_on_window,
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
        (
            processed_idx,
            processed_pipelines,
            processed_artifacts,
        ) = _sequential_train_on_window(pipeline, X, y, splits, sample_weights, backend)

    trained_pipelines = _extract_trained_pipelines(processed_idx, processed_pipelines)
    if return_artifacts is True:
        return trained_pipelines, concat_on_index(processed_artifacts)
    else:
        return trained_pipelines


def train_for_deployment(
    pipeline: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series] = None,
) -> DeployablePipeline:
    X, y = check_types(X, y)

    pipeline = wrap_in_list(pipeline)
    pipeline = wrap_transformation_if_needed(pipeline)
    _, transformations, artifacts = _train_on_window(
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
