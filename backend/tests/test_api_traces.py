"""API 端点测试。"""
from app.models import Event, EventType, TraceCreate


def test_create_and_get_trace(client):
    payload = TraceCreate(
        name="test-agent",
        input={"messages": [{"role": "user", "content": "hi"}]},
        output={"result": "hello"},
        events=[
            Event(run_id="r1", event_type=EventType.CHAIN_START, name="agent"),
        ],
    )
    resp = client.post("/api/v1/traces", json=payload.model_dump(mode="json"))
    assert resp.status_code == 201
    trace_id = resp.json()["trace_id"]

    get_resp = client.get(f"/api/v1/traces/{trace_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test-agent"
    assert len(get_resp.json()["events"]) == 1


def test_list_traces(client):
    for i in range(3):
        client.post("/api/v1/traces", json=TraceCreate(name=f"t{i}").model_dump(mode="json"))
    resp = client.get("/api/v1/traces?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_trace_not_found(client):
    resp = client.get("/api/v1/traces/missing")
    assert resp.status_code == 404


def test_delete_trace(client):
    resp = client.post("/api/v1/traces", json=TraceCreate(name="x").model_dump(mode="json"))
    tid = resp.json()["trace_id"]
    del_resp = client.delete(f"/api/v1/traces/{tid}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/traces/{tid}").status_code == 404


def test_count_traces(client):
    client.post("/api/v1/traces", json=TraceCreate(name="a").model_dump(mode="json"))
    resp = client.get("/api/v1/traces/count/total")
    assert resp.json()["count"] >= 1
