"""An added stock-model consumer must keep its service alive."""

from scripts.watch_v5_stock_consumers import consumers_exited


def test_two_old_consumers_exiting_does_not_close_service_for_third():
    registry = {'registration_complete': True, 'consumer_jobs': [3083, 3084, 3154]}
    states = {'3083': 'COMPLETED', '3084': 'COMPLETED', '3154': 'RUNNING'}
    assert not consumers_exited(registry, states)
    states['3154'] = 'COMPLETED'
    assert consumers_exited(registry, states)


def test_missing_accounting_or_incomplete_registration_keeps_service_alive():
    registry = {'registration_complete': False, 'consumer_jobs': [3154]}
    assert not consumers_exited(registry, {'3154': 'COMPLETED'})
    registry['registration_complete'] = True
    assert not consumers_exited(registry, {})
    assert not consumers_exited(registry, {'3154': 'PENDING'})
    assert consumers_exited(registry, {'3154': 'CANCELLED by 1000'})
