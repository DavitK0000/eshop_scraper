import time
import re
from typing import Optional, Dict, Any, Tuple
from playwright.sync_api import Page
from app.logging_config import get_logger

logger = get_logger(__name__)


class AltchaCaptchaHandler:
    """Handler for Altcha captcha challenges"""
    
    def __init__(self):
        self.captcha_detected = False
        self.solving_attempts = 0
        self.max_solving_attempts = 3
    
    def detect_altcha_captcha(self, page: Page) -> bool:
        """
        Detect if Altcha captcha is present on the page
        
        Args:
            page: Playwright page object
            
        Returns:
            True if Altcha captcha is detected, False otherwise
        """
        try:
            # Check for Altcha-specific elements (including the widget structure from Cdiscount)
            altcha_selectors = [
                'altcha-widget',  # New: Cdiscount uses altcha-widget
                'altcha-challenge',
                '[data-altcha]',
                '.altcha-challenge',
                '#altcha-challenge',
                'iframe[src*="altcha"]',
                'div[class*="altcha"]',
                'div[id*="altcha"]',
                '[id="altcha"]',  # Specific ID used by Cdiscount
                '[class*="altcha"]'  # Any class containing "altcha"
            ]
            
            # Check for Altcha elements
            for selector in altcha_selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        logger.info(f"Altcha captcha detected with selector: {selector}")
                        self.captcha_detected = True
                        return True
                except Exception as e:
                    logger.debug(f"Error checking selector {selector}: {e}")
                    continue
            
            # Check page content for Altcha-specific patterns
            page_content = page.content()
            
            # Look for specific Altcha patterns from Cdiscount
            altcha_patterns = [
                r'<altcha-widget',  # Cdiscount's altcha-widget tag
                r'challengeurl="/\.well-known/baleen/captcha/generate',  # Cdiscount's challenge URL pattern
                r'strings="[^"]*Je ne suis pas un robot[^"]*"',  # French "I am not a robot" text
                r'Protected by <a href="https://baleen\.cloud/"',  # Baleen protection text
                r'data-state="unverified"',  # Altcha state attribute
                r'window\.__CF\$cv\$params',  # Cloudflare challenge parameters
            ]
            
            for pattern in altcha_patterns:
                if re.search(pattern, page_content, re.IGNORECASE):
                    logger.info(f"Altcha pattern detected: {pattern}")
                    self.captcha_detected = True
                    return True
            
            # Check for Altcha keywords in page content (fallback)
            altcha_keywords = [
                'altcha',
                'challenge',
                'verifier',
                'captcha',
                'baleen',  # Cdiscount uses Baleen service
                'je ne suis pas un robot'  # French captcha text
            ]
            
            page_content_lower = page_content.lower()
            for keyword in altcha_keywords:
                if keyword in page_content_lower:
                    # Additional check to avoid false positives
                    if 'altcha' in page_content_lower and ('challenge' in page_content_lower or 'verifier' in page_content_lower or 'baleen' in page_content_lower):
                        logger.info(f"Altcha keywords detected in page content: {keyword}")
                        self.captcha_detected = True
                        return True
            
            # Check for common captcha indicators
            captcha_indicators = [
                'verify you are human',
                'prove you are human',
                'captcha verification',
                'security check',
                'robot verification',
                'je ne suis pas un robot',  # French version
                'bienvenue sur',  # French welcome text from Cdiscount
                'afin de vous laisser continuer nous devons d\'abord vérifier'  # French verification text
            ]
            
            for indicator in captcha_indicators:
                try:
                    if page.query_selector(f"text={indicator}"):
                        logger.info(f"Captcha indicator found: {indicator}")
                        self.captcha_detected = True
                        return True
                except Exception:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting Altcha captcha: {e}")
            return False
    
    def solve_altcha_captcha(self, page: Page, strategy: str = "auto") -> bool:
        """
        Attempt to solve Altcha captcha using various strategies
        
        Args:
            page: Playwright page object
            strategy: Solving strategy ('auto', 'local', 'manual', 'bypass')
            
        Returns:
            True if captcha was solved, False otherwise
        """
        if not self.captcha_detected:
            logger.info("No captcha detected to solve")
            return True
        
        if self.solving_attempts >= self.max_solving_attempts:
            logger.warning("Maximum solving attempts reached")
            return False
        
        self.solving_attempts += 1
        logger.info(f"Attempting to solve Altcha captcha (attempt {self.solving_attempts}/{self.max_solving_attempts})")
        
        try:
            if strategy == "auto":
                # Try multiple strategies automatically
                strategies = ["local", "bypass", "manual"]
                for strat in strategies:
                    if self._try_strategy(page, strat):
                        return True
                return False
            else:
                return self._try_strategy(page, strategy)
                
        except Exception as e:
            logger.error(f"Error solving Altcha captcha: {e}")
            return False
    
    def _try_strategy(self, page: Page, strategy: str) -> bool:
        """Try a specific solving strategy"""
        try:
            if strategy == "local":
                return self._solve_local(page)
            elif strategy == "bypass":
                return self._try_bypass(page)
            elif strategy == "manual":
                return self._wait_for_manual(page)
            else:
                logger.warning(f"Unknown strategy: {strategy}")
                return False
        except Exception as e:
            logger.error(f"Error with strategy {strategy}: {e}")
            return False
    
    def _solve_local(self, page: Page) -> bool:
        """Attempt local solving methods"""
        try:
            # Method 1: Try to find and click any "I'm human" or similar buttons
            human_buttons = [
                "text=I'm human",
                "text=I am human",
                "text=Verify",
                "text=Continue",
                "text=Submit",
                "text=Proceed",
                "text=Next",
                "text=Je ne suis pas un robot",  # French version from Cdiscount
                "text=Je ne suis pas un robot"
            ]
            
            for button_text in human_buttons:
                try:
                    button = page.query_selector(button_text)
                    if button and button.is_visible():
                        logger.info(f"Found human verification button: {button_text}")
                        button.click()
                        time.sleep(2)
                        
                        # Check if captcha is still present
                        if not self.detect_altcha_captcha(page):
                            logger.info("Captcha appears to be solved locally")
                            return True
                except Exception:
                    continue
            
            # Method 2: Try to interact with Cdiscount-specific Altcha elements
            cdiscount_selectors = [
                'altcha-widget',  # Cdiscount's altcha-widget
                '#altcha',  # Cdiscount's altcha ID
                '.altcha',  # Cdiscount's altcha class
                'input[type="checkbox"]',  # Checkbox in altcha widget
                'label[for="altcha_checkbox"]',  # Label for checkbox
                '.altcha-checkbox',  # Checkbox container
                '.altcha-main',  # Main altcha container
                '.altcha-label'  # Label container
            ]
            
            for selector in cdiscount_selectors:
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        logger.info(f"Found Cdiscount Altcha element: {selector}")
                        
                        # If it's a checkbox, try to check it
                        if selector == 'input[type="checkbox"]':
                            element.check()
                            logger.info("Checked Altcha checkbox")
                        else:
                            # For other elements, try to click
                            element.click()
                            logger.info(f"Clicked Altcha element: {selector}")
                        
                        time.sleep(2)
                        
                        # Check if captcha is still present
                        if not self.detect_altcha_captcha(page):
                            logger.info("Cdiscount Altcha appears to be solved locally")
                            return True
                except Exception as e:
                    logger.debug(f"Error interacting with {selector}: {e}")
                    continue
            
            # Method 3: Try to interact with any interactive elements
            interactive_selectors = [
                'button',
                'input[type="submit"]',
                'a[href="#"]',
                '.btn',
                '.button'
            ]
            
            for selector in interactive_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements[:3]:  # Try first 3 elements
                        if element.is_visible():
                            element.click()
                            time.sleep(1)
                            
                            if not self.detect_altcha_captcha(page):
                                logger.info("Captcha solved by interacting with element")
                                return True
                except Exception:
                    continue
            
            # Method 4: Try to fill any form fields
            form_fields = page.query_selector_all('input[type="text"], input[type="email"]')
            for field in form_fields:
                try:
                    if field.is_visible():
                        field.fill("test@example.com")
                        time.sleep(0.5)
                except Exception:
                    continue
            
            # Method 5: Try to interact with the Altcha form specifically
            try:
                altcha_form = page.query_selector('#altcha-form')
                if altcha_form:
                    logger.info("Found Altcha form, attempting to submit")
                    
                    # Try to find and click submit button
                    submit_btn = altcha_form.query_selector('button[type="submit"], input[type="submit"]')
                    if submit_btn:
                        submit_btn.click()
                        time.sleep(3)
                        
                        if not self.detect_altcha_captcha(page):
                            logger.info("Altcha form submitted successfully")
                            return True
            except Exception as e:
                logger.debug(f"Error with Altcha form: {e}")
            
            logger.info("Local solving methods exhausted")
            return False
            
        except Exception as e:
            logger.error(f"Error in local solving: {e}")
            return False
    
    def _try_bypass(self, page: Page) -> bool:
        """Attempt to bypass captcha using various techniques"""
        try:
            # Method 1: Wait and refresh
            logger.info("Attempting bypass method: wait and refresh")
            time.sleep(5)
            page.reload()
            time.sleep(3)
            
            if not self.detect_altcha_captcha(page):
                logger.info("Captcha bypassed with refresh")
                return True
            
            # Method 2: Try different user agent
            logger.info("Attempting bypass method: change user agent")
            page.evaluate("""
                Object.defineProperty(navigator, 'userAgent', {
                    get: function () { return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'; }
                });
            """)
            page.reload()
            time.sleep(3)
            
            if not self.detect_altcha_captcha(page):
                logger.info("Captcha bypassed with user agent change")
                return True
            
            # Method 3: Try to clear cookies and storage
            logger.info("Attempting bypass method: clear storage")
            page.evaluate("""
                localStorage.clear();
                sessionStorage.clear();
                document.cookie.split(";").forEach(function(c) { 
                    document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
                });
            """)
            page.reload()
            time.sleep(3)
            
            if not self.detect_altcha_captcha(page):
                logger.info("Captcha bypassed with storage clear")
                return True
            
            logger.info("Bypass methods exhausted")
            return False
            
        except Exception as e:
            logger.error(f"Error in bypass method: {e}")
            return False
    
    def _wait_for_manual(self, page: Page) -> bool:
        """Wait for manual captcha solving"""
        try:
            logger.info("Waiting for manual captcha solving...")
            logger.info("Please solve the captcha manually in the browser window")
            
            # Wait up to 60 seconds for manual solving
            max_wait = 60
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                if not self.detect_altcha_captcha(page):
                    logger.info("Captcha appears to be solved manually")
                    return True
                time.sleep(2)
            
            logger.warning("Manual solving timeout reached")
            return False
            
        except Exception as e:
            logger.error(f"Error in manual solving: {e}")
            return False
    
    def get_captcha_info(self) -> Dict[str, Any]:
        """Get information about the current captcha status"""
        return {
            "detected": self.captcha_detected,
            "solving_attempts": self.solving_attempts,
            "max_attempts": self.max_solving_attempts,
            "remaining_attempts": self.max_solving_attempts - self.solving_attempts
        }
    
    def reset(self):
        """Reset the captcha handler state"""
        self.captcha_detected = False
        self.solving_attempts = 0
        logger.info("Captcha handler reset")


# Global captcha handler instance
captcha_handler = AltchaCaptchaHandler()
