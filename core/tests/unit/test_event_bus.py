from core.events import Event, EventBus


def test_delivers_to_all_subscribers_at_least_once():
    bus = EventBus()
    received_a, received_b = [], []
    bus.subscribe("job.created", received_a.append)
    bus.subscribe("job.created", received_b.append)

    event = Event("job.created", {"job_id": "123"})
    errors = bus.publish(event)

    assert errors == []
    assert received_a == [event]
    assert received_b == [event]


def test_only_matching_event_type_subscribers_are_called():
    bus = EventBus()
    received = []
    bus.subscribe("job.created", received.append)

    bus.publish(Event("job.deleted", {}))

    assert received == []


def test_publish_with_no_subscribers_is_a_noop():
    bus = EventBus()
    assert bus.publish(Event("nothing.listens", {})) == []


def test_one_failing_subscriber_does_not_block_others():
    bus = EventBus()
    received = []

    def bad_handler(event):
        raise RuntimeError("subscriber exploded")

    bus.subscribe("job.created", bad_handler)
    bus.subscribe("job.created", received.append)

    errors = bus.publish(Event("job.created", {}))

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)
    assert len(received) == 1  # the good subscriber still ran
