#  Copyright (c) ZenML GmbH 2020. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""CLI to interact with pipelines."""
import types
from typing import Any, Optional

import click

from zenml.cli import utils as cli_utils
from zenml.cli.cli import cli
from zenml.config.config_keys import (
    PipelineConfigurationKeys,
    StepConfigurationKeys,
)
from zenml.exceptions import PipelineConfigurationError
from zenml.logger import get_logger
from zenml.repository import Repository
from zenml.utils import source_utils, yaml_utils

logger = get_logger(__name__)


def _get_module_attribute(module: types.ModuleType, attribute_name: str) -> Any:
    """Gets an attribute from a module.

    Args:
        module: The module to load the attribute from.
        attribute_name: Name of the attribute to load.

    Returns:
        The attribute value.

    Raises:
        PipelineConfigurationError: If the module does not have an attribute
            with the given name.
    """
    try:
        return getattr(module, attribute_name)
    except AttributeError:
        raise PipelineConfigurationError(
            f"Unable to load '{attribute_name}' from"
            f" file '{module.__file__}'"
        ) from None


@cli.group()
def pipeline() -> None:
    """Pipeline group"""


@pipeline.command("run", help="Run a pipeline with the given configuration.")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
)
@click.argument("python_file")
def run_pipeline(python_file: str, config_path: str) -> None:
    """Runs pipeline specified by the given config YAML object.

    Args:
        python_file: Path to the python file that defines the pipeline.
        config_path: Path to configuration YAML file.
    """
    module = source_utils.import_python_file(python_file)
    config = yaml_utils.read_yaml(config_path)
    PipelineConfigurationKeys.key_check(config)

    pipeline_name = config[PipelineConfigurationKeys.NAME]
    pipeline_class = _get_module_attribute(module, pipeline_name)

    steps = {}
    for step_name, step_config in config[
        PipelineConfigurationKeys.STEPS
    ].items():
        StepConfigurationKeys.key_check(step_config)
        step_class = _get_module_attribute(
            module, step_config[StepConfigurationKeys.SOURCE_]
        )
        step_instance = step_class()
        materializers_config = step_config.get(
            StepConfigurationKeys.MATERIALIZERS_, None
        )
        if materializers_config:
            # We need to differentiate whether it's a single materializer
            # or a dictionary mapping output names to materializers
            if isinstance(materializers_config, str):
                materializers = _get_module_attribute(
                    module, materializers_config
                )
            elif isinstance(materializers_config, dict):
                materializers = {
                    output_name: _get_module_attribute(module, source)
                    for output_name, source in materializers_config.items()
                }
            else:
                raise PipelineConfigurationError(
                    f"Only `str` and `dict` values are allowed for "
                    f"'materializers' attribute of a step configuration. You "
                    f"tried to pass in `{materializers_config}` (type: "
                    f"`{type(materializers_config).__name__}`)."
                )
            step_instance = step_instance.with_return_materializers(
                materializers
            )

        steps[step_name] = step_instance

    pipeline_instance = pipeline_class(**steps).with_config(
        config_path, overwrite_step_parameters=True
    )
    logger.debug("Finished setting up pipeline '%s' from CLI", pipeline_name)
    pipeline_instance.run()


@pipeline.command("list", help="List all pipelines in the current stack.")
@click.option("--project", type=str)
@click.option("--stack", "-s", type=str)
def list_pipelines(
    project: Optional[str] = None, stack: Optional[str] = None
) -> None:
    """List all pipelines in the active stack's metadata store."""
    cli_utils.print_active_profile()
    repo = Repository()
    if project is not None:
        try:
            repo.zen_store.get_project(project)
        except KeyError:
            cli_utils.error(f"No such project: '{project}'")
    pipelines = repo.get_pipelines(stack_name=stack, project=project)
    table = [{"ID": str(p._id), "NAME": p._name} for p in pipelines]
    if table:
        cli_utils.print_table(table)
    else:
        for_project = f" for project '{project}'" if project is not None else ""
        cli_utils.declare(f"No pipelines found{for_project}.")


@pipeline.group("runs")
def pipeline_runs() -> None:
    """Information about pipeline runs."""


@pipeline_runs.command("list", help="Help")
@click.argument("pipeline", required=False)
@click.option("--stack", "-s", type=str)
def list_runs(
    pipeline: Optional[str] = None, stack: Optional[str] = None
) -> None:
    """List all pipeline runs in the active stack's metadata store."""
    cli_utils.print_active_profile()
    repo = Repository()
    if pipeline is not None:
        pipeline_view = repo.get_pipeline(pipeline, stack_name=stack)
        if pipeline_view is None:
            cli_utils.error(f"No pipeline named {pipeline} found.")
        table = [
            {"PIPELINE": pipeline, "RUN": n}
            for n in pipeline_view.get_run_names()
        ]
    else:
        table = [
            {"PIPELINE": p._name, "RUN": n}
            for p in repo.get_pipelines()
            for n in p.get_run_names()
        ]
    if table:
        cli_utils.print_table(table)
    else:
        for_pipeline = "" if pipeline is None else f" for pipeline '{pipeline}'"
        cli_utils.declare(f"No pipeline runs found{for_pipeline}.")
