"""Finding a Dash page's components in a callback's JSON answer."""

from typing import Any


def find(component: Any, test: Any) -> list[Any]:
    """Every component, at any depth, that passes `test`."""
    if isinstance(component, list):
        return [c for item in component for c in find(item, test)]
    if not isinstance(component, dict):
        return []
    props = component.get("props", {})
    found = [component] if test(component) else []
    return found + find(props.get("children"), test)


def graphs(body: Any) -> dict[str, Any]:
    found = find(body, lambda c: c.get("type") == "Graph")
    return {g["props"]["id"]: g["props"]["figure"] for g in found}


def class_named(body: Any, name: str) -> list[Any]:
    return find(body, lambda c: name in (c.get("props", {}).get("className") or "").split())
