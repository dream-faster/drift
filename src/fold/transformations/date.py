from __future__ import annotations

from enum import Enum
from typing import Callable, List, Union

import pandas as pd

from ..base import SingleFunctionTransformation, Transformation, fit_noop


class DateTimeFeature(Enum):
    second = "second"
    minute = "minute"
    hour = "hour"
    day_of_week = "day_of_week"
    day_of_month = "day_of_month"
    day_of_year = "day_of_year"
    week = "week"
    week_of_year = "week_of_year"
    month = "month"
    quarter = "quarter"
    year = "year"

    @staticmethod
    def from_str(value: Union[str, DateTimeFeature]) -> DateTimeFeature:
        if isinstance(value, DateTimeFeature):
            return value
        for strategy in DateTimeFeature:
            if strategy.value == value:
                return strategy
        else:
            raise ValueError(f"Unknown DateTimeFeature: {value}")


class AddDateTimeFeatures(Transformation):
    """
    Adds (potentially multiple) date/time features to the input, as additional columns.
    The name of the new column will be the name of the DateTimeFeature passed in.
    Values are returned as integers, so the 59th minute of the hour will be `59`, and year 2022 will be `2022`.

    Parameters
    ----------

    features: List[Union[DateTimeFeature, str]]
        The features to add to the input. Options: `second`, `minute`, `hour`, `day_of_week`, `day_of_month`, `day_of_year`, `week`, `week_of_year`, `month`, `quarter`, `year`.

    """

    properties = Transformation.Properties(requires_X=False)
    name = "AddDateTimeFeatures"

    def __init__(
        self,
        features: List[Union[DateTimeFeature, str]],
    ) -> None:
        self.features = [DateTimeFeature(f) for f in features]

    def transform(self, X: pd.DataFrame, in_sample: bool) -> pd.DataFrame:
        X_datetime = pd.DataFrame([], index=X.index)
        for feature in self.features:
            if feature == DateTimeFeature.second:
                X_datetime[feature.value] = X.index.second
            elif feature == DateTimeFeature.minute:
                X_datetime[feature.value] = X.index.minute
            elif feature == DateTimeFeature.hour:
                X_datetime[feature.value] = X.index.hour
            elif feature == DateTimeFeature.day_of_week:
                X_datetime[feature.value] = X.index.dayofweek
            elif feature == DateTimeFeature.day_of_month:
                X_datetime[feature.value] = X.index.day
            elif feature == DateTimeFeature.day_of_year:
                X_datetime[feature.value] = X.index.dayofyear
            elif (
                feature == DateTimeFeature.week
                or feature == DateTimeFeature.week_of_year
            ):
                X_datetime[feature.value] = pd.Index(
                    X.index.isocalendar().week, dtype="int"
                )
            elif feature == DateTimeFeature.month:
                X_datetime[feature.value] = X.index.month
            elif feature == DateTimeFeature.quarter:
                X_datetime[feature.value] = X.index.quarter
            elif feature == DateTimeFeature.year:
                X_datetime[feature.value] = X.index.year
            else:
                raise ValueError(f"Unsupported feature: {feature}")
        return pd.concat([X, X_datetime], axis="columns")

    fit = fit_noop
    update = fit_noop


class AddSecond(SingleFunctionTransformation):
    name = "AddSecond"

    def get_function(self) -> Callable:
        return lambda X: X.index.second


class AddMinute(SingleFunctionTransformation):
    name = "AddMinute"

    def get_function(self) -> Callable:
        return lambda X: X.index.second


class AddHour(SingleFunctionTransformation):
    name = "AddHour"

    def get_function(self) -> Callable:
        return lambda X: X.index.hour


class AddDayOfWeek(SingleFunctionTransformation):
    name = "AddDayOfWeek"

    def get_function(self) -> Callable:
        return lambda X: X.index.dayofweek


class AddDayOfMonth(SingleFunctionTransformation):
    name = "AddDayOfMonth"

    def get_function(self) -> Callable:
        return lambda X: X.index.day


class AddDayOfYear(SingleFunctionTransformation):
    name = "AddDayOfYear"

    def get_function(self) -> Callable:
        return lambda X: X.index.dayofyear


class AddWeek(SingleFunctionTransformation):
    name = "AddWeek"

    def get_function(self) -> Callable:
        return lambda X: pd.Index(X.index.isocalendar().week, dtype="int")


class AddWeekOfYear(SingleFunctionTransformation):
    name = "AddWeekOfYear"

    def get_function(self) -> Callable:
        return lambda X: pd.Index(X.index.isocalendar().week, dtype="int")


class AddMonth(SingleFunctionTransformation):
    name = "AddMonth"

    def get_function(self) -> Callable:
        return lambda X: X.index.month


class AddQuarter(SingleFunctionTransformation):
    name = "AddQuarter"

    def get_function(self) -> Callable:
        return lambda X: X.index.quarter


class AddYear(SingleFunctionTransformation):
    name = "AddYear"

    def get_function(self) -> Callable:
        return lambda X: X.index.year
