# Maosen Hu
# 20207104
# End-to-End tests for Assignment 4
# Tests simulate real user behavior using Playwright

import re
import pytest
from playwright.sync_api import Page, expect

# Note: Ensure the Flask app is running at http://localhost:5000 before running these tests

# --- Test Flow 1: Add a New Book ---
def test_add_book_flow(page: Page):
    """
    Test Flow 1: Add a new book to the catalog and verify it appears.
    """
    # 1. Navigate to the 'Add Book' page
    page.goto("http://localhost:5000/add_book")

    # 2. Fill in the form
    # Using a distinct ISBN to avoid duplication errors during repeated tests
    test_isbn = "9789999999999"
    
    page.fill('input[name="title"]', "Playwright Test Book")
    page.fill('input[name="author"]', "Automated Tester")
    page.fill('input[name="isbn"]', test_isbn)
    page.fill('input[name="total_copies"]', "10")

    # 3. Submit the form
    page.click('button[type="submit"]')

    # 4. Verify redirection to the catalog page
    expect(page).to_have_url(re.compile(r".*/catalog"))

    # 5. Verify the new book appears in the list
    # Check if the page body contains the submitted title and author
    expect(page.locator("body")).to_contain_text("Playwright Test Book")
    expect(page.locator("body")).to_contain_text("Automated Tester")


# --- Test Flow 2: Borrow a Book ---
def test_borrow_book_flow(page: Page):
    """
    Test Flow 2: Navigate to catalog and borrow a book.
    """
    # 1. Navigate to the catalog page
    page.goto("http://localhost:5000/catalog")

    # 2. Locate the first available book's borrow input
    # We target the first input field with name="patron_id"
    patron_input = page.locator('input[name="patron_id"]').first
    
    # Ensure the input is visible (meaning there is at least one book to borrow)
    expect(patron_input).to_be_visible()

    # 3. Enter a valid Patron ID (6 digits)
    patron_input.fill("123456")

    # 4. Click the corresponding 'Borrow' button
    # Locate the button containing text "Borrow" that is closest to our input
    page.locator('button:has-text("Borrow")').first.click()

    # 5. Verify the success message
    # The 'flash-success' class is defined in base.html for success messages
    success_message = page.locator(".flash-success")
    expect(success_message).to_be_visible()
    expect(success_message).to_contain_text("Successfully borrowed")