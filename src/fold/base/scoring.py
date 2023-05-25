import importlib
from typing import Callable, Optional

import pandas as pd

from ..utils.checks import (
    all_have_probabilities,
    get_prediction_column,
    get_probabilities_columns,
)
from ..utils.enums import ParsableEnum
from .classes import Artifact, Extras


class ScoreOn(ParsableEnum):
    predictions = "predictions"
    probabilities = "probabilities"


def score_results(
    result: pd.DataFrame,
    y: pd.Series,
    extras: Extras,
    artifacts: Artifact,
    evaluation_func: Callable,
    krisi_args: Optional[dict] = None,
):
    probabilities = (
        get_probabilities_columns(result) if all_have_probabilities([result]) else None
    )
    pred_point = get_prediction_column(result)

    labels = get_labels(extras, artifacts)
    if labels is not None:
        y = labels.reindex(result.index).dropna()
        pred_point = pred_point.dropna()
        probabilities = probabilities.dropna()

    if len(y) != len(pred_point):
        if probabilities is not None:
            probabilities = probabilities[: len(y)]
        pred_point = pred_point[: len(y)]

    if importlib.util.find_spec("krisi") is not None:
        from krisi import score

        return score(
            y=y[pred_point.index],
            predictions=pred_point,
            probabilities=probabilities,
            **(krisi_args if krisi_args is not None else {}),
        )
    else:
        pred_point = get_prediction_column(result)
        return {
            evaluation_func.__class__.__name__: evaluation_func(
                y[pred_point.index], pred_point.squeeze()
            )
        }


def get_labels(extras: Extras, artifacts: Artifact) -> Optional[pd.Series]:
    if artifacts is not None and "label" in artifacts.columns:
        return artifacts["label"]
    elif extras.events is not None:
        return extras.events["label"]
    else:
        return None