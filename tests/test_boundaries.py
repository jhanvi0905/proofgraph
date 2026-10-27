"""Blind checker boundaries. No network."""

import ast
import json
from pathlib import Path
from typing import Any, Mapping, get_args, get_type_hints

import pytest

from proofgraph.clients.checker import CheckerError, WordingAnswer, blind_wording
from proofgraph.clients.muse import ExtractionFailed, MissingApiKeyError, MuseClient
from proofgraph.config import load_settings
from proofgraph.schema import Case, ClaimProgram

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
PROMPT = ROOT / "prompts" / "blind_wording.md"
ENGINE = ROOT / "proofgraph" / "engine"
_PASSAGE = "<<one quote or one clause>>"
_SENTENCE = "<<one plain sentence>>"


def _settings(tmp_path, **env: str):
    base = {"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)}
    base.update(env)
    return load_settings(base)


def _envelope(text: str) -> dict[str, Any]:
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": "muse-spark-1.3",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
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


def _use(monkeypatch: pytest.MonkeyPatch, client: MuseClient) -> None:
    monkeypatch.setattr(
        "proofgraph.clients.checker.MuseClient",
        lambda *args, **kwargs: client,
    )


def _client(tmp_path, transport: FakeTransport, **env: str) -> MuseClient:
    return MuseClient(_settings(tmp_path, **env), transport=transport)


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
    transport = FakeTransport([_envelope(json.dumps({"answer": "entails"}))])
    _use(monkeypatch, _client(tmp_path, transport))

    assert blind_wording(quote, statement) == "entails"

    assert transport.calls == 1
    body = transport.bodies[0]
    assert set(body) == {"model", "input", "reasoning", "text"}
    assert body["model"] == "muse-spark-1.3"
    assert body["reasoning"] == {"effort": "medium"}
    assert set(body["text"]) == {"format"}
    assert set(body["text"]["format"]) == {"type", "name", "schema"}
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["name"] == "WordingAnswer"
    assert body["text"]["format"]["schema"] == WordingAnswer.model_json_schema()
    assert set(body["text"]["format"]["schema"]["properties"]) == {"answer"}
    assert "response_format" not in body
    assert "strict" not in body["text"]["format"]
    assert "test-key" not in json.dumps(body)

    expected = (
        template[: template.find(_PASSAGE)]
        + quote
        + template[template.find(_PASSAGE) + len(_PASSAGE) : template.find(_SENTENCE)]
        + statement
        + template[template.find(_SENTENCE) + len(_SENTENCE) :]
    )
    assert body["input"] == expected
    assert body["input"].count(quote) == 1
    assert body["input"].count(statement) == 1
    assert _PASSAGE not in body["input"]
    assert _SENTENCE not in body["input"]

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
            _envelope("not json"),
            _envelope(json.dumps({"answer": "contradicts"})),
            _envelope(json.dumps({"answer": "entails"})),
        ]
    )
    _use(monkeypatch, _client(tmp_path, transport))

    assert blind_wording("The dock is closed.", "The dock is open.") == "contradicts"

    assert transport.calls == 2
    assert transport.bodies[1]["input"].startswith(transport.bodies[0]["input"])
    assert transport.bodies[1]["model"] == transport.bodies[0]["model"]
    assert "not json" in transport.bodies[1]["input"]


def test_second_malformed_reply_is_extraction_failed(tmp_path, monkeypatch):
    transport = FakeTransport(
        [
            _envelope("not json"),
            _envelope("{still"),
            _envelope(json.dumps({"answer": "entails"})),
        ]
    )
    _use(monkeypatch, _client(tmp_path, transport))

    with pytest.raises(CheckerError, match="EXTRACTION_FAILED") as caught:
        blind_wording("The dock is closed.", "The dock is open.")

    assert caught.value.reason_code == "EXTRACTION_FAILED"
    assert isinstance(caught.value.__cause__, ExtractionFailed)
    assert transport.calls == 2


def test_missing_key_does_not_call_transport(tmp_path, monkeypatch):
    transport = FakeTransport([_envelope(json.dumps({"answer": "not_mentioned"}))])
    client = MuseClient(load_settings({"CACHE_DIR": str(tmp_path)}), transport=transport)
    _use(monkeypatch, client)

    with pytest.raises(CheckerError, match="MODEL_API_KEY") as caught:
        blind_wording("The dock is closed.", "The dock is open.")

    assert caught.value.reason_code == "CHECKER_UNAVAILABLE"
    assert isinstance(caught.value.__cause__, MissingApiKeyError)
    assert transport.calls == 0
    assert list(tmp_path.glob("*.json")) == []


def test_blank_quote_does_not_construct_a_client(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("muse constructed")

    monkeypatch.setattr("proofgraph.clients.checker.MuseClient", _boom)

    with pytest.raises(CheckerError, match="quote") as caught:
        blind_wording("  ", "The dock is open.")

    assert caught.value.reason_code == "CHECKER_UNAVAILABLE"


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
