"""YAML configuration loading, profile selection, and recursive merging."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .config import AppConfig, ConfigurationConfig, default_config_dir

_DEFAULT_FILE = "config.default.yaml"


class ConfigError(RuntimeError):
    """Raised when a configuration source cannot be loaded or validated."""


def deep_merge[TMapping: Mapping[str, Any]](
    base: TMapping, override: Mapping[str, Any]
) -> dict[str, Any]:
    """Recursively merge mappings, replacing lists and scalar values wholesale."""
    merged = deepcopy(dict(base))
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, Mapping) and isinstance(override_value, Mapping):
            merged[key] = deep_merge(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def load_config(*, config_dir: Path | None = None) -> AppConfig:
    """Load the default YAML and all existing profile overlays by priority.

    ``config.default.yaml`` is mandatory and owns the complete profile registry.
    Registered profiles are sorted by ascending priority, so a larger priority
    overrides a smaller one. A missing ``config.<tag>.yaml`` is intentionally
    skipped, allowing deployments to supply only the overlays they need.
    """
    directory = config_dir or default_config_dir()
    default_data = _read_yaml(directory / _DEFAULT_FILE)
    try:
        registry = ConfigurationConfig.model_validate(
            default_data.get("configuration", {})
        ).profiles
    except ValidationError as error:
        raise ConfigError(
            f"Invalid {_DEFAULT_FILE} profile registry: {error}"
        ) from error

    merged: dict[str, Any] = default_data
    for tag in sorted(registry, key=lambda tag: registry[tag].priority):
        profile_path = directory / f"config.{tag}.yaml"
        if not profile_path.is_file():
            continue
        profile_data = _read_yaml(profile_path)
        if "configuration" in profile_data:
            raise ConfigError(
                f"{profile_path.name} cannot redefine the default-only 'configuration' section"
            )
        merged = deep_merge(merged, profile_data)

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as error:
        raise ConfigError(
            f"Invalid merged application configuration: {error}"
        ) from error


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a required YAML mapping and produce clear configuration errors."""
    if not path.is_file():
        raise ConfigError(f"Configuration file does not exist: {path}")
    try:
        with path.open(encoding="utf-8") as stream:
            loaded = yaml.safe_load(stream)
    except yaml.YAMLError as error:
        raise ConfigError(f"Invalid YAML in {path}: {error}") from error
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigError(f"Configuration root must be a mapping: {path}")
    return loaded
