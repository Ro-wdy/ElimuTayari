from app.llm_client import AnthropicLlmClient, StubLlmClient


def test_stub_records_calls_and_replays_replies_in_order():
    stub = StubLlmClient(replies=["first", "second"])
    assert stub.complete("sys", "one") == "first"
    assert stub.complete("sys", "two") == "second"
    assert stub.complete("sys", "three") == "second"  # queue dry: last repeats
    assert stub.calls == [("sys", "one"), ("sys", "two"), ("sys", "three")]


def test_real_client_defers_sdk_setup_until_first_call():
    # Constructing the client must not import or initialize the SDK, so the
    # app can start without an Anthropic key configured.
    client = AnthropicLlmClient("")
    assert client._client is None


def test_app_wires_injected_client(client, llm_stub):
    assert client.app.state.llm_client is llm_stub
