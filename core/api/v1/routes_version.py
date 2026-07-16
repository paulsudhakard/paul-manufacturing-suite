import core
from core.api.app import ApiContext, Request


def version(context: ApiContext, request: Request) -> tuple[int, dict]:
    return 200, {
        "core_version": core.__version__,
        "api_version": "v1",
        "correlation_id": request.correlation_id,
    }
