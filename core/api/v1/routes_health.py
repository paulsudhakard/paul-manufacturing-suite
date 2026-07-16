from core.api.app import ApiContext, Request


def health(context: ApiContext, request: Request) -> tuple[int, dict]:
    return 200, {"status": "ok", "correlation_id": request.correlation_id}
