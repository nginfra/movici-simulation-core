from __future__ import annotations

import typing as t


class IPubSubFilter(t.Protocol):
    name: str
    pub: dict
    sub: dict
    subscribers: t.List[IPubSubFilter]


def format_matrix(models: t.Sequence[IPubSubFilter], title="", match="X"):
    """
    ::

        title     |0|1|2|3|
        0|model_0 | |X|X|X|
        1|model_1 | | | |X|
        2|model_2 | | | |X|
        3|model_10| | | | |
    """
    box_size = 1 if len(models) < 11 else 2  # Too lazy for logarithms
    prefix_size = box_size + 1
    first_column_size = max([len(model.name) for model in models] + [len(title)]) + prefix_size
    model_nums = {model.name: idx for idx, model in enumerate(models)}

    def header_row():
        return first_column(title) + "".join(box(num) for num in model_nums.values())

    def model_row(model):
        return first_column(box(model_nums[model.name]) + model.name) + "".join(
            box(match if sub in model.publishes_to else "") for sub in models
        )

    def first_column(val: t.Any = ""):
        return f"{val: <{first_column_size}}|"

    def box(val: t.Any = ""):
        return f"{val: >{box_size}}|"

    return "\n".join([header_row()] + [model_row(model) for model in models])
