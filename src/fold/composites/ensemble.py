from __future__ import annotations

from typing import Callable, List, Optional

import pandas as pd

from ..base import Composite, Pipelines
from .columns import postprocess_results
from .common import get_concatenated_names


class Ensemble(Composite):
    """
    Ensemble (average) the results of multiple pipelines.

    Parameters
    ----------

    pipelines : Pipelines
        A list of pipelines to be applied to the data, independently of each other.

    """

    properties = Composite.Properties()

    def __init__(self, pipelines: Pipelines) -> None:
        self.pipelines = pipelines
        self.name = "Ensemble-" + get_concatenated_names(pipelines)

    def postprocess_result_primary(
        self, results: List[pd.DataFrame], y: Optional[pd.Series]
    ) -> pd.DataFrame:
        return postprocess_results(results, self.name)

    def get_child_transformations_primary(self) -> Pipelines:
        return self.pipelines

    def clone(self, clone_child_transformations: Callable) -> Ensemble:
        return Ensemble(
            pipelines=clone_child_transformations(self.pipelines),
        )
