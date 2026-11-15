from enum import Enum


class State(str, Enum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    APPROVED = "APPROVED"
    NEEDS_HUMAN = "NEEDS_HUMAN"
    FAILED = "FAILED"


TERMINAL = {State.APPROVED, State.NEEDS_HUMAN, State.FAILED}

TRANSITIONS = {
    State.PENDING: {State.GENERATING},
    State.GENERATING: {State.VALIDATING},
    State.VALIDATING: {State.REVIEWING, State.REVISION_REQUIRED, State.NEEDS_HUMAN},
    State.REVIEWING: {State.APPROVED, State.REVISION_REQUIRED, State.NEEDS_HUMAN},
    State.REVISION_REQUIRED: {State.GENERATING, State.NEEDS_HUMAN},
}


class IllegalTransition(Exception):
    pass


class Machine:
    def __init__(self):
        self.state = State.PENDING
        self.history = [State.PENDING]

    def to(self, new):
        if new != State.FAILED and new not in TRANSITIONS.get(self.state, set()):
            raise IllegalTransition(f"{self.state.value} -> {new.value}")
        if self.state in TERMINAL:
            raise IllegalTransition(f"{self.state.value} is terminal")
        self.state = new
        self.history.append(new)
