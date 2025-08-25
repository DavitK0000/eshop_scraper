#!/usr/bin/env python3
"""
Example script demonstrating local Altcha solving
"""

import os
import sys
from dotenv import load_dotenv

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.captcha_solver_service import altcha_local_solver

def demonstrate_altcha_solving():
    """Demonstrate the local Altcha solving capabilities"""
    
    print("=== Local Altcha Solver Demonstration ===")
    
    # Example HTML content with Altcha challenge
    example_html = """
    <html>
    <head>
        <title>Example Page with Altcha</title>
    </head>
    <body>
        <altcha-challenge 
            data-challenge="eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTAsInJhbmRvbSI6ImFiY2RlZiJ9"
            data-verifier="verifier123">
        </altcha-challenge>
        
        <script>
            window.altchaChallenge = "eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTAsInJhbmRvbSI6ImFiY2RlZiJ9";
            window.altchaVerifier = "verifier123";
        </script>
    </body>
    </html>
    """
    
    print("Example HTML with Altcha challenge:")
    print(example_html)
    print()
    
    # Try to solve the Altcha challenge
    print("Attempting to solve Altcha challenge...")
    solution = altcha_local_solver.solve_altcha_locally(example_html, "https://example.com")
    
    if solution:
        print(f"✅ Successfully solved Altcha challenge!")
        print(f"Solution: {solution}")
        
        # Decode the solution to see what was created
        try:
            import base64
            import json
            decoded_solution = base64.b64decode(solution).decode('utf-8')
            solution_data = json.loads(decoded_solution)
            print(f"Decoded solution: {json.dumps(solution_data, indent=2)}")
        except Exception as e:
            print(f"Could not decode solution: {e}")
    else:
        print("❌ Failed to solve Altcha challenge")
    
    print()
    
    # Show solver capabilities
    print("=== Solver Capabilities ===")
    status = altcha_local_solver.get_solver_status()
    print(f"Type: {status['type']}")
    print(f"Capabilities: {', '.join(status['capabilities'])}")
    print(f"Solving attempts: {status['solving_attempts']}/{status['max_attempts']}")

def demonstrate_challenge_extraction():
    """Demonstrate challenge extraction from different formats"""
    
    print("\n=== Challenge Extraction Demonstration ===")
    
    # Different Altcha challenge formats
    challenge_formats = [
        # Format 1: Standard HTML element
        """
        <altcha-challenge 
            data-challenge="eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTB9"
            data-verifier="abc123">
        </altcha-challenge>
        """,
        
        # Format 2: Data attributes
        """
        <div data-altcha-challenge="eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTB9"
             data-altcha-verifier="def456">
        </div>
        """,
        
        # Format 3: JavaScript variables
        """
        <script>
            window.altchaChallenge = "eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTB9";
            window.altchaVerifier = "ghi789";
        </script>
        """,
        
        # Format 4: Altcha configuration
        """
        <script>
            altcha.challenge = "eyJ0aW1lc3RhbXAiOjE3MzQ1Njc4OTB9";
            altcha.verifier = "jkl012";
        </script>
        """
    ]
    
    for i, html in enumerate(challenge_formats, 1):
        print(f"\nFormat {i}:")
        print(html.strip())
        
        # Try to extract challenge data
        challenge_data = altcha_local_solver._extract_altcha_challenge(html)
        if challenge_data:
            print(f"✅ Extracted: {challenge_data}")
        else:
            print("❌ No challenge data found")

def main():
    """Main demonstration function"""
    
    # Load environment variables
    load_dotenv()
    
    print("Local Altcha Solver Examples")
    print("=" * 50)
    
    # Demonstrate basic solving
    demonstrate_altcha_solving()
    
    # Demonstrate challenge extraction
    demonstrate_challenge_extraction()
    
    print("\n" + "=" * 50)
    print("Demonstration completed!")
    print("\nTo use in your own code:")
    print("""
    from app.services.captcha_solver_service import altcha_local_solver
    
    # Solve Altcha challenge
    solution = altcha_local_solver.solve_altcha_locally(html_content, url)
    
    if solution:
        print(f"Solution: {solution}")
    else:
        print("Failed to solve")
    """)

if __name__ == "__main__":
    main()
