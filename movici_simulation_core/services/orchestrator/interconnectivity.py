from __future__ import annotations
import typing as t


class IPubSubFilter(t.Protocol):
    name: str
    pub: dict
    sub: dict
    subscribers: t.List[IPubSubFilter]


def format_matrix(models: t.Sequence[IPubSubFilter], title="", match="X"):
    """
    title   |0|1|2|3|
    model_0 | |X|X|X|
    model_1 | | | |X|
    model_2 | | | |X|
    model_10| | | | |
    """
    first_column_size = max([len(model.name) for model in models] + [len(title)])
    box_size = 1 if len(models) < 11 else 2  # Too lazy for logarithms

    def header_row():
        return first_column(title) + "".join(box(num) for num in range(len(models)))

    def model_row(model):
        return first_column(model.name) + "".join(
            box(match if sub in model.subscribers else "") for sub in models
        )

    def first_column(val: t.Any = ""):
        return f"{val: <{first_column_size}}|"

    def box(val: t.Any = ""):
        return f"{val: >{box_size}}|"

    return "\n".join([header_row()] + [model_row(model) for model in models])
