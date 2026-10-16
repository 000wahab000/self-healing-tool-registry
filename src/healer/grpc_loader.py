"""Load unary gRPC operations through server reflection."""

from __future__ import annotations

from google.protobuf import descriptor as pb_descriptor
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

from healer.canonical import sha256
from healer.models import LoadedSpec, OperationSpec, SpecSource
from healer.settings import SPEC_FETCH_TIMEOUT_S

_SCALARS = {
    1: "number", 2: "number", 3: "integer", 4: "integer", 5: "integer",
    6: "integer", 7: "integer", 8: "boolean", 9: "string", 12: "string",
    13: "integer", 15: "integer", 16: "integer", 17: "integer", 18: "integer",
}
_REFLECTION_SERVICE = "grpc.reflection.v1alpha.ServerReflection"


def _schema(message: pb_descriptor.Descriptor) -> dict:
    properties: dict = {}
    required = []
    for field in message.fields:
        schema = (
            {"type": "object", "properties": _schema(field.message_type)["properties"]}
            if field.message_type is not None
            else {"type": _SCALARS.get(field.type, "string")}
        )
        if field.is_repeated:
            schema = {"type": "array", "items": schema}
        properties[field.name] = schema
        if field.is_required:
            required.append(field.name)
    result = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _pool(descriptors: list[bytes]) -> descriptor_pool.DescriptorPool:
    pending = [descriptor_pb2.FileDescriptorProto.FromString(item) for item in descriptors]
    pool = descriptor_pool.DescriptorPool()
    while pending:
        remaining = []
        for file_proto in pending:
            try:
                pool.Add(file_proto)
            except (KeyError, TypeError):
                remaining.append(file_proto)
        if len(remaining) == len(pending):
            raise ValueError("incomplete gRPC reflection descriptors")
        pending = remaining
    return pool


def operations(pool: descriptor_pool.DescriptorPool, services: list[str]) -> dict[str, OperationSpec]:
    result = {}
    for service_name in services:
        service = pool.FindServiceByName(service_name)
        for method in service.methods:
            if method.client_streaming or method.server_streaming:
                continue
            name = f"{service_name}.{method.name}"
            result[name] = {
                "operation_id": name,
                "method": "GRPC",
                "path": f"/{service_name}/{method.name}",
                "body_schema": _schema(method.input_type),
                "params": [],
                "security": [],
                "response_schema": _schema(method.output_type),
                "description": "",
            }
    return result


def grpc_source(channel) -> SpecSource:
    """Return a SpecSource backed by the reflection service on ``channel``."""

    async def load() -> LoadedSpec:
        stub = reflection_pb2_grpc.ServerReflectionStub(channel)

        async def requests():
            yield reflection_pb2.ServerReflectionRequest(list_services="")

        descriptors: dict[bytes, bytes] = {}
        services: list[str] = []
        try:
            async for response in stub.ServerReflectionInfo(
                requests(), timeout=SPEC_FETCH_TIMEOUT_S
            ):
                if response.HasField("error_response"):
                    raise ValueError("gRPC reflection request failed")
                if response.HasField("list_services_response"):
                    services = [
                        item.name
                        for item in response.list_services_response.service
                        if item.name != _REFLECTION_SERVICE
                    ]
                    break
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("gRPC reflection unavailable") from exc
        if not services:
            raise ValueError("gRPC reflection returned no services")

        async def descriptor_requests():
            for service in services:
                yield reflection_pb2.ServerReflectionRequest(file_containing_symbol=service)

        try:
            async for response in stub.ServerReflectionInfo(
                descriptor_requests(), timeout=SPEC_FETCH_TIMEOUT_S
            ):
                if response.HasField("error_response"):
                    raise ValueError("gRPC reflection descriptor lookup failed")
                for raw in response.file_descriptor_response.file_descriptor_proto:
                    descriptors[raw] = raw
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("gRPC reflection unavailable") from exc
        pool = _pool(list(descriptors.values()))
        ops = operations(pool, services)
        raw = {"services": services, "descriptors": sorted(v.hex() for v in descriptors.values())}
        return LoadedSpec(raw, ops, sha256(raw))

    return load


def message_class(pool: descriptor_pool.DescriptorPool, full_name: str):
    """Resolve a protobuf message class for an RPC request or response."""
    return message_factory.GetMessageClass(pool.FindMessageTypeByName(full_name))
