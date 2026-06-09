from unittest.mock import MagicMock

from src.infrastructure.langfuse.prompt_repository import LangfusePromptRepository


def _template(compiled="PROMPT", version=3, is_fallback=False):
    template = MagicMock()
    template.version = version
    template.is_fallback = is_fallback
    template.labels = ["production"]
    template.commit_message = "msg"
    template.compile.return_value = compiled
    return template


def test_compile_returns_rendered_prompt_and_passes_variables():
    client = MagicMock()
    client.get_prompt.return_value = _template(compiled="rendered")
    repo = LangfusePromptRepository(client=client, prompt_name="architectural-review")

    out = repo.compile({"repository": "org/repo"})

    assert out == "rendered"
    client.get_prompt.assert_called_once_with(
        "architectural-review", cache_ttl_seconds=60
    )
    client.get_prompt.return_value.compile.assert_called_once_with(repository="org/repo")


def test_compile_warns_when_template_is_fallback(mocker):
    client = MagicMock()
    client.get_prompt.return_value = _template(is_fallback=True)
    log = mocker.patch("src.infrastructure.langfuse.prompt_repository.logger")
    repo = LangfusePromptRepository(client=client, prompt_name="x", cache_ttl_seconds=5)

    repo.compile({})

    client.get_prompt.assert_called_once_with("x", cache_ttl_seconds=5)
    log.warning.assert_called_once()


def test_compile_sets_prompt_version_on_recording_span(mocker):
    client = MagicMock()
    client.get_prompt.return_value = _template(version=7)
    span = MagicMock()
    span.is_recording.return_value = True
    mocker.patch(
        "src.infrastructure.langfuse.prompt_repository.trace.get_current_span",
        return_value=span,
    )
    repo = LangfusePromptRepository(client=client, prompt_name="x")

    repo.compile({})

    span.set_attribute.assert_called_once_with("prompt_version", "7")
