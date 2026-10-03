"""Issue #67：同日稍后读取和UTC换日，显式窗口不受缺省修正影响。"""
from datetime import datetime, timedelta, timezone

from app import api_warning as module
from helpers import API, api_call
from test_spec004 import lab


def test_default_batch_survives_clock_advancing_and_matches_ui_window(lab, monkeypatch):
    now = datetime(2026,9,30,10,20,30,tzinfo=timezone.utc)
    monkeypatch.setattr(module,"_now",lambda:now)
    client, csrf = lab["teacher_a"]
    class_id = lab["class_a"]["id"]
    response = api_call(client,"post",f"{API}/warnings/generations",csrf_token=csrf,json={"class_id":class_id})
    assert response.status_code == 201
    expected = {"from":"2026-09-01T00:00:00Z","to":"2026-10-01T00:00:00Z"}
    assert response.json["data"]["window"] == expected
    monkeypatch.setattr(module,"_now",lambda:now+timedelta(seconds=5))
    read = client.get(f"{API}/warnings?class_id={class_id}")
    assert read.status_code == 200
    assert read.json["data"] == response.json["data"]["students"]
    explicit = client.get(f"{API}/warnings?class_id={class_id}&from={expected['from']}&to={expected['to']}")
    assert explicit.json["data"] == read.json["data"]


def test_utc_midnight_selects_new_window_but_old_explicit_batch_remains(lab, monkeypatch):
    client, csrf = lab["teacher_a"]
    class_id = lab["class_a"]["id"]
    monkeypatch.setattr(module,"_now",lambda:datetime(2026,9,30,23,59,59,tzinfo=timezone.utc))
    old = api_call(client,"post",f"{API}/warnings/generations",csrf_token=csrf,json={"class_id":class_id})
    monkeypatch.setattr(module,"_now",lambda:datetime(2026,10,1,0,0,0,tzinfo=timezone.utc))
    assert client.get(f"{API}/warnings?class_id={class_id}").json["data"] == []
    explicit = client.get(f"{API}/warnings?class_id={class_id}&from=2026-09-01T00:00:00Z&to=2026-10-01T00:00:00Z")
    assert explicit.json["data"] == old.json["data"]["students"]
    assert module._resolve_window(None,None) == ("2026-09-02T00:00:00Z","2026-10-02T00:00:00Z")


def test_explicit_second_precision_is_preserved(monkeypatch):
    monkeypatch.setattr(module,"_now",lambda:datetime(2026,10,4,tzinfo=timezone.utc))
    assert module._resolve_window("2026-09-01T01:02:03Z","2026-10-01T01:02:04Z") == (
        "2026-09-01T01:02:03Z","2026-10-01T01:02:04Z",
    )
