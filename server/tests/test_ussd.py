AT_USSD_PAYLOAD = {
    "sessionId": "ATUid_1234567890",
    "phoneNumber": "+254711223344",
    "networkCode": "63902",
    "serviceCode": "*384*1234#",
    "text": "",
}


def test_ussd_callback_accepts_africas_talking_payload(client):
    response = client.post("/ussd", data=AT_USSD_PAYLOAD)

    assert response.status_code == 200


def test_ussd_callback_replies_in_africas_talking_menu_format(client):
    response = client.post("/ussd", data=AT_USSD_PAYLOAD)

    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith(("CON ", "END "))
