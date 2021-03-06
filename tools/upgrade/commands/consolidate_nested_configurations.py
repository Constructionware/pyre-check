# Copyright (c) 2016-present, Facebook, Inc.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from typing_extensions import Final

from ..configuration import Configuration
from ..errors import Errors
from ..filesystem import find_files
from ..repository import Repository
from .command import ErrorSuppressingCommand


LOG: logging.Logger = logging.getLogger(__name__)


class ConsolidateNestedConfigurations(ErrorSuppressingCommand):
    def __init__(self, arguments: argparse.Namespace, repository: Repository) -> None:
        super().__init__(arguments, repository)
        self._subdirectory: Final[Optional[str]] = arguments.subdirectory
        self._lint: bool = arguments.lint
        self._no_commit: bool = arguments.no_commit
        self._submit: bool = arguments.submit

    @staticmethod
    def add_arguments(parser: argparse.ArgumentParser) -> None:
        ErrorSuppressingCommand.add_arguments(parser)
        parser.set_defaults(command=ConsolidateNestedConfigurations)
        parser.add_argument("--subdirectory")
        parser.add_argument("--lint", action="store_true", help=argparse.SUPPRESS)
        parser.add_argument(
            "--no-commit", action="store_true", help="Keep changes in working state."
        )
        parser.add_argument("--submit", action="store_true", help=argparse.SUPPRESS)

    def gather_nested_configuration_mapping(
        self, configurations: List[str]
    ) -> Dict[str, List[str]]:
        nested_configurations = {}
        for configuration in configurations:
            if len(nested_configurations) == 0:
                nested_configurations[configuration] = []
                continue
            inserted = False
            for topmost_configuration in nested_configurations.keys():
                existing = topmost_configuration.replace(
                    "/.pyre_configuration.local", ""
                )
                current = configuration.replace("/.pyre_configuration.local", "")
                if current.startswith(existing):
                    nested_configurations[topmost_configuration].append(configuration)
                    inserted = True
                    break
                elif existing.startswith(current):
                    nested_configurations[configuration] = nested_configurations[
                        topmost_configuration
                    ] + [topmost_configuration]
                    del nested_configurations[topmost_configuration]
                    inserted = True
                    break
            if not inserted:
                nested_configurations[configuration] = []
        return nested_configurations

    def consolidate(self, topmost: Path, nested: List[Path]) -> None:
        total_targets = []
        for nested_configuration in nested:
            with open(nested_configuration) as configuration_file:
                configuration = Configuration(
                    nested_configuration, json.load(configuration_file)
                )
                targets = configuration.targets
                if targets:
                    total_targets.extend(targets)
        with open(topmost) as configuration_file:
            configuration = Configuration(topmost, json.load(configuration_file))
            configuration.add_targets(total_targets)
            configuration.deduplicate_targets()
            configuration.write()
        self._repository.remove_paths(nested)

        # Suppress errors
        all_errors = configuration.get_errors()
        for _, errors in all_errors:
            self._suppress_errors(Errors(list(errors)))

    def run(self) -> None:
        subdirectory = self._subdirectory
        subdirectory = Path(subdirectory) if subdirectory else Path.cwd()

        # Find configurations
        configurations = sorted(find_files(subdirectory, ".pyre_configuration.local"))
        if not configurations:
            LOG.warning(
                f"Skipping consolidation. No configurations found in {subdirectory}"
            )
            return
        if len(configurations) == 1:
            configuration = configurations[0]
            LOG.warning(
                f"Skipping consolidation. Only one configuration found: {configuration}"
            )
            return

        # Gather nesting structure of configurations
        nested_configurations = self.gather_nested_configuration_mapping(configurations)

        # Consolidate targets
        for topmost, nested in nested_configurations.items():
            if len(nested) == 0:
                continue
            self.consolidate(
                Path(topmost), [Path(configuration) for configuration in nested]
            )

        self._repository.submit_changes(
            commit=(not self._no_commit),
            submit=self._submit,
            title=f"Consolidate configurations in {subdirectory}",
            summary="Consolidating nested configurations.",
            set_dependencies=False,
        )
