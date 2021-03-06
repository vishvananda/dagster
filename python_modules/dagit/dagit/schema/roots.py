from dagit.schema import dauphin
from dagit.schema import model
from dagster.core.execution import ExecutionSelector, ExecutionMetadata
from ..version import __version__


class DauphinQuery(dauphin.ObjectType):
    class Meta:
        name = 'Query'

    version = dauphin.NonNull(dauphin.String)
    pipelineOrError = dauphin.Field(
        dauphin.NonNull('PipelineOrError'), params=dauphin.NonNull('ExecutionSelector')
    )
    pipeline = dauphin.Field(
        dauphin.NonNull('Pipeline'), params=dauphin.NonNull('ExecutionSelector')
    )
    pipelinesOrError = dauphin.NonNull('PipelinesOrError')
    pipelines = dauphin.Field(dauphin.NonNull('PipelineConnection'))

    configTypeOrError = dauphin.Field(
        dauphin.NonNull('ConfigTypeOrError'),
        pipelineName=dauphin.Argument(dauphin.NonNull(dauphin.String)),
        configTypeName=dauphin.Argument(dauphin.NonNull(dauphin.String)),
    )

    runtimeTypeOrError = dauphin.Field(
        dauphin.NonNull('RuntimeTypeOrError'),
        pipelineName=dauphin.Argument(dauphin.NonNull(dauphin.String)),
        runtimeTypeName=dauphin.Argument(dauphin.NonNull(dauphin.String)),
    )
    pipelineRuns = dauphin.non_null_list('PipelineRun')
    pipelineRun = dauphin.Field('PipelineRun', runId=dauphin.NonNull(dauphin.ID))

    isPipelineConfigValid = dauphin.Field(
        dauphin.NonNull('PipelineConfigValidationResult'),
        args={
            'pipeline': dauphin.Argument(dauphin.NonNull('ExecutionSelector')),
            'config': dauphin.Argument('PipelineConfig'),
        },
    )

    executionPlan = dauphin.Field(
        dauphin.NonNull('ExecutionPlanResult'),
        args={
            'pipeline': dauphin.Argument(dauphin.NonNull('ExecutionSelector')),
            'config': dauphin.Argument('PipelineConfig'),
        },
    )

    def resolve_configTypeOrError(self, graphene_info, **kwargs):
        return model.get_config_type(
            graphene_info, kwargs['pipelineName'], kwargs['configTypeName']
        )

    def resolve_runtimeTypeOrError(self, graphene_info, **kwargs):
        return model.get_runtime_type(
            graphene_info, kwargs['pipelineName'], kwargs['runtimeTypeName']
        )

    def resolve_version(self, _graphene_info):
        return __version__

    def resolve_pipelineOrError(self, graphene_info, **kwargs):
        return model.get_pipeline(graphene_info, kwargs['params'].to_selector())

    def resolve_pipeline(self, graphene_info, **kwargs):
        return model.get_pipeline_or_raise(graphene_info, kwargs['params'].to_selector())

    def resolve_pipelinesOrError(self, graphene_info):
        return model.get_pipelines(graphene_info)

    def resolve_pipelines(self, graphene_info):
        return model.get_pipelines_or_raise(graphene_info)

    def resolve_type(self, graphene_info, pipelineName, typeName):
        return model.get_pipeline_type(graphene_info, pipelineName, typeName)

    def resolve_pipelineRuns(self, graphene_info):
        return model.get_runs(graphene_info)

    def resolve_pipelineRun(self, graphene_info, runId):
        return model.get_run(graphene_info, runId)

    def resolve_isPipelineConfigValid(self, graphene_info, pipeline, config):
        return model.validate_pipeline_config(graphene_info, pipeline.to_selector(), config)

    def resolve_executionPlan(self, graphene_info, pipeline, config):
        return model.get_execution_plan(graphene_info, pipeline.to_selector(), config)


class DauphinStartPipelineExecutionMutation(dauphin.Mutation):
    class Meta:
        name = 'StartPipelineExecutionMutation'

    class Arguments:
        pipeline = dauphin.NonNull('ExecutionSelector')
        config = dauphin.Argument('PipelineConfig')

    Output = dauphin.NonNull('StartPipelineExecutionResult')

    def mutate(self, graphene_info, **kwargs):
        return model.start_pipeline_execution(
            graphene_info, kwargs['pipeline'].to_selector(), kwargs.get('config')
        )


class DauphinExecutionTag(dauphin.InputObjectType):
    class Meta:
        name = 'ExecutionTag'

    key = dauphin.NonNull(dauphin.String)
    value = dauphin.NonNull(dauphin.String)


class DauphinMarshalledInput(dauphin.InputObjectType):
    class Meta:
        name = 'MarshalledInput'

    input_name = dauphin.NonNull(dauphin.String)
    key = dauphin.NonNull(dauphin.String)


class DauphinMarshalledOutput(dauphin.InputObjectType):
    class Meta:
        name = 'MarshalledOutput'

    output_name = dauphin.NonNull(dauphin.String)
    key = dauphin.NonNull(dauphin.String)


class DauphinStepExecution(dauphin.InputObjectType):
    class Meta:
        name = 'StepExecution'

    stepKey = dauphin.NonNull(dauphin.String)
    marshalledInputs = dauphin.List(dauphin.NonNull(DauphinMarshalledInput))
    marshalledOutputs = dauphin.List(dauphin.NonNull(DauphinMarshalledOutput))


class DauphinExecutionMetadata(dauphin.InputObjectType):
    class Meta:
        name = 'ExecutionMetadata'

    runId = dauphin.String()
    tags = dauphin.List(dauphin.NonNull(DauphinExecutionTag))

    def to_metadata(self):
        tags = {}
        if tags:
            for tag in self.tags:  # pylint: disable=E1133
                tags[tag['key']] = tag['value']

        return ExecutionMetadata(run_id=self.runId, tags=tags)


class DauphinStartSubplanExecution(dauphin.Mutation):
    class Meta:
        name = 'StartSubplanExecution'

    class Arguments:
        pipelineName = dauphin.NonNull(dauphin.String)
        config = dauphin.Argument('PipelineConfig')
        stepExecutions = dauphin.non_null_list(DauphinStepExecution)
        executionMetadata = dauphin.Argument(dauphin.NonNull(DauphinExecutionMetadata))

    Output = dauphin.NonNull('StartSubplanExecutionResult')

    def mutate(self, graphene_info, **kwargs):
        return model.start_subplan_execution(
            model.SubplanExecutionArgs(
                graphene_info,
                kwargs['pipelineName'],
                kwargs.get('config'),
                list(
                    map(
                        lambda data: model.StepExecution(
                            data['stepKey'],
                            data.get('marshalledInputs', []),
                            data.get('marshalledOutputs', []),
                        ),
                        kwargs['stepExecutions'],
                    )
                ),
                kwargs['executionMetadata'].to_metadata(),
            )
        )


class DauphinMutation(dauphin.ObjectType):
    class Meta:
        name = 'Mutation'

    start_pipeline_execution = DauphinStartPipelineExecutionMutation.Field()
    # TODO this name should indicate that this is synchronous
    # https://github.com/dagster-io/dagster/issues/810
    start_subplan_execution = DauphinStartSubplanExecution.Field()


class DauphinSubscription(dauphin.ObjectType):
    class Meta:
        name = 'Subscription'

    pipelineRunLogs = dauphin.Field(
        dauphin.NonNull('PipelineRunLogsSubscriptionPayload'),
        runId=dauphin.Argument(dauphin.NonNull(dauphin.ID)),
        after=dauphin.Argument('Cursor'),
    )

    def resolve_pipelineRunLogs(self, graphene_info, runId, after=None):
        return model.get_pipeline_run_observable(graphene_info, runId, after)


class DauphinPipelineConfig(dauphin.GenericScalar, dauphin.Scalar):
    class Meta:
        name = 'PipelineConfig'
        description = '''This type is used when passing in a configuration object
        for pipeline configuration. This is any-typed in the GraphQL type system,
        but must conform to the constraints of the dagster config type system'''


class DauphinExecutionSelector(dauphin.InputObjectType):
    class Meta:
        name = 'ExecutionSelector'
        description = '''This type represents the fields necessary to identify a
        pipeline or pipeline subset.'''

    name = dauphin.NonNull(dauphin.String)
    solidSubset = dauphin.List(dauphin.NonNull(dauphin.String))

    def to_selector(self):
        return ExecutionSelector(self.name, self.solidSubset)
