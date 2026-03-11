"""Reusable Click option decorators for CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click

from rebalancer.cli_defaults import DEFAULT_CONFIG, DEFAULT_POSITIONS


F = TypeVar("F", bound=Callable[..., Any])


def with_config_option(*, exists: bool = True) -> Callable[[F], F]:
    return click.option(
        "--config",
        type=click.Path(exists=exists, path_type=Path),
        default=DEFAULT_CONFIG,
        show_default=True,
        help="Path to portfolio YAML config.",
    )


def with_positions_option(*, exists: bool = True) -> Callable[[F], F]:
    return click.option(
        "--positions",
        type=click.Path(exists=exists, path_type=Path),
        default=DEFAULT_POSITIONS,
        show_default=True,
        help="Path to current positions YAML file.",
    )


def with_output_option(*, default: Path, help_text: str) -> Callable[[F], F]:
    return click.option(
        "--output",
        type=click.Path(path_type=Path),
        default=default,
        show_default=True,
        help=help_text,
    )


def with_start_date_option(*, help_text: str) -> Callable[[F], F]:
    return click.option(
        "--start",
        required=True,
        type=click.DateTime(formats=["%Y-%m-%d"]),
        help=help_text,
    )


def with_end_date_option(*, help_text: str) -> Callable[[F], F]:
    return click.option(
        "--end",
        required=True,
        type=click.DateTime(formats=["%Y-%m-%d"]),
        help=help_text,
    )
