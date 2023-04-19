# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from typing import Callable, List, Optional

import pandas as pd
from tqdm.auto import tqdm

from ...base import Composite, Transformations
from ...splitters import Fold
from ..types import Backend, Stage


def train_transformations(
    func: Callable,
    transformations: Transformations,
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series],
    splits: List[Fold],
    never_update: bool,
    backend: Backend,
    silent: bool,
):
    return [
        func(X, y, sample_weights, transformations, split, never_update, backend)
        for split in tqdm(splits, disable=silent)
    ]


def process_primary_child_transformations(
    func: Callable,
    list_of_child_transformations_with_index: List,
    composite: Composite,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    sample_weights: Optional[pd.Series],
    stage: Stage,
    backend: Backend,
):
    return [
        func(
            composite, index, child_transformation, X, y, sample_weights, stage, backend
        )
        for index, child_transformation in list_of_child_transformations_with_index
    ]


def process_secondary_child_transformations(
    func: Callable,
    list_of_child_transformations_with_index: List,
    composite: Composite,
    X: pd.DataFrame,
    y: Optional[pd.Series],
    sample_weights: Optional[pd.Series],
    results_primary: List[pd.DataFrame],
    stage: Stage,
    backend: Backend,
):
    return [
        func(
            composite,
            index,
            child_transformation,
            X,
            y,
            sample_weights,
            results_primary,
            stage,
            backend,
        )
        for index, child_transformation in list_of_child_transformations_with_index
    ]
