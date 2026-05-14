from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:  # pragma: no cover - handled at runtime with explicit message
    webdriver = None
    TimeoutException = RuntimeError  # type: ignore[assignment]
    ChromeOptions = None
    By = None
    WebDriver = Any
    EC = None
    WebDriverWait = None


class AADEDeclaration:
    """Automate AADE short-term letting declaration flows.

    Notes:
    - The TAXISnet flow may include MFA/captcha steps that require manual completion.
    - This class uses resilient selector fallbacks because IDs/classes can differ across sessions.
    """

    BASE_URL = "https://www1.gsis.gr/taxisnet/short_term_letting/views/declarationSearch.xhtml"

    def __init__(
            self,
            *,
            headless: bool = False,
            timeout_seconds: int = 30,
            property_id: str = "0000",
            screenshots_enabled: bool = False,
            screenshots_dir: str = "aade_screenshots",
            password: str | None = None,
            username: str | None = None,
    ) -> None:
        self.password = password
        self.username = username
        if webdriver is None or ChromeOptions is None or WebDriverWait is None or By is None or EC is None:
            raise ImportError(
                "Selenium is required. Install dependencies with: pip install -r requirements.txt")
        self.timeout_seconds = timeout_seconds
        self.property_id = property_id
        self.screenshots_enabled = screenshots_enabled
        self.screenshots_dir = Path(screenshots_dir)
        if self.screenshots_enabled:
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.driver = self._build_driver(headless=headless)
        self.wait = WebDriverWait(self.driver, timeout_seconds)

    def _take_screenshot(self, step_name: str) -> str | None:
        if not self.screenshots_enabled:
            return None
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", step_name).strip(
            "_") or "step"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = self.screenshots_dir / f"{timestamp}_{safe_name}.png"
        self.driver.save_screenshot(str(output_path))
        return str(output_path)

    def _build_driver(self, *, headless: bool) -> WebDriver:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1600,1000")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(options=options)

    def close(self) -> None:
        self.driver.quit()

    def __enter__(self) -> "AADEDeclaration":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _first_visible(self, selectors: Iterable[tuple[str, str]]):
        for by, value in selectors:
            try:
                return self.wait.until(
                    EC.visibility_of_element_located((by, value)))
            except TimeoutException:
                continue
        self._take_screenshot("error_visible_selector_not_found")
        raise TimeoutException(
            f"No visible element matched selectors: {selectors}")

    def _first_clickable(self, selectors: Iterable[tuple[str, str]]):
        for by, value in selectors:
            try:
                return self.wait.until(EC.element_to_be_clickable((by, value)))
            except TimeoutException:
                continue
        self._take_screenshot("error_clickable_selector_not_found")
        raise TimeoutException(
            f"No clickable element matched selectors: {selectors}")

    def open_property_page(self, property_id: str | None = None) -> None:
        target_property_id = property_id or self.property_id
        self.driver.get(f"{self.BASE_URL}?propertyId={target_property_id}")
        self._take_screenshot("opened_property_page")

    def login(self, username: str, password: str) -> None:
        """Login to TAXISnet and wait for the declarations screen to load."""
        self._take_screenshot("before_login_fill")
        username_input = self._first_visible(
            [
                # Exact selectors from login.gsis.gr markup.
                (By.ID, "username"),
                (By.CSS_SELECTOR, "input[name='username']"),
                (By.CSS_SELECTOR, "input[id*='username']"),
                (By.CSS_SELECTOR, "input[type='text']"),
            ]
        )
        username_input.clear()
        username_input.send_keys(username)

        password_input = self._first_visible(
            [
                (By.ID, "password"),
                (By.CSS_SELECTOR, "input[name='password']"),
                (By.CSS_SELECTOR, "input[id*='password']"),
                (By.CSS_SELECTOR, "input[type='password']"),
            ]
        )
        password_input.clear()
        password_input.send_keys(password)

        self._first_clickable(
            [
                (By.CSS_SELECTOR, "button[name='btn_login']"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
                (By.XPATH,
                 "//button[contains(., 'Συνδεση') or contains(., 'Σύνδεση') or contains(., 'Login') or contains(., 'Είσοδος')]")
            ]
        ).click()
        self._take_screenshot("after_login_submit_click")

        # Allow TAXISnet redirect + optional manual MFA/captcha completion.
        self.wait.until(
            lambda d: (
                              "short_term_letting" in d.current_url
                              or "declarationSearch.xhtml" in d.current_url
                              or "www1.gsis.gr" in d.current_url
                      )
                      and "login.gsis.gr" not in d.current_url
        )
        self._take_screenshot("after_login_redirect")

    def click_new_declaration(self) -> None:
        """Open the new declaration form from the declarations page."""
        self._first_clickable(
            [
                (By.XPATH,
                 "//a[contains(., 'Νέα Δήλωση') or contains(., 'New Declaration')]"),
                (By.XPATH,
                 "//button[contains(., 'Νέα Δήλωση') or contains(., 'New Declaration')]"),
                (By.CSS_SELECTOR, "a[id*='newDeclaration']"),
                (By.CSS_SELECTOR, "button[id*='newDeclaration']"),
            ]
        ).click()
        self._take_screenshot("opened_new_declaration_form")

    # ------------------------------------------------------------------
    # PrimeFaces helpers
    # ------------------------------------------------------------------

    def _select_primefaces_dropdown(self, component_id: str, value_or_label: str) -> None:
        """Select an option in a PrimeFaces selectOneMenu.

        Works by clicking the visible dropdown trigger and then clicking the
        matching list item in the popup panel.

        Args:
            component_id: PrimeFaces component root id, e.g. ``appForm:paymentType``
            value_or_label: The option value (e.g. ``"1"``) or its visible text label.
        """
        import time

        panel_id = f"{component_id}_panel"

        # Try up to 3 times in case of stale element or panel not opening
        for attempt in range(3):
            # Click the visible dropdown trigger to open the panel.
            trigger = self._first_clickable(
                [
                    (By.ID, f"{component_id}_label"),
                    (By.CSS_SELECTOR, f"#{component_id} .ui-selectonemenu-trigger"),
                    (By.CSS_SELECTOR, f"[id='{component_id}'] .ui-selectonemenu-trigger"),
                ]
            )
            # Try a regular click first; fall back to JS click if panel doesn't open.
            trigger.click()
            time.sleep(0.4)

            # Check if panel became visible; if not, try JS click.
            try:
                self.wait.until(EC.visibility_of_element_located((By.ID, panel_id)))
                break  # panel is open, proceed
            except TimeoutException:
                if attempt < 2:
                    # Force-open via JavaScript and retry
                    self.driver.execute_script(
                        "var el = document.getElementById(arguments[0]);"
                        "if(el){ el.style.display='block'; el.style.visibility='visible'; }",
                        panel_id,
                    )
                    # Also try JS click on the trigger
                    self.driver.execute_script("arguments[0].click();", trigger)
                    time.sleep(0.4)
                    try:
                        self.wait.until(EC.visibility_of_element_located((By.ID, panel_id)))
                        break
                    except TimeoutException:
                        continue
                else:
                    self._take_screenshot(f"error_dropdown_{component_id}_panel_timeout")
                    raise

        # Find the matching list item by data-label or visible text.
        panel = self.driver.find_element(By.ID, panel_id)
        items = panel.find_elements(By.CSS_SELECTOR, "li.ui-selectonemenu-item")
        for item in items:
            label = item.get_attribute("data-label") or item.text
            if label == value_or_label or item.get_attribute("data-value") == value_or_label:
                item.click()
                return

        # Fallback: match by numeric position if value_or_label is a digit string.
        if value_or_label.isdigit():
            idx = int(value_or_label)
            if 0 < idx <= len(items):
                items[idx].click()  # item[0] is the blank option, so idx lines up
                return

        self._take_screenshot(f"error_dropdown_{component_id}_option_not_found")
        raise ValueError(
            f"Option '{value_or_label}' not found in dropdown '{component_id}'. "
            f"Available: {[i.get_attribute('data-label') for i in items]}"
        )

    def _set_date_input(self, element_id: str, date_str: str) -> None:
        """Fill a PrimeFaces datepicker text input using JavaScript to bypass picker.

        Args:
            element_id: Full id of the ``<input>`` element, e.g. ``appForm:rentalFrom_input``.
            date_str: Date string, e.g. ``'21/05/2026'``.
        """
        el = self.wait.until(EC.presence_of_element_located((By.ID, element_id)))
        self.driver.execute_script(
            "arguments[0].removeAttribute('readonly');"
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            el, date_str,
        )

    # ------------------------------------------------------------------
    # Form filling
    # ------------------------------------------------------------------

    def fill_declaration_fields(
        self, declaration_data: dict[str, Any]
    ) -> None:
        """Fill the short-term letting declaration form.

        Field mapping (exact HTML IDs from AADE form):

        ============== =========================================== ======================
        Argument       Label (EN)                                  HTML id
        ============== =========================================== ======================
        arrival_date   Arrival Date                                appForm:rentalFrom_input
        departure_date Departure Date                              appForm:rentalTo_input
        total_rent     Total agreed rent                           appForm:sumAmount_input
        payment_method Method of Payment (value or label)         appForm:paymentType
        platform       E-platform (value or label)                appForm:platform
        tenant_tin     Tax Identification No                       appForm:renterAfm
        tenant_full_name Full name (auto-filled after TIN lookup)  appForm:renterName
        is_foreigner   Foreigner checkbox                          appForm:foreignCheckBox
        passport_id    Passport ID (enabled after checking foreign)appForm:renterIdCard
        notes          Notes                                       appForm:j_idt93
        ============== =========================================== ======================

        Payment method values: 1 = Domestic Payment Account, 2 = Foreign Payment Account,
                               3 = Cash (Μετρητά), 4 = Other (Λοιποί).
        Platform values: 1 = Airbnb, 2 = Booking.com, 3 = Clickstay, 4 = HomeAway,
                         5 = Homestay, 6 = Luxury Retreats, 7 = Only-apartments,
                         8 = TripAdvisor Rentals/Holiday Lettings, 9 = Other platforms.
        """
        # --- Arrival date ---
        self._set_date_input("appForm:rentalFrom_input", declaration_data['arrival_date'])

        # --- Departure date ---
        self._set_date_input("appForm:rentalTo_input", declaration_data['departure_date'])

        # --- Total agreed rent ---
        rent_input = self._first_visible([(By.ID, "appForm:sumAmount_input")])
        rent_input.clear()
        rent_input.send_keys(declaration_data['total_rent'])

        # --- Method of payment (PrimeFaces dropdown) ---
        self._select_primefaces_dropdown("appForm:paymentType", declaration_data['payment_method'])

        # --- E-platform (PrimeFaces dropdown) ---
        self._select_primefaces_dropdown("appForm:platform", declaration_data['platform'])
        tenant_tin = declaration_data.get('tenant_tin')
        # --- Tenant TIN ---
        if tenant_tin:
            tin_input = self._first_visible([(By.ID, "appForm:renterAfm")])
            tin_input.clear()
            tin_input.send_keys(tenant_tin)
            # Trigger blur so the form can auto-fill name via AJAX if applicable.
            self.driver.execute_script(
                "arguments[0].dispatchEvent(new Event('blur', {bubbles:true}));",
                tin_input,
            )

        # --- Foreigner checkbox + Passport ID ---
        is_foreigner = declaration_data.get('is_foreigner', False)
        passport_id = declaration_data.get('passport_id')
        if is_foreigner:
            checkbox_box = self._first_clickable(
                [(By.CSS_SELECTOR, "#appForm\\:foreignCheckBox .ui-chkbox-box")]
            )
            if "ui-state-default" in (checkbox_box.get_attribute("class") or ""):
                checkbox_box.click()  # tick it only if currently unchecked

            if passport_id:
                # Field is enabled after checking the foreigner box.
                passport_input = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "appForm:renterIdCard"))
                )
                passport_input.clear()
                passport_input.send_keys(passport_id)

        # --- Notes ---
        notes = declaration_data.get('notes')
        if notes:
            notes_el = self._first_visible(
                [(By.CSS_SELECTOR, "textarea[name='appForm:j_idt93']")]
            )
            notes_el.clear()
            notes_el.send_keys(notes)

        self._take_screenshot("filled_declaration_fields")

    def submit_declaration(self) -> None:
        self._take_screenshot("before_submit_declaration")
        self._first_clickable(
            [
                (By.XPATH,
                 "//button[contains(., 'Υποβολή') or contains(., 'Submit')]"),
                (By.XPATH, "//input[@type='submit']"),
                (By.CSS_SELECTOR, "button[id*='submit']"),
            ]
        ).click()
        self._take_screenshot("after_submit_declaration")

    def create_new_declaration(
            self,
            declaration_data = None,
            submit: bool = False,
            save: bool = False,
    ) -> None:
        """Full flow: open property page -> login -> open declaration -> fill -> optional submit."""
        self.open_property_page(property_id=self.property_id)
        self.login(username=self.username or "", password=self.password or "")
        self.click_new_declaration()
        self.fill_declaration_fields(declaration_data = declaration_data )
        if submit:
            self.submit_declaration()
        elif save:
            self.save_draft()

    def save_draft(self):
        pass
