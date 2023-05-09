# Copyright (c) 2022 - Present Myalo UG (haftungbeschränkt) (Mark Aron Szulyovszky, Daniel Szemerey) <info@dreamfaster.ai>. All rights reserved. See LICENSE in root folder.


from __future__ import annotations

from typing import Callable, List, Optional, Union

import pandas as pd

from ..base import Composite, Pipelines, Transformation, Tunable
from ..utils.list import wrap_in_list


class SelectBest(Composite, Tunable):
    properties = Composite.Properties()
    selected_: Optional[int] = None

    def __init__(
        self,
        choose_from: List[Union[Transformation, Composite]],
    ) -> None:
        self.choose_from = choose_from
        for i in self.choose_from:
            if hasattr(i, "ger_params_to_try"):
                assert i.get_params_to_try() is None, ValueError(
                    "Cannot optimize SelectBest with a child that has params_to_try defined."
                )
        self.name = "SelectBest"

    @classmethod
    def from_cloned_instance(
        cls,
        choose_from: List[Union[Transformation, Composite]],
        selected_: Optional[int],
    ) -> SelectBest:
        instance = cls(choose_from)
        instance.selected_ = selected_
        return instance

    def postprocess_result_primary(
        self, results: List[pd.DataFrame], y: Optional[pd.Series]
    ) -> pd.DataFrame:
        return results[0]

    def get_child_transformations_primary(self) -> Pipelines:
        return wrap_in_list(
            self.choose_from[self.selected_ if self.selected_ is not None else 0]
        )

    def clone(self, clone_children: Callable) -> SelectBest:
        return SelectBest.from_cloned_instance(
            choose_from=clone_children(self.choose_from), selected_=self.selected_
        )

    def get_params(self) -> dict:
        return {"selected_": self.selected_}

    def get_params_to_try(self) -> Optional[dict]:
        return {"selected_": list(range(len(self.choose_from)))}

    def clone_with_params(
        self, parameters: dict, clone_children: Optional[Callable] = None
    ) -> Tunable:
        assert clone_children is not None
        return SelectBest.from_cloned_instance(
            choose_from=clone_children(self.choose_from),
            selected_=parameters["selected_"],
        )
