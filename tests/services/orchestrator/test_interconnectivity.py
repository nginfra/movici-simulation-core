import typing as t

from movici_simulation_core.services.orchestrator.context import ConnectedModel, ModelCollection
from movici_simulation_core.services.orchestrator.interconnectivity import (
    format_matrix,
)


def create_subscribed_models(subscriptions: t.Dict[str, t.List[str]]):
    models = ModelCollection(
        {
            model: ConnectedModel(
                model,
                timeline=None,
                send=None,
                pub={model: None},
                sub={sub: None for sub in subscription},
            )
            for model, subscription in subscriptions.items()
        }
    )
    models.determine_interdependency()
    return list(models.values())


def create_simple_subscribed_models(size):
    models = [f"model_{i}" for i in range(size)]

    return create_subscribed_models(
        {models[i]: ([models[i + 1]] if i < len(models) - 1 else []) for i in range(len(models))}
    )


def test_format_matrix():
    subscribed_models = create_subscribed_models({"a": ["c"], "b": ["a", "c"], "c": []})
    assert format_matrix(subscribed_models, title="title") == "\n".join(
        [
            "title|0|1|2|",
            "a    | |X| |",
            "b    | | | |",
            "c    |X|X| |",
        ]
    )


def test_format_len_10_matrix():
    subscribed_models = create_simple_subscribed_models(10)

    assert format_matrix(subscribed_models, title="title") == "\n".join(
        [
            "title  |0|1|2|3|4|5|6|7|8|9|",
            "model_0| | | | | | | | | | |",
            "model_1|X| | | | | | | | | |",
            "model_2| |X| | | | | | | | |",
            "model_3| | |X| | | | | | | |",
            "model_4| | | |X| | | | | | |",
            "model_5| | | | |X| | | | | |",
            "model_6| | | | | |X| | | | |",
            "model_7| | | | | | |X| | | |",
            "model_8| | | | | | | |X| | |",
            "model_9| | | | | | | | |X| |",
        ]
    )


def test_format_large_matrix():
    subscribed_models = create_simple_subscribed_models(11)

    assert format_matrix(subscribed_models, title="title") == "\n".join(
        [
            "title   | 0| 1| 2| 3| 4| 5| 6| 7| 8| 9|10|",
            "model_0 |  |  |  |  |  |  |  |  |  |  |  |",
            "model_1 | X|  |  |  |  |  |  |  |  |  |  |",
            "model_2 |  | X|  |  |  |  |  |  |  |  |  |",
            "model_3 |  |  | X|  |  |  |  |  |  |  |  |",
            "model_4 |  |  |  | X|  |  |  |  |  |  |  |",
            "model_5 |  |  |  |  | X|  |  |  |  |  |  |",
            "model_6 |  |  |  |  |  | X|  |  |  |  |  |",
            "model_7 |  |  |  |  |  |  | X|  |  |  |  |",
            "model_8 |  |  |  |  |  |  |  | X|  |  |  |",
            "model_9 |  |  |  |  |  |  |  |  | X|  |  |",
            "model_10|  |  |  |  |  |  |  |  |  | X|  |",
        ]
    )
