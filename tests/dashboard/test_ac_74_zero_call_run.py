from __future__ import annotations

from copy import deepcopy

from dashboard.explorer import check_data_correctness
from mock_api.app import SEED


def test_ac_74_zero_calls_checks_full_task() -> None:
    seeded = deepcopy(SEED)

    assert check_data_correctness(seeded, None, set())[0] is False
    assert check_data_correctness(seeded, None, None)[0] is False


def test_ac_74_scoped_completed_run_is_correct() -> None:
    completed = deepcopy(SEED)
    completed["users"]["123"]["email"] = "ada.new@example.com"

    assert check_data_correctness(completed, None, {"update_email"})[0] is True
    assert check_data_correctness(completed, None)[0] is False


def test_ac_74_control_mutations_accept_seeded_state_without_calls() -> None:
    seeded = deepcopy(SEED)

    assert check_data_correctness(seeded, "C2", set())[0] is True
    assert check_data_correctness(seeded, "C3", set())[0] is True
