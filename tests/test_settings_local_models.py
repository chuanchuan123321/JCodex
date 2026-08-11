"""Settings persistence and local-model discovery for the desktop app."""

from __future__ import annotations

from agent.ui.desktop import main as desktop


def test_custom_system_prompt_env_round_trip(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    desktop._write_env_file(
        env_file,
        {
            "api_base_url": "https://api.deepseek.com",
            "api_model": "deepseek-v4-pro",
            "custom_system_prompt": "你是助手\n请简洁回答",
        },
    )

    raw = desktop._read_env_file(env_file)
    assert raw["CUSTOM_SYSTEM_PROMPT"] == "你是助手\\n请简洁回答"

    monkeypatch.setattr(desktop, "DATA_ROOT", tmp_path)
    settings = desktop.load_settings()
    assert settings["custom_system_prompt"] == "你是助手\n请简洁回答"


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {}

    def json(self) -> dict:
        return self._payload


def test_list_local_models_via_openai_compatible(monkeypatch) -> None:
    def fake_get(url, timeout):
        assert url == "http://localhost:11434/v1/models"
        return _FakeResponse(
            200, {"data": [{"id": "llama3:8b"}, {"id": "qwen2.5:7b"}]}
        )

    monkeypatch.setattr(desktop.requests, "get", fake_get)
    result = desktop.list_local_models("http://localhost:11434")
    assert result["success"] is True
    assert [entry["name"] for entry in result["models"]] == [
        "llama3:8b",
        "qwen2.5:7b",
    ]
    assert result["base_url"] == "http://localhost:11434"


def test_list_local_models_falls_back_to_ollama_tags(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(url, timeout):
        calls.append(url)
        if url.endswith("/v1/models") or url.endswith("/models"):
            return _FakeResponse(404, {})
        return _FakeResponse(
            200,
            {"models": [{"name": "llama3:8b"}, {"name": "deepseek-r1:7b"}]},
        )

    monkeypatch.setattr(desktop.requests, "get", fake_get)
    result = desktop.list_local_models("http://localhost:11434/")
    assert result["success"] is True
    assert [entry["name"] for entry in result["models"]] == [
        "deepseek-r1:7b",
        "llama3:8b",
    ]
    assert any(url.endswith("/api/tags") for url in calls)


def test_list_local_models_llamacpp_uses_friendly_name(monkeypatch) -> None:
    calls: list[str] = []
    model_id = (
        "/Users/a1-6/Models/qwen3.5-2b-uncensored/"
        "Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
    )

    def fake_get(url, timeout):
        calls.append(url)
        if url.endswith("/v1/models"):
            return _FakeResponse(
                200,
                {
                    "object": "list",
                    "data": [{"id": model_id}],
                },
            )
        return _FakeResponse(404, {})

    monkeypatch.setattr(desktop.requests, "get", fake_get)
    result = desktop.list_local_models("http://127.0.0.1:8080")
    assert result["success"] is True
    assert result["server"] == ""
    assert result["models"][0]["id"] == model_id
    assert (
        result["models"][0]["name"]
        == "Qwen3.5-2B-Uncensored-HauhauCS-Aggressive-Q4_K_M"
    )


def test_list_local_models_rejects_non_http_address() -> None:
    result = desktop.list_local_models("localhost:11434")
    assert result["success"] is False
    assert "http" in result["error"]
