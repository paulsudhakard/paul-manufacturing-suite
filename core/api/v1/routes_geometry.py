from core.api.app import ApiContext, Request
from core.geometry import validate_geometry_dict


def validate_format(context: ApiContext, request: Request) -> tuple[int, dict]:
    issues = validate_geometry_dict(request.json_body)
    return 200, {
        "valid": len(issues) == 0,
        "issues": issues,
        "correlation_id": request.correlation_id,
    }
