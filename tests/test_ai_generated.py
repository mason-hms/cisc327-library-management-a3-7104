import re
from datetime import datetime, timedelta

import pytest

from services.library_service import (
    add_book_to_catalog,
    borrow_book_by_patron,
    return_book_by_patron,
    calculate_late_fee_for_book,
    search_books_in_catalog,
    get_patron_status_report,
)

from database import (
    init_database,
    get_db_connection,
    get_book_by_id,
)


# ---------------------------- shared fixtures ----------------------------

@pytest.fixture(autouse=True)
def fresh_db():
    """
    Recreate a clean DB before each test and seed deterministic data.
    """
    init_database()
    conn = get_db_connection()
    # wipe
    conn.execute("DELETE FROM borrow_records")
    conn.execute("DELETE FROM books")
    # seed baseline books
    conn.execute("""
        INSERT INTO books (id, title, author, isbn, total_copies, available_copies)
        VALUES
          (1, 'Harry Potter', 'J.K. Rowling', '9780590353427', 3, 3),
          (2, 'The Hobbit', 'J.R.R. Tolkien', '9780547928227', 1, 0)
    """)
    conn.commit()
    conn.close()


def _insert_borrow(patron_id: str, book_id: int, borrow_date: datetime, due_date: datetime):
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO borrow_records (patron_id, book_id, borrow_date, due_date) VALUES (?, ?, ?, ?)",
        (patron_id, book_id, borrow_date.isoformat(), due_date.isoformat()),
    )
    conn.commit()
    conn.close()


# --------------------------------- R1/R2 ---------------------------------

class TestAddBookToCatalog:
    def test_happy_path(self):
        ok, msg = add_book_to_catalog("A Good Book", "An Author", "9780111222333", 5)
        assert ok is True
        assert "successfully added" in msg.lower()

        # verify persistence via DB
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM books WHERE isbn = '9780111222333'").fetchone()
        conn.close()
        assert row is not None
        assert row["title"] == "A Good Book"
        assert row["available_copies"] == 5

    @pytest.mark.parametrize(
        "title,author,isbn,total,expected_substring",
        [
            ("", "Author", "9780222333444", 1, "Title is required"),
            ("T"*201, "Author", "9780222333444", 1, "less than 200"),
            ("Title", "", "9780222333444", 1, "Author is required"),
            ("Title", "A"*101, "9780222333444", 1, "less than 100"),
            ("Title", "Author", "12345", 1, "13 digits"),
            ("Title", "Author", "9780222333444", 0, "positive integer"),
        ],
    )
    def test_validation_paths(self, title, author, isbn, total, expected_substring):
        ok, msg = add_book_to_catalog(title, author, isbn, total)
        assert ok is False
        assert expected_substring in msg

    def test_duplicate_isbn(self):
        ok, msg = add_book_to_catalog("Another Harry", "Someone", "9780590353427", 1)
        assert ok is False
        assert "already exists" in msg.lower()



# ----------------------------------- R3 -----------------------------------

class TestBorrowBookByPatron:
    def test_borrow_success_sets_due_date_and_decrements_stock(self):
        ok, msg = borrow_book_by_patron("123456", 1)
        assert ok is True

        # message contains YYYY-MM-DD date
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", msg)
        assert m, "Due date must be present in YYYY-MM-DD format"
        # sanity check the due date is around 14 days from now (±1day for runtime variance)
        due = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        assert (due - datetime.now().date()).days in {13, 14, 15}

        # stock decremented
        book = get_book_by_id(1)
        assert book["available_copies"] == 2

    @pytest.mark.parametrize("pid", ["", "12", "abcdef", "12345a", "1234567"])
    def test_invalid_patron_id(self, pid):
        ok, msg = borrow_book_by_patron(pid, 1)
        assert ok is False
        assert "invalid patron id" in msg.lower()

    def test_book_not_found_and_not_available(self):
        ok1, msg1 = borrow_book_by_patron("123456", 999)
        assert ok1 is False and "book not found" in msg1.lower()

        ok2, msg2 = borrow_book_by_patron("123456", 2)  # Hobbit has 0 available
        assert ok2 is False and "not available" in msg2.lower()




# ----------------------------------- R4 -----------------------------------

class TestReturnBookByPatron:
    def test_return_updates_availability_and_sets_return_date(self):
        # borrow then return
        assert borrow_book_by_patron("123456", 1)[0] is True
        ok, msg = return_book_by_patron("123456", 1)
        assert ok is True
        assert "returned successfully" in msg.lower()

        # availability back to 3
        b = get_book_by_id(1)
        assert b["available_copies"] == 3

        # DB has a return_date now
        conn = get_db_connection()
        r = conn.execute(
            "SELECT return_date FROM borrow_records WHERE patron_id=? AND book_id=? ORDER BY rowid DESC LIMIT 1",
            ("123456", 1),
        ).fetchone()
        conn.close()
        assert r is not None and r["return_date"] is not None

    def test_return_without_active_record(self):
        ok, msg = return_book_by_patron("123456", 1)
        assert ok is False
        assert "no active borrow record" in msg.lower()


# ----------------------------------- R5 -----------------------------------

class TestCalculateLateFeeForBook:
    def test_overdue_fee_piecewise_correct(self):
        # borrowed 20 days ago, due 6 days ago -> 6 * 0.50 = 3.00
        borrow_dt = datetime.now() - timedelta(days=20)
        due_dt = borrow_dt + timedelta(days=14)
        _insert_borrow("123456", 1, borrow_dt, due_dt)

        out = calculate_late_fee_for_book("123456", 1)
        assert out["days_overdue"] == 6
        assert abs(out["fee_amount"] - 3.00) < 1e-6

    def test_not_overdue_zero_fee(self):
        assert borrow_book_by_patron("123456", 1)[0] is True
        out = calculate_late_fee_for_book("123456", 1)
        assert out["days_overdue"] == 0
        assert out["fee_amount"] == 0.0
        assert out["status"] in ("Book not overdue", "Success")

    def test_fee_cap_at_15(self):
        # make it very late: due 40 days ago -> base 36.5, capped to 15.00
        borrow_dt = datetime.now() - timedelta(days=60)
        due_dt = datetime.now() - timedelta(days=40)
        _insert_borrow("222222", 1, borrow_dt, due_dt)

        out = calculate_late_fee_for_book("222222", 1)
        assert out["days_overdue"] >= 40
        assert abs(out["fee_amount"] - 15.00) < 1e-6
        assert out["status"] == "Success"


# ----------------------------------- R6 -----------------------------------

class TestSearchBooksInCatalog:
    def test_title_partial(self):
        res = search_books_in_catalog("Potter", "title")
        assert len(res) == 1 and res[0]["title"] == "Harry Potter"

    def test_author_case_insensitive_partial(self):
        res = search_books_in_catalog("rowling", "author")
        assert len(res) == 1 and res[0]["isbn"] == "9780590353427"

    def test_isbn_exact(self):
        res = search_books_in_catalog("9780547928227", "isbn")
        assert len(res) == 1 and res[0]["title"] == "The Hobbit"

    def test_no_match(self):
        assert search_books_in_catalog("No Such Title", "title") == []


# ----------------------------------- R7 -----------------------------------

class TestGetPatronStatusReport:
    def test_with_active_loans(self):
        # borrow one
        assert borrow_book_by_patron("123456", 1)[0] is True
        report = get_patron_status_report("123456")

        assert isinstance(report, dict)
        assert report.get("number_of_books_borrowed") == 1
        assert isinstance(report.get("currently_borrowed_books"), list)
        assert isinstance(report.get("total_late_fees_owed"), float)

    def test_without_loans(self):
        report = get_patron_status_report("123456")
        assert report["number_of_books_borrowed"] == 0
        assert report["total_late_fees_owed"] == 0.0
        assert isinstance(report["borrowing_history"], list)
