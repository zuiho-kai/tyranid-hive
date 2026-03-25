"""状态机测试 —— 无需数据库"""

import pytest
from greyfield_hive.models.task import TaskState, STATE_TRANSITIONS, TERMINAL_STATES


def test_all_states_have_transitions_or_terminal():
    for state in TaskState:
        if state not in TERMINAL_STATES:
            assert state in STATE_TRANSITIONS, f"{state} 无跳转路径"


def test_terminal_states_no_outgoing():
    for state in TERMINAL_STATES:
        assert state not in STATE_TRANSITIONS or not STATE_TRANSITIONS[state]


def test_valid_transitions():
    assert TaskState.Planning in STATE_TRANSITIONS[TaskState.Incubating]
    assert TaskState.WaitingInput in STATE_TRANSITIONS[TaskState.Incubating]
    assert TaskState.Executing in STATE_TRANSITIONS[TaskState.Spawning]
    assert TaskState.Complete in STATE_TRANSITIONS[TaskState.Executing]


def test_invalid_transition_not_in_map():
    # 不能从 Complete 跳转到任何状态
    assert TaskState.Complete not in STATE_TRANSITIONS


def test_dormant_can_recover():
    # 阻塞态可以恢复到多个中间态
    assert len(STATE_TRANSITIONS[TaskState.Dormant]) >= 3


def test_waiting_input_can_resume():
    assert TaskState.WaitingInput in STATE_TRANSITIONS
    assert TaskState.Planning in STATE_TRANSITIONS[TaskState.WaitingInput]
