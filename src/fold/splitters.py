from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class Split:
    model_index: int
    train_window_start: int
    train_window_end: int
    test_window_start: int
    test_window_end: int


class Splitter:
    def splits(self, length: int) -> List[Split]:
        raise NotImplementedError


def translate_float_if_needed(window_size: Union[int, float], length: int) -> int:
    if window_size > 1 and type(window_size) is int:
        return window_size
    elif window_size < 1 and type(window_size) is float:
        return int(window_size * length)
    else:
        raise ValueError(
            "Invalid window size, should be either a float less than 1 or an int"
            " greater than 1"
        )


class SlidingWindowSplitter(Splitter):
    def __init__(
        self,
        train_window_size: Union[int, float],
        step: Union[int, float],
        embargo: int = 0,
        start: int = 0,
        end: Optional[int] = None,
    ) -> None:
        self.window_size = train_window_size
        self.step = step
        self.embargo = embargo
        self.start = start
        self.end = end

    def splits(self, length: int) -> List[Split]:
        end = self.end if self.end is not None else length
        window_size = translate_float_if_needed(self.window_size, length)
        step = translate_float_if_needed(self.step, length)
        return [
            Split(
                model_index=index,
                train_window_start=index - window_size,
                train_window_end=index - self.embargo,
                test_window_start=index,
                test_window_end=min(end, index + step),
            )
            for index in range(self.start + window_size, end, step)
        ]


class ExpandingWindowSplitter(Splitter):
    def __init__(
        self,
        train_window_size: Union[int, float],
        step: Union[int, float],
        embargo: int = 0,
        start: int = 0,
        end: Optional[int] = None,
    ) -> None:
        self.window_size = train_window_size
        self.step = step
        self.embargo = embargo
        self.start = start
        self.end = end

    def splits(self, length: int) -> List[Split]:
        end = self.end if self.end is not None else length
        window_size = translate_float_if_needed(self.window_size, length)
        step = translate_float_if_needed(self.step, length)

        return [
            Split(
                model_index=index,
                train_window_start=self.start,
                train_window_end=index - self.embargo,
                test_window_start=index,
                test_window_end=min(end, index + step),
            )
            for index in range(self.start + window_size, end, step)
        ]


class SingleWindowSplitter(Splitter):
    def __init__(
        self,
        train_window_size: Union[int, float],
        embargo: int = 0,
    ) -> None:
        self.window_size = train_window_size
        self.embargo = embargo

    def splits(self, length: int) -> List[Split]:
        window_size = translate_float_if_needed(self.window_size, length)

        return [
            Split(
                model_index=0,
                train_window_start=0,
                train_window_end=window_size - self.embargo,
                test_window_start=window_size,
                test_window_end=length,
            ),
        ]
