"""
Form filler module for identifying and filling form fields.
"""

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from playwright.async_api import ElementHandle, Frame, Page

if TYPE_CHECKING:
    from .llm_helper import LLMHelper

from .config import (
    Profile,
    CustomAnswer,
    load_custom_answers,
    find_custom_answer,
    save_pending_question,
    promote_pending_to_answered,
)
from .field_mapping import (
    FIELD_PATTERNS,
    HIGH_RISK_FIELDS,
    EEO_DECLINE_OPTIONS,
    FieldPattern,
    FieldType,
    is_high_risk_field,
    is_eeo_field,
    is_eeo_keyword_in_text,
)


@dataclass
class FormField:
    """Represents a detected form field."""
    element: ElementHandle
    field_type: FieldType
    label: str
    name: str
    input_type: str  # text, select, checkbox, radio, file, textarea
    options: List[str]  # For select/radio fields
    current_value: str
    is_required: bool
    confidence: float
    selector: str


@dataclass
class FilledField:
    """Result of filling a field."""
    field: FormField
    filled_value: str
    success: bool
    is_high_risk: bool


class FormFiller:
    """Identifies and fills form fields on job application pages."""

    def __init__(
        self,
        page: Page,
        profile: Profile,
        profile_name: str = "default",
        job_info: str = "",
        llm_helper: Optional["LLMHelper"] = None,
    ):
        self.page = page
        self.profile = profile
        self.profile_name = profile_name
        self.job_info = job_info  # For context when saving pending questions
        self.llm_helper = llm_helper  # Optional LLM for answering unknown questions
        self._active_frame: Frame = None  # Track which frame has the form
        self._iframe_selector: str = None  # Store iframe selector for re-acquisition
        self._file_input_count: int = 0  # Track file inputs to distinguish resume vs cover letter

        # Parse job_info for LLM context
        self._job_title = ""
        self._company_name = ""
        if " - " in job_info:
            parts = job_info.split(" - ", 1)
            self._company_name = parts[0]
            self._job_title = parts[1] if len(parts) > 1 else ""

        # Load custom answers for this profile
        self._custom_answers: List[CustomAnswer] = []
        self._load_custom_answers()

    def _load_custom_answers(self):
        """Load custom answers from profile's custom_answers.yaml."""
        try:
            answered, pending = load_custom_answers(self.profile_name)
            self._custom_answers = answered

            # Promote any pending questions that now have answers
            promoted = promote_pending_to_answered(self.profile_name)
            if promoted > 0:
                print(f"  Promoted {promoted} answered questions from pending")
                # Reload to get the promoted answers
                answered, _ = load_custom_answers(self.profile_name)
                self._custom_answers = answered

            if self._custom_answers:
                print(f"  Loaded {len(self._custom_answers)} custom answers")
        except Exception as e:
            print(f"  Warning: Could not load custom answers: {e}")
            self._custom_answers = []

    def _check_custom_answer(self, field: "FormField") -> Optional[str]:
        """Check if we have a custom answer for this field.

        Args:
            field: The form field to check

        Returns:
            The answer string if found, None otherwise
        """
        if not self._custom_answers:
            return None

        # Get dropdown options if available
        options = field.options if field.options else []

        # Also try to get options from the dropdown if it's a custom dropdown field
        # (options list may be empty for custom dropdown components)

        answer = find_custom_answer(field.label, options, self._custom_answers)
        if answer:
            print(f"    Found custom answer for '{field.label}': '{answer}'")
        return answer

    def _save_unanswered_question(self, field: "FormField", options: List[str] = None):
        """Save an unanswered question to pending list for user to fill later."""
        # Don't save EEO fields (they have decline options)
        if is_eeo_field(field.field_type):
            return

        # Don't save standard profile fields that just have no profile data
        # These should be filled in the profile.yaml, not custom_answers.yaml
        standard_fields = {
            FieldType.FIRST_NAME, FieldType.LAST_NAME, FieldType.FULL_NAME,
            FieldType.EMAIL, FieldType.PHONE, FieldType.ADDRESS,
            FieldType.CITY, FieldType.STATE, FieldType.ZIP_CODE, FieldType.COUNTRY,
            FieldType.LINKEDIN, FieldType.GITHUB, FieldType.PORTFOLIO, FieldType.WEBSITE,
            FieldType.RESUME, FieldType.COVER_LETTER,
            FieldType.CURRENT_COMPANY, FieldType.CURRENT_TITLE,
            FieldType.UNIVERSITY, FieldType.HIGHEST_DEGREE, FieldType.FIELD_OF_STUDY,
            FieldType.YEARS_OF_EXPERIENCE, FieldType.GRADUATION_YEAR,
            FieldType.EXPECTED_SALARY, FieldType.SALARY_RANGE_MIN, FieldType.SALARY_RANGE_MAX,
            FieldType.START_DATE, FieldType.AVAILABLE_IMMEDIATELY,
            FieldType.AUTHORIZED_TO_WORK, FieldType.REQUIRE_SPONSORSHIP, FieldType.VISA_STATUS,
            FieldType.WILLING_TO_RELOCATE, FieldType.HOW_DID_YOU_HEAR,
        }
        if field.field_type in standard_fields:
            return

        # Get options to save (only if non-empty)
        opts = options if options else field.options
        opts = opts if opts else []  # Ensure it's a list, not None

        # Save the question
        save_pending_question(
            profile_name=self.profile_name,
            question=field.label,
            options=opts,
            job_info=self.job_info
        )

    async def _find_form_frame(self) -> Frame:
        """Find the frame containing the application form (main page or iframe)."""
        # First check for Greenhouse-specific iframes (common pattern)
        grnhse_selectors = ['#grnhse_iframe', '#grnhse_app iframe', 'iframe[src*="greenhouse"]']
        for selector in grnhse_selectors:
            try:
                grnhse_iframe = await self.page.query_selector(selector)
                if grnhse_iframe:
                    frame = await grnhse_iframe.content_frame()
                    if frame:
                        inputs = await frame.query_selector_all(
                            "input:not([type='hidden']):not([type='submit']):not([type='button']), "
                            "textarea, select"
                        )
                        if len(inputs) > 0:
                            print(f"Found Greenhouse iframe: {frame.url[:80]}...")
                            self._iframe_selector = selector
                            return frame
            except Exception:
                continue

        # Check main page
        main_inputs = await self.page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']), "
            "textarea, select"
        )
        if len(main_inputs) > 3:  # Likely has a form
            self._iframe_selector = None
            return self.page.main_frame

        # Check iframes for forms (e.g., other ATS embeds)
        iframes = await self.page.query_selector_all('iframe')
        for i, iframe in enumerate(iframes):
            try:
                frame = await iframe.content_frame()
                if not frame:
                    continue

                frame_url = frame.url
                if any(keyword in frame_url.lower() for keyword in
                       ['greenhouse', 'lever', 'ashby', 'workday', 'job_app', 'apply']):
                    inputs = await frame.query_selector_all(
                        "input:not([type='hidden']):not([type='submit']):not([type='button']), "
                        "textarea, select"
                    )
                    if len(inputs) > 3:
                        print(f"Found form in iframe: {frame_url[:80]}...")
                        # Store iframe selector for later re-acquisition
                        iframe_id = await iframe.get_attribute('id')
                        iframe_name = await iframe.get_attribute('name')
                        if iframe_id:
                            self._iframe_selector = f'iframe#{iframe_id}'
                        elif iframe_name:
                            self._iframe_selector = f'iframe[name="{iframe_name}"]'
                        else:
                            self._iframe_selector = f'iframe:nth-of-type({i+1})'
                        return frame
            except Exception:
                continue

        # Fallback: check all frames
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                inputs = await frame.query_selector_all(
                    "input:not([type='hidden']):not([type='submit']):not([type='button']), "
                    "textarea, select"
                )
                if len(inputs) > 3:
                    print(f"Found form in iframe: {frame.url[:80]}...")
                    return frame
            except Exception:
                continue

        self._iframe_selector = None
        return self.page.main_frame

    async def _get_active_frame(self) -> Frame:
        """Get or re-acquire the active frame."""
        if self._iframe_selector:
            try:
                iframe = await self.page.query_selector(self._iframe_selector)
                if iframe:
                    frame = await iframe.content_frame()
                    if frame:
                        return frame
            except Exception:
                pass

        # Fallback to finding the frame again
        return await self._find_form_frame()

    async def extract_form_fields(self) -> List[FormField]:
        """Extract all fillable form fields from the page or iframe."""
        fields = []

        # Find the frame with the form
        self._active_frame = await self._find_form_frame()

        # Find all input fields in the active frame
        inputs = await self._active_frame.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='button']), "
            "textarea, select"
        )

        for element in inputs:
            # Skip invisible elements to avoid duplicates
            try:
                if not await element.is_visible():
                    continue
            except Exception:
                continue

            field = await self._analyze_field(element)
            if field:
                fields.append(field)

        return fields

    async def _analyze_field(self, element: ElementHandle) -> Optional[FormField]:
        """Analyze a form element and determine its semantic type."""
        try:
            # Get element properties
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            input_type = await element.get_attribute("type") or "text"
            name = await element.get_attribute("name") or ""
            id_attr = await element.get_attribute("id") or ""
            placeholder = await element.get_attribute("placeholder") or ""
            aria_label = await element.get_attribute("aria-label") or ""

            # Determine input type category
            if tag_name == "select":
                input_type = "select"
            elif tag_name == "textarea":
                input_type = "textarea"
            elif input_type in ("checkbox", "radio"):
                pass  # Keep as is
            elif input_type == "file":
                pass  # Keep as is

            # Get label text
            label = await self._get_field_label(element, id_attr)

            # Get current value
            current_value = ""
            if input_type == "select":
                current_value = await element.evaluate(
                    "el => el.options[el.selectedIndex]?.text || ''"
                )
            elif input_type in ("checkbox", "radio"):
                is_checked = await element.is_checked()
                current_value = "checked" if is_checked else ""
            else:
                current_value = await element.input_value() or ""

            # Get options for select fields
            options = []
            if input_type == "select":
                options = await element.evaluate(
                    "el => Array.from(el.options).map(o => o.text)"
                )

            # Check if required
            is_required = await element.evaluate(
                "el => el.required || el.getAttribute('aria-required') === 'true'"
            )

            # Match to semantic field type
            field_type, confidence = self._match_field_type(
                label, name, id_attr, placeholder, aria_label
            )

            # Build selector
            selector = await self._build_selector(element, name, id_attr)

            return FormField(
                element=element,
                field_type=field_type,
                label=label or placeholder or name,
                name=name,
                input_type=input_type,
                options=options,
                current_value=current_value,
                is_required=is_required,
                confidence=confidence,
                selector=selector,
            )
        except Exception as e:
            print(f"Error analyzing field: {e}")
            return None

    async def _get_field_label(self, element: ElementHandle, id_attr: str) -> str:
        """Get the label text for a form field."""
        # Use active frame if available, otherwise main page
        frame = self._active_frame or self.page.main_frame

        # Try finding associated label
        if id_attr:
            label_elem = await frame.query_selector(f'label[for="{id_attr}"]')
            if label_elem:
                return (await label_elem.inner_text()).strip()

        # Try parent label
        parent_label = await element.evaluate("""
            el => {
                let parent = el.closest('label');
                return parent ? parent.innerText.trim() : '';
            }
        """)
        if parent_label:
            return parent_label

        # Try previous sibling or nearby text
        nearby_text = await element.evaluate("""
            el => {
                let prev = el.previousElementSibling;
                if (prev && prev.tagName === 'LABEL') return prev.innerText.trim();
                let parent = el.parentElement;
                if (parent) {
                    let label = parent.querySelector('label');
                    if (label) return label.innerText.trim();
                }
                return '';
            }
        """)

        if nearby_text:
            return nearby_text

        # For file inputs, look for field title in parent container (Greenhouse style)
        container_label = await element.evaluate("""
            el => {
                // Look up to 5 levels for a container with a heading/label
                let current = el.parentElement;
                for (let i = 0; i < 5 && current; i++) {
                    // Look for common heading patterns
                    let heading = current.querySelector('h3, h4, .field-label, .label, [class*="title"]');
                    if (heading) {
                        let text = heading.innerText.trim();
                        if (text && text.length < 100) return text;
                    }
                    // Check for text that looks like a field name
                    let firstText = current.querySelector('span, div, p');
                    if (firstText && firstText !== el) {
                        let text = firstText.innerText.trim();
                        if (text && text.length < 50 && !text.includes('\\n')) {
                            // Check if it's not just "Attach" or similar generic text
                            if (text.toLowerCase() !== 'attach' &&
                                text.toLowerCase() !== 'upload' &&
                                text.toLowerCase() !== 'choose file') {
                                return text;
                            }
                        }
                    }
                    current = current.parentElement;
                }
                return '';
            }
        """)

        return container_label or nearby_text

    async def _build_selector(
        self, element: ElementHandle, name: str, id_attr: str
    ) -> str:
        """Build a reliable and UNIQUE CSS selector for the element."""
        if id_attr:
            # IDs starting with numbers are invalid CSS selectors, use attribute selector
            if id_attr[0].isdigit():
                return f'[id="{id_attr}"]'
            return f"#{id_attr}"
        if name:
            return f'[name="{name}"]'

        # Try to build a unique selector using multiple strategies
        selector = await element.evaluate("""
            el => {
                // Strategy 1: Use unique data attributes
                if (el.dataset && Object.keys(el.dataset).length > 0) {
                    for (let key of Object.keys(el.dataset)) {
                        let selector = `[data-${key}="${el.dataset[key]}"]`;
                        // Check if this selector is unique
                        if (document.querySelectorAll(selector).length === 1) {
                            return selector;
                        }
                    }
                }

                // Strategy 2: Use aria-describedby (often unique)
                if (el.getAttribute('aria-describedby')) {
                    let selector = `[aria-describedby="${el.getAttribute('aria-describedby')}"]`;
                    if (document.querySelectorAll(selector).length === 1) {
                        return selector;
                    }
                }

                // Strategy 3: Use aria-labelledby
                if (el.getAttribute('aria-labelledby')) {
                    let selector = `[aria-labelledby="${el.getAttribute('aria-labelledby')}"]`;
                    if (document.querySelectorAll(selector).length === 1) {
                        return selector;
                    }
                }

                // Strategy 4: Use aria-label
                if (el.getAttribute('aria-label')) {
                    let selector = `[aria-label="${el.getAttribute('aria-label')}"]`;
                    if (document.querySelectorAll(selector).length === 1) {
                        return selector;
                    }
                }

                // Strategy 5: Use placeholder
                if (el.placeholder) {
                    let selector = `[placeholder="${el.placeholder}"]`;
                    if (document.querySelectorAll(selector).length === 1) {
                        return selector;
                    }
                }

                // Strategy 6: Use autocomplete attribute
                if (el.getAttribute('autocomplete')) {
                    let selector = `[autocomplete="${el.getAttribute('autocomplete')}"]`;
                    if (document.querySelectorAll(selector).length === 1) {
                        return selector;
                    }
                }

                // Strategy 7: Build an index-based selector (most reliable fallback)
                // Find this element's position among siblings of same tag/type
                let tag = el.tagName.toLowerCase();
                let type = el.type || '';
                let parent = el.parentElement;

                if (parent) {
                    let siblings = parent.querySelectorAll(tag + (type ? `[type="${type}"]` : ''));
                    for (let i = 0; i < siblings.length; i++) {
                        if (siblings[i] === el) {
                            // Build a more specific path
                            let parentClass = parent.className ? '.' + parent.className.split(' ')[0] : '';
                            let parentId = parent.id ? '#' + parent.id : '';
                            let parentSelector = parentId || parentClass || parent.tagName.toLowerCase();
                            return `${parentSelector} > ${tag}${type ? `[type="${type}"]` : ''}:nth-of-type(${i + 1})`;
                        }
                    }
                }

                // Last resort
                if (type) {
                    return `${tag}[type="${type}"]`;
                }
                return tag;
            }
        """)
        return selector or 'input'

    def _match_field_type(
        self,
        label: str,
        name: str,
        id_attr: str,
        placeholder: str,
        aria_label: str,
    ) -> Tuple[FieldType, float]:
        """Match field attributes to semantic type."""
        # Combine all text for matching
        combined = f"{label} {name} {id_attr} {placeholder} {aria_label}".lower()

        best_match = (FieldType.UNKNOWN, 0.0)

        for pattern in FIELD_PATTERNS:
            score = 0.0

            # Check label patterns (highest weight)
            for p in pattern.label_patterns:
                if re.search(p, label.lower()):
                    score = max(score, 0.9)
                    break

            # Check name/id patterns
            for p in pattern.name_patterns:
                if re.search(p, name.lower()) or re.search(p, id_attr.lower()):
                    score = max(score, 0.8)
                    break

            # Check placeholder patterns
            for p in pattern.placeholder_patterns:
                if re.search(p, placeholder.lower()):
                    score = max(score, 0.7)
                    break

            if score > best_match[1]:
                best_match = (pattern.field_type, score)

        return best_match

    async def _reacquire_element(self, field: FormField, retries: int = 3) -> Optional[ElementHandle]:
        """Re-acquire an element handle using its selector with retries."""
        if not field.selector:
            return field.element

        for attempt in range(retries):
            try:
                frame = await self._get_active_frame()
                element = await frame.query_selector(field.selector)
                if element:
                    # Verify element is attached
                    try:
                        await element.is_visible()
                        return element
                    except Exception:
                        # Element detached, retry
                        await asyncio.sleep(0.5)
                        continue
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(0.5)
                continue
        return None

    async def _find_element_by_label(self, field: FormField) -> Optional[ElementHandle]:
        """
        Fallback method to find form element by its label text.
        Used when selector-based lookup fails.
        """
        frame = self._active_frame or self.page.main_frame
        label_text = field.label.replace("*", "").strip()

        if not label_text:
            return None

        try:
            # Method 1: Find label and get associated input via 'for' attribute
            element_id = await frame.evaluate(f"""
                () => {{
                    let labels = document.querySelectorAll('label');
                    for (let label of labels) {{
                        let text = label.innerText.trim().replace('*', '').trim();
                        if (text.toLowerCase() === "{label_text.lower()}") {{
                            let forId = label.getAttribute('for');
                            if (forId) {{
                                let input = document.getElementById(forId);
                                if (input) return forId;
                            }}
                            // Check for input inside label
                            let input = label.querySelector('input, select, textarea');
                            if (input && input.id) return input.id;
                        }}
                    }}
                    return null;
                }}
            """)
            if element_id:
                # Use getElementById via JS if ID starts with number (invalid CSS selector)
                if element_id[0].isdigit():
                    el = await frame.evaluate_handle(f'document.getElementById("{element_id}")')
                    if el:
                        return el.as_element()
                else:
                    el = await frame.query_selector(f'#{element_id}')
                    if el and await el.is_visible():
                        return el

            # Method 2: Find input near label text using aria-labelledby
            element = await frame.query_selector(f'[aria-label*="{label_text}" i]')
            if element and await element.is_visible():
                return element

            # Method 3: Find by placeholder
            element = await frame.query_selector(f'[placeholder*="{label_text}" i]')
            if element and await element.is_visible():
                return element

            # Method 4: Look for input/select in same container as label text
            element_id = await frame.evaluate(f"""
                () => {{
                    // Find elements containing the label text
                    let walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    while (walker.nextNode()) {{
                        let text = walker.currentNode.textContent.trim().replace('*', '').trim();
                        if (text.toLowerCase() === "{label_text.lower()}") {{
                            // Look for nearby input/select
                            let parent = walker.currentNode.parentElement;
                            for (let i = 0; i < 5 && parent; i++) {{
                                let input = parent.querySelector('input:not([type="hidden"]), select, textarea');
                                if (input && input.id) return input.id;
                                if (input && input.name) return `[name="${{input.name}}"]`;
                                parent = parent.parentElement;
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            if element_id:
                if element_id.startswith('['):
                    el = await frame.query_selector(element_id)
                else:
                    el = await frame.query_selector(f'#{element_id}')
                if el and await el.is_visible():
                    return el

        except Exception as e:
            print(f"    Label lookup error for '{label_text}': {e}")

        return None

    async def fill_field(self, field: FormField) -> FilledField:
        """Fill a single form field with the appropriate value."""
        value = self._get_value_for_field(field)

        if not value and field.field_type != FieldType.UNKNOWN:
            # Save unanswered question for user to fill later
            self._save_unanswered_question(field)
            return FilledField(
                field=field,
                filled_value="",
                success=False,
                is_high_risk=is_high_risk_field(field.field_type),
            )

        try:
            # Re-acquire element to handle frame detachment
            element = await self._reacquire_element(field)
            if not element:
                # Try fallback element finding for certain field types
                element = await self._find_element_by_label(field)
                if not element:
                    print(f"Could not find element for field: {field.label}")
                    return FilledField(
                        field=field,
                        filled_value=value,
                        success=False,
                        is_high_risk=is_high_risk_field(field.field_type),
                    )

            # Update the field's element reference
            field.element = element

            # Debug: Log the selector being used
            # print(f"  Filling '{field.label}' using selector: {field.selector}")

            success = await self._fill_by_type(field, value)

            # Verify the field wasn't cleared (sanity check for First Name issue)
            if success and field.field_type == FieldType.FIRST_NAME:
                await asyncio.sleep(0.1)
                try:
                    current_val = await element.input_value()
                    if current_val != value:
                        print(f"  WARNING: First Name value changed from '{value}' to '{current_val}'")
                except Exception:
                    pass

            return FilledField(
                field=field,
                filled_value=value,
                success=success,
                is_high_risk=is_high_risk_field(field.field_type),
            )
        except Exception as e:
            print(f"Fill error for {field.label}: {e}")
            return FilledField(
                field=field,
                filled_value=value,
                success=False,
                is_high_risk=is_high_risk_field(field.field_type),
            )

    def _get_value_for_field(self, field: FormField) -> str:
        """Get the appropriate value for a field from the profile."""
        # Map field type to profile value
        value = self.profile.get_field_value(field.field_type.value)

        # === Validate that value makes sense for field type ===
        # Prevent cross-contamination (e.g., visa status "H1B" in disability field)
        if value:
            value_lower = value.lower()
            label_lower = field.label.lower()

            # Don't use visa values for non-visa fields
            visa_values = ["h1b", "h-1b", "opt", "f1", "f-1", "green card", "l1", "l-1", "tn", "o1", "o-1"]
            is_visa_value = any(v in value_lower for v in visa_values)
            is_visa_field = field.field_type in {FieldType.VISA_STATUS, FieldType.AUTHORIZED_TO_WORK, FieldType.REQUIRE_SPONSORSHIP}
            is_visa_label = any(kw in label_lower for kw in ["visa", "immigration", "sponsorship", "authorization", "work status"])
            # EEO fields should never get visa values
            is_eeo_label = any(kw in label_lower for kw in [
                "disability", "veteran", "gender", "race", "ethnicity", "hispanic",
                "do not want to answer", "decline", "prefer not", "self-identify"
            ])

            if is_visa_value and (not is_visa_field or is_eeo_label) and not is_visa_label:
                # This is a visa value being used for a non-visa field - skip it
                print(f"    Skipping value '{value}' for non-visa field '{field.label}'")
                value = None

            # Don't use salary values for non-salary fields
            if value and field.field_type not in {FieldType.EXPECTED_SALARY, FieldType.SALARY_RANGE_MIN, FieldType.SALARY_RANGE_MAX}:
                if any(c.isdigit() for c in value) and ("," in value or len(value) > 5):
                    salary_keywords = ["salary", "compensation", "pay", "wage"]
                    if not any(kw in label_lower for kw in salary_keywords):
                        # Might be a salary value in wrong field
                        try:
                            # Check if it looks like a salary (e.g., "500,000")
                            clean_val = value.replace(",", "").replace("$", "")
                            if clean_val.isdigit() and int(clean_val) > 10000:
                                print(f"    Skipping salary-like value '{value}' for field '{field.label}'")
                                value = None
                        except Exception:
                            pass

        if value:
            return value

        # Check default answers
        if field.field_type == FieldType.HOW_DID_YOU_HEAR:
            return self.profile.default_answers.get("how_did_you_hear", "")

        # Check custom answers for unknown/unmapped fields
        custom_answer = self._check_custom_answer(field)
        if custom_answer:
            return custom_answer

        # For file inputs, check if it's likely a resume or cover letter field
        if field.input_type == "file":
            label_lower = field.label.lower()
            name_lower = field.name.lower() if field.name else ""

            # Check if this is explicitly a cover letter field by label or field name
            is_cover_letter = (
                "cover" in label_lower or "letter" in label_lower or
                "cover" in name_lower or "letter" in name_lower
            )

            # Check if this is explicitly a resume field
            is_resume = (
                "resume" in label_lower or "cv" in label_lower or
                "resume" in name_lower or "cv" in name_lower
            )

            if is_cover_letter:
                cover_letter_path = self.profile.get_field_value("cover_letter")
                if cover_letter_path:
                    return cover_letter_path
                # Don't upload resume to cover letter field
                return ""

            if is_resume:
                resume_path = self.profile.resume.get_absolute_path()
                if resume_path:
                    return str(resume_path)

            # For generic file inputs (like "Attach"), use position:
            # First file input = resume, subsequent = skip (likely cover letter)
            self._file_input_count += 1
            if self._file_input_count == 1:
                # First file input - assume it's resume
                resume_path = self.profile.resume.get_absolute_path()
                if resume_path:
                    return str(resume_path)
            # Skip additional file inputs without clear labels
            return ""

        # FALLBACK: Use LLM helper if available
        # Only for non-trivial fields that couldn't be matched
        if self.llm_helper and self.llm_helper.is_available():
            # Skip LLM for simple fields that just don't have profile data
            skip_llm_types = {
                FieldType.FIRST_NAME, FieldType.LAST_NAME, FieldType.EMAIL,
                FieldType.PHONE, FieldType.ADDRESS, FieldType.ZIP_CODE,
                FieldType.LINKEDIN, FieldType.GITHUB, FieldType.PORTFOLIO,
                FieldType.WEBSITE, FieldType.RESUME, FieldType.COVER_LETTER,
            }
            if field.field_type not in skip_llm_types:
                print(f"    Asking LLM for: '{field.label}'")
                llm_answer = self.llm_helper.answer_form_field(
                    field=field,
                    custom_answers=self._custom_answers,
                    job_title=self._job_title,
                    company_name=self._company_name,
                )
                if llm_answer:
                    return llm_answer

        return ""

    async def _fill_by_type(self, field: FormField, value: str) -> bool:
        """Fill field based on its input type."""
        try:
            # Check if this is an EEO field - use special handling
            is_eeo = is_eeo_field(field.field_type) or is_eeo_keyword_in_text(field.label)


            if field.input_type == "file":
                return await self._fill_file(field, value)
            elif field.input_type == "select":
                if is_eeo:
                    return await self._fill_eeo_select(field, value)
                return await self._fill_select(field, value)
            elif field.input_type == "checkbox":
                return await self._fill_checkbox(field, value)
            elif field.input_type == "radio":
                if is_eeo:
                    return await self._fill_eeo_radio(field, value)
                return await self._fill_radio(field, value)
            else:
                # text, email, tel, textarea, etc.
                return await self._fill_text(field, value)
        except Exception as e:
            print(f"Fill error for {field.label}: {e}")
            return False

    async def _fill_text(self, field: FormField, value: str) -> bool:
        """Fill a text input or textarea."""
        try:
            # Check if element is visible first (with short timeout)
            if not await field.element.is_visible():
                # For phone fields, try alternative selectors
                if field.field_type == FieldType.PHONE:
                    return await self._fill_phone_fallback(field, value)
                return False

            # Check if this is an EEO field or other custom dropdown that needs special handling
            is_eeo = is_eeo_field(field.field_type) or is_eeo_keyword_in_text(field.label)

            # Also handle work authorization and other Yes/No dropdown fields
            label_lower = field.label.lower()
            is_custom_dropdown = (
                is_eeo or
                field.field_type in {FieldType.AUTHORIZED_TO_WORK, FieldType.REQUIRE_SPONSORSHIP, FieldType.HOW_DID_YOU_HEAR} or
                any(kw in label_lower for kw in [
                    "authorized", "sponsorship", "visa", "legally",
                    "worked for", "previously worked", "currently work",
                    "how did you hear", "hear about", "referral source",
                ])
            )

            if is_custom_dropdown:
                # Try custom dropdown handling
                success = await self._fill_eeo_text_dropdown(field, value)
                if success:
                    return True
                # Fall through to regular text fill if custom dropdown handling failed

            # Check if this field might have autocomplete dropdown
            # Common for: location, city, state, school, university, company, etc.
            autocomplete_fields = {
                FieldType.CITY, FieldType.STATE, FieldType.COUNTRY,
                FieldType.UNIVERSITY, FieldType.CURRENT_COMPANY,
                FieldType.ADDRESS,
            }
            label_lower = field.label.lower()
            is_autocomplete_candidate = (
                field.field_type in autocomplete_fields or
                any(kw in label_lower for kw in [
                    "location", "city", "state", "school", "university",
                    "college", "company", "employer", "institution"
                ])
            )

            if is_autocomplete_candidate:
                success = await self._fill_autocomplete_field(field, value)
                if success:
                    return True
                # Fall through to regular text fill if autocomplete handling failed

            # Standard text fill - ensure proper focus
            await field.element.focus()
            await asyncio.sleep(0.05)
            await field.element.click(timeout=5000)
            await field.element.fill("")  # Clear existing value
            await field.element.fill(value)
            await asyncio.sleep(0.1)  # Small delay for validation
            return True
        except Exception:
            # For phone fields, try fallback
            if field.field_type == FieldType.PHONE:
                return await self._fill_phone_fallback(field, value)
            return False

    async def _fill_phone_fallback(self, field: FormField, value: str) -> bool:
        """
        Fallback method for filling phone fields when standard methods fail.
        Tries multiple selectors and strategies.
        """
        frame = self._active_frame or self.page.main_frame

        # Common phone field selectors
        phone_selectors = [
            'input[type="tel"]',
            'input[name*="phone"]',
            'input[name*="Phone"]',
            'input[id*="phone"]',
            'input[id*="Phone"]',
            'input[placeholder*="phone"]',
            'input[placeholder*="Phone"]',
            'input[autocomplete="tel"]',
            'input[autocomplete="tel-national"]',
            '[data-testid*="phone"]',
            '[data-qa*="phone"]',
            # Ashby specific
            'input[name="phoneNumber"]',
            'input[name="phone_number"]',
            '[data-field="phoneNumber"]',
        ]

        for selector in phone_selectors:
            try:
                element = await frame.query_selector(selector)
                if element and await element.is_visible():
                    await element.focus()
                    await element.fill("")
                    await element.fill(value)
                    print(f"  Phone filled via fallback selector: {selector}")
                    return True
            except Exception:
                continue

        # Try finding by label text
        try:
            # Find label containing "phone" and then find its input
            phone_input_id = await frame.evaluate("""
                () => {
                    // Look for labels containing "phone"
                    let labels = document.querySelectorAll('label');
                    for (let label of labels) {
                        if (label.innerText.toLowerCase().includes('phone')) {
                            // Try to find associated input
                            let forId = label.getAttribute('for');
                            if (forId) {
                                let input = document.getElementById(forId);
                                if (input) return forId;
                            }
                            // Check for input inside label
                            let input = label.querySelector('input');
                            if (input && input.id) return input.id;
                        }
                    }
                    return null;
                }
            """)
            if phone_input_id:
                # Handle IDs starting with numbers (invalid CSS)
                if phone_input_id[0].isdigit():
                    element = await frame.evaluate_handle(f'document.getElementById("{phone_input_id}")')
                    if element:
                        el = element.as_element()
                        if el:
                            await el.focus()
                            await el.fill("")
                            await el.fill(value)
                            print(f"  Phone filled via label lookup (JS): {phone_input_id}")
                            return True
                else:
                    element = await frame.query_selector(f'#{phone_input_id}')
                    if element:
                        await element.focus()
                        await element.fill("")
                        await element.fill(value)
                        print(f"  Phone filled via label lookup: #{phone_input_id}")
                        return True
        except Exception as e:
            print(f"  Phone label lookup error: {e}")

        print(f"  Phone fallback failed for '{field.label}'")
        return False

    async def _fill_autocomplete_field(self, field: FormField, value: str) -> bool:
        """
        Handle autocomplete/typeahead fields that show dropdown suggestions.

        Common for location, city, school, company fields where typing triggers
        a dropdown with multiple options like:
        - "San Diego, CA, United States"
        - "San Diego County, CA"
        - "San Diego State University"

        Uses keyboard navigation to select options (safer than clicking).
        """
        try:
            # Re-acquire element to ensure we have fresh reference
            element = await self._reacquire_element(field)
            if not element:
                return False
            field.element = element

            # Focus and click the field explicitly
            await element.focus()
            await asyncio.sleep(0.1)
            await element.click()
            await asyncio.sleep(0.1)

            # Clear and type the value using fill() - faster and more reliable
            await element.fill("")
            await element.fill(value)
            await asyncio.sleep(1.0)  # Wait longer for autocomplete to fully populate

            # Get the options text from the field's associated dropdown only
            dropdown_options = await self._get_field_dropdown_options(field)

            if not dropdown_options:
                # No dropdown appeared, return False to let regular fill handle it
                return False

            print(f"  Autocomplete options for '{field.label}': {dropdown_options[:5]}")

            # Find the best option index using scoring
            best_index = self._score_autocomplete_options(field, value, dropdown_options)

            if best_index >= 0:
                best_option = dropdown_options[best_index]

                # Method 1: Try clicking on the option element directly
                frame = self._active_frame or self.page.main_frame
                option_clicked = False

                try:
                    # Re-type to refresh the dropdown
                    await element.focus()
                    await element.fill("")
                    await element.fill(value)
                    await asyncio.sleep(0.5)

                    # Find and click the matching option element
                    option_elements = await frame.query_selector_all('[role="option"]')
                    for opt_el in option_elements:
                        try:
                            opt_text = await opt_el.inner_text()
                            if opt_text and best_option in opt_text.strip():
                                if await opt_el.is_visible():
                                    await opt_el.click()
                                    option_clicked = True
                                    await asyncio.sleep(0.3)
                                    break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"    Click option failed: {e}")

                # Method 2: If clicking failed, try keyboard navigation
                if not option_clicked:
                    await element.focus()
                    await asyncio.sleep(0.1)
                    # Navigate to the option
                    for i in range(best_index + 1):
                        await element.press("ArrowDown")
                        await asyncio.sleep(0.05)
                    await element.press("Enter")
                    await asyncio.sleep(0.3)

                print(f"  Selected autocomplete: '{best_option}'")
                return True

            # No good match, press Escape and return False
            await element.press("Escape")
            await asyncio.sleep(0.1)
            return False

        except Exception as e:
            print(f"  Autocomplete error for {field.label}: {e}")
            try:
                await field.element.press("Escape")
            except Exception:
                pass
            return False

    async def _get_field_dropdown_options(self, field: FormField) -> List[str]:
        """
        Get dropdown options specifically associated with this field.
        Uses aria-controls or parent container to find the right dropdown.
        Returns list of option texts (not element handles to avoid clicking wrong elements).
        """
        try:
            # Method 1: Use aria-controls to find associated listbox
            options = await field.element.evaluate("""
                el => {
                    let results = [];

                    // Check aria-controls first (most reliable)
                    let ariaControls = el.getAttribute('aria-controls');
                    if (ariaControls) {
                        let listbox = document.getElementById(ariaControls);
                        if (listbox) {
                            let opts = listbox.querySelectorAll('[role="option"], li, div');
                            opts.forEach(opt => {
                                let text = opt.innerText.trim();
                                // Filter out empty, very long, or phone-number-like options
                                if (text && text.length > 0 && text.length < 150) {
                                    // Skip if it looks like a country code (e.g., "United States +1")
                                    if (!text.match(/\\+\\d+$/)) {
                                        results.push(text);
                                    } else {
                                        // For country codes, extract just the country name
                                        let match = text.match(/^(.+?)\\s*\\+\\d+$/);
                                        if (match) {
                                            results.push(match[1].trim());
                                        }
                                    }
                                }
                            });
                            if (results.length > 0) return results;
                        }
                    }

                    // Method 2: Look in parent containers (up to 6 levels)
                    let parent = el.parentElement;
                    for (let i = 0; i < 6 && parent; i++) {
                        // Find dropdown/listbox that's visible
                        let containers = parent.querySelectorAll(
                            '[role="listbox"], [class*="dropdown"]:not([class*="hidden"]), ' +
                            '[class*="autocomplete"], [class*="suggestion"], [class*="options"]'
                        );

                        for (let container of containers) {
                            // Skip if container is hidden
                            let style = window.getComputedStyle(container);
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                continue;
                            }

                            let opts = container.querySelectorAll(
                                '[role="option"], li:not([class*="hidden"]), div[class*="option"]'
                            );

                            opts.forEach(opt => {
                                let text = opt.innerText.trim();
                                if (text && text.length > 0 && text.length < 150) {
                                    if (!text.match(/\\+\\d+$/)) {
                                        results.push(text);
                                    } else {
                                        let match = text.match(/^(.+?)\\s*\\+\\d+$/);
                                        if (match) results.push(match[1].trim());
                                    }
                                }
                            });

                            // If we found reasonable options, return them
                            if (results.length >= 1 && results.length <= 30) {
                                return results;
                            }
                            results = [];  // Reset if too many (probably wrong container)
                        }
                        parent = parent.parentElement;
                    }

                    return results;
                }
            """)

            return options if options else []

        except Exception as e:
            print(f"  Error getting dropdown options: {e}")
            return []

    def _score_autocomplete_options(
        self,
        field: FormField,
        typed_value: str,
        options: List[str]
    ) -> int:
        """
        Score autocomplete options and return the index of the best match.
        Returns -1 if no good match found.
        """
        if not options:
            return -1

        typed_lower = typed_value.lower().strip()
        label_lower = field.label.lower()

        # Get profile context for better matching
        profile_state = self.profile.location.state.lower() if self.profile.location.state else ""
        profile_country = self.profile.location.country.lower() if self.profile.location.country else ""

        # Normalize state names (CA -> california, etc.)
        state_variants = [profile_state]
        state_abbrev_map = {
            "ca": "california", "ny": "new york", "tx": "texas", "fl": "florida",
            "wa": "washington", "il": "illinois", "pa": "pennsylvania", "oh": "ohio",
            "ga": "georgia", "nc": "north carolina", "mi": "michigan", "nj": "new jersey",
            "va": "virginia", "az": "arizona", "ma": "massachusetts", "tn": "tennessee",
            "in": "indiana", "mo": "missouri", "md": "maryland", "wi": "wisconsin",
            "co": "colorado", "mn": "minnesota", "sc": "south carolina", "al": "alabama",
            "la": "louisiana", "ky": "kentucky", "or": "oregon", "ok": "oklahoma",
            "ct": "connecticut", "ut": "utah", "ia": "iowa", "nv": "nevada",
            "ar": "arkansas", "ms": "mississippi", "ks": "kansas", "nm": "new mexico",
        }
        if profile_state.lower() in state_abbrev_map:
            state_variants.append(state_abbrev_map[profile_state.lower()])
        # Also add reverse lookup
        for abbrev, full in state_abbrev_map.items():
            if profile_state.lower() == full:
                state_variants.append(abbrev)

        # Score each option
        scored_options = []
        for idx, opt_text in enumerate(options):
            opt_lower = opt_text.lower()
            score = 0

            # Must contain the typed value (or be very similar)
            if typed_lower not in opt_lower and opt_lower not in typed_lower:
                # Check for partial match at start
                if not opt_lower.startswith(typed_lower[:3]) and not typed_lower.startswith(opt_lower[:3]):
                    continue

            # Base score for containing/matching typed value
            if typed_lower in opt_lower:
                score += 10
            if opt_lower.startswith(typed_lower):
                score += 5

            # Context-aware scoring based on field type
            is_location_field = any(kw in label_lower for kw in ["location", "city"])
            is_country_field = "country" in label_lower

            if is_location_field:
                # For location/city fields, prefer options with matching state/country
                if any(sv in opt_lower for sv in state_variants if sv):
                    score += 50  # Strong preference for matching state

                if profile_country:
                    country_variants = [profile_country]
                    if "united states" in profile_country:
                        country_variants.extend(["usa", "us", "united states", "u.s."])
                    if any(cv in opt_lower for cv in country_variants):
                        score += 30  # Strong preference for matching country

                # Penalize options from OTHER countries when user is in US
                if profile_country and "united states" in profile_country.lower():
                    other_countries = ["costa rica", "mexico", "canada", "puerto rico", "brazil",
                                      "argentina", "chile", "spain", "portugal", "philippines"]
                    if any(oc in opt_lower for oc in other_countries):
                        score -= 100  # Strong penalty for wrong country

                # Penalize non-city matches
                if "county" in opt_lower:
                    score -= 8
                if "university" in opt_lower or "college" in opt_lower or "school" in opt_lower:
                    score -= 15
                if "airport" in opt_lower:
                    score -= 12
                if "station" in opt_lower:
                    score -= 10

            if is_country_field:
                # For country fields, exact match is best
                if opt_lower == typed_lower or typed_lower in opt_lower:
                    score += 10

            # For school/university fields
            is_school_field = any(kw in label_lower for kw in ["school", "university", "college", "institution"])
            if is_school_field:
                if "university" in opt_lower or "college" in opt_lower:
                    score += 5

            # Prefer shorter options (usually more specific/common)
            if len(opt_text) < 40:
                score += 3
            elif len(opt_text) > 80:
                score -= 2

            # Bonus for first few options (usually most relevant)
            if idx == 0:
                score += 2
            elif idx == 1:
                score += 1

            scored_options.append((idx, opt_text, score))

        if not scored_options:
            return -1

        # Sort by score descending
        scored_options.sort(key=lambda x: x[2], reverse=True)

        # Return index of best option (must have positive score)
        best_idx, best_text, best_score = scored_options[0]
        if best_score > 0:
            return best_idx

        return -1

    async def _fill_eeo_text_dropdown(self, field: FormField, value: str) -> bool:
        """
        Handle EEO fields that appear as text inputs but are actually custom dropdowns.

        Greenhouse and other ATS systems often use custom dropdown components that:
        1. Look like text inputs
        2. When clicked, show a dropdown list
        3. May support typing to filter options
        """
        try:
            frame = self._active_frame or self.page.main_frame
            value_lower = value.lower().strip()
            label_lower = field.label.lower()

            # CRITICAL: Don't try to fill if we have no value
            # Empty string would match ANY option via startswith("")
            if not value_lower:
                print(f"    Skipping '{field.label}': no value provided")
                return False

            # Re-acquire element to ensure fresh reference
            element = await self._reacquire_element(field)
            if not element:
                return False
            field.element = element

            # Focus and click the field to reveal dropdown options
            await element.focus()
            await asyncio.sleep(0.05)
            await element.click()
            await asyncio.sleep(0.5)

            # Find all visible option elements
            option_elements = await frame.query_selector_all('[role="option"]')
            visible_options = []
            for opt in option_elements:
                try:
                    if await opt.is_visible():
                        text = await opt.inner_text()
                        if text and text.strip():
                            visible_options.append((opt, text.strip()))
                except Exception:
                    continue

            if visible_options:
                print(f"    EEO dropdown '{field.label}': {len(visible_options)} options - {[o[1][:30] for o in visible_options[:5]]}")

                # Find the best matching option and CLICK it directly
                best_match = None
                best_score = -1

                for opt_el, opt_text in visible_options:
                    opt_lower = opt_text.lower()
                    score = 0

                    # Exact match
                    if opt_lower == value_lower:
                        score = 100

                    # Starts with the value (e.g., "Yes" matches "Yes, I am authorized...")
                    elif opt_lower.startswith(value_lower):
                        score = 80

                    # Value at word boundary
                    elif f" {value_lower}" in f" {opt_lower}" or opt_lower.startswith(value_lower + ","):
                        score = 70

                    # For Yes/No questions
                    elif value_lower == "yes" and opt_lower.startswith("yes"):
                        score = 75
                    elif value_lower == "no" and opt_lower.startswith("no"):
                        score = 75

                    # Contains value (but not as substring of another word)
                    elif value_lower in opt_lower:
                        # Make sure it's not a substring (e.g., "male" in "female")
                        import re
                        if re.search(rf'\b{re.escape(value_lower)}\b', opt_lower):
                            score = 50

                    if score > best_score:
                        best_score = score
                        best_match = (opt_el, opt_text)

                if best_match and best_score > 0:
                    opt_el, opt_text = best_match
                    try:
                        await opt_el.click()
                        print(f"    Selected: '{opt_text}' (score: {best_score})")
                        await asyncio.sleep(0.3)
                        return True
                    except Exception as e:
                        print(f"    Click failed: {e}")

                # Try decline options as fallback
                for opt_el, opt_text in visible_options:
                    opt_lower = opt_text.lower()
                    if any(d in opt_lower for d in ["decline", "prefer not", "don't wish", "choose not"]):
                        try:
                            await opt_el.click()
                            print(f"    Selected decline: '{opt_text}'")
                            await asyncio.sleep(0.3)
                            return True
                        except Exception:
                            continue

            # Close dropdown if nothing selected
            await element.press("Escape")
            await asyncio.sleep(0.1)

            # Save as pending question if we had options but couldn't match
            if visible_options:
                option_texts = [opt[1] for opt in visible_options]
                self._save_unanswered_question(field, option_texts)

            # Fallback: No visible options found or no match
            return False

        except Exception as e:
            print(f"    EEO text dropdown error: {e}")
            return False

    async def _fill_select(self, field: FormField, value: str) -> bool:
        """Fill a select dropdown."""
        label_lower = field.label.lower()
        value_lower = value.lower().strip()

        # === Handle date dropdowns (month/year) ===
        is_month_field = any(kw in label_lower for kw in ["month", "start date", "end date"])
        is_year_field = "year" in label_lower

        if is_month_field and not is_year_field:
            # Month dropdown - map month names
            months = {
                "january": ["january", "jan", "01", "1"],
                "february": ["february", "feb", "02", "2"],
                "march": ["march", "mar", "03", "3"],
                "april": ["april", "apr", "04", "4"],
                "may": ["may", "05", "5"],
                "june": ["june", "jun", "06", "6"],
                "july": ["july", "jul", "07", "7"],
                "august": ["august", "aug", "08", "8"],
                "september": ["september", "sep", "sept", "09", "9"],
                "october": ["october", "oct", "10"],
                "november": ["november", "nov", "11"],
                "december": ["december", "dec", "12"],
            }
            # Try to find matching month in options
            for option in field.options:
                opt_lower = option.lower().strip()
                for month_name, variants in months.items():
                    if opt_lower in variants or month_name in opt_lower:
                        # Check if this matches what we want (current month or profile start date)
                        try:
                            await field.element.select_option(label=option)
                            print(f"    Selected month: '{option}'")
                            return True
                        except Exception:
                            continue
            # Default to first non-empty option
            for option in field.options:
                if option.strip() and option.lower() not in ["select", "month", "--"]:
                    try:
                        await field.element.select_option(label=option)
                        print(f"    Selected month (default): '{option}'")
                        return True
                    except Exception:
                        continue

        if is_year_field:
            # Year dropdown - try to select current or recent year
            import datetime
            current_year = datetime.datetime.now().year
            # For end date, might want "Present" or current year
            if "end" in label_lower:
                for option in field.options:
                    opt_lower = option.lower()
                    if "present" in opt_lower or "current" in opt_lower:
                        try:
                            await field.element.select_option(label=option)
                            print(f"    Selected year: '{option}'")
                            return True
                        except Exception:
                            continue
            # Try years from profile or recent years
            target_years = [str(current_year), str(current_year - 1), str(current_year - 2)]
            for year in target_years:
                for option in field.options:
                    if year in option:
                        try:
                            await field.element.select_option(label=option)
                            print(f"    Selected year: '{option}'")
                            return True
                        except Exception:
                            continue

        # === Standard select handling ===
        # Try exact match first
        for option in field.options:
            if option.lower() == value_lower:
                await field.element.select_option(label=option)
                return True

        # Try partial match
        for option in field.options:
            if value_lower in option.lower() or option.lower() in value_lower:
                await field.element.select_option(label=option)
                return True

        # Try matching Yes/No
        if value_lower in ("yes", "true"):
            for option in field.options:
                if option.lower() in ("yes", "true"):
                    await field.element.select_option(label=option)
                    return True

        if value_lower in ("no", "false"):
            for option in field.options:
                if option.lower() in ("no", "false"):
                    await field.element.select_option(label=option)
                    return True

        return False

    async def _fill_eeo_select(self, field: FormField, value: str) -> bool:
        """
        Fill an EEO select dropdown with safe handling.

        EEO fields are legally voluntary but technically fragile.
        This method prioritizes submission success over data completeness.

        Logic:
        1. Try to select the preferred answer if it exists exactly
        2. If not found or unsafe, try decline/skip options
        3. If nothing works, don't interact (return False but don't raise error)
        """
        print(f"  EEO select '{field.label}': options={field.options}, looking for '{value}'")

        # Step 1: Try exact match for preferred value
        value_lower = value.lower().strip()
        for opt in field.options:
            if opt.lower().strip() == value_lower:
                try:
                    await field.element.select_option(label=opt)
                    print(f"  EEO field '{field.label}': selected preferred '{opt}'")
                    return True
                except Exception as e:
                    print(f"  EEO field '{field.label}': failed to select '{opt}': {e}")
                    break

        # Step 2: Handle Yes/No questions (common for Hispanic/Latino)
        # Options might be "Hispanic or Latino" / "Not Hispanic or Latino"
        if value_lower in ("yes", "no"):
            for opt in field.options:
                opt_lower = opt.lower()
                # Skip empty options and "select" placeholder
                if not opt_lower or opt_lower in ("select", "select one", "-- select --", "choose"):
                    continue

                if value_lower == "yes":
                    # For "Yes" - look for options that don't start with "not" or "non"
                    # and don't contain decline phrases
                    if not any(d in opt_lower for d in ["decline", "wish", "prefer not", "choose not"]):
                        if not opt_lower.startswith(("not ", "non")) and "not " not in opt_lower:
                            # Check if it's a positive option (contains the topic word)
                            label_lower = field.label.lower()
                            if "hispanic" in label_lower or "latino" in label_lower:
                                if "hispanic" in opt_lower or "latino" in opt_lower:
                                    try:
                                        await field.element.select_option(label=opt)
                                        print(f"  EEO field '{field.label}': selected Yes equivalent '{opt}'")
                                        return True
                                    except Exception:
                                        continue

                elif value_lower == "no":
                    # For "No" - look for options that start with "not" or "non"
                    if opt_lower.startswith(("not ", "non")) or "not " in opt_lower:
                        # Make sure it's not a decline option
                        if not any(d in opt_lower for d in ["decline", "wish", "prefer"]):
                            try:
                                await field.element.select_option(label=opt)
                                print(f"  EEO field '{field.label}': selected No equivalent '{opt}'")
                                return True
                            except Exception:
                                continue

        # Step 3: Try partial match for preferred value
        for opt in field.options:
            if value_lower in opt.lower():
                try:
                    await field.element.select_option(label=opt)
                    print(f"  EEO field '{field.label}': selected partial match '{opt}'")
                    return True
                except Exception:
                    break

        # Step 4: Fallback - try decline/skip options
        for decline_text in EEO_DECLINE_OPTIONS:
            for opt in field.options:
                if decline_text in opt.lower():
                    try:
                        await field.element.select_option(label=opt)
                        print(f"  EEO field '{field.label}': selected decline option '{opt}'")
                        return True
                    except Exception:
                        continue

        # Step 5: If nothing works, don't interact at all
        print(f"  EEO field '{field.label}': skipping (no safe option found)")
        return False

    async def _fill_checkbox(self, field: FormField, value: str) -> bool:
        """Fill a checkbox."""
        should_check = value.lower() in ("yes", "true", "1", "checked")
        is_checked = await field.element.is_checked()

        if should_check and not is_checked:
            await field.element.check()
        elif not should_check and is_checked:
            await field.element.uncheck()

        return True

    async def _fill_radio(self, field: FormField, value: str) -> bool:
        """Fill a radio button by selecting the matching option."""
        # Radio buttons are usually in groups, find the right one
        name = field.name
        if not name:
            return False

        # Use active frame if available
        frame = self._active_frame or self.page.main_frame
        radios = await frame.query_selector_all(f'input[type="radio"][name="{name}"]')

        for radio in radios:
            radio_value = await radio.get_attribute("value") or ""
            radio_label = await self._get_field_label(radio, await radio.get_attribute("id") or "")

            # Check if this radio matches the desired value
            if (
                radio_value.lower() == value.lower()
                or value.lower() in radio_label.lower()
                or radio_label.lower() in value.lower()
            ):
                await radio.check()
                return True

        return False

    async def _fill_eeo_radio(self, field: FormField, value: str) -> bool:
        """
        Fill an EEO radio button with safe handling.

        EEO fields are legally voluntary but technically fragile.
        This method prioritizes submission success over data completeness.
        """
        frame = self._active_frame or self.page.main_frame
        name = field.name
        value_lower = value.lower().strip()

        # === Method 1: If we have the name attribute, find all radios in the group ===
        if name:
            radios = await frame.query_selector_all(f'input[type="radio"][name="{name}"]')
            if radios:
                radio_options = []
                for radio in radios:
                    radio_value = await radio.get_attribute("value") or ""
                    radio_id = await radio.get_attribute("id") or ""
                    radio_label = await self._get_field_label(radio, radio_id)

                    # If label is empty, try getting text from adjacent elements
                    if not radio_label:
                        radio_label = await radio.evaluate("""
                            el => {
                                let next = el.nextSibling;
                                if (next && next.nodeType === 3) {
                                    let text = next.textContent.trim();
                                    if (text) return text;
                                }
                                let nextEl = el.nextElementSibling;
                                if (nextEl) {
                                    let text = nextEl.innerText.trim();
                                    if (text && text.length < 50) return text;
                                }
                                let parent = el.parentElement;
                                if (parent && parent.tagName === 'LABEL') {
                                    return parent.innerText.trim();
                                }
                                let labelParent = el.closest('label');
                                if (labelParent) {
                                    return labelParent.innerText.trim();
                                }
                                return '';
                            }
                        """) or ""

                    radio_options.append((radio, radio_value, radio_label))

                # Try to select the right option
                result = await self._select_radio_option(field.label, radio_options, value_lower)
                if result:
                    return True

        # === Method 2: Ashby-style - The field itself IS the radio button to click ===
        # In Ashby, each radio button is detected as a separate field
        # The field.label contains the option text (e.g., "Male", "Asian", etc.)
        label_lower = field.label.lower().strip()

        # Check if this field's label matches what we want to select
        should_select = False

        # Exact match
        if label_lower == value_lower:
            should_select = True
        # For gender field
        elif value_lower == "male" and label_lower == "male":
            should_select = True
        elif value_lower == "female" and label_lower == "female":
            should_select = True
        # For race/ethnicity
        elif value_lower == "asian" and "asian" in label_lower:
            should_select = True
        elif value_lower == "no" and ("not hispanic" in label_lower or label_lower.startswith("no")):
            should_select = True
        elif value_lower == "yes" and ("hispanic" in label_lower and "not" not in label_lower):
            should_select = True
        # For veteran status
        elif value_lower == "no" and "not a protected veteran" in label_lower:
            should_select = True
        elif value_lower == "no" and "not have a disability" in label_lower:
            should_select = True
        # Decline options
        elif any(d in label_lower for d in ["decline", "prefer not", "don't wish", "do not want"]):
            # Only select decline if we're looking for decline
            if any(d in value_lower for d in ["decline", "prefer not"]):
                should_select = True

        if should_select:
            try:
                # Try multiple methods to click the radio
                element = await self._reacquire_element(field)
                if element:
                    # Method A: Try Playwright's check()
                    try:
                        await element.check()
                        print(f"  EEO radio: selected '{field.label}'")
                        return True
                    except Exception:
                        pass

                    # Method B: Try click()
                    try:
                        await element.click()
                        print(f"  EEO radio: clicked '{field.label}'")
                        return True
                    except Exception:
                        pass

                    # Method C: Try JavaScript click
                    try:
                        await element.evaluate("el => el.click()")
                        print(f"  EEO radio: JS clicked '{field.label}'")
                        return True
                    except Exception:
                        pass

                # Method D: Try finding by label text and clicking
                try:
                    # Find label containing this text and click it
                    label_el = await frame.query_selector(f'label:has-text("{field.label}")')
                    if label_el:
                        await label_el.click()
                        print(f"  EEO radio: clicked label '{field.label}'")
                        return True
                except Exception:
                    pass

            except Exception as e:
                print(f"  EEO radio '{field.label}': error - {e}")

        # This field doesn't match what we want - return False but don't print error
        return False

    async def _select_radio_option(
        self,
        field_label: str,
        radio_options: list,
        value_lower: str
    ) -> bool:
        """Helper to select the right option from a radio group."""
        # Step 1: Try exact match
        for radio, radio_value, radio_label in radio_options:
            if radio_value.lower().strip() == value_lower or radio_label.lower().strip() == value_lower:
                try:
                    await radio.check()
                    print(f"  EEO radio '{field_label}': selected '{radio_label or radio_value}'")
                    return True
                except Exception:
                    # Try JavaScript click as fallback
                    try:
                        await radio.evaluate("el => el.click()")
                        print(f"  EEO radio '{field_label}': JS selected '{radio_label or radio_value}'")
                        return True
                    except Exception:
                        continue

        # Step 2: Yes/No matching
        if value_lower in ("yes", "no"):
            for radio, radio_value, radio_label in radio_options:
                combined = f"{radio_value} {radio_label}".lower()
                if value_lower == "yes" and any(x in combined for x in ["yes", "true", "1"]):
                    try:
                        await radio.evaluate("el => el.click()")
                        print(f"  EEO radio '{field_label}': selected Yes '{radio_label or radio_value}'")
                        return True
                    except Exception:
                        continue
                elif value_lower == "no" and any(x in combined for x in ["no", "false", "0"]):
                    if not any(d in combined for d in ["decline", "wish", "prefer not"]):
                        try:
                            await radio.evaluate("el => el.click()")
                            print(f"  EEO radio '{field_label}': selected No '{radio_label or radio_value}'")
                            return True
                        except Exception:
                            continue

        # Step 3: Partial match
        for radio, radio_value, radio_label in radio_options:
            if value_lower in radio_label.lower() or value_lower in radio_value.lower():
                try:
                    await radio.evaluate("el => el.click()")
                    print(f"  EEO radio '{field_label}': selected partial '{radio_label or radio_value}'")
                    return True
                except Exception:
                    continue

        # Step 4: Decline options
        for decline_text in EEO_DECLINE_OPTIONS:
            for radio, radio_value, radio_label in radio_options:
                if decline_text in radio_label.lower() or decline_text in radio_value.lower():
                    try:
                        await radio.evaluate("el => el.click()")
                        print(f"  EEO radio '{field_label}': selected decline '{radio_label or radio_value}'")
                        return True
                    except Exception:
                        continue

        return False

    async def _fill_file(self, field: FormField, value: str) -> bool:
        """Upload a file to a file input."""
        if not value:
            # Try to get resume path
            resume_path = self.profile.resume.get_absolute_path()
            if not resume_path:
                print(f"  No resume path configured for file field: {field.label}")
                return False
            value = str(resume_path)

        path = Path(value).expanduser()
        if not path.exists():
            print(f"  File not found: {path}")
            return False

        try:
            print(f"  Uploading file to '{field.label}' (name={field.name}): {path}")

            # Set files on the input element
            await field.element.set_input_files(str(path))

            # Trigger change event to notify the page of the file selection
            await field.element.dispatch_event("change")
            await field.element.dispatch_event("input")

            # Wait for any JavaScript handlers to process
            await asyncio.sleep(0.5)

            print(f"  File upload completed for '{field.label}'")
            return True
        except Exception as e:
            print(f"  File upload error for '{field.label}': {e}")
            return False

    async def fill_all_fields(
        self, fields: Optional[List[FormField]] = None
    ) -> List[FilledField]:
        """Fill all detected fields."""
        if fields is None:
            fields = await self.extract_form_fields()

        # Reset file input counter for this fill session
        self._file_input_count = 0

        # Wait for frame to stabilize (increased for iframe stability)
        await asyncio.sleep(3)

        # Re-acquire the active frame before filling
        self._active_frame = await self._get_active_frame()

        # Extra wait after frame acquisition
        await asyncio.sleep(1)

        # Track successfully filled field labels to skip duplicates
        filled_labels = {}  # label -> success status
        # Store reference to First Name element for verification
        first_name_element = None
        first_name_value = None

        results = []
        is_first_field = True
        for field in fields:
            # Skip unknown fields without required flag
            if field.field_type == FieldType.UNKNOWN and not field.is_required:
                continue

            # Skip duplicate fields only if the previous instance was successfully filled
            field_key = f"{field.label}_{field.field_type.value}"
            if field_key in filled_labels:
                if filled_labels[field_key]:  # Previous instance was successful
                    print(f"  Skipping duplicate field: {field.label}")
                    continue
                else:
                    # Previous instance failed, try this one (might be the visible element)
                    print(f"  Retrying field (previous attempt failed): {field.label}")

            # Extra handling for first field (often fails due to timing)
            if is_first_field:
                await asyncio.sleep(1)  # Extra wait for first field
                is_first_field = False

            result = await self.fill_field(field)

            # Retry first field if it failed
            if not result.success and field.field_type == FieldType.FIRST_NAME:
                print(f"  Retrying {field.label}...")
                await asyncio.sleep(1)
                self._active_frame = await self._get_active_frame()
                result = await self.fill_field(field)

            # Store First Name reference for later verification
            if field.field_type == FieldType.FIRST_NAME and result.success:
                first_name_element = field.element
                first_name_value = result.filled_value

            results.append(result)
            # Only mark as filled if successful
            if result.success:
                filled_labels[field_key] = True
            elif field_key not in filled_labels:
                filled_labels[field_key] = False

            # After filling autocomplete/dropdown fields, verify First Name wasn't cleared
            if first_name_element and field.field_type != FieldType.FIRST_NAME:
                label_lower = field.label.lower()
                is_dropdown_field = (
                    field.field_type in {FieldType.COUNTRY, FieldType.CITY, FieldType.STATE} or
                    any(kw in label_lower for kw in ["country", "location", "city"])
                )
                if is_dropdown_field:
                    try:
                        current_first_name = await first_name_element.input_value()
                        if current_first_name != first_name_value:
                            print(f"  WARNING: First Name was cleared! Restoring '{first_name_value}'...")
                            await first_name_element.focus()
                            await first_name_element.fill(first_name_value)
                            await asyncio.sleep(0.1)
                    except Exception as e:
                        print(f"  Could not verify First Name: {e}")

            # Delay between fields (increased to avoid overwhelming the page)
            await asyncio.sleep(0.3)

        # === TWO-PASS FILLING: Handle dynamically appearing fields ===
        # Some forms show additional fields after answering certain questions
        # (e.g., "Please identify your race" appears after answering "No" to Hispanic/Latino)
        results = await self._fill_dynamic_fields(results, filled_labels, first_name_element, first_name_value)

        return results

    async def _fill_dynamic_fields(
        self,
        results: List[FilledField],
        filled_labels: Dict[str, bool],
        first_name_element: Optional[ElementHandle],
        first_name_value: Optional[str],
        max_passes: int = 2
    ) -> List[FilledField]:
        """
        Re-scan the form for dynamically appearing fields and fill them.

        Some forms show additional fields after answering certain questions:
        - "Please identify your race" appears after answering "No" to Hispanic/Latino
        - Additional address fields after selecting certain countries
        - Conditional skill/experience questions

        Args:
            results: Current list of filled field results
            filled_labels: Dictionary tracking which fields have been filled
            first_name_element: Reference to First Name element for verification
            first_name_value: Value that should be in First Name field
            max_passes: Maximum number of re-scan passes (default: 2)

        Returns:
            Updated results list including newly filled fields
        """
        for pass_num in range(max_passes):
            # Wait for DOM to update after previous interactions
            await asyncio.sleep(1.0)

            # Re-acquire the active frame
            self._active_frame = await self._get_active_frame()

            # Re-extract all visible form fields
            new_fields = await self.extract_form_fields()

            # Find fields that weren't in the original list
            # Compare by selector since element handles may have changed
            existing_selectors = {f.field.selector for f in results}
            existing_labels = set(filled_labels.keys())

            dynamic_fields = []
            for field in new_fields:
                field_key = f"{field.label}_{field.field_type.value}"
                # Check if this is a new field
                if field.selector not in existing_selectors and field_key not in existing_labels:
                    # Skip unknown/required-only fields
                    if field.field_type == FieldType.UNKNOWN and not field.is_required:
                        continue
                    dynamic_fields.append(field)

            if not dynamic_fields:
                # No new fields found, we're done
                if pass_num == 0:
                    print("  No dynamic fields detected")
                break

            print(f"\n  === Dynamic Field Pass {pass_num + 1}: Found {len(dynamic_fields)} new fields ===")
            for df in dynamic_fields:
                print(f"    - {df.label} ({df.field_type.value})")

            # Fill the new dynamic fields
            for field in dynamic_fields:
                field_key = f"{field.label}_{field.field_type.value}"

                # Skip if already in our tracking (shouldn't happen but safety check)
                if field_key in filled_labels and filled_labels[field_key]:
                    continue

                result = await self.fill_field(field)
                results.append(result)

                # Update tracking
                if result.success:
                    filled_labels[field_key] = True
                    existing_selectors.add(field.selector)
                elif field_key not in filled_labels:
                    filled_labels[field_key] = False

                # Verify First Name wasn't cleared by this dynamic field
                if first_name_element and first_name_value:
                    try:
                        current_first_name = await first_name_element.input_value()
                        if current_first_name != first_name_value:
                            print(f"  WARNING: First Name cleared during dynamic fill! Restoring...")
                            await first_name_element.focus()
                            await first_name_element.fill(first_name_value)
                            await asyncio.sleep(0.1)
                    except Exception:
                        pass

                # Small delay between dynamic fields
                await asyncio.sleep(0.3)

        return results
