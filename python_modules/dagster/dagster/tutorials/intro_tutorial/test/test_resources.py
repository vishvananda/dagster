from dagster import execute_pipeline, ReentrantInfo
from dagster.tutorials.intro_tutorial.resources import (
    define_resource_test_pipeline,
)


def has_message(events, message):
    for event in events:
        if message == event.user_message:
            return True

    return False


def test_run_local():
    events = []

    def _event_callback(ev):
        events.append(ev)

    result = execute_pipeline(
        define_resource_test_pipeline(),
        environment={
            'context': {'local': {}},
            'solids': {
                'add_ints': {
                    'inputs': {
                        'num_one': {'value': 2},
                        'num_two': {'value': 3},
                    }
                }
            },
        },
        reentrant_info=ReentrantInfo(event_callback=_event_callback),
    )

    assert result.success
    assert result.result_for_solid('add_ints').transformed_value() == 5

    assert has_message(events, 'Setting key=add value=5 in memory')
    assert not has_message(events, 'Setting key=add value=5 in cloud')


def test_run_cloud():
    events = []

    def _event_callback(ev):
        events.append(ev)

    result = execute_pipeline(
        define_resource_test_pipeline(),
        environment={
            'context': {
                'cloud': {
                    'resources': {
                        'store': {
                            'config': {
                                'username': 'some_user',
                                'password': 'some_password',
                            }
                        }
                    }
                }
            },
            'solids': {
                'add_ints': {
                    'inputs': {
                        'num_one': {'value': 2},
                        'num_two': {'value': 6},
                    }
                }
            },
        },
        reentrant_info=ReentrantInfo(event_callback=_event_callback),
    )

    assert result.success
    assert result.result_for_solid('add_ints').transformed_value() == 8

    assert not has_message(events, 'Setting key=add value=8 in memory')
    assert has_message(events, 'Setting key=add value=8 in cloud')