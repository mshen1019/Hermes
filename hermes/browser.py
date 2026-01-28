"""
Browser module for connecting to Chrome via CDP.
"""

import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright


class BrowserManager:
    """Manages browser connection via Chrome DevTools Protocol."""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def connect(self) -> Page:
        """Connect to existing Chrome browser via CDP."""
        self._playwright = await async_playwright().start()

        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(
                self.cdp_url
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Chrome at {self.cdp_url}. "
                "Make sure Chrome is running with --remote-debugging-port=9222\n"
                f"Error: {e}"
            )

        # Get existing context or create new one
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
        else:
            self._context = await self._browser.new_context()

        # Create a new page
        self._page = await self._context.new_page()

        return self._page

    @property
    def page(self) -> Optional[Page]:
        """Get current page."""
        return self._page

    async def navigate(self, url: str, timeout: int = 30000) -> bool:
        """Navigate to URL with timeout."""
        if not self._page:
            raise RuntimeError("Browser not connected. Call connect() first.")

        try:
            await self._page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            # Wait a bit for dynamic content
            await asyncio.sleep(1)
            return True
        except Exception as e:
            print(f"Navigation failed: {e}")
            return False

    async def screenshot(self, path: str) -> str:
        """Take screenshot of current page."""
        if not self._page:
            raise RuntimeError("Browser not connected.")

        screenshot_path = Path(path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        await self._page.screenshot(path=str(screenshot_path), full_page=True)
        return str(screenshot_path)

    async def get_page_content(self) -> str:
        """Get current page HTML content."""
        if not self._page:
            raise RuntimeError("Browser not connected.")
        return await self._page.content()

    async def get_current_url(self) -> str:
        """Get current page URL."""
        if not self._page:
            raise RuntimeError("Browser not connected.")
        return self._page.url

    async def wait_for_selector(
        self, selector: str, timeout: int = 10000
    ) -> bool:
        """Wait for element to appear."""
        if not self._page:
            return False
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    async def close(self):
        """Close browser connection."""
        if self._page:
            await self._page.close()
            self._page = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
