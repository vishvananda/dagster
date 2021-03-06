import sqlalchemy as sa


from dagster import (
    DependencyDefinition,
    InputDefinition,
    PipelineContextDefinition,
    PipelineDefinition,
    execute_pipeline,
)
from dagster.utils import script_relative_path

import dagster_sqlalchemy.common
from dagster_sqlalchemy.subquery_builder_experimental import sql_file_solid


def in_mem_engine():
    engine = sa.create_engine('sqlite://', echo=False)
    return engine


def create_in_mem_context():
    return dagster_sqlalchemy.common.create_sqlalchemy_context_from_engine(engine=in_mem_engine())


def pipeline_engine(context):
    return context.resources.sa.engine


def create_persisted_context():
    full_path = script_relative_path('testdb.db')
    engine = sa.create_engine('sqlite:///{full_path}'.format(full_path=full_path), echo=False)
    return dagster_sqlalchemy.common.create_sqlalchemy_context_from_engine(engine=engine)


def create_mem_sql_pipeline_context_tuple(context, solids, dependencies=None):
    default_def = PipelineContextDefinition(context_fn=lambda _info: context)
    return PipelineDefinition(
        solids=solids, dependencies=dependencies, context_definitions={'default': default_def}
    )


def _get_sql_script_path(name):
    return script_relative_path(
        '../../dagster_sqlalchemy/examples/sql_project_example/sql_files/{name}.sql'.format(
            name=name
        )
    )


def _get_project_solid(name, inputs=None):
    return sql_file_solid(_get_sql_script_path(name), inputs=inputs)


def test_sql_create_tables():
    create_all_tables_solids = _get_project_solid('create_all_tables')

    context = create_in_mem_context()
    pipeline = create_mem_sql_pipeline_context_tuple(context, solids=[create_all_tables_solids])

    pipeline_result = execute_pipeline(pipeline, {'context': {'default': {}}})
    assert pipeline_result.success

    assert set(pipeline_engine(context).table_names()) == set(
        ['num_table', 'sum_sq_table', 'sum_table']
    )


def test_sql_populate_tables():
    create_all_tables_solids = _get_project_solid('create_all_tables')

    populate_num_table_solid = _get_project_solid(
        'populate_num_table', inputs=[InputDefinition(create_all_tables_solids.name)]
    )

    context = create_in_mem_context()
    pipeline = create_mem_sql_pipeline_context_tuple(
        context,
        solids=[create_all_tables_solids, populate_num_table_solid],
        dependencies={
            populate_num_table_solid.name: {
                create_all_tables_solids.name: DependencyDefinition(create_all_tables_solids.name)
            }
        },
    )

    pipeline_result = execute_pipeline(pipeline, {'context': {'default': {}}})

    assert pipeline_result.success

    assert pipeline_engine(context).execute('SELECT * FROM num_table').fetchall() == [
        (1, 2),
        (3, 4),
    ]


def create_full_pipeline(context):
    create_all_tables_solids = _get_project_solid('create_all_tables')

    populate_num_table_solid = _get_project_solid(
        'populate_num_table', inputs=[InputDefinition('create_all_tables_solids')]
    )

    insert_into_sum_table_solid = _get_project_solid(
        'insert_into_sum_table', inputs=[InputDefinition('populate_num_table_solid')]
    )

    insert_into_sum_sq_table_solid = _get_project_solid(
        'insert_into_sum_sq_table', inputs=[InputDefinition('insert_into_sum_sq_table')]
    )

    return create_mem_sql_pipeline_context_tuple(
        context,
        solids=[
            create_all_tables_solids,
            populate_num_table_solid,
            insert_into_sum_table_solid,
            insert_into_sum_sq_table_solid,
        ],
        dependencies={
            populate_num_table_solid.name: {
                'create_all_tables_solids': DependencyDefinition(create_all_tables_solids.name)
            },
            insert_into_sum_table_solid.name: {
                'populate_num_table_solid': DependencyDefinition(populate_num_table_solid.name)
            },
            insert_into_sum_sq_table_solid.name: {
                'insert_into_sum_sq_table': DependencyDefinition(insert_into_sum_table_solid.name)
            },
        },
    )


def test_full_in_memory_pipeline():

    context = create_in_mem_context()
    pipeline = create_full_pipeline(context)
    pipeline_result = execute_pipeline(pipeline, {'context': {'default': {}}})
    assert pipeline_result.success

    engine = pipeline_engine(context)
    assert engine.execute('SELECT * FROM num_table').fetchall() == [(1, 2), (3, 4)]
    assert engine.execute('SELECT * FROM sum_table').fetchall() == [(1, 2, 3), (3, 4, 7)]
    assert engine.execute('SELECT * FROM sum_sq_table').fetchall() == [(1, 2, 3, 9), (3, 4, 7, 49)]
