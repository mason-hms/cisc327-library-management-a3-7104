"""
Library Service Module - Business Logic Functions
Contains all the core business logic for the Library Management System
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from database import (
    get_book_by_id, get_book_by_isbn, get_patron_borrow_count,
    insert_book, insert_borrow_record, update_book_availability,
    update_borrow_record_return_date, get_all_books
)

def add_book_to_catalog(title: str, author: str, isbn: str, total_copies: int) -> Tuple[bool, str]:
    """
    Add a new book to the catalog.
    Implements R1: Book Catalog Management

    Args:
        title: Book title (max 200 chars)
        author: Book author (max 100 chars)
        isbn: 13-digit ISBN
        total_copies: Number of copies (positive integer)

    Returns:
        tuple: (success: bool, message: str)
    """
    # Input validation
    if not title or not title.strip():
        return False, "Title is required."

    if len(title.strip()) > 200:
        return False, "Title must be less than 200 characters."

    if not author or not author.strip():
        return False, "Author is required."

    if not isinstance(isbn, str):
        isbn = str(isbn)
    isbn = isbn.strip()

    if len(author.strip()) > 100:
        return False, "Author must be less than 100 characters."

    if len(isbn) != 13 or not isbn.isdigit():
        return False, "ISBN must be exactly 13 digits (numbers only)."

    if not isinstance(total_copies, int) or total_copies <= 0:
        return False, "Total copies must be a positive integer."

    # Check for duplicate ISBN
    existing = get_book_by_isbn(isbn)
    if existing:
        return False, "A book with this ISBN already exists."

    # Insert new book
    success = insert_book(title.strip(), author.strip(), isbn, total_copies, total_copies)
    if success:
        return True, f'Book "{title.strip()}" has been successfully added to the catalog.'
    else:
        return False, "Database error occurred while adding the book."

def borrow_book_by_patron(patron_id: str, book_id: int) -> Tuple[bool, str]:
    """
    Allow a patron to borrow a book.
    Implements R3 as per requirements

    Args:
        patron_id: 6-digit library card ID
        book_id: ID of the book to borrow

    Returns:
        tuple: (success: bool, message: str)
    """
    # Validate patron ID
    if not patron_id or not patron_id.isdigit() or len(patron_id) != 6:
        return False, "Invalid patron ID. Must be exactly 6 digits."

    # Check if book exists and is available
    book = get_book_by_id(book_id)
    if not book:
        return False, "Book not found."

    if book['available_copies'] <= 0:
        return False, "This book is currently not available."

    # Check patron's current borrowed books count
    current_borrowed = get_patron_borrow_count(patron_id)

    if current_borrowed >= 5:
        return False, "You have reached the maximum borrowing limit of 5 books."

    # Create borrow record
    borrow_date = datetime.now()
    due_date = borrow_date + timedelta(days=14)

    # Insert borrow record and update availability
    borrow_success = insert_borrow_record(patron_id, book_id, borrow_date, due_date)
    if not borrow_success:
        return False, "Database error occurred while creating borrow record."

    availability_success = update_book_availability(book_id, -1)
    if not availability_success:
        return False, "Database error occurred while updating book availability."

    return True, f'Successfully borrowed "{book["title"]}". Due date: {due_date.strftime("%Y-%m-%d")}.'


def return_book_by_patron(patron_id: str, book_id: int) -> Tuple[bool, str]:
    """
    Process book return by a patron.

    """
    from database import get_db_connection, get_book_by_id

    # Check patron ID format
    if patron_id is None or len(patron_id) != 6:
        return False, "Invalid patron ID. Must be exactly 6 digits."

    # Check if all digits
    for char in patron_id:
        if not char.isdigit():
            return False, "Invalid patron ID. Must be exactly 6 digits."

    # Check if book exists
    book = get_book_by_id(book_id)
    if book is None:
        return False, "Book not found."

    # Find borrow record
    conn = get_db_connection()
    cursor = conn.execute(
        'SELECT * FROM borrow_records WHERE patron_id = ? AND book_id = ? AND return_date IS NULL',
        (patron_id, book_id)
    )
    record = cursor.fetchone()

    if record is None:
        conn.close()
        return False, "No active borrow record found for this book and patron."

    # Calculate late fee
    due_date_str = record['due_date']
    due_date = datetime.fromisoformat(due_date_str)
    today = datetime.now()

    late_fee = 0.0
    days_late = 0

    if today > due_date:
        difference = today - due_date
        days_late = difference.days

        if days_late <= 7:
            late_fee = days_late * 0.50
        else:
            late_fee = 7 * 0.50
            extra_days = days_late - 7
            late_fee = late_fee + (extra_days * 1.00)

        if late_fee > 15.00:
            late_fee = 15.00

    # Update return date
    conn.execute(
        'UPDATE borrow_records SET return_date = ? WHERE patron_id = ? AND book_id = ? AND return_date IS NULL',
        (today.isoformat(), patron_id, book_id)
    )

    # Increase available copies
    conn.execute(
        'UPDATE books SET available_copies = available_copies + 1 WHERE id = ?',
        (book_id,)
    )

    conn.commit()
    conn.close()

    # Return message
    book_title = book['title']

    if late_fee > 0:
        message = f'Book "{book_title}" returned successfully. Late fee owed: ${late_fee:.2f} ({days_late} days overdue).'
        return True, message
    else:
        message = f'Book "{book_title}" returned successfully. No late fees.'
        return True, message


def calculate_late_fee_for_book(patron_id: str, book_id: int) -> Dict:
    """
    Calculate late fees for a specific book.


    return { // return the calculated values
        'fee_amount': 0.00,
        'days_overdue': 0,
        'status': 'Late fee calculation not implemented'
    }
    """
    from database import get_db_connection, get_book_by_id

    # Check patron ID format
    if patron_id is None or len(patron_id) != 6:
        return {
            'fee_amount': 0.00,
            'days_overdue': 0,
            'status': 'Invalid patron ID'
        }

    # Check if all digits
    for char in patron_id:
        if not char.isdigit():
            return {
                'fee_amount': 0.00,
                'days_overdue': 0,
                'status': 'Invalid patron ID'
            }

    # Check if book exists
    book = get_book_by_id(book_id)
    if book is None:
        return {
            'fee_amount': 0.00,
            'days_overdue': 0,
            'status': 'Book not found'
        }

    # Find unreturned borrow record
    conn = get_db_connection()
    cursor = conn.execute(
        'SELECT * FROM borrow_records WHERE patron_id = ? AND book_id = ? AND return_date IS NULL',
        (patron_id, book_id)
    )
    record = cursor.fetchone()
    conn.close()

    if record is None:
        return {
            'fee_amount': 0.00,
            'days_overdue': 0,
            'status': 'No active borrow record found'
        }

    # Calculate overdue days
    due_date_str = record['due_date']
    due_date = datetime.fromisoformat(due_date_str)
    today = datetime.now()

    if today <= due_date:
        return {
            'fee_amount': 0.00,
            'days_overdue': 0,
            'status': 'Book not overdue'
        }

    # Calculate days and fee
    difference = today - due_date
    days_overdue = difference.days

    fee = 0.00

    if days_overdue <= 7:
        fee = days_overdue * 0.50
    else:
        fee = 7 * 0.50
        extra_days = days_overdue - 7
        fee = fee + (extra_days * 1.00)

    if fee > 15.00:
        fee = 15.00

    return {
        'fee_amount': fee,
        'days_overdue': days_overdue,
        'status': 'Success'
    }

def search_books_in_catalog(search_term: str, search_type: str) -> List[Dict]:
    """
    Search for books in the catalog.

    """
    from database import get_db_connection

    if not search_term:
        return []

    conn = get_db_connection()
    books = []

    if search_type == 'title':
        # Partial match
        cursor = conn.execute(
            'SELECT * FROM books WHERE LOWER(title) LIKE LOWER(?)',
            ('%' + search_term + '%',)
        )
        books = cursor.fetchall()
    elif search_type == 'author':
        # Partial match, case-insensitive
        cursor = conn.execute(
            'SELECT * FROM books WHERE LOWER(author) LIKE LOWER(?)',
            ('%' + search_term + '%',)
        )
        books = cursor.fetchall()
    elif search_type == 'isbn':
        # Exact match
        cursor = conn.execute(
            'SELECT * FROM books WHERE isbn = ?',
            (search_term,)
        )
        books = cursor.fetchall()

    conn.close()

    # Convert to list of dicts
    result = []
    for book in books:
        result.append({
            'id': book['id'],
            'title': book['title'],
            'author': book['author'],
            'isbn': book['isbn'],
            'total_copies': book['total_copies'],
            'available_copies': book['available_copies']
        })

    return result


def get_patron_status_report(patron_id: str) -> Dict:
    """
    Get status report for a patron.

    """
    from database import get_db_connection, get_patron_borrowed_books

    # Check patron ID format
    if patron_id is None or len(patron_id) != 6:
        return {}

    # Check if all digits
    for char in patron_id:
        if not char.isdigit():
            return {}

    # Get currently borrowed books
    borrowed_books = get_patron_borrowed_books(patron_id)

    # Calculate total late fees
    total_fees = 0.00
    for book in borrowed_books:
        if book['is_overdue']:
            fee_result = calculate_late_fee_for_book(patron_id, book['book_id'])
            total_fees = total_fees + fee_result['fee_amount']

    # Get borrowing history
    conn = get_db_connection()
    cursor = conn.execute(
        'SELECT * FROM borrow_records WHERE patron_id = ? ORDER BY borrow_date DESC',
        (patron_id,)
    )
    history = cursor.fetchall()
    conn.close()

    # Build report
    report = {
        'currently_borrowed_books': borrowed_books,
        'number_of_books_borrowed': len(borrowed_books),
        'total_late_fees_owed': total_fees,
        'borrowing_history': [dict(record) for record in history]
    }

    return report
