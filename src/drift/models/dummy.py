from typing import Union

import pandas as pd

from ..transformations.base import Transformation
from .base import Model


class DummyClassifier(Model):

    properties = Transformation.Properties(requires_past_X=False)
    name = "DummyClassifier"

    def __init__(self, predicted_value, all_classes, predicted_probabilities) -> None:
        self.predicted_value = predicted_value
        self.all_classes = all_classes
        self.predicted_probabilities = predicted_probabilities

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        pass

    def predict(self, X: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        predictions = pd.Series(
            [self.predicted_value] * len(X),
            index=X.index,
            name="predictions_DummyClassifier",
        )
        probabilities = [
            pd.Series(
                [prob] * len(X),
                index=X.index,
                name=f"probabilities_DummyClassifier_{associated_class}",
            )
            for associated_class, prob in zip(
                self.all_classes, self.predicted_probabilities
            )
        ]

        return pd.concat([predictions] + probabilities, axis=1)


class DummyRegressor(Model):

    properties = Transformation.Properties(requires_past_X=False)
    name = "DummyRegressor"

    def __init__(self, predicted_value: float) -> None:
        self.predicted_value = predicted_value

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        pass

    def predict(self, X: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        predictions = pd.Series(
            [self.predicted_value] * len(X),
            index=X.index,
            name="predictions_DummyClassifier",
        )

        return predictions