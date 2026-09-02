from app.sms_client import AfricasTalkingSmsClient, RecordingSmsClient


def test_recording_client_records_instead_of_sending():
    outbox = RecordingSmsClient()
    outbox.send("+254700000001", "hello")
    outbox.send("+254700000001", "again")
    assert outbox.sent == [
        ("+254700000001", "hello"),
        ("+254700000001", "again"),
    ]


def test_real_client_defers_sdk_setup_until_first_send():
    # Constructing the client must not import or initialize the SDK, so the
    # app can start without Africa's Talking credentials configured.
    client = AfricasTalkingSmsClient("sandbox", "")
    assert client._sms is None


def test_app_wires_injected_client(client, sms_outbox):
    assert client.app.state.sms_client is sms_outbox
