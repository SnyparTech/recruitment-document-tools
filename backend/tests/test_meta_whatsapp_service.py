import httpx
import respx

from app.services.meta_whatsapp_service import MetaWhatsAppService


def _service(**overrides):
    defaults = dict(access_token="tok", phone_number_id="12345", api_version="v19.0", base_url="https://graph.facebook.com")
    defaults.update(overrides)
    return MetaWhatsAppService(**defaults)


def test_create_group_and_send_to_group_are_never_supported():
    service = _service()
    assert service.check_operation_supported("create_group") == (False, MetaWhatsAppService.UNSUPPORTED_REASON)
    supported, reason = service.check_operation_supported("send_to_group")
    assert supported is False
    assert reason == MetaWhatsAppService.UNSUPPORTED_REASON


@respx.mock
async def test_send_to_group_never_makes_http_request():
    service = _service()
    route = respx.post(service._messages_url()).mock(return_value=httpx.Response(200, json={"messages": [{"id": "wamid.1"}]}))

    result = await service.send_to_group("some-group-id", "hello")

    assert result.ok is False
    assert result.status == "unsupported"
    assert not route.called


def test_missing_credentials_marks_send_operations_unsupported():
    service = _service(access_token="", phone_number_id="")
    supported, reason = service.check_operation_supported("send_text_message")
    assert supported is False
    assert "not configured" in reason


@respx.mock
async def test_send_text_message_success():
    service = _service()
    respx.post(service._messages_url()).mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.123"}]})
    )

    result = await service.send_text_message("+911234567890", "hello")

    assert result.ok is True
    assert result.status == "sent"
    assert result.message_id == "wamid.123"


@respx.mock
async def test_send_text_message_client_error_no_retry():
    service = _service()
    route = respx.post(service._messages_url()).mock(
        return_value=httpx.Response(400, json={"error": {"message": "Invalid recipient", "code": 131030}})
    )

    result = await service.send_text_message("+911234567890", "hello")

    assert result.ok is False
    assert result.status == "failed"
    assert result.reason == "Invalid recipient"
    assert route.call_count == 1


@respx.mock
async def test_retries_on_server_error_then_succeeds():
    service = _service()
    responses = [httpx.Response(500), httpx.Response(200, json={"messages": [{"id": "wamid.9"}]})]

    def responder(request):
        return responses.pop(0)

    respx.post(service._messages_url()).mock(side_effect=responder)

    result = await service.send_text_message("+911234567890", "hello")

    assert result.ok is True
    assert result.message_id == "wamid.9"


@respx.mock
async def test_exhausts_retries_and_fails():
    service = _service()
    route = respx.post(service._messages_url()).mock(return_value=httpx.Response(503))

    result = await service.send_text_message("+911234567890", "hello")

    assert result.ok is False
    assert result.status == "failed"
    assert route.call_count == 3  # 1 initial + 2 retries


@respx.mock
async def test_send_broadcast_sends_to_each_recipient():
    service = _service()
    respx.post(service._messages_url()).mock(
        return_value=httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})
    )

    results = await service.send_broadcast(["+911111111111", "+922222222222"], "hello")

    assert len(results) == 2
    assert all(r.ok for r in results)


async def test_never_logs_access_token(caplog):
    """Regression guard: the access token must never appear in log output."""
    import logging
    caplog.set_level(logging.DEBUG)
    service = _service(access_token="SUPER-SECRET-TOKEN")
    with respx.mock:
        respx.post(service._messages_url()).mock(return_value=httpx.Response(401, json={"error": {"message": "bad token", "code": 190}}))
        await service.send_text_message("+911234567890", "hello")

    assert "SUPER-SECRET-TOKEN" not in caplog.text
