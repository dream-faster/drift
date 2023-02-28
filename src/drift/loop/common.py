from __future__ import annotations

from copy import deepcopy
from typing import List, Optional, Union

import pandas as pd

from ..transformations.base import Composite, Transformation, Transformations
from ..utils.checks import is_prediction


def recursively_fit_transform(
    X: pd.DataFrame,
    y: pd.Series,
    sample_weights: Optional[pd.Series],
    transformations: Transformations,
) -> pd.DataFrame:

    if isinstance(transformations, List):
        for transformation in transformations:
            X = recursively_fit_transform(X, y, sample_weights, transformation)
        return X

    elif isinstance(transformations, Composite):
        composite: Composite = transformations
        # TODO: here we have the potential to parallelize/distribute training of child transformations
        composite.before_fit(X)
        results_primary = [
            recursively_fit_transform(
                composite.preprocess_X_primary(X, index, y),
                composite.preprocess_y_primary(y),
                sample_weights,
                child_transformation,
            )
            for index, child_transformation in enumerate(
                composite.get_child_transformations_primary()
            )
        ]

        if composite.properties.primary_only_single_pipeline:
            assert len(results_primary) == 1, ValueError(
                f"Expected single output from primary transformations, got {len(results_primary)} instead."
            )
        if composite.properties.primary_requires_predictions:
            assert is_prediction(results_primary[0]), ValueError(
                "Expected predictions from primary transformations, but got something else."
            )

        secondary_transformations = composite.get_child_transformations_secondary()
        if secondary_transformations is None:
            return composite.postprocess_result_primary(results_primary)
        else:
            results_secondary = [
                recursively_fit_transform(
                    composite.preprocess_X_secondary(X, results_primary, index),
                    composite.preprocess_y_secondary(y, results_primary),
                    sample_weights,
                    child_transformation,
                )
                for index, child_transformation in enumerate(secondary_transformations)
            ]

            if composite.properties.secondary_only_single_pipeline:
                assert len(results_secondary) == 1, ValueError(
                    f"Expected single output from secondary transformations, got {len(results_secondary)} instead."
                )
            if composite.properties.secondary_requires_predictions:
                assert is_prediction(results_secondary[0]), ValueError(
                    "Expected predictions from secondary transformations, but got something else."
                )

            return composite.postprocess_result_secondary(
                results_primary, results_secondary
            )

    elif isinstance(transformations, Transformation):
        if len(X) == 0:
            return pd.DataFrame()
        transformations.fit(X, y, sample_weights)
        return transformations.transform(X)

    else:
        raise ValueError(
            f"{transformations} is not a Drift Transformation, but of type {type(transformations)}"
        )


def recursively_transform(
    X: pd.DataFrame,
    transformations: Transformations,
) -> pd.DataFrame:

    if isinstance(transformations, List):
        for transformation in transformations:
            X = recursively_transform(X, transformation)
        return X

    elif isinstance(transformations, Composite):
        composite: Composite = transformations
        # TODO: here we have the potential to parallelize/distribute training of child transformations
        results_primary = [
            recursively_transform(
                composite.preprocess_X_primary(X, index, y=None),
                child_transformation,
            )
            for index, child_transformation in enumerate(
                composite.get_child_transformations_primary()
            )
        ]
        secondary_transformations = composite.get_child_transformations_secondary()

        if secondary_transformations is None:
            return composite.postprocess_result_primary(results_primary)
        else:
            results_secondary = [
                recursively_transform(
                    composite.preprocess_X_secondary(X, results_primary, index),
                    child_transformation,
                )
                for index, child_transformation in enumerate(secondary_transformations)
            ]
            return composite.postprocess_result_secondary(
                results_primary, results_secondary
            )

    elif isinstance(transformations, Transformation):
        if len(X) == 0:
            return pd.DataFrame()
        else:
            return transformations.transform(X)

    else:
        raise ValueError(
            f"{transformations} is not a Drift Transformation, but of type {type(transformations)}"
        )


def deepcopy_transformations(
    transformation: Union[
        Transformation, Composite, List[Union[Transformation, Composite]]
    ]
) -> Union[Transformation, Composite, List[Union[Transformation, Composite]]]:
    if isinstance(transformation, List):
        return [deepcopy_transformations(t) for t in transformation]
    elif isinstance(transformation, Composite):
        return transformation.clone(deepcopy_transformations)
    else:
        return deepcopy(transformation)
