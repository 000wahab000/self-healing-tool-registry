from __future__ import annotations

import pytest

grpc = pytest.importorskip("grpc")
pytest.importorskip("grpc_reflection")
pytest.importorskip("grpc_status")
pytest.importorskip("google.rpc")

from healer.adapters.grpc import send
from healer.grpc_loader import grpc_source, message_class
from healer.models import ErrorClass
from mock_api.grpc_server import SERVICE, create_server


@pytest.fixture
async def grpc_api():
    server, _ = await create_server()
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel
    finally:
        await channel.close()
        await server.stop(None)


@pytest.mark.asyncio
async def test_ac_38_grpc_healthy(grpc_api):
    spec = await grpc_source(grpc_api)()
    operation = spec.ops[f"{SERVICE}.Lookup"]
    req = message_class(spec_pool(spec), "mock.LookupRequest")
    resp = message_class(spec_pool(spec), "mock.LookupResponse")
    result = await send(grpc_api, {"route": {"path": operation["path"]}, "body": {"user_id": "123"}}, 1, req, resp)
    assert result.cls == ErrorClass.OK
    assert result.data == {"user_id": "123", "name": "Ada"}


@pytest.mark.asyncio
async def test_grpc_source_without_reflection_raises_value_error():
    server = grpc.aio.server()
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        with pytest.raises(ValueError):
            await grpc_source(channel)()
    finally:
        await channel.close()
        await server.stop(None)


@pytest.mark.asyncio
@pytest.mark.parametrize(("mutation", "body", "field", "kind"), [("M1", {"user_id": "123"}, "user_id", "unknown"), ("M2", {"user_id": "123"}, "user_id", "type")])
async def test_ac_38_grpc_mutation_bad_request(mutation, body, field, kind):
    server, pool = await create_server(mutation)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        spec = await grpc_source(channel)()
        operation = spec.ops[f"{SERVICE}.Lookup"]
        expected_field = "customer_id" if mutation == "M1" else "user_id"
        expected_type = "integer" if mutation == "M2" else "string"
        assert spec.ops[f"{SERVICE}.Lookup"]["body_schema"]["properties"][expected_field]["type"] == expected_type
        req = message_class(pool, "mock.LookupRequest")
        resp = message_class(pool, "mock.LookupResponse")
        # The adapter fails closed on unknown and type-shifted base fields.
        result = await send(channel, {"route": {"path": operation["path"]}, "body": body}, 1, req, resp)
        assert result.cls == ErrorClass.E2
        assert result.violations[0].path == ["body", field]
        assert result.violations[0].kind == kind
        # Empty input reaches the mock and exercises rich google.rpc.BadRequest details.
        detailed = await send(channel, {"route": {"path": operation["path"]}, "body": {}}, 1, req, resp)
        assert detailed.cls == ErrorClass.E2
        assert detailed.violations[0].path == ["body", "customer_id" if mutation == "M1" else "user_id"]
    finally:
        await channel.close()
        await server.stop(None)


def spec_pool(spec):
    # Reflection source exposes its canonical descriptor snapshot; tests resolve classes from that snapshot.
    from google.protobuf import descriptor_pb2, descriptor_pool

    pool = descriptor_pool.DescriptorPool()
    pending = [descriptor_pb2.FileDescriptorProto.FromString(bytes.fromhex(raw)) for raw in spec.raw["descriptors"]]
    for descriptor in pending:
        pool.Add(descriptor)
    return pool
