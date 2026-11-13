"""Общие HTTP-контракты для permission_classes (все ORM)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional


def assert_unauthenticated_forbidden(client, endpoint: str) -> None:
    assert client.get(endpoint).status_code == 403


def assert_owner_list_is_scoped(client, endpoint: str, headers_user_2: Dict[str, str], own_title: str) -> None:
    listed = client.get(endpoint, headers=headers_user_2).json()
    titles = {row["title"] for row in listed}
    assert titles == {own_title}


def assert_foreign_owner_id_is_404(
    client,
    endpoint: str,
    foreign_id: Any,
    headers_user_2: Dict[str, str],
) -> None:
    base = f"{endpoint}/{foreign_id}"
    assert client.get(base, headers=headers_user_2).status_code == 404
    assert client.patch(base, json={"title": "hack"}, headers=headers_user_2).status_code == 404
    assert client.delete(base, headers=headers_user_2).status_code == 404


def assert_post_binds_current_owner(
    client,
    endpoint: str,
    headers_user_2: Dict[str, str],
    *,
    owner_key: str = "user_id",
) -> int:
    payload = {"title": "new", owner_key: 1}
    created = client.post(endpoint, json=payload, headers=headers_user_2)
    assert created.status_code == 200, created.text
    body = created.json()
    item_id = body["id"]
    owned = client.get(f"{endpoint}/{item_id}", headers=headers_user_2)
    assert owned.status_code == 200, owned.text
    # Созданная запись доступна владельцу, чужому пользователю — 404 (не 403).
    assert client.get(f"{endpoint}/{item_id}", headers={"X-User-Id": "1"}).status_code == 404
    return item_id


def assert_staff_sees_all(
    client,
    endpoint: str,
    owned: Mapping[str, int],
    headers_staff: Dict[str, str],
) -> None:
    titles = {row["title"] for row in client.get(endpoint, headers=headers_staff).json()}
    assert titles == set(owned.keys())
    assert client.get(f"{endpoint}/{owned[next(iter(owned))]}", headers=headers_staff).status_code == 200


def assert_plain_viewset_has_no_auth_gate(client, endpoint: str, item_id: Any) -> None:
    assert client.get(endpoint).status_code == 200
    assert client.get(f"{endpoint}/{item_id}").status_code == 200
