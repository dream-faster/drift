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
from ..transformations.base import Composite, Transformation, Transformations
from ..transformations.function import FunctionTransformation


def process_pipeline(
    pipeline: Union[
        Transformation,
        Model,
        Callable,
        BaseEstimator,
        List[Union[Transformation, Model, Callable, BaseEstimator]],
    ]
) -> Transformations:
    def replace_transformation_if_not_drift_native(
        transformation: Union[
            Transformation,
            Model,
            Callable,
            BaseEstimator,
            List[Union[Transformation, Model, Callable, BaseEstimator]],
        ]
    ) -> Transformations:
        if isinstance(transformation, List):
            return [
                replace_transformation_if_not_drift_native(t) for t in transformation
            ]
        elif isinstance(transformation, RegressorMixin):
            return SKLearnModel(transformation)
        elif isinstance(transformation, ClassifierMixin):
            return SKLearnModel(transformation)
        elif isinstance(transformation, Callable):
            return FunctionTransformation(transformation)
        elif isinstance(transformation, SelectorMixin):
            return SKLearnFeatureSelector(transformation)
        elif isinstance(transformation, TransformerMixin):
            return SKLearnTransformation(transformation)
        elif isinstance(transformation, Composite):
            return transformation.clone(process_pipeline)
        elif isinstance(transformation, Transformation):
            return transformation
        else:
            raise ValueError(f"Transformation {transformation} is not supported")

    return replace_transformation_if_not_drift_native(pipeline)
