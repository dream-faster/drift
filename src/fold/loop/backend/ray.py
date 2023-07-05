# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from typing import Callable, List, Optional

import pandas as pd
import ray

from ...base import Artifact, Composite, Pipeline, TrainedPipeline, X
from ...splitters import Fold
from ..types import Backend, Stage


def train_pipeline(
    func: Callable,
    pipeline: Pipeline,
    X: X,
    y: pd.Series,
    artifact: Artifact,
    splits: List[Fold],
    never_update: bool,
    backend: Backend,
    silent: bool,
):
    func = ray.remote(func)
    X = ray.put(X)
    y = ray.put(y)
    return ray.get(
        [
            func.remote(
                X,
                y,
                artifact,
                pipeline,
                split,
                never_update,
                backend,
            )
            for split in splits
        ]
    )


def backtest_pipeline(
    func: Callable,
    pipeline: TrainedPipeline,
    splits: List[Fold],
    X: pd.DataFrame,
    y: pd.Series,
    artifact: Artifact,
    backend: Backend,
    mutate: bool,
    silent: bool,
):
    func = ray.remote(func)
    X = ray.put(X)
    y = ray.put(y)
    return ray.get(
        [
            func.remote(pipeline, split, X, y, artifact, backend, mutate)
            for split in splits
        ]
    )


def process_child_transformations(
    func: Callable,
    list_of_child_transformations_with_index: List,
    composite: Composite,
    X: X,
    y: Optional[pd.Series],
    artifacts: Artifact,
    stage: Stage,
    backend: Backend,
    results_primary: Optional[List[pd.DataFrame]],
):
    # list_of_child_transformations_with_index = list(
    #     list_of_child_transformations_with_index
    # )
    # available_resources = ray.available_resources()
    # if (
    #     len(list_of_child_transformations_with_index) == 1
    #     or "CPU" not in available_resources
    #     or ("CPU" in available_resources and available_resources["CPU"] < 2)
    # ):
    return [
        func(
            composite,
            index,
            child_transformation,
            X,
            y,
            artifacts,
            stage,
            backend,
            results_primary,
        )
        for index, child_transformation in list_of_child_transformations_with_index
    ]
    # else:
    #     func = ray.remote(func)
    #     X = ray.put(X)
    #     y = ray.put(y)

    #     futures = [
    #         func.remote(
    #             composite,
    #             index,
    #             child_transformation,
    #             X,
    #             y,
    #             artifacts,
    #             stage,
    #             backend,
    #             results_primary,
    #         )
    #         for index, child_transformation in list_of_child_transformations_with_index
    #     ]
    # batch_size = 2

    # chunk processing of futures with ray
    # results = []
    # for i in range(0, len(futures), batch_size):
    #     results.extend(ray.get(futures[i : i + batch_size]))
    # while futures:
    #     if len(futures) < batch_size:
    #         batch_size = len(futures)
    #     ready_futures, futures = ray.wait(futures, num_returns=batch_size)
    #     result = ray.get(ready_futures)
    #     results.append(result)

    # return results
