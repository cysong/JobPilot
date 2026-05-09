from fastapi import status

from app.core.exceptions import ServiceUnavailableError
from app.core.response_codes import ResponseCode


def test_service_unavailable_error_defaults():
    err = ServiceUnavailableError()
    assert err.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert err.response_code == ResponseCode.INTERNAL_ERROR
    assert err.message == "Service unavailable"


def test_service_unavailable_error_custom_message():
    err = ServiceUnavailableError("upstream down")
    assert err.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert err.message == "upstream down"
