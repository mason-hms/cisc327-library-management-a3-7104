# Maosen Hu
# 20207104
# Unit tests for library_service.py
# This tests file is based on the requirements
# Some functions will be rejected due to non-implementation

import pytest
from datetime import datetime, timedelta
from library_service import (
    add_book_to_catalog,
    borrow_book_by_patron,
    return_book_by_patron,
    calculate_late_fee_for_book,
    search_books_in_catalog,
    get_patron_status_report
)
from database import init_database, get_db_connection, get_book_by_id


# Reset a clean database
@pytest.fixture(autouse=True)
def clean_database_before_each_test():
    init_database()
    conn = get_db_connection()
    conn.execute('DELETE FROM books')
    conn.execute('DELETE FROM borrow_records')

    # Add initial example for a predictable test
    conn.execute('''
                 INSERT INTO books (id, title, author, isbn, total_copies, available_copies)
                 VALUES (1, 'Harry Potter', 'J.K. Rowling', '9780590353427', 3, 3),
                        (2, 'The Hobbit', 'J.R.R. Tolkien', '9780547928227', 1, 0)
                 ''')
    conn.commit()
    conn.close()


# --- Tests for add_book_to_catalog (R1 & R2) ---
# Positive
def test_add_book_valid_input():
    """Test adding a book with valid input."""
    success, message = add_book_to_catalog("A Good Book", "An Author", "9780111222333", 5)
    assert success == True
    assert "successfully added" in message.lower()

# Title (required, max 200 characters)
def test_add_book_empty_title():
    """Test adding a book with an empty title."""
    success, message = add_book_to_catalog("", "Some Author", "9780222333444", 2)
    assert success == False
    assert "Title is required" in message

# ISBN (required, exactly 13 digits)
def test_add_book_invalid_isbn_too_short():
    """Test adding a book with an ISBN that is too short."""
    success, message = add_book_to_catalog("Another Book", "An Author", "12345", 3)
    assert success == False
    assert "13 digits" in message


def test_add_book_duplicate_isbn():
    """Test adding a book with a same ISBN."""
    # Test same ISBN with Harry Potter
    success, message = add_book_to_catalog("Another Harry Potter", "An Author", "9780590353427", 1)
    assert success == False
    assert "already exists" in message.lower()

# Bug test for ISBN
def test_add_book_isbn_with_letters_bug():
    """Test that the ISBN validation bug exists."""
    # This test should fail if there is a bug
    # system rejects ISBN containing letters
    success, message = add_book_to_catalog("Bugged Book", "An Author", "ABC1234567890", 1)
    assert success == False, "This test should fail on the original code, proving the bug."


# --- Tests for borrow_book_by_patron (R3) ---

def test_borrow_book_valid_input():
    """Test borrowing a book with valid input."""
    # Validates patron ID (6-digit format)
    success, message = borrow_book_by_patron("123456", 1)
    assert success == True
    assert "successfully borrowed" in message.lower()

# Accepts patron ID and book ID as the form parameters
def test_borrow_book_invalid_patron_id():
    """Test borrowing with an invalid patron ID."""
    success, message = borrow_book_by_patron("123", 1)
    assert success == False
    assert "Invalid patron ID" in message

# Creates borrowing record and updates available copies
def test_borrow_book_out_of_stock():
    """Test borrowing a book that is out of stock."""
    success, message = borrow_book_by_patron("123456", 2)
    assert success == False
    assert "not available" in message.lower()

# Checks book availability
def test_borrow_book_does_not_exist():
    """Test borrowing a book that does not exist."""
    success, message = borrow_book_by_patron("123456", 999)
    assert success == False
    assert "book not found" in message.lower()

# Patron borrowing limits (max 5 books)
def test_borrow_limit_bug():
    """Test that the borrowing limit bug"""
    # Add enough books to borrow
    for i in range(3, 8):
        add_book_to_catalog(f"Book {i}", "Author", f"{i}" * 13, 1)
    # Borrow 5 books
    for bid in [1, 3, 4, 5, 6]:
        borrow_book_by_patron("111222", bid)
    # Try to borrow the 6th book, which should be fail
    ok, _ = borrow_book_by_patron("111222", 7)
    assert ok is False

# Update: All the function are implemented
# --- Tests for return_book_by_patron (R4) ---

# Updates available copies and records return date
def test_return_book_updates_copies():
    """Test that returning a book updates its available copies."""
    borrow_book_by_patron("123456", 1)
    success, message = return_book_by_patron("123456", 1)
    assert success == True
    book = get_book_by_id(1)
    assert book['available_copies'] == 3

# Verifies the book was borrowed by the patron
def test_return_book_not_borrowed():
    """Test returning a book that not borrowed."""
    success, message = return_book_by_patron("123456", 1)
    assert success == False


# --- Tests for calculate_late_fee_for_book (R5) ---

# Calculates and displays any late fees owed
def test_calculate_fee_overdue_book():
    """Test calculating a fee for overdue book."""
    conn = get_db_connection()
    # Borrowed 20 days ago
    borrow_date = datetime.now() - timedelta(days=20)
    # Due 6 days ago
    due_date = borrow_date + timedelta(days=14)
    conn.execute("INSERT INTO borrow_records (patron_id, book_id, borrow_date, due_date) VALUES (?, ?, ?, ?)",
                 ("123456", 1, borrow_date.isoformat(), due_date.isoformat()))
    conn.commit()
    conn.close()

    result = calculate_late_fee_for_book("123456", 1)
    assert result['days_overdue'] == 6
    assert result['fee_amount'] == 3.00


def test_calculate_fee_book_on_time():
    """Test calculating a fee for a book returned on time."""
    borrow_book_by_patron("123456", 1)
    result = calculate_late_fee_for_book("123456", 1)
    assert result['days_overdue'] == 0
    assert result['fee_amount'] == 0.00


# --- Tests for search_books_in_catalog (R6) ---

# Partial match
def test_search_by_title_partial_match():
    """Test searching by a partial match."""
    results = search_books_in_catalog("Potter", "title")
    assert len(results) == 1
    assert results[0]['title'] == 'Harry Potter'

# Exact match
def test_search_by_isbn_exact_match():
    """Test searching by an exact match."""
    results = search_books_in_catalog("9780547928227", "isbn")
    assert len(results) == 1
    assert results[0]['title'] == "The Hobbit"

# Return results
def test_search_no_results():
    """Test a search that should return no results."""
    results = search_books_in_catalog("Non Existent Book", "title")
    assert len(results) == 0


# --- Tests for get_patron_status_report (R7) ---

# Currently borrowed books with due dates
def test_patron_status_report_with_books():
    """Test the status report for a patron with borrowed books."""
    borrow_book_by_patron("123456", 1)
    report = get_patron_status_report("123456")
    assert "currently_borrowed_books" in report
    assert report['number_of_books_borrowed'] == 1


def test_patron_status_report_no_books():
    """Test the status report for a patron without borrowed books."""
    report = get_patron_status_report("123456")
    assert report['number_of_books_borrowed'] == 0
    assert report['total_late_fees_owed'] == 0.00

