# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from __future__ import annotations

import logging
from typing import List, Optional, Tuple, TypeVar, Union

import pandas as pd
from tqdm import tqdm

from fold.base.classes import EventDataFrame, PipelineCard
from fold.events import UsePredefinedEvents

from ..base import (
    Artifact,
    Composite,
    Optimizer,
    Pipeline,
    Sampler,
    TrainedPipeline,
    TrainedPipelines,
    Transformation,
    X,
)
from ..base.utils import _get_maximum_memory_size
from ..models.base import Model
from ..splitters import Fold
from ..utils.checks import is_prediction
from ..utils.dataframe import concat_on_columns
from ..utils.list import unpack_list_of_tuples
from ..utils.trim import trim_initial_nans_single
from .process.process_inner_loop import _process_with_inner_loop
from .process.process_minibatch import (
    _process_internal_online_model_minibatch_inference_and_update,
    _process_minibatch_transformation,
)
from .types import Backend, Stage
from .utils import (
    _extract_trained_pipelines,
    _set_metadata,
    deepcopy_pipelines,
    replace_with,
)

logger = logging.getLogger("fold:loop")
DEBUG_MULTI_PROCESSING = False

T = TypeVar(
    "T",
    bound=Union[
        Transformation,
        Composite,
        Optimizer,
        Sampler,
        List[Union[Transformation, Optimizer, Sampler, Composite]],
    ],
)


def __post_checks(
    pipeline: T, X: pd.DataFrame, artifacts: Artifact
) -> Tuple[T, X, Artifact]:
    assert X.shape[0] == artifacts.shape[0]
    assert X.index.equals(artifacts.index)
    return pipeline, X, artifacts


def recursively_transform(
    X: X,
    y: Optional[pd.Series],
    artifacts: Artifact,
    transformations: T,
    stage: Stage,
    backend: Backend,
    tqdm: Optional[tqdm] = None,
) -> Tuple[T, X, Artifact]:
    """
    The main function to transform (and fit or update) a pipline of transformations.
    `stage` is used to determine whether to run the inner loop for online models.
    """
    logger.debug(f"Processing {transformations.__class__.__name__} with stage {stage}")

    if tqdm is not None and hasattr(transformations, "name"):
        tqdm.set_description(f"Processing: {transformations.name}")

    if isinstance(transformations, List) or isinstance(transformations, Tuple):
        processed_transformations = []
        for transformation in transformations:
            processed_transformation, X, artifacts = recursively_transform(
                X,
                y,
                artifacts,
                transformation,
                stage,
                backend,
                tqdm,
            )
            processed_transformations.append(processed_transformation)
        return __post_checks(processed_transformations, X, artifacts)

    elif isinstance(transformations, UsePredefinedEvents):
        return __post_checks(
            *_process_use_predefined_events(
                transformations,
                X,
                y,
                artifacts,
                stage,
                backend,
                tqdm,
            )
        )

    elif isinstance(transformations, Composite):
        return __post_checks(
            *_process_composite(
                transformations,
                X,
                y,
                artifacts,
                stage,
                backend,
                tqdm,
            )
        )
    elif isinstance(transformations, Optimizer):
        return __post_checks(
            *_process_optimizer(
                transformations,
                X,
                y,
                artifacts,
                stage,
                backend,
                tqdm,
            )
        )

    elif isinstance(transformations, Sampler):
        return __post_checks(
            *_process_sampler(
                transformations,
                X,
                y,
                artifacts,
                stage,
                backend,
                tqdm,
            )
        )

    elif isinstance(transformations, Transformation) or isinstance(
        transformations, Model
    ):
        # If the transformation needs to be "online", and we're in the update stage, we need to run the inner loop.
        if (
            transformations.properties.mode == Transformation.Properties.Mode.online
            and stage in [Stage.update, Stage.update_online_only]
            and not transformations.properties._internal_supports_minibatch_backtesting
        ):
            return __post_checks(
                *_process_with_inner_loop(transformations, X, y, artifacts)
            )
        # If the transformation is "online" but also supports our internal "mini-batch"-style updating
        elif (
            transformations.properties.mode == Transformation.Properties.Mode.online
            and stage in [Stage.update, Stage.update_online_only]
            and transformations.properties._internal_supports_minibatch_backtesting
        ):
            return __post_checks(
                *_process_internal_online_model_minibatch_inference_and_update(
                    transformations, X, y, artifacts
                )
            )

        # or perform "mini-batch" updating OR the initial fit.
        else:
            return __post_checks(
                *_process_minibatch_transformation(
                    transformations,
                    X,
                    y,
                    artifacts,
                    stage,
                )
            )

    else:
        raise ValueError(
            f"{transformations} is not a Fold Transformation, but of type"
            f" {type(transformations)}"
        )


def _process_composite(
    composite: Composite,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    tqdm: Optional[tqdm] = None,
) -> Tuple[Composite, X, Artifact]:
    composite.before_fit(X)
    primary_transformations = composite.get_children_primary()

    (
        primary_transformations,
        results_primary,
        y_primary,
        artifacts_primary,
    ) = unpack_list_of_tuples(
        backend.process_child_transformations(
            __process_primary_child_transform,
            enumerate(primary_transformations),
            composite,
            X,
            y,
            artifacts,
            stage,
            backend,
            None,
            tqdm,
        )
    )
    if composite.properties.artifacts_length_should_match:
        assert all(
            [
                r.shape[0] == a.shape[0]
                for r, a in zip(results_primary, artifacts_primary)
            ]
        ), ValueError("Artifacts shape doesn't match result's length.")
    composite = composite.clone(replace_with(primary_transformations))

    if composite.properties.primary_only_single_pipeline:
        assert len(results_primary) == 1, ValueError(
            "Expected single output from primary transformations, got"
            f" {len(results_primary)} instead."
        )
    if composite.properties.primary_requires_predictions:
        assert is_prediction(results_primary[0]), ValueError(
            "Expected predictions from primary transformations, but got something else."
        )

    secondary_transformations = composite.get_children_secondary()

    original_results_primary = results_primary
    results_primary = composite.postprocess_result_primary(
        results_primary,
        y_primary[0],
        fit=stage.is_fit_or_update(),
    )
    artifacts_primary = composite.postprocess_artifacts_primary(
        primary_artifacts=artifacts_primary,
        results=original_results_primary,
        fit=stage.is_fit_or_update(),
        original_artifact=artifacts,
    )
    if composite.properties.artifacts_length_should_match:
        assert artifacts_primary.shape[0] == results_primary.shape[0], ValueError(
            f"Artifacts shape doesn't match result's length after {composite.__class__.__name__}.postprocess_artifacts_primary() was called"
        )
    if secondary_transformations is None:
        return (
            composite,
            results_primary,
            artifacts_primary,
        )

    (
        secondary_transformations,
        results_secondary,
        artifacts_secondary,
    ) = unpack_list_of_tuples(
        backend.process_child_transformations(
            __process_secondary_child_transform,
            enumerate(secondary_transformations),
            composite,
            X,
            y,
            artifacts,
            stage,
            backend,
            results_primary,
            tqdm,
        )
    )
    composite = composite.clone(replace_with(secondary_transformations))

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

    return (
        composite,
        composite.postprocess_result_secondary(
            results_primary,
            results_secondary,
            y,
            in_sample=stage == Stage.inital_fit,
        ),
        composite.postprocess_artifacts_secondary(
            artifacts_primary, artifacts_secondary, artifacts
        ),
    )


def _process_use_predefined_events(
    composite: UsePredefinedEvents,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    tqdm: Optional[tqdm] = None,
) -> Tuple[UsePredefinedEvents, X, Artifact]:
    primary_transformations = composite.get_children_primary()

    (
        primary_transformations,
        results_primary,
        y_primary,
        artifacts_primary,
    ) = unpack_list_of_tuples(
        backend.process_child_transformations(
            __process_primary_child_transform,
            enumerate(primary_transformations),
            composite,
            X,
            y,
            artifacts,
            stage,
            backend,
            None,
            tqdm,
        )
    )
    if composite.properties.artifacts_length_should_match:
        assert all(
            [
                r.shape[0] == a.shape[0]
                for r, a in zip(results_primary, artifacts_primary)
            ]
        ), ValueError("Artifacts shape doesn't match result's length.")
    composite = composite.clone(replace_with(primary_transformations))

    if composite.properties.primary_only_single_pipeline:
        assert len(results_primary) == 1, ValueError(
            "Expected single output from primary transformations, got"
            f" {len(results_primary)} instead."
        )
    if composite.properties.primary_requires_predictions:
        assert is_prediction(results_primary[0]), ValueError(
            "Expected predictions from primary transformations, but got something else."
        )

    results_primary = results_primary[0].reindex(y.index)
    artifacts_primary = artifacts_primary[0].reindex(y.index)
    assert artifacts_primary.shape[0] == results_primary.shape[0], ValueError(
        f"Artifacts shape doesn't match result's length after {composite.__class__.__name__}.postprocess_artifacts_primary() was called"
    )
    return (
        composite,
        results_primary,
        artifacts_primary,
    )


def _process_sampler(
    sampler: Sampler,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    tqdm: Optional[tqdm] = None,
) -> Tuple[Composite, X, Artifact]:
    primary_transformations = sampler.get_children_primary()

    (
        primary_transformations,
        primary_results,
        y_primary,
        primary_artifacts,
    ) = unpack_list_of_tuples(
        backend.process_child_transformations(
            __process_primary_child_transform,
            enumerate(primary_transformations),
            sampler,
            X,
            y,
            artifacts,
            stage,
            backend,
            None,
            tqdm,
        )
    )
    sampler = sampler.clone(replace_with(primary_transformations))

    assert len(primary_results) == 1, ValueError(
        "Expected single output from primary transformations, got"
        f" {len(primary_results)} instead."
    )

    if stage is Stage.inital_fit:
        secondary_transformations = sampler.get_children_primary()
        (
            secondary_transformations,
            primary_results,
            primary_y,
            primary_artifacts,
        ) = unpack_list_of_tuples(
            backend.process_child_transformations(
                __process_primary_child_transform,
                enumerate(secondary_transformations),
                sampler,
                X,
                y,
                artifacts,
                Stage.infer,
                backend,
                None,
                tqdm,
            )
        )

    primary_results = primary_results[0]
    primary_artifacts = primary_artifacts[0]
    assert primary_artifacts.shape[0] == primary_results.shape[0], ValueError(
        f"Artifacts shape doesn't match result's length after {sampler.__class__.__name__}.postprocess_artifacts_primary() was called"
    )
    return sampler, primary_results, primary_artifacts


def _process_optimizer(
    optimizer: Optimizer,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    tqdm: Optional[tqdm] = None,
) -> Tuple[Pipeline, X, Artifact]:
    if tqdm is not None:
        tqdm.set_description(f"Processing: {optimizer.name}")
    optimized_pipeline = optimizer.get_optimized_pipeline()
    artifact = None
    if optimized_pipeline is None:
        while True:
            candidates = optimizer.get_candidates()
            if len(candidates) == 0:
                break

            _, results, candidate_artifacts = unpack_list_of_tuples(
                backend.process_child_transformations(
                    __process_candidates,
                    enumerate(candidates),
                    optimizer,
                    X,
                    y,
                    artifacts,
                    stage,
                    backend,
                    None,
                    None,
                )
            )
            results = [trim_initial_nans_single(result) for result in results]
            artifact = optimizer.process_candidate_results(
                results,
                y=y.loc[results[0].index],
                artifacts=candidate_artifacts,
            )

    optimized_pipeline = optimizer.get_optimized_pipeline()
    processed_optimized_pipeline, X, artifact = recursively_transform(
        X,
        y,
        concat_on_columns([artifact, artifacts], copy=False),
        optimized_pipeline,
        stage,
        backend,
    )
    return optimizer, X, artifact


def __process_candidates(
    optimizer: Optimizer,
    index: int,
    child_transform: Pipeline,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    results_primary: Optional[List[pd.DataFrame]],
    tqdm: Optional[tqdm] = None,
) -> Tuple[Pipeline, X, Artifact]:
    splits = optimizer.splitter.splits(y.index)

    (
        processed_idx,
        processed_pipelines,
        processed_predictions,
        processed_artifacts,
    ) = _sequential_train_on_window(
        child_transform, X, y, splits, artifacts, events=None, backend=backend
    )
    trained_pipelines = _extract_trained_pipelines(processed_idx, processed_pipelines)

    result, artifact = _backtest_on_window(
        trained_pipelines,
        splits[0],
        X,
        y,
        artifacts,
        backend,
        mutate=False,
    )
    assert result.index.equals(artifact.index)
    return (
        trained_pipelines,
        trim_initial_nans_single(result),
        artifact,
    )


def __process_primary_child_transform(
    composite: Union[Composite, Sampler],
    index: int,
    child_transform: Pipeline,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    results_primary: Optional[List[pd.DataFrame]],
    tqdm: Optional[tqdm] = None,
) -> Tuple[Pipeline, X, Optional[pd.Series], Artifact]:
    X, y, artifacts = composite.preprocess_primary(
        X=X, index=index, y=y, artifact=artifacts, fit=stage.is_fit_or_update()
    )
    transformations, X, artifacts = recursively_transform(
        X,
        y,
        artifacts,
        child_transform,
        stage,
        backend,
        tqdm,
    )
    return transformations, X, y, artifacts


def __process_secondary_child_transform(
    composite: Composite,
    index: int,
    child_transform: Pipeline,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    results_primary: Optional[List[pd.DataFrame]],
    tqdm: Optional[tqdm] = None,
) -> Tuple[Pipeline, X, Artifact]:
    X, y, artifacts = composite.preprocess_secondary(
        X=X,
        y=y,
        artifact=artifacts,
        results_primary=results_primary,
        index=index,
        fit=stage.is_fit_or_update(),
    )
    return recursively_transform(
        X,
        y,
        artifacts,
        child_transform,
        stage,
        backend,
        tqdm,
    )


def _backtest_on_window(
    trained_pipelines: TrainedPipelines,
    split: Fold,
    X: pd.DataFrame,
    y: pd.Series,
    artifact: Artifact,
    backend: Backend,
    mutate: bool,
) -> Tuple[X, Artifact]:
    pd.options.mode.copy_on_write = True
    current_pipeline = [
        pipeline_over_time.loc[split.model_index]
        for pipeline_over_time in trained_pipelines
    ]
    if not mutate:
        current_pipeline = deepcopy_pipelines(current_pipeline)

    overlap = _get_maximum_memory_size(current_pipeline)
    test_window_start = max(split.test_window_start - overlap, 0)
    X_test = X.iloc[test_window_start : split.test_window_end]
    y_test = y.iloc[test_window_start : split.test_window_end]
    artifact_test = artifact.iloc[test_window_start : split.test_window_end]
    results, artifacts = recursively_transform(
        X_test,
        y_test,
        artifact_test,
        current_pipeline,
        stage=Stage.update_online_only,
        backend=backend,
    )[1:]
    return (
        results.loc[X.index[split.test_window_start] :],
        artifacts.loc[X.index[split.test_window_start] :],
    )


def _train_on_window(
    X: pd.DataFrame,
    y: pd.Series,
    artifact: Artifact,
    events: Optional[EventDataFrame],
    pipeline: Pipeline,
    split: Fold,
    never_update: bool,
    backend: Backend,
    show_progress: bool = False,
) -> Tuple[int, TrainedPipeline, X, Artifact]:
    pd.options.mode.copy_on_write = True

    stage = Stage.inital_fit if (split.order == 0 or never_update) else Stage.update
    X_train: pd.DataFrame = __cut_to_train_window(X, split, stage)  # type: ignore
    y_train = __cut_to_train_window(y, split, stage)
    artifact_train = __cut_to_train_window(artifact, split, stage)

    pipeline = deepcopy_pipelines(pipeline)
    pipeline = _set_metadata(
        pipeline, Composite.Metadata(fold_index=split.order, target=y.name)
    )
    trained_pipeline, X_train, artifacts = recursively_transform(
        X_train,
        y_train,
        artifact_train,
        pipeline,
        stage,
        backend,
        tqdm=tqdm() if show_progress else None,
    )

    return split.model_index, trained_pipeline, X_train, artifacts


def __cut_to_train_window(df: pd.DataFrame, fold: Fold, stage: Stage):
    window_start = (
        fold.update_window_start if stage == Stage.update else fold.train_window_start
    )
    window_end = (
        fold.update_window_end if stage == Stage.update else fold.train_window_end
    )
    return df.iloc[window_start:window_end]


def _sequential_train_on_window(
    pipeline: Pipeline,
    X: Optional[pd.DataFrame],
    y: pd.Series,
    splits: List[Fold],
    artifact: Artifact,
    events: Optional[EventDataFrame],
    backend: Backend,
) -> Tuple[List[int], List[Pipeline], List[X], List[Artifact]]:
    processed_idx = []
    processed_pipelines: List[Pipeline] = []
    processed_pipeline = pipeline
    processed_predictions = []
    processed_artifacts = []
    for split in splits:
        (
            processed_id,
            processed_pipeline,
            processed_prediction,
            processed_artifact,
        ) = _train_on_window(
            X,
            y,
            artifact,
            events,
            processed_pipeline,
            split,
            False,
            backend,
        )
        processed_idx.append(processed_id)
        processed_pipelines.append(processed_pipeline)
        processed_predictions.append(processed_prediction)
        processed_artifacts.append(processed_artifact)

    return (
        processed_idx,
        processed_pipelines,
        processed_predictions,
        processed_artifacts,
    )


def _create_events(
    y: pd.Series, pipeline_card: PipelineCard
) -> Optional[EventDataFrame]:
    if pipeline_card.event_filter is None:
        return None
    start_times = (
        pipeline_card.event_filter.get_event_start_times(y)
        if pipeline_card.event_filter is not None
        else y.index
    )
    return pipeline_card.event_labeler.label_events(start_times, y).reindex(y.index)
