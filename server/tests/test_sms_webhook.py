AT_INBOUND_SMS_PAYLOAD = {
    "from": "+254711223344",
    "to": "12345",
    "text": "Q M-ALG-02 Why do we swap the sign?",
    "date": "2026-09-02 11:04:00",
    "id": "aa4f8b12",
    "linkId": "SomeLinkId",
}


def test_inbound_sms_accepts_africas_talking_payload(client):
    response = client.post("/sms/inbound", data=AT_INBOUND_SMS_PAYLOAD)

    assert response.status_code == 200


def test_inbound_sms_accepts_payload_without_optional_link_id(client):
    payload = {k: v for k, v in AT_INBOUND_SMS_PAYLOAD.items() if k != "linkId"}

    response = client.post("/sms/inbound", data=payload)

    assert response.status_code == 200
