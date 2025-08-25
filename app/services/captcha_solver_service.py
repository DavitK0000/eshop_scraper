import time
import requests
import json
from typing import Optional, Dict, Any, List
from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class CaptchaSolverService:
    """Service for solving captchas using third-party services"""
    
    def __init__(self):
        self.services = {
            "2captcha": {
                "api_key": getattr(settings, "CAPTCHA_2CAPTCHA_API_KEY", None),
                "base_url": "https://2captcha.com/in.php",
                "result_url": "https://2captcha.com/res.php",
                "enabled": bool(getattr(settings, "CAPTCHA_2CAPTCHA_API_KEY", None))
            },
            "anticaptcha": {
                "api_key": getattr(settings, "CAPTCHA_ANTICAPTCHA_API_KEY", None),
                "base_url": "https://api.anti-captcha.com/createTask",
                "result_url": "https://api.anti-captcha.com/getTaskResult",
                "enabled": bool(getattr(settings, "CAPTCHA_ANTICAPTCHA_API_KEY", None))
            },
            "capmonster": {
                "api_key": getattr(settings, "CAPTCHA_CAPMONSTER_API_KEY", None),
                "base_url": "https://api.capmonster.cloud/createTask",
                "result_url": "https://api.capmonster.cloud/getTaskResult",
                "enabled": bool(getattr(settings, "CAPTCHA_CAPMONSTER_API_KEY", None))
            }
        }
        
        # Check which services are available
        self.available_services = [name for name, config in self.services.items() if config["enabled"]]
        if self.available_services:
            logger.info(f"Available captcha solving services: {', '.join(self.available_services)}")
        else:
            logger.warning("No captcha solving services configured")
    
    def solve_altcha_captcha(self, page_content: str, url: str, service_name: Optional[str] = None) -> Optional[str]:
        """
        Solve Altcha captcha using third-party service
        
        Args:
            page_content: HTML content of the page with captcha
            url: URL of the page
            service_name: Specific service to use (optional)
            
        Returns:
            Solved captcha token or None if failed
        """
        if not self.available_services:
            logger.error("No captcha solving services available")
            return None
        
        # Determine which service to use
        if service_name and service_name in self.available_services:
            services_to_try = [service_name]
        else:
            services_to_try = self.available_services
        
        for service in services_to_try:
            try:
                logger.info(f"Attempting to solve Altcha captcha using {service}")
                result = self._solve_with_service(service, page_content, url)
                if result:
                    logger.info(f"Successfully solved captcha using {service}")
                    return result
            except Exception as e:
                logger.error(f"Error solving captcha with {service}: {e}")
                continue
        
        logger.error("All captcha solving services failed")
        return None
    
    def _solve_with_service(self, service_name: str, page_content: str, url: str) -> Optional[str]:
        """Solve captcha using a specific service"""
        try:
            if service_name == "2captcha":
                return self._solve_with_2captcha(page_content, url)
            elif service_name == "anticaptcha":
                return self._solve_with_anticaptcha(page_content, url)
            elif service_name == "capmonster":
                return self._solve_with_capmonster(page_content, url)
            else:
                logger.error(f"Unknown service: {service_name}")
                return None
        except Exception as e:
            logger.error(f"Error with {service_name}: {e}")
            return None
    
    def _solve_with_2captcha(self, page_content: str, url: str) -> Optional[str]:
        """Solve using 2captcha service"""
        try:
            service_config = self.services["2captcha"]
            api_key = service_config["api_key"]
            
            # Create task for Altcha captcha
            task_data = {
                "key": api_key,
                "method": "altcha",  # 2captcha supports Altcha
                "pageurl": url,
                "data": self._extract_altcha_data(page_content),
                "json": 1
            }
            
            # Submit task
            response = requests.post(service_config["base_url"], data=task_data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("status") != 1:
                logger.error(f"2captcha task creation failed: {result}")
                return None
            
            task_id = result.get("request")
            logger.info(f"2captcha task created with ID: {task_id}")
            
            # Wait for solution
            solution = self._wait_for_2captcha_solution(service_config["result_url"], api_key, task_id)
            return solution
            
        except Exception as e:
            logger.error(f"Error with 2captcha: {e}")
            return None
    
    def _solve_with_anticaptcha(self, page_content: str, url: str) -> Optional[str]:
        """Solve using AntiCaptcha service"""
        try:
            service_config = self.services["anticaptcha"]
            api_key = service_config["api_key"]
            
            # Create task for Altcha captcha
            task_data = {
                "clientKey": api_key,
                "task": {
                    "type": "AltchaTaskProxyless",
                    "websiteURL": url,
                    "websiteKey": self._extract_altcha_key(page_content),
                    "pageAction": "verify"
                }
            }
            
            # Submit task
            response = requests.post(service_config["base_url"], json=task_data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("errorId") != 0:
                logger.error(f"AntiCaptcha task creation failed: {result}")
                return None
            
            task_id = result.get("taskId")
            logger.info(f"AntiCaptcha task created with ID: {task_id}")
            
            # Wait for solution
            solution = self._wait_for_anticaptcha_solution(service_config["result_url"], api_key, task_id)
            return solution
            
        except Exception as e:
            logger.error(f"Error with AntiCaptcha: {e}")
            return None
    
    def _solve_with_capmonster(self, page_content: str, url: str) -> Optional[str]:
        """Solve using CapMonster service"""
        try:
            service_config = self.services["capmonster"]
            api_key = service_config["api_key"]
            
            # Create task for Altcha captcha
            task_data = {
                "clientKey": api_key,
                "task": {
                    "type": "AltchaTaskProxyless",
                    "websiteURL": url,
                    "websiteKey": self._extract_altcha_key(page_content),
                    "pageAction": "verify"
                }
            }
            
            # Submit task
            response = requests.post(service_config["base_url"], json=task_data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("errorId") != 0:
                logger.error(f"CapMonster task creation failed: {result}")
                return None
            
            task_id = result.get("taskId")
            logger.info(f"CapMonster task created with ID: {task_id}")
            
            # Wait for solution
            solution = self._wait_for_capmonster_solution(service_config["result_url"], api_key, task_id)
            return solution
            
        except Exception as e:
            logger.error(f"Error with CapMonster: {e}")
            return None
    
    def _extract_altcha_data(self, page_content: str) -> str:
        """Extract Altcha-specific data from page content"""
        try:
            # Look for Altcha challenge data
            import re
            
            # Try to find Altcha challenge element
            altcha_patterns = [
                r'<altcha-challenge[^>]*data-challenge="([^"]*)"',
                r'data-altcha="([^"]*)"',
                r'<div[^>]*class="[^"]*altcha[^"]*"[^>]*data-challenge="([^"]*)"',
                r'window\.altchaChallenge\s*=\s*["\']([^"\']*)["\']',
                r'altcha\.challenge\s*=\s*["\']([^"\']*)["\']'
            ]
            
            for pattern in altcha_patterns:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # If no specific data found, return the page content for manual analysis
            return page_content[:1000]  # First 1000 chars
            
        except Exception as e:
            logger.error(f"Error extracting Altcha data: {e}")
            return page_content[:1000]
    
    def _extract_altcha_key(self, page_content: str) -> str:
        """Extract Altcha website key from page content"""
        try:
            import re
            
            # Look for Altcha website key
            key_patterns = [
                r'data-sitekey="([^"]*)"',
                r'data-key="([^"]*)"',
                r'websiteKey["\']?\s*:\s*["\']([^"\']*)["\']',
                r'altcha\.key\s*=\s*["\']([^"\']*)["\']'
            ]
            
            for pattern in key_patterns:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            # Default fallback
            return "altcha"
            
        except Exception as e:
            logger.error(f"Error extracting Altcha key: {e}")
            return "altcha"
    
    def _wait_for_2captcha_solution(self, result_url: str, api_key: str, task_id: str, timeout: int = 120) -> Optional[str]:
        """Wait for 2captcha solution"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                time.sleep(5)  # Wait 5 seconds between checks
                
                response = requests.get(f"{result_url}?key={api_key}&action=get&id={task_id}&json=1")
                response.raise_for_status()
                
                result = response.json()
                if result.get("status") == 1:
                    return result.get("request")
                elif result.get("request") == "CAPCHA_NOT_READY":
                    continue
                else:
                    logger.error(f"2captcha solution failed: {result}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error checking 2captcha solution: {e}")
                continue
        
        logger.error("2captcha solution timeout")
        return None
    
    def _wait_for_anticaptcha_solution(self, result_url: str, api_key: str, task_id: str, timeout: int = 120) -> Optional[str]:
        """Wait for AntiCaptcha solution"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                time.sleep(5)  # Wait 5 seconds between checks
                
                response = requests.post(result_url, json={
                    "clientKey": api_key,
                    "taskId": task_id
                })
                response.raise_for_status()
                
                result = response.json()
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("token")
                elif result.get("errorId") == 0:
                    continue  # Still processing
                else:
                    logger.error(f"AntiCaptcha solution failed: {result}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error checking AntiCaptcha solution: {e}")
                continue
        
        logger.error("AntiCaptcha solution timeout")
        return None
    
    def _wait_for_capmonster_solution(self, result_url: str, api_key: str, task_id: str, timeout: int = 120) -> Optional[str]:
        """Wait for CapMonster solution"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                time.sleep(5)  # Wait 5 seconds between checks
                
                response = requests.post(result_url, json={
                    "clientKey": api_key,
                    "taskId": task_id
                })
                response.raise_for_status()
                
                result = response.json()
                if result.get("status") == "ready":
                    return result.get("solution", {}).get("token")
                elif result.get("errorId") == 0:
                    continue  # Still processing
                else:
                    logger.error(f"CapMonster solution failed: {result}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error checking CapMonster solution: {e}")
                continue
        
        logger.error("CapMonster solution timeout")
        return None
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get status of all captcha solving services"""
        status = {}
        for service_name, config in self.services.items():
            status[service_name] = {
                "enabled": config["enabled"],
                "configured": bool(config["api_key"]),
                "available": config["enabled"] and bool(config["api_key"])
            }
        return status


# Global captcha solver service instance
captcha_solver_service = CaptchaSolverService()
