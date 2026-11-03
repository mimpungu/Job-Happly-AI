from enum import StrEnum


class BudgetPeriod(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"
    PER_OPERATION = "per_operation"


class CallOutcome(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    INVALID_OUTPUT = "invalid_output"
    CACHE_HIT = "cache_hit"
    BLOCKED_BUDGET = "blocked_budget"
