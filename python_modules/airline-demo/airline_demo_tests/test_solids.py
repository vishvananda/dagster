"""Unit and pipeline tests for the airline_demo.

As is common in real-world pipelines, we want to test some fairly heavy-weight operations,
requiring, e.g., a connection to S3, Spark, and a database.

We lever pytest marks to isolate subsets of tests with different requirements. E.g., to run only
those tests that don't require Spark, `pytest -m "not spark"`.
"""
import logging
import os

import pyspark
import pytest

from dagster import (
    DependencyDefinition,
    ExecutionContext,
    PipelineContextDefinition,
    PipelineDefinition,
    execute_solid,
    lambda_solid,
)

from airline_demo.solids import sql_solid, download_from_s3, ingest_csv_to_spark, thunk, unzip_file
from airline_demo.pipelines import define_lambda_resource, define_tempfile_resource
from airline_demo.utils import create_s3_session, create_spark_session_local

from .marks import nettest, postgres, redshift, skip, spark


def _tempfile_context():
    return {
        'test': PipelineContextDefinition(
            context_fn=lambda info: ExecutionContext.console_logging(log_level=logging.DEBUG),
            resources={'tempfile': define_tempfile_resource()},
        )
    }


def _s3_context():
    return {
        'test': PipelineContextDefinition(
            context_fn=lambda info: ExecutionContext.console_logging(log_level=logging.DEBUG),
            resources={
                's3': define_lambda_resource(create_s3_session, signed=False),
                'tempfile': define_tempfile_resource(),
            },
        )
    }


def _spark_context():
    return {
        'test': PipelineContextDefinition(
            context_fn=lambda info: ExecutionContext.console_logging(log_level=logging.DEBUG),
            resources={'spark': define_lambda_resource(create_spark_session_local)},
        )
    }


def test_sql_solid_with_bad_materialization_strategy():
    with pytest.raises(Exception) as excinfo:
        sql_solid('foo', 'select * from bar', 'view')
    assert str(excinfo.value) == 'Invalid materialization strategy view, must be one of [\'table\']'


def test_sql_solid_without_table_name():
    with pytest.raises(Exception) as excinfo:
        sql_solid('foo', 'select * from bar', 'table')
    assert (
        str(excinfo.value) == 'Missing table_name: required for materialization strategy \'table\''
    )


def test_sql_solid():
    result = sql_solid('foo', 'select * from bar', 'table', 'quux')
    assert result
    # TODO: test execution?


def test_thunk():
    result = execute_solid(
        PipelineDefinition([thunk]),
        'thunk',
        environment_dict={'solids': {'thunk': {'config': 'foo'}}},
    )
    assert result.success
    assert result.transformed_value() == 'foo'


@nettest
def test_download_from_s3():
    result = execute_solid(
        PipelineDefinition([download_from_s3], context_definitions=_s3_context()),
        'download_from_s3',
        environment_dict={
            'context': {'test': {}},
            'solids': {
                'download_from_s3': {
                    'config': [
                        {'bucket': 'dagster-airline-demo-source-data', 'key': 'test/test_file'}
                    ]
                }
            },
        },
    )
    assert result.success
    assert result.transformed_value() == ['test/test_file']
    assert os.path.isfile(result.transformed_value()[0])
    with open(result.transformed_value()[0], 'r') as fd:
        assert fd.read() == 'test\n'


@nettest
def test_download_from_s3_tempfile():
    result = execute_solid(
        PipelineDefinition([download_from_s3], context_definitions=_s3_context()),
        'download_from_s3',
        environment_dict={
            'context': {'test': {}},
            'solids': {
                'download_from_s3': {
                    'config': [
                        {'bucket': 'dagster-airline-demo-source-data', 'key': 'test/test_file'}
                    ]
                }
            },
        },
    )
    assert result.success
    assert result.transformed_value()
    assert [not os.path.isfile(v) for v in result.transformed_value()]


def test_unzip_file_tempfile():
    @lambda_solid
    def nonce():
        return None

    result = execute_solid(
        PipelineDefinition(
            solids=[nonce, unzip_file],
            dependencies={
                'unzip_file': {
                    'archive_paths': DependencyDefinition('nonce'),
                    'archive_members': DependencyDefinition('nonce'),
                }
            },
            context_definitions=_tempfile_context(),
        ),
        'unzip_file',
        inputs={
            'archive_paths': [os.path.join(os.path.dirname(__file__), 'data/test.zip')],
            'archive_members': ['test/test_file'],
        },
        environment_dict={'solids': {'unzip_file': {'config': {'skip_if_present': False}}}},
    )
    assert result.success
    assert result.transformed_value()
    assert all([v for v in result.transformed_value()])
    assert [not os.path.isfile(v) for v in result.transformed_value()]


@spark
def test_ingest_csv_to_spark():
    @lambda_solid
    def nonce():
        return None

    result = execute_solid(
        PipelineDefinition(
            [nonce, ingest_csv_to_spark],
            dependencies={'ingest_csv_to_spark': {'input_csv': DependencyDefinition('nonce')}},
            context_definitions=_spark_context(),
        ),
        'ingest_csv_to_spark',
        inputs={'input_csv': os.path.join(os.path.dirname(__file__), 'data/test.csv')},
        environment_dict={'context': {'test': {}}},
    )
    assert result.success
    assert isinstance(result.transformed_value(), pyspark.sql.dataframe.DataFrame)
    assert result.transformed_value().head()[0] == '1'


@postgres
@skip
@spark
def test_load_data_to_postgres_from_spark_postgres():
    raise NotImplementedError()


@nettest
@redshift
@skip
@spark
def test_load_data_to_redshift_from_spark():
    raise NotImplementedError()


@skip
@spark
def test_subsample_spark_dataset():
    raise NotImplementedError()


@skip
@spark
def test_join_spark_data_frame():
    raise NotImplementedError()
