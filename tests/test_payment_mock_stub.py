"""
Task 2.1 - Stubbing & Mocking tests for:
- services.library_service.pay_late_fees
- services.library_service.refund_late_fee_payment
"""

import pytest
from unittest.mock import Mock
from services.payment_service import PaymentGateway
from services import library_service as lib

def test_pay_late_fees_success(mocker):
    """
    Should process payment successfully when fee_amount > 0 and gateway approves.
    """
    # Stub database/logic dependencies with fixed values (no interaction verification)
    mocker.patch.object(lib, "calculate_late_fee_for_book", return_value={
        "fee_amount": 6.0,
        "days_overdue": 3,
        "status": "Success",
    })
    mocker.patch.object(lib, "get_book_by_id", return_value={
        "id": 1,
        "title": "Clean Code",
    })

    # Mock external gateway and verify interaction
    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.return_value = (True, "txn_123", "Success")

    ok, msg, txn = lib.pay_late_fees("123456", 1, gateway)

    assert ok is True
    assert "Payment successful" in msg
    assert txn == "txn_123"
    gateway.process_payment.assert_called_once_with(
        patron_id="123456",
        amount=6.0,
        description="Late fees for 'Clean Code'",
    )

def test_pay_late_fees_declined_by_gateway(mocker):
    """
    Should return failure when gateway declines the charge.
    """
    mocker.patch.object(lib, "calculate_late_fee_for_book", return_value={
        "fee_amount": 12.5,
        "days_overdue": 10,
        "status": "Success",
    })
    mocker.patch.object(lib, "get_book_by_id", return_value={
        "id": 2,
        "title": "Refactoring",
    })

    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.return_value = (False, "", "Payment declined")

    ok, msg, txn = lib.pay_late_fees("123456", 2, gateway)

    assert ok is False
    assert "Payment failed" in msg
    assert txn is None
    gateway.process_payment.assert_called_once_with(
        patron_id="123456",
        amount=12.5,
        description="Late fees for 'Refactoring'",
    )


def test_pay_late_fees_invalid_patron_id_gateway_not_called():
    """
    Should reject invalid patron_id and not call the gateway.
    """
    gateway = Mock(spec=PaymentGateway)

    ok, msg, txn = lib.pay_late_fees("12A456", 1, gateway)

    assert ok is False
    assert "Invalid patron ID" in msg
    assert txn is None
    gateway.process_payment.assert_not_called()


def test_pay_late_fees_zero_fee_gateway_not_called(mocker):
    """
    Should not call the gateway when fee_amount == 0.
    """
    mocker.patch.object(lib, "calculate_late_fee_for_book", return_value={
        "fee_amount": 0.0,
        "days_overdue": 0,
        "status": "Book not overdue",
    })

    gateway = Mock(spec=PaymentGateway)

    ok, msg, txn = lib.pay_late_fees("123456", 1, gateway)

    assert ok is False
    assert "No late fees" in msg
    assert txn is None
    gateway.process_payment.assert_not_called()


def test_pay_late_fees_gateway_raises_exception(mocker):
    """
    Should handle gateway exceptions gracefully and return proper error message.
    """
    mocker.patch.object(lib, "calculate_late_fee_for_book", return_value={
        "fee_amount": 5.0,
        "days_overdue": 2,
        "status": "Success",
    })
    mocker.patch.object(lib, "get_book_by_id", return_value={
        "id": 1,
        "title": "Design Patterns",
    })

    gateway = Mock(spec=PaymentGateway)
    gateway.process_payment.side_effect = RuntimeError("network error")

    ok, msg, txn = lib.pay_late_fees("123456", 1, gateway)

    assert ok is False
    assert "Payment processing error" in msg
    assert txn is None
    gateway.process_payment.assert_called_once()


# Tests for refund_late_fee_payment

def test_refund_success():
    """
    Should process refund successfully when transaction_id and amount are valid.
    """
    gateway = Mock(spec=PaymentGateway)
    gateway.refund_payment.return_value = (True, "Refund OK")

    ok, msg = lib.refund_late_fee_payment("txn_123", 7.5, gateway)

    assert ok is True
    assert "Refund OK" in msg
    gateway.refund_payment.assert_called_once_with("txn_123", 7.5)


@pytest.mark.parametrize("txn", ["", "abc123", None])
def test_refund_invalid_transaction_id_rejected(txn):
    """
    Should reject invalid transaction_id and not call the gateway.
    """
    gateway = Mock(spec=PaymentGateway)

    ok, msg = lib.refund_late_fee_payment(txn, 5.0, gateway)

    assert ok is False
    assert "Invalid transaction ID" in msg
    gateway.refund_payment.assert_not_called()


@pytest.mark.parametrize("amount", [-1.0, 0.0])
def test_refund_invalid_amount_non_positive(amount):
    """
    Should reject non-positive refund amounts and not call the gateway.
    """
    gateway = Mock(spec=PaymentGateway)

    ok, msg = lib.refund_late_fee_payment("txn_123", amount, gateway)

    assert ok is False
    assert "greater than 0" in msg
    gateway.refund_payment.assert_not_called()


def test_refund_amount_exceeds_max():
    """
    Should reject refund amounts exceeding the $15 maximum and not call the gateway.
    """
    gateway = Mock(spec=PaymentGateway)

    ok, msg = lib.refund_late_fee_payment("txn_123", 20.0, gateway)

    assert ok is False
    assert "exceeds maximum late fee" in msg
    gateway.refund_payment.assert_not_called()