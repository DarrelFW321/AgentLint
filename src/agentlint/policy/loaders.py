"""YAML policy loading for AgentLint policy v1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agentlint.policy.models import Policy


class PolicyLoadError(Exception):
    """Base class for policy loading errors."""


class PolicyFileError(PolicyLoadError):
    """Raised when a policy file cannot be read."""


class PolicyYamlError(PolicyLoadError):
    """Raised when a policy file is not valid YAML for AgentLint loading."""


class PolicySchemaError(PolicyLoadError):
    """Raised when a policy file is YAML but not valid AgentLint policy v1."""

    def __init__(self, validation_error: ValidationError) -> None:
        super().__init__("policy schema validation failed")
        self.validation_error = validation_error


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe PyYAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    seen: set[Any] = set()

    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        marker = key if _is_hashable(key) else repr(key)

        if marker in seen:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        seen.add(marker)

    return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)


def _is_hashable(value: object) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_policy(path: str | Path) -> Policy:
    """Load an AgentLint YAML policy from a file."""
    policy_path = Path(path)

    if policy_path.is_dir():
        raise PolicyFileError(f"policy path is a directory, not a file: {policy_path}")

    try:
        raw_text = policy_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PolicyFileError(f"policy file not found: {policy_path}") from exc
    except IsADirectoryError as exc:
        raise PolicyFileError(f"policy path is a directory, not a file: {policy_path}") from exc
    except OSError as exc:
        raise PolicyFileError(f"could not read policy file {policy_path}: {exc}") from exc

    try:
        raw_data = yaml.load(raw_text, Loader=_UniqueKeySafeLoader)
    except yaml.YAMLError as exc:
        raise PolicyYamlError(_format_yaml_error(exc)) from exc

    try:
        return Policy.model_validate(raw_data)
    except ValidationError as exc:
        raise PolicySchemaError(exc) from exc


def format_policy_validation_error(error: ValidationError) -> list[str]:
    """Format Pydantic policy validation errors without echoing raw values."""
    formatted_errors: list[str] = []

    for item in error.errors(include_url=False, include_input=False):
        location = _format_location(item.get("loc", ()))
        message = item.get("msg", "validation error")
        error_type = item.get("type", "unknown")
        formatted_errors.append(f"{location}: {message} [{error_type}]")

    return formatted_errors


def _format_yaml_error(error: yaml.YAMLError) -> str:
    problem = getattr(error, "problem", None) or str(error)
    mark = getattr(error, "problem_mark", None)

    if mark is None:
        return f"policy YAML parse failed: {problem}"

    line = mark.line + 1
    column = mark.column + 1
    return f"policy YAML parse failed at line {line}, column {column}: {problem}"


def _format_location(location: Any) -> str:
    if not isinstance(location, tuple) or not location:
        return "<root>"

    parts: list[str] = []
    for item in location:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))

    return ".".join(parts)
