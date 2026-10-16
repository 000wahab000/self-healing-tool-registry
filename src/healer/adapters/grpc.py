"""Unary gRPC adapter and machine-readable status normalization."""

from __future__ import annotations

from typing import Any

from google.protobuf import descriptor as pb_descriptor
from google.protobuf import json_format
from google.rpc import error_details_pb2

from healer.models import ErrorClass, Outcome, Side, Violation

_E1 = {"CANCELLED", "DEADLINE_EXCEEDED", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "INTERNAL"}
_E2 = {"INVALID_ARGUMENT", "NOT_FOUND", "ALREADY_EXISTS", "FAILED_PRECONDITION", "OUT_OF_RANGE"}
_E5 = {"UNAUTHENTICATED", "PERMISSION_DENIED"}
_TYPE_MAP = {
    1: (int, float), 2: (int, float), 3: (int,), 4: (int,), 5: (int,),
    6: (int,), 7: (int,), 8: (bool,), 9: (str,), 12: (str,), 13: (int,),
    15: (int,), 16: (int,), 17: (int,), 18: (int,),
}
_INTEGER_TYPES = {3, 4, 5, 6, 7, 13, 15, 16, 17, 18}
_FLOAT_TYPES = {1, 2}


def _violations(exc: Exception) -> list[Violation]:
    try:
        from grpc_status import rpc_status

        status = rpc_status.from_call(exc)
        if status is None:
            return []
        result = []
        for detail in status.details:
            if detail.Is(error_details_pb2.BadRequest.DESCRIPTOR):
                bad_request = error_details_pb2.BadRequest()
                detail.Unpack(bad_request)
                result.extend(
                    Violation(Side.REQ, ["body", *item.field.split(".")], "invalid")
                    for item in bad_request.field_violations
                    if item.field
                )
        return result
    except (ImportError, AttributeError, TypeError, ValueError):
        return []


def classify(response: Any, exc: Exception | None = None) -> Outcome:
    if exc is not None:
        code = exc.code().name if callable(getattr(exc, "code", None)) else "UNKNOWN"
        cls = (
            ErrorClass.E1 if code in _E1 else ErrorClass.E2 if code in _E2
            else ErrorClass.E5 if code in _E5 else ErrorClass.BUSINESS
        )
        return Outcome(cls, "grpc", code, violations=_violations(exc))
    return Outcome(ErrorClass.OK, "grpc", "OK", data=response)


def _request_violations(body: dict, descriptor: pb_descriptor.Descriptor) -> list[Violation]:
    violations = []
    fields = {field.name: field for field in descriptor.fields}
    for name, value in body.items():
        field = fields.get(name)
        if field is None:
            violations.append(Violation(Side.REQ, ["body", name], "unknown"))
            continue
        expected = _TYPE_MAP.get(field.type)
        if field.type == pb_descriptor.FieldDescriptor.TYPE_ENUM:
            valid = isinstance(value, str)
        elif field.is_repeated:
            valid = isinstance(value, list)
        else:
            valid = expected is None or isinstance(value, expected)
            if field.type in _INTEGER_TYPES:
                valid = isinstance(value, int) and not isinstance(value, bool)
            elif field.type in _FLOAT_TYPES:
                valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        if not valid:
            violations.append(Violation(Side.REQ, ["body", name], "type"))
    return violations


async def send(
    channel: Any,
    doc: dict,
    timeout: float,
    request_class: type,
    response_class: type,
) -> Outcome:
    """Send one unary call; classes come from the reflected request descriptor."""
    try:
        request_descriptor = request_class.DESCRIPTOR
        violations = _request_violations(doc["body"], request_descriptor)
        if violations:
            return Outcome(ErrorClass.E2, "grpc", "INVALID_ARGUMENT", violations=violations)
        request = json_format.ParseDict(doc["body"], request_class())
        method = channel.unary_unary(
            doc["route"]["path"],
            request_serializer=lambda value: value.SerializeToString(),
            response_deserializer=response_class.FromString,
        )
        response = await method(request, timeout=timeout)
        return classify(json_format.MessageToDict(response, preserving_proto_field_name=True))
    except Exception as exc:
        # gRPC call errors carry a status code; invalid local documents are not gRPC failures.
        if callable(getattr(exc, "code", None)):
            return classify(None, exc)
        raise
