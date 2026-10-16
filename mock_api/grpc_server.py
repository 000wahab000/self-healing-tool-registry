"""Small unary gRPC drift fixture with reflection and rich validation errors."""

from __future__ import annotations

from typing import Any

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

SERVICE = "mock.UserService"


def _file(mutation: str | None) -> descriptor_pb2.FileDescriptorProto:
    file = descriptor_pb2.FileDescriptorProto(
        name="mock_user.proto", package="mock", syntax="proto3"
    )
    user_id = "customer_id" if mutation == "M1" else "user_id"
    user_type = 5 if mutation == "M2" else 9
    request = file.message_type.add(name="LookupRequest")
    request.field.add(name=user_id, number=2 if mutation == "M1" else 1, label=1, type=user_type)
    response = file.message_type.add(name="LookupResponse")
    response.field.add(name="user_id", number=1, label=1, type=9)
    response.field.add(name="name", number=2, label=1, type=9)
    service = file.service.add(name="UserService")
    method = service.method.add(name="Lookup")
    method.input_type = ".mock.LookupRequest"
    method.output_type = ".mock.LookupResponse"
    return file


async def create_server(mutation: str | None = None) -> tuple[Any, descriptor_pool.DescriptorPool]:
    """Create (but do not start) a grpc.aio server and its descriptor pool."""
    import grpc
    from google.rpc import code_pb2, error_details_pb2, status_pb2
    from grpc_reflection.v1alpha import reflection
    from grpc_status import rpc_status

    if mutation not in (None, "M1", "M2"):
        raise ValueError("mutation must be M1, M2, or None")
    pool = descriptor_pool.DescriptorPool()
    pool.Add(_file(mutation))
    request_class = message_factory.GetMessageClass(pool.FindMessageTypeByName("mock.LookupRequest"))
    response_class = message_factory.GetMessageClass(pool.FindMessageTypeByName("mock.LookupResponse"))
    identifier = "customer_id" if mutation == "M1" else "user_id"

    async def lookup(request, context):
        value = getattr(request, identifier)
        if not value:
            detail = error_details_pb2.BadRequest()
            detail.field_violations.add(field=identifier, reason="required")
            status = status_pb2.Status(code=code_pb2.INVALID_ARGUMENT, message="invalid request")
            status.details.add().Pack(detail)
            await context.abort_with_status(rpc_status.to_status(status))
        uid = str(value)
        if uid not in {"123", "456"}:
            await context.abort(grpc.StatusCode.NOT_FOUND, "user not found")
        return response_class(user_id=uid, name={"123": "Ada", "456": "Bob"}[uid])

    server = grpc.aio.server()
    handler = grpc.unary_unary_rpc_method_handler(
        lookup,
        request_deserializer=request_class.FromString,
        response_serializer=lambda response: response.SerializeToString(),
    )
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(SERVICE, {"Lookup": handler}),))
    reflection.enable_server_reflection((SERVICE, reflection.SERVICE_NAME), server, pool=pool)
    return server, pool
