"""Blind checker boundaries. No network."""

import ast
import json
from pathlib import Path
from typing import Any, Mapping, get_args, get_type_hints

import pytest

from proofgraph.clients.checker import CheckerClient, CheckerError, blind_wording
from proofgraph.config import BASETEN_BASE_URL, DEFAULT_CHECKER_MODEL, load_settings
from proofgraph.schema import Case, ClaimProgram

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
PROMPT = ROOT / "prompts" / "blind_wording.md"
ENGINE = ROOT / "proofgraph" / "engine"
_PASSAGE = "<<one quote or one clause>>"
_SENTENCE = "<<one plain sentence>>"


def _settings(tmp_path, **env: str):
    base = {"BASETEN_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)}
    base.update(env)
    return load_settings(base)


def _chat(text: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "model": DEFAULT_CHECKER_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


class FakeTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("transport called too many times")
        return self._responses.pop(0)

    @property
    def calls(self) -> int:
        return len(self.bodies)


def _use(monkeypatch: pytest.MonkeyPatch, client: CheckerClient) -> None:
    monkeypatch.setattr(
        "proofgraph.clients.checker.CheckerClient",
        lambda *args, **kwargs: client,
    )


def _client(tmp_path, transport: FakeTransport, **env: str) -> CheckerClient:
    return CheckerClient(_settings(tmp_path, **env), transport=transport)


def test_blind_wording_signature_is_quote_and_statement():
    hints = get_type_hints(blind_wording)
    assert list(hints) == ["quote", "statement", "return"]
    assert hints["quote"] is str
    assert hints["statement"] is str
    assert get_args(hints["return"]) == ("entails", "contradicts", "not_mentioned")
    parameters = blind_wording.__code__.co_varnames[: blind_wording.__code__.co_argcount]
    assert parameters == ("quote", "statement")
    with pytest.raises(TypeError):
        blind_wording("A quote.", "A statement.", "extra")  # type: ignore[misc]


def test_blind_request_is_one_quote_and_one_statement(tmp_path, monkeypatch):
    payload = json.loads((FIXTURES / "detention_program.json").read_text())
    case = Case.model_validate(payload["case"]).model_copy(
        update={"answer": "SUPPORTED", "gold_evidence": ["secret-gold-span"]}
    )
    program = ClaimProgram.model_validate(payload["program"])
    quote = next(source.text for source in case.sources if source.id == "rate_conf")
    statement = "The rate applies after free time."
    assert isinstance(quote, str)
    template = PROMPT.read_text(encoding="utf-8").strip()
    transport = FakeTransport([_chat(json.dumps({"answer": "entails"}))])
    _use(monkeypatch, _client(tmp_path, transport))

    assert blind_wording(quote, statement) == "entails"

    assert transport.calls == 1
    body = transport.bodies[0]
    assert set(body) == {"model", "messages", "response_format"}
    assert body["model"] == DEFAULT_CHECKER_MODEL
    assert body["model"] != "muse-spark-1.3"
    format_ = body["response_format"]
    assert format_["type"] == "json_schema"
    assert format_["json_schema"]["name"] == "WordingAnswer"
    assert format_["json_schema"]["strict"] is True
    schema = format_["json_schema"]["schema"]
    assert set(schema["properties"]) == {"answer"}
    assert schema["properties"]["answer"]["enum"] == [
        "entails",
        "contradicts",
        "not_mentioned",
    ]
    assert schema["additionalProperties"] is False
    assert "test-key" not in json.dumps(body)

    expected = (
        template[: template.find(_PASSAGE)]
        + quote
        + template[template.find(_PASSAGE) + len(_PASSAGE) : template.find(_SENTENCE)]
        + statement
        + template[template.find(_SENTENCE) + len(_SENTENCE) :]
    )
    content = body["messages"][0]["content"]
    assert body["messages"] == [{"role": "user", "content": expected}]
    assert content.count(quote) == 1
    assert content.count(statement) == 1
    assert _PASSAGE not in content
    assert _SENTENCE not in content

    wire = json.dumps(body)
    assert wire.count(quote) == 1
    assert wire.count(statement) == 1
    expr = program.links[0].expr
    assert expr is not None
    forbidden = [
        case.id,
        case.claim,
        case.answer,
        *case.gold_evidence,
        "gold_evidence",
        expr,
        "checker=fallback",
    ]
    forbidden.extend(
        source.text
        for source in case.sources
        if source.text and source.text != quote
    )
    for item in forbidden:
        assert item not in wire


def test_one_client_repair_returns_the_label(tmp_path, monkeypatch):
    transport = FakeTransport(
        [
            _chat("not json"),
            _chat(json.dumps({"answer": "contradicts"})),
            _chat(json.dumps({"answer": "entails"})),
        ]
    )
    _use(monkeypatch, _client(tmp_path, transport))

    assert blind_wording("The dock is closed.", "The dock is open.") == "contradicts"

    assert transport.calls == 2
    first = transport.bodies[0]["messages"][0]["content"]
    second = transport.bodies[1]["messages"][0]["content"]
    assert second.startswith(first)
    assert transport.bodies[1]["model"] == transport.bodies[0]["model"]
    assert "not json" in second


def test_second_malformed_reply_is_extraction_failed(tmp_path, monkeypatch):
    transport = FakeTransport(
        [
            _chat("not json"),
            _chat("{still"),
            _chat(json.dumps({"answer": "entails"})),
        ]
    )
    _use(monkeypatch, _client(tmp_path, transport))

    with pytest.raises(CheckerError, match="EXTRACTION_FAILED") as caught:
        blind_wording("The dock is closed.", "The dock is open.")

    assert caught.value.reason_code == "EXTRACTION_FAILED"
    assert transport.calls == 2


def test_missing_key_does_not_call_transport(tmp_path, monkeypatch):
    transport = FakeTransport([_chat(json.dumps({"answer": "not_mentioned"}))])
    client = CheckerClient(load_settings({"CACHE_DIR": str(tmp_path)}), transport=transport)
    _use(monkeypatch, client)

    with pytest.raises(CheckerError, match="BASETEN_API_KEY") as caught:
        blind_wording("The dock is closed.", "The dock is open.")

    assert caught.value.reason_code == "CHECKER_UNAVAILABLE"
    assert transport.calls == 0
    assert list(tmp_path.glob("*.json")) == []


def test_blank_quote_does_not_construct_a_client(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("checker constructed")

    monkeypatch.setattr("proofgraph.clients.checker.CheckerClient", _boom)

    with pytest.raises(CheckerError, match="quote") as caught:
        blind_wording("  ", "The dock is open.")

    assert caught.value.reason_code == "CHECKER_UNAVAILABLE"


def test_blind_wording_posts_chat_completions_to_baseten(tmp_path, monkeypatch):
    captured: dict[str, Any] = {}

    class _Response:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            assert mode == "json"
            return _chat(json.dumps({"answer": "entails"}))

    class _Completions:
        def create(self, **kwargs: Any) -> _Response:
            captured["kwargs"] = kwargs
            captured["api"] = "chat.completions.create"
            return _Response()

    class _Chat:
        def __init__(self) -> None:
            self.completions = _Completions()

    class _OpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["init"] = kwargs
            self.chat = _Chat()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _OpenAI)
    monkeypatch.setenv("BASETEN_API_KEY", "test-key")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("CHECKER_MODEL", raising=False)
    monkeypatch.delenv("BASETEN_BASE_URL", raising=False)

    assert blind_wording("The dock is closed.", "The dock is closed.") == "entails"

    assert captured["api"] == "chat.completions.create"
    assert captured["init"]["base_url"] == BASETEN_BASE_URL
    assert captured["init"]["base_url"] == "https://inference.baseten.co/v1"
    assert captured["init"]["max_retries"] == 0
    assert captured["init"]["api_key"] == "test-key"
    assert captured["kwargs"]["model"] == DEFAULT_CHECKER_MODEL
    assert captured["kwargs"]["model"] == "meta-models/muse-spark-open-1026"
    assert set(captured["kwargs"]) == {"model", "messages", "response_format"}
    assert "test-key" not in json.dumps(captured["kwargs"])


def test_checker_does_not_call_muse_structured():
    tree = ast.parse((ROOT / "proofgraph" / "clients" / "checker.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "muse" not in alias.name.split(".")
        elif isinstance(node, ast.ImportFrom):
            assert "muse" not in (node.module or "").split(".")
        elif isinstance(node, ast.Attribute):
            assert node.attr != "structured"


def test_cached_wording_does_not_call_transport_twice(tmp_path, monkeypatch):
    transport = FakeTransport([_chat(json.dumps({"answer": "entails"}))])
    _use(monkeypatch, _client(tmp_path, transport))

    assert blind_wording("The dock is closed.", "The dock is closed.") == "entails"
    assert blind_wording("The dock is closed.", "The dock is closed.") == "entails"

    assert transport.calls == 1


def test_engine_does_not_import_proposer_or_muse():
    for path in ENGINE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for name in modules:
                assert "propose" not in name
                assert "muse" not in name.split(".")


def test_engine_propose_and_cli_do_not_read_sealed_case_fields():
    paths = [ROOT / "proofgraph" / "propose.py", ROOT / "proofgraph" / "__main__.py"]
    paths.extend(ENGINE.rglob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"answer", "gold_evidence"}
