
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()

    # Login
    page.goto("http://127.0.0.1:5000/login")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "password")
    page.click('button[type="submit"]')

    # Navigate to Items page and add an item
    page.goto("http://127.0.0.1:5000/items")
    page.fill('input[name="name"]', "Test Item")
    page.click('button[type="submit"]')

    # Navigate to Add Product page and verify the new item
    page.goto("http://127.0.0.1:5000/products/add")

    # Take a screenshot
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
