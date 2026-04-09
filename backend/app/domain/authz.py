from enum import Enum

class ApiRole(str, Enum):
    operator = "operator"
    observer = "observer"
    pipeline = "pipeline"


API_ROLES: set[str] = {role.value for role in ApiRole}
OBSERVER_OR_HIGHER_ROLES: set[str] = {ApiRole.operator.value, ApiRole.observer.value}
WRITER_ROLES: set[str] = {ApiRole.operator.value, ApiRole.pipeline.value}
