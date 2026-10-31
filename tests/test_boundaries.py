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
    paths = [
        ROOT / "proofgraph" / "propose.py",
        ROOT / "proofgraph" / "pipeline.py",
        ROOT / "proofgraph" / "__main__.py",
    ]
    paths.extend(ENGINE.rglob("*.py"))
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"answer", "gold_evidence"}


def test_review_check_stays_blind_and_pure():
    path = ROOT / "proofgraph" / "review" / "check.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned = ("proofgraph.review.relate", "proofgraph.clients.muse", "gold", "packs")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
        for name in names:
            assert not any(b in name for b in banned), name
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"answer", "gold_evidence", "why", "doc", "page"}


# ---------------------------------------------------------------------------
# R-17: gold and answers never reach the product or a model request.
# ---------------------------------------------------------------------------

import builtins  # noqa: E402
import io  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

from PIL import Image  # noqa: E402

from proofgraph.clients.muse import MuseClient  # noqa: E402
from proofgraph.review.check import check_cards  # noqa: E402
from proofgraph.review.ingest import ingest  # noqa: E402
from proofgraph.review.models import Card, Part  # noqa: E402
from proofgraph.review.run import run_review  # noqa: E402
from proofgraph.review.scan import transcribe  # noqa: E402
from proofgraph.review.split import split  # noqa: E402

PRODUCT = ROOT / "proofgraph"
REVIEW = PRODUCT / "review"
PACKS_PY = REVIEW / "packs.py"
# The one path allowed the literal "ground_truth": LEAK_FIELDS there lists field
# names to STRIP, which is the opposite of reading gold. Nothing else is exempt.
LEAK_LIST_PY = PRODUCT / "adapters" / "base.py"
FORBIDDEN_IDENTS = re.compile(r"^(load_gold|Gold\w*|Solutions|ground_truth|GROUND_TRUTH)$")
FORBIDDEN_TEXT = ("ground_truth", "Solutions", "pack.json", "_Evaluation", "annotation_sets", "load_gold")
FORBIDDEN_PATH = ("ground_truth", "Solutions", "pack.json", "_Evaluation", "annotation_sets", "handoff-2026-10-31")
SENTINEL = "SENTINEL-7f3a9c-GOLD-DO-NOT-LEAK"
RUN_PDF = ROOT / "tests" / "fixtures" / "text_span_rate.pdf"
CLAIM = "Detention is paid at $100.00 per hour."


def _resolved_imports(path: Path) -> set[str]:
    """Absolute dotted names a file imports, relative imports resolved."""
    package = list(path.relative_to(ROOT).with_suffix("").parts[:-1])
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - (node.level - 1)] if node.level else []
            module = ".".join(base + ([node.module] if node.module else []))
            names.add(module)
            names.update(f"{module}.{a.name}" for a in node.names)
    return names


def _mentions(path: Path) -> list[str]:
    """Forbidden identifiers, attribute names, imported names and string literals."""
    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        idents: list[str] = []
        if isinstance(node, ast.Name):
            idents = [node.id]
        elif isinstance(node, ast.Attribute):
            idents = [node.attr]
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            idents = [node.name]
        elif isinstance(node, ast.arg):
            idents = [node.arg]
        elif isinstance(node, ast.alias):
            idents = [node.name.split(".")[-1], node.asname or ""]
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found += [f"string:{t}" for t in FORBIDDEN_TEXT if t in node.value]
        found += [i for i in idents if FORBIDDEN_IDENTS.match(i)]
    if path == LEAK_LIST_PY:
        found = [f for f in found if f != "string:ground_truth"]
    return found


def _product_files() -> list[Path]:
    return [p for p in sorted(PRODUCT.rglob("*.py")) if p != PACKS_PY]


def test_only_packs_py_mentions_gold_or_ground_truth():
    assert _product_files()
    for path in _product_files():
        assert _mentions(path) == [], path.relative_to(ROOT)


def test_ground_truth_exemption_covers_only_the_leak_list_file(tmp_path: Path):
    planted = tmp_path / "other.py"
    planted.write_text('KEYS = ("ground_truth",)\n', encoding="utf-8")
    assert _mentions(planted) == ["string:ground_truth"]
    siblings = [p for p in LEAK_LIST_PY.parent.glob("*.py") if p != LEAK_LIST_PY]
    assert siblings
    for sibling in siblings:
        assert _mentions(sibling) == [], sibling.name
    assert LEAK_LIST_PY.read_text(encoding="utf-8").count("ground_truth") >= 1


def test_no_product_module_imports_packs():
    for path in _product_files():
        names = _resolved_imports(path)
        assert not any(n.startswith("proofgraph.review.packs") for n in names), path.name
    for name in ("run", "relate", "split", "scan", "check", "snap"):
        assert (REVIEW / f"{name}.py").exists(), name


def test_check_imports_neither_relate_nor_muse_resolved():
    names = _resolved_imports(REVIEW / "check.py")
    assert not any(n.startswith(("proofgraph.review.relate", "proofgraph.clients.muse")) for n in names)


def test_engine_imports_no_proposer_resolved():
    for path in ENGINE.rglob("*.py"):
        names = _resolved_imports(path)
        assert not any(
            n.startswith(("proofgraph.propose", "proofgraph.clients.muse", "proofgraph.pipeline"))
            for n in names
        ), path.name


# --- runtime: fake pack with planted gold, recorded requests -----------------

_GOLD_FIELDS = {
    "gold": SENTINEL + "-gold",
    "note": SENTINEL + "-note",
    "expected_verdict": SENTINEL + "-verdict",
    "ground_truth": SENTINEL + "-gt",
}


def _fake_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "packs" / "frt-99"
    (pack / "upload").mkdir(parents=True)
    shutil.copy(RUN_PDF, pack / "upload" / "rate_conf.pdf")
    (pack / "pack.json").write_text(json.dumps({"id": "frt-99", **_GOLD_FIELDS}), encoding="utf-8")
    (pack / "ground_truth").mkdir()
    (pack / "ground_truth" / "gold.json").write_text(
        json.dumps({"version": "gold-1", "parts": [{"note": SENTINEL + "-gold-note"}]}), encoding="utf-8"
    )
    (pack / "Solutions").mkdir()
    (pack / "Solutions" / "a.txt").write_text(SENTINEL + "-solution", encoding="utf-8")
    return pack


class _Opened:
    def __init__(self) -> None:
        self.paths: list[str] = []


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> _Opened:
    rec = _Opened()

    def wrap(fn):
        def inner(target, *args, **kwargs):
            if isinstance(target, (str, bytes, os.PathLike)):
                rec.paths.append(os.fsdecode(target))
            return fn(target, *args, **kwargs)

        return inner

    monkeypatch.setattr(builtins, "open", wrap(builtins.open))
    monkeypatch.setattr(io, "open", wrap(io.open))
    monkeypatch.setattr(os, "listdir", wrap(os.listdir))
    monkeypatch.setattr(os, "scandir", wrap(os.scandir))
    monkeypatch.setattr(os, "open", wrap(os.open))
    return rec


class _Muse:
    """Fake Muse transport and files transport; records every request."""

    def __init__(self, *payloads: dict) -> None:
        self._responses = [self._envelope(p) for p in payloads]
        self.bodies: list[dict[str, Any]] = []
        self.uploads: list[bytes] = []

    @staticmethod
    def _envelope(payload: dict) -> dict[str, Any]:
        return {
            "id": "r", "object": "response", "status": "completed", "model": "muse-spark-1.3",
            "output": [{"id": "m", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]}],
        }

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        return self._responses.pop(0)


class _Files:
    def __init__(self, sink: _Muse) -> None:
        self._sink = sink

    def create(self, *, filename: str, content: bytes, purpose: str) -> dict[str, Any]:
        self._sink.uploads.append(content)
        return {"id": "file_1"}


def _full_offline_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rec: _Opened | None = None):
    pack = _fake_pack(tmp_path)
    if rec is not None:
        rec.paths.clear()  # setup wrote the planted files; only product reads count
    pdf = pack / "upload" / "rate_conf.pdf"
    doc_id = ingest([pdf])[0].doc_id
    quote = "Detention: $75.00/hour after 2 hours free time"
    muse = _Muse(
        {"parts": [{"text": CLAIM}]},
        {"relation": "contradicts", "weakener_type": "magnitude", "quote": quote, "doc": doc_id,
         "page": 1, "why": "The rate is $75.00 an hour."},
        {"lines": [{"text": "Guard check-in 09:18", "box": [10, 10, 500, 40]}]},
    )
    cache = tmp_path / "cache"
    settings = load_settings({"MODEL_API_KEY": "k", "CACHE_DIR": str(cache), "SPEND_LIMIT_USD": "0"})
    client = MuseClient(settings, transport=muse, files_transport=_Files(muse))

    assert [p.text for p in split(CLAIM, client)] == [CLAIM]
    # run_review streams events since R-15; drain them. A stub checker keeps this offline: the
    # blind-check request body is recorded below through check_cards.
    result = list(run_review(CLAIM, [pdf], client, checker=lambda quote, part: "entails"))[-1].result
    buf = io.BytesIO()
    Image.new("L", (40, 60), 220).save(buf, format="PNG")
    transcribe(buf.getvalue(), client)

    checker = FakeTransport([_chat(json.dumps({"answer": "contradicts"}))])
    _use(monkeypatch, _client(cache, checker))
    cards = check_cards(result.review.cards, result.review.parts)
    return muse, checker, cache, cards


def test_sentinel_never_reaches_any_request_prompt_or_cache(tmp_path, monkeypatch, opened):
    muse, checker, cache, cards = _full_offline_run(tmp_path, monkeypatch)

    assert len(muse.bodies) == 3 and checker.calls == 1 and cards[0].check == "agrees"
    wire = json.dumps(muse.bodies) + json.dumps(checker.bodies)
    for token in (SENTINEL, *_GOLD_FIELDS.values(), "gold-1", "frt-99", "ground_truth", "Solutions"):
        assert token not in wire, token
    for content in muse.uploads:
        assert SENTINEL.encode() not in content
    for prompt in (ROOT / "prompts").glob("*.md"):
        assert SENTINEL not in prompt.read_text(encoding="utf-8"), prompt.name
    cached = list(cache.rglob("*"))
    assert cached
    for item in cached:
        assert SENTINEL not in item.name
        if item.is_file():
            assert SENTINEL not in item.read_text(encoding="utf-8", errors="ignore")


def test_run_never_opens_gold_or_pack_files(tmp_path, monkeypatch, opened):
    _full_offline_run(tmp_path, monkeypatch, opened)

    assert any(p.endswith("rate_conf.pdf") for p in opened.paths)  # the recorder works
    for path in opened.paths:
        assert not any(token in path for token in FORBIDDEN_PATH), path


def test_importing_the_product_opens_no_gold_path():
    modules = [
        ".".join(p.relative_to(ROOT).with_suffix("").parts).removesuffix(".__init__")
        for p in _product_files()
    ]
    script = (
        "import builtins, io, os, sys, importlib\n"
        "seen = []\n"
        "def wrap(fn):\n"
        "    def inner(t, *a, **k):\n"
        "        if isinstance(t, (str, bytes, os.PathLike)): seen.append(os.fsdecode(t))\n"
        "        return fn(t, *a, **k)\n"
        "    return inner\n"
        "builtins.open = wrap(builtins.open); io.open = wrap(io.open)\n"
        "os.listdir = wrap(os.listdir); os.scandir = wrap(os.scandir)\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module(name)\n"
        f"bad = [p for p in seen if any(t in p for t in {FORBIDDEN_PATH!r})]\n"
        "print('BAD', bad)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


# --- checker blindness over a multi-card run ---------------------------------

def test_checker_body_is_exactly_quote_and_part_for_every_card(tmp_path, monkeypatch):
    template = PROMPT.read_text(encoding="utf-8").strip()
    parts = [
        Part(id="P1", text="Part one says rates apply.", span=(0, 26), status="supported"),
        Part(id="P2", text="Part two says fees were waived.", span=(0, 31), status="supported"),
    ]
    cards = [
        Card(id="card-A", part="P1", relation="supports", quote="QUOTE-ALPHA text.", doc="doc-alpha.pdf",
             page=3, box_status="pinned", why="WHY-ALPHA", check="not_run"),
        Card(id="card-B", part="P1", relation="weakens", weakener_type="scope", quote="QUOTE-BETA text.",
             doc="doc-beta.pdf", page=4, box_status="pinned", why="WHY-BETA", check="not_run"),
        Card(id="card-C", part="P2", relation="contradicts", quote="QUOTE-GAMMA text.", doc="doc-gamma.pdf",
             page=5, box_status="unpinned", why="WHY-GAMMA", check="not_run"),
    ]
    transport = FakeTransport([_chat(json.dumps({"answer": "entails"}))] * 3)
    _use(monkeypatch, _client(tmp_path, transport))

    check_cards(cards, parts)

    assert transport.calls == 3
    texts = {p.id: p.text for p in parts}
    expected = {template.replace(_PASSAGE, c.quote).replace(_SENTENCE, texts[c.part]) for c in cards}
    sent = set()
    for body in transport.bodies:
        assert set(body) == {"model", "messages", "response_format"}
        assert len(body["messages"]) == 1 and body["messages"][0]["role"] == "user"
        sent.add(body["messages"][0]["content"])
        content = body["messages"][0]["content"]
        for c in cards:
            for hidden in (c.id, c.doc, c.why, c.relation, c.weakener_type):
                if hidden and hidden not in template:
                    assert hidden not in content, hidden
    assert sent == expected
