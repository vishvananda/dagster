import logging
import uuid

from collections import namedtuple

import boto3

# import numpy
import pytest

import dagster.check as check
import dagster.core.types as types

from dagster import (
    DependencyDefinition,
    ExecutionContext,
    InputDefinition,
    lambda_solid,
    PipelineContextDefinition,
    PipelineDefinition,
    ExecutionMetadata,
    ResourceDefinition,
)
from dagster.core.execution import (
    create_execution_plan_core,
    create_environment_config,
    yield_pipeline_execution_context,
)
from dagma import execute_plan, define_dagma_resource


def create_lambda_context():
    return PipelineContextDefinition(
        context_fn=lambda _: ExecutionContext.console_logging(log_level=logging.DEBUG),
        resources={'dagma': define_dagma_resource()},
    )


context_definitions = {'lambda': create_lambda_context()}


@lambda_solid
def solid_a():
    return 1


@lambda_solid(inputs=[InputDefinition('arg_a')])
def solid_b(arg_a):
    return arg_a * 2


@lambda_solid(inputs=[InputDefinition('arg_a')])
def solid_c(arg_a):
    return arg_a * 3


@lambda_solid(inputs=[InputDefinition('arg_b'), InputDefinition('arg_c')])
def solid_d(arg_b, arg_c):
    return arg_b + arg_c / 2.0
    # return numpy.mean([arg_b, arg_c])
    # TODO: figure out how to deal with installing packages like numpy where the target
    # architecture on lambda is not the architecture running the pipeline


def define_diamond_dag_pipeline():
    return PipelineDefinition(
        name='actual_dag_pipeline',
        context_definitions=context_definitions,
        solids=[solid_a, solid_b, solid_c, solid_d],
        dependencies={
            'solid_b': {'arg_a': DependencyDefinition('solid_a')},
            'solid_c': {'arg_a': DependencyDefinition('solid_a')},
            'solid_d': {
                'arg_b': DependencyDefinition('solid_b'),
                'arg_c': DependencyDefinition('solid_c'),
            },
        },
    )


def define_single_solid_pipeline():
    return PipelineDefinition(
        name='single_solid_pipeline',
        context_definitions=context_definitions,
        solids=[solid_a],
        dependencies={},
    )


TEST_ENVIRONMENT = {
    'context': {'lambda': {'resources': {'dagma': {'config': {'aws_region_name': 'us-east-2'}}}}}
}


def run_test_pipeline(pipeline):
    execution_metadata = ExecutionMetadata(run_id=str(uuid.uuid4()))
    with yield_pipeline_execution_context(
        pipeline, TEST_ENVIRONMENT, execution_metadata
    ) as context:
        execution_plan = create_execution_plan_core(context)
        return execute_plan(context, execution_plan)


@pytest.mark.skip('Skipping pending pickling issues in lambda engine. Issue #491')
def test_execution_diamond():
    pipeline = define_diamond_dag_pipeline()
    results = run_test_pipeline(pipeline)

    assert len(results) == 4


@pytest.mark.skip('Skipping pending pickling issues in lambda engine. Issue #491')
def test_execution_single():
    pipeline = define_single_solid_pipeline()
    results = run_test_pipeline(pipeline)

    assert len(results) == 1
    assert results[('solid_a.transform', 'result')][0] is True
    assert results[('solid_a.transform', 'result')][1].output_name == 'result'
    assert results[('solid_a.transform', 'result')][1].value == 1
    assert results[('solid_a.transform', 'result')][2] is None
