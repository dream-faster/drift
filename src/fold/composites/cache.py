# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from __future__ import annotations

import os
from typing import Callable, List, Optional

import pandas as pd

from ..base import Artifact, Composite, Pipeline, Pipelines, get_concatenated_names
from ..transformations.dev import Identity
from ..utils.dataframe import ResolutionStrategy, concat_on_columns_with_duplicates
from ..utils.list import wrap_in_double_list_if_needed


class Cache(Composite):
    """
    Saves the results of the pipeline up until its position for the first time, to the given directory (in parquet format).
    If the file exists at the location, it loads it and skips execution of the wrapped pipeline.
    It only works during backtesting, and can not be used in live deployments.

    Parameters
    ----------

    pipeline: Pipeline
        pipeline to execute if file at path doesn't exist.

    path: str
        path to the directory used for caching.
    """

    def __init__(
        self,
        pipeline: Pipeline,
        path: str,
        name: Optional[str] = None,
    ) -> None:
        self.path = path
        self.pipeline: Pipelines = wrap_in_double_list_if_needed(pipeline)  # type: ignore
        self.name = name or "Cache-" + get_concatenated_names(self.pipeline)
        self.properties = Composite.Properties(
            primary_only_single_pipeline=True, artifacts_length_should_match=False
        )
        self.metadata = None

    def postprocess_result_primary(
        self,
        results: List[pd.DataFrame],
        y: Optional[pd.Series],
        fit: bool,
    ) -> pd.DataFrame:
        if os.path.exists(self.path) and os.path.exists(
            _result_path(self.path, self.metadata.fold_index, self.metadata.target, fit)
        ):
            return pd.read_parquet(
                _result_path(
                    self.path, self.metadata.fold_index, self.metadata.target, fit
                )
            )
        else:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            results[0].to_parquet(
                _result_path(
                    self.path, self.metadata.fold_index, self.metadata.target, fit
                )
            )
            return results[0]

    def postprocess_artifacts_primary(
        self,
        primary_artifacts: List[Artifact],
        results: List[pd.DataFrame],
        original_artifact: Artifact,
        fit: bool,
    ) -> pd.DataFrame:
        if os.path.exists(self.path) and os.path.exists(
            _artifacts_path(
                self.path, self.metadata.fold_index, self.metadata.target, fit
            )
        ):
            return pd.read_parquet(
                _artifacts_path(
                    self.path, self.metadata.fold_index, self.metadata.target, fit
                )
            )
        else:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            artifacts = concat_on_columns_with_duplicates(
                primary_artifacts,
                strategy=ResolutionStrategy.last,
            )
            artifacts.to_parquet(
                _artifacts_path(
                    self.path, self.metadata.fold_index, self.metadata.target, fit
                )
            )
            return primary_artifacts[0]

    def get_children_primary(self) -> Pipelines:
        if self.metadata is None:
            return self.pipeline
        if os.path.exists(self.path) and os.path.exists(
            _result_path(
                self.path, self.metadata.fold_index, self.metadata.target, True
            )
        ):
            return [Identity()]
        return self.pipeline

    def clone(self, clone_children: Callable) -> Cache:
        clone = Cache(
            pipeline=clone_children(self.pipeline),
            path=self.path,
        )
        clone.properties = self.properties
        clone.name = self.name
        clone.metadata = self.metadata
        return clone


def __fit_to_str(fit: bool) -> str:
    return "fit" if fit else "predict"


def _result_path(path, fold_index: int, y_name: str, fit: bool) -> str:
    return os.path.join(
        path, f"result_{y_name}_fold{str(fold_index)}_{__fit_to_str(fit)}.parquet"
    )


def _artifacts_path(path, fold_index: int, y_name: str, fit: bool) -> str:
    return os.path.join(
        path, f"artifacts_{y_name}_fold{str(fold_index)}_{__fit_to_str(fit)}.parquet"
    )
