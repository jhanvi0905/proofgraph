"""Tests stay offline."""

import socket

import pytest


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network is disabled in tests")

    monkeypatch.setattr(socket, "create_connection", _blocked)
