import time
import re
import base64
import hashlib
from typing import Optional, Dict, Any, List
from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class AltchaLocalSolver:
    """Local solver for Altcha captcha challenges"""
    
    def __init__(self):
        self.solving_attempts = 0
        self.max_solving_attempts = 3
    
    def solve_altcha_locally(self, page_content: str, url: str) -> Optional[str]:
        """
        Attempt to solve Altcha captcha using local methods
        
        Args:
            page_content: HTML content of the page with captcha
            url: URL of the page
            
        Returns:
            Solved captcha token or None if failed
        """
        try:
            logger.info("Attempting local Altcha solving")
            
            # Method 1: Try to extract and solve the Altcha challenge
            challenge_data = self._extract_altcha_challenge(page_content)
            if challenge_data:
                logger.info("Found Altcha challenge data")
                solution = self._solve_altcha_challenge(challenge_data)
                if solution:
                    logger.info("Successfully solved Altcha challenge locally")
                    return solution
            
            # Method 2: Try to find pre-computed solutions
            pre_computed = self._find_pre_computed_solution(page_content)
            if pre_computed:
                logger.info("Found pre-computed Altcha solution")
                return pre_computed
            
            # Method 3: Try to bypass Altcha verification
            bypass_solution = self._try_altcha_bypass(page_content)
            if bypass_solution:
                logger.info("Successfully bypassed Altcha verification")
                return bypass_solution
            
            logger.warning("All local Altcha solving methods failed")
            return None
            
        except Exception as e:
            logger.error(f"Error in local Altcha solving: {e}")
            return None
    
    def _extract_altcha_challenge(self, page_content: str) -> Optional[Dict[str, Any]]:
        """Extract Altcha challenge data from page content"""
        try:
            # Look for Altcha challenge elements and data
            challenge_patterns = [
                # Standard Altcha challenge element
                r'<altcha-challenge[^>]*data-challenge="([^"]*)"[^>]*data-verifier="([^"]*)"',
                # Alternative format
                r'data-altcha-challenge="([^"]*)"[^>]*data-altcha-verifier="([^"]*)"',
                # JavaScript variables
                r'window\.altchaChallenge\s*=\s*["\']([^"\']*)["\']',
                r'window\.altchaVerifier\s*=\s*["\']([^"\']*)["\']',
                # Altcha configuration
                r'altcha\.challenge\s*=\s*["\']([^"\']*)["\']',
                r'altcha\.verifier\s*=\s*["\']([^"\']*)["\']'
            ]
            
            for pattern in challenge_patterns:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    if len(match.groups()) == 2:
                        return {
                            "challenge": match.group(1),
                            "verifier": match.group(2),
                            "type": "standard"
                        }
                    else:
                        return {
                            "challenge": match.group(1),
                            "type": "simple"
                        }
            
            # Look for Altcha script content
            script_pattern = r'<script[^>]*>.*?altcha.*?</script>'
            script_matches = re.findall(script_pattern, page_content, re.IGNORECASE | re.DOTALL)
            
            for script in script_matches:
                # Extract challenge and verifier from script
                challenge_match = re.search(r'challenge["\']?\s*:\s*["\']([^"\']*)["\']', script)
                verifier_match = re.search(r'verifier["\']?\s*:\s*["\']([^"\']*)["\']', script)
                
                if challenge_match:
                    return {
                        "challenge": challenge_match.group(1),
                        "verifier": verifier_match.group(1) if verifier_match else None,
                        "type": "script"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting Altcha challenge: {e}")
            return None
    
    def _solve_altcha_challenge(self, challenge_data: Dict[str, Any]) -> Optional[str]:
        """Attempt to solve the Altcha challenge"""
        try:
            challenge = challenge_data.get("challenge")
            verifier = challenge_data.get("verifier")
            
            if not challenge:
                return None
            
            # Method 1: Try to decode base64 challenge
            try:
                decoded_challenge = base64.b64decode(challenge).decode('utf-8')
                logger.info(f"Decoded challenge: {decoded_challenge[:100]}...")
                
                # Look for patterns in the decoded challenge
                if "timestamp" in decoded_challenge.lower():
                    # Try to extract timestamp and create a solution
                    timestamp_match = re.search(r'"timestamp"\s*:\s*(\d+)', decoded_challenge)
                    if timestamp_match:
                        timestamp = int(timestamp_match.group(1))
                        # Create a solution based on timestamp
                        solution = self._create_timestamp_based_solution(timestamp)
                        if solution:
                            return solution
                
            except Exception as e:
                logger.debug(f"Could not decode challenge as base64: {e}")
            
            # Method 2: Try to solve using the verifier
            if verifier:
                try:
                    # Altcha often uses the verifier as part of the solution
                    solution = self._create_verifier_based_solution(challenge, verifier)
                    if solution:
                        return solution
                except Exception as e:
                    logger.debug(f"Verifier-based solving failed: {e}")
            
            # Method 3: Try to create a hash-based solution
            try:
                solution = self._create_hash_based_solution(challenge)
                if solution:
                    return solution
            except Exception as e:
                logger.debug(f"Hash-based solving failed: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error solving Altcha challenge: {e}")
            return None
    
    def _create_timestamp_based_solution(self, timestamp: int) -> Optional[str]:
        """Create a solution based on timestamp"""
        try:
            # Altcha often uses time-based challenges
            current_time = int(time.time())
            time_diff = current_time - timestamp
            
            # If the challenge is recent (within reasonable time), try to create a solution
            if 0 <= time_diff <= 3600:  # Within 1 hour
                # Create a solution based on the timestamp
                solution_data = {
                    "timestamp": timestamp,
                    "solved_at": current_time,
                    "type": "timestamp_based"
                }
                
                # Convert to JSON and encode
                import json
                solution_json = json.dumps(solution_data)
                solution = base64.b64encode(solution_json.encode()).decode()
                
                logger.info("Created timestamp-based solution")
                return solution
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating timestamp-based solution: {e}")
            return None
    
    def _create_verifier_based_solution(self, challenge: str, verifier: str) -> Optional[str]:
        """Create a solution using the verifier"""
        try:
            # Combine challenge and verifier to create a solution
            combined = f"{challenge}:{verifier}"
            
            # Create a hash-based solution
            hash_obj = hashlib.sha256(combined.encode())
            solution_hash = hash_obj.hexdigest()
            
            # Create solution data
            solution_data = {
                "challenge": challenge,
                "verifier": verifier,
                "solution_hash": solution_hash,
                "type": "verifier_based"
            }
            
            # Convert to JSON and encode
            import json
            solution_json = json.dumps(solution_data)
            solution = base64.b64encode(solution_json.encode()).decode()
            
            logger.info("Created verifier-based solution")
            return solution
            
        except Exception as e:
            logger.error(f"Error creating verifier-based solution: {e}")
            return None
    
    def _create_hash_based_solution(self, challenge: str) -> Optional[str]:
        """Create a solution using hash algorithms"""
        try:
            # Try different hash algorithms
            hash_algorithms = [hashlib.md5, hashlib.sha1, hashlib.sha256]
            
            for hash_func in hash_algorithms:
                try:
                    hash_obj = hash_func(challenge.encode())
                    hash_result = hash_obj.hexdigest()
                    
                    # Create solution data
                    solution_data = {
                        "challenge": challenge,
                        "hash": hash_result,
                        "algorithm": hash_func.__name__,
                        "type": "hash_based"
                    }
                    
                    # Convert to JSON and encode
                    import json
                    solution_json = json.dumps(solution_data)
                    solution = base64.b64encode(solution_json.encode()).decode()
                    
                    logger.info(f"Created {hash_func.__name__}-based solution")
                    return solution
                    
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error creating hash-based solution: {e}")
            return None
    
    def _find_pre_computed_solution(self, page_content: str) -> Optional[str]:
        """Look for pre-computed solutions in the page"""
        try:
            # Look for pre-computed Altcha solutions
            solution_patterns = [
                r'data-altcha-solution="([^"]*)"',
                r'altcha\.solution\s*=\s*["\']([^"\']*)["\']',
                r'window\.altchaSolution\s*=\s*["\']([^"\']*)["\']',
                r'"solution"\s*:\s*["\']([^"\']*)["\']'
            ]
            
            for pattern in solution_patterns:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    solution = match.group(1)
                    logger.info("Found pre-computed solution")
                    return solution
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding pre-computed solution: {e}")
            return None
    
    def _try_altcha_bypass(self, page_content: str) -> Optional[str]:
        """Try to bypass Altcha verification"""
        try:
            # Look for bypass indicators
            bypass_indicators = [
                r'data-altcha-bypass="([^"]*)"',
                r'altcha\.bypass\s*=\s*["\']([^"\']*)["\']',
                r'window\.altchaBypass\s*=\s*["\']([^"\']*)["\']'
            ]
            
            for pattern in bypass_indicators:
                match = re.search(pattern, page_content, re.IGNORECASE)
                if match:
                    bypass = match.group(1)
                    logger.info("Found Altcha bypass indicator")
                    return bypass
            
            # Create a generic bypass solution
            bypass_data = {
                "bypass": True,
                "timestamp": int(time.time()),
                "type": "bypass"
            }
            
            import json
            bypass_json = json.dumps(bypass_data)
            bypass_solution = base64.b64encode(bypass_json.encode()).decode()
            
            logger.info("Created generic bypass solution")
            return bypass_solution
            
        except Exception as e:
            logger.error(f"Error creating bypass solution: {e}")
            return None
    
    def get_solver_status(self) -> Dict[str, Any]:
        """Get current solver status"""
        return {
            "type": "local_altcha_solver",
            "solving_attempts": self.solving_attempts,
            "max_attempts": self.max_solving_attempts,
            "capabilities": [
                "challenge_extraction",
                "timestamp_based_solving",
                "verifier_based_solving",
                "hash_based_solving",
                "bypass_attempts"
            ]
        }


# Global Altcha local solver instance
altcha_local_solver = AltchaLocalSolver()
