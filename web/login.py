from playwright.sync_api import sync_playwright
from pathlib import Path

STATE_FILE = Path(__file__).parent / "ig_browser_state.json"


def manual_login():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # visible window
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.instagram.com/accounts/login/")
        print("\n[🌐] Browser opened — please log in to Instagram manually.")
        print("[⏳] Waiting for you to finish login...")

        # Wait until Instagram redirects away from the login page
        page.wait_for_url("https://www.instagram.com/**", wait_until="networkidle", timeout=120000)

        # Extra wait to make sure all cookies are fully set
        page.wait_for_timeout(20000)

        # Save full session: cookies + localStorage
        context.storage_state(path=str(STATE_FILE))
        print(f"\n[✅] Session saved to {STATE_FILE}")
        print("[🔒] You can close the browser now.")

        browser.close()


if __name__ == "__main__":
    manual_login()