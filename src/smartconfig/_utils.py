"""Shared internal utilities."""

from copy import deepcopy


def deep_update(dictionaries: list[dict]) -> dict:
    """Recursively merge a list of dictionaries, left to right.

    Later dictionaries override earlier ones. When both sides of a key are
    dicts the merge recurses; otherwise the later value wins. The input
    dictionaries are not mutated.

    Parameters
    ----------
    dictionaries
        A non-empty list of dictionaries to merge. The first dictionary serves
        as the base; each subsequent dictionary is merged into it in order.

    Returns
    -------
    dict
        A new dictionary containing the deep-merged result.

    Examples
    --------
    Nested dictionaries are merged recursively rather than replaced:

    >>> deep_update([{"a": {"x": 1, "y": 2}}, {"a": {"y": 3}}])
    {'a': {'x': 1, 'y': 3}}

    """
    first = deepcopy(dictionaries[0])
    for dct in dictionaries[1:]:
        for key, value in dct.items():
            if isinstance(value, dict) and isinstance(first.get(key), dict):
                first[key] = deep_update([first[key], value])
            else:
                first[key] = value

    return first
