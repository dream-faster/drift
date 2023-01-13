from ast import Call
from typing import Callable, List, Union

from sklearn.base import (
    BaseEstimator,
    ClassifierMixin,
    RegressorMixin,
    TransformerMixin,
)
from sklearn.feature_selection import SelectorMixin

from drift.models.sklearn import SKLearnModel
from drift.transformations.sklearn import SKLearnFeatureSelector, SKLearnTransformation

from ..models.base import Model
from ..models.ensemble import Ensemble
from ..transformations.base import Transformation
from ..transformations.concat import Concat
from ..transformations.function import FunctionTransformation


def process_pipeline(
    pipeline: List[Union[Transformation, Model, Callable, BaseEstimator]]
) -> List[Transformation]:
    def replace_transformation_if_not_drift_native(
        transformation: Union[Transformation, Model, Callable]
    ) -> Transformation:
        if isinstance(transformation, RegressorMixin):
            return SKLearnModel(transformation)
        elif isinstance(transformation, ClassifierMixin):
            return SKLearnModel(transformation)
        elif isinstance(transformation, Callable):
            return FunctionTransformation(transformation)
        elif isinstance(transformation, SelectorMixin):
            return SKLearnFeatureSelector(transformation)
        elif isinstance(transformation, TransformerMixin):
            return SKLearnTransformation(transformation)
        elif isinstance(transformation, Ensemble):
            return Ensemble(
                process_pipeline(transformation.get_child_transformations())
            )
        elif isinstance(transformation, Concat):
            return Concat(process_pipeline(transformation.get_child_transformations()))
        elif isinstance(transformation, Transformation):
            return transformation
        else:
            raise ValueError(f"Transformation {transformation} is not supported")

    return [replace_transformation_if_not_drift_native(t) for t in pipeline]
