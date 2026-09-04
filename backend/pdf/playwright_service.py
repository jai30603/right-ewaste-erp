import subprocess
import sys
import os
import threading

# Auto-installer for playwright package and chromium browser binaries
def check_and_install_playwright():
    try:
        import playwright
    except ImportError:
        print("Playwright is not installed. Installing playwright python package...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright==1.42.0"])
        except Exception as e:
            print("Error running pip install playwright:", e)

    # Ensure browser binaries are installed
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            browser.close()
    except Exception as e:
        print("Chromium browser is missing or failed to launch. Installing chromium binaries...", e)
        try:
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        except Exception as install_err:
            print("Error installing chromium via playwright CLI:", install_err)

# Run the installer check
check_and_install_playwright()

from playwright.sync_api import sync_playwright

class PlaywrightService:
    def url_to_pdf(self, url, landscape=False):
        """
        Thread-safe method that launches Playwright locally per request.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(viewport={"width": 1440, "height": 2000})
            page = context.new_page()
            try:
                # Enable print media emulation
                page.emulate_media(media="print")
                # Navigate to print route and wait for complete rendering
                page.goto(url, wait_until="networkidle")
                # Wait for all system and web fonts to complete loading
                page.evaluate("document.fonts.ready")
                # Compile PDF honoring CSS @page parameters
                pdf_bytes = page.pdf(
                    print_background=True,
                    prefer_css_page_size=True,
                    landscape=landscape
                )
                return pdf_bytes
            finally:
                page.close()
                context.close()
                browser.close()

    def html_to_pdf(self, html_content, margin=None, format="A4", landscape=False):
        """
        Thread-safe method that launches Playwright locally per HTML compile request.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(viewport={"width": 1440, "height": 2000})
            page = context.new_page()
            try:
                page.emulate_media(media="print")
                page.set_content(html_content, wait_until="load")
                page.evaluate("document.fonts.ready")
                pdf_bytes = page.pdf(
                    format=format,
                    print_background=True,
                    margin=margin or {"top": "0.5in", "bottom": "0.5in", "left": "0.6in", "right": "0.6in"},
                    landscape=landscape
                )
                return pdf_bytes
            finally:
                page.close()
                context.close()
                browser.close()

# Singleton instance for backwards compatibility api calls
playwright_service = PlaywrightService()
