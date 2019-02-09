from dagster import check

from dagster.core.definitions import InputDefinition, Solid

from dagster.core.errors import DagsterInvariantViolationError

from .objects import (
    ExecutionPlanInfo,
    ExecutionStep,
    StepOutput,
    StepOutputHandle,
    StepOutputValue,
    StepKind,
    PlanBuilder,
)

INPUT_THUNK_OUTPUT = 'input_thunk_output'


def _create_input_thunk_execution_step(plan_builder, solid, input_def, config_value):
    check.invariant(input_def.runtime_type.input_schema)
    check.inst_param(plan_builder, 'plan_builder', PlanBuilder)

    def _fn(_context, _step, _inputs):
        value = input_def.runtime_type.input_schema.construct_from_config_value(config_value)
        yield StepOutputValue(output_name=INPUT_THUNK_OUTPUT, value=value)

    return ExecutionStep(
        key=solid.name + '.' + input_def.name + '.input_thunk',
        step_inputs=[],
        step_outputs=[StepOutput(name=INPUT_THUNK_OUTPUT, runtime_type=input_def.runtime_type)],
        compute_fn=_fn,
        kind=StepKind.INPUT_THUNK,
        solid=solid,
        tags=plan_builder.get_tags(),
    )


def create_input_thunk_execution_step(execution_info, plan_builder, solid, input_def, value):
    check.inst_param(execution_info, 'execution_info', ExecutionPlanInfo)
    check.inst_param(plan_builder, 'plan_builder', PlanBuilder)
    check.inst_param(solid, 'solid', Solid)
    check.inst_param(input_def, 'input_def', InputDefinition)

    dependency_structure = execution_info.pipeline.dependency_structure
    input_handle = solid.input_handle(input_def.name)

    if dependency_structure.has_dep(input_handle):
        raise DagsterInvariantViolationError(
            (
                'In pipeline {pipeline_name} solid {solid_name}, input {input_name} '
                'you have specified an input via config while also specifying '
                'a dependency. Either remove the dependency, specify a subdag '
                'to execute, or remove the inputs specification in the environment.'
            ).format(
                pipeline_name=execution_info.pipeline.name,
                solid_name=solid.name,
                input_name=input_def.name,
            )
        )

    input_thunk = _create_input_thunk_execution_step(plan_builder, solid, input_def, value)
    return StepOutputHandle(input_thunk, INPUT_THUNK_OUTPUT)
