"""POST /v1/jobs — accepts a job submission, validates the geometry
payload structurally (interface-level only — see core/geometry/validator.py
for what that does and doesn't check), and stores an interim JobRecord
(core/jobs/store.py; not the full TDD §12 Job schema, which arrives with
the Workflow Engine).
"""

from core.api.app import ApiContext, Request
from core.exceptions import ValidationException
from core.geometry import geometry_from_dict, geometry_to_dict, validate_geometry_dict_or_raise


def create_job(context: ApiContext, request: Request) -> tuple[int, dict]:
    body = request.json_body
    if not isinstance(body, dict):
        raise ValidationException("Request body must be a JSON object")

    product_type = body.get("product_type")
    if not isinstance(product_type, str) or not product_type:
        raise ValidationException("product_type is required and must be a non-empty string")

    geometry_payload = body.get("geometry")
    validate_geometry_dict_or_raise(geometry_payload)
    geometry = geometry_from_dict(geometry_payload)

    record = context.job_store.create(product_type=product_type, geometry=geometry)

    context.log_writer.log(
        "INFO",
        f"Job {record.job_id} received for product_type={product_type}",
        component="api.jobs",
        correlation_id=request.correlation_id,
        job_id=record.job_id,
    )

    return 201, {
        "job_id": record.job_id,
        "product_type": record.product_type,
        "status": record.status,
        "created_at": record.created_at,
        "geometry": geometry_to_dict(record.geometry),
        "correlation_id": request.correlation_id,
    }
