# Altcha Captcha Handling for Cdiscount Scraping

This document provides comprehensive information about handling Altcha captchas when scraping Cdiscount.com using the eshop-scraper application.

## Overview

Altcha is a privacy-friendly captcha system that's becoming increasingly common on e-commerce websites. This implementation provides multiple strategies for handling Altcha captchas:

1. **Local Detection and Solving** - Automatic detection and local solving attempts
2. **Local Altcha Challenge Solving** - Advanced local solving using challenge data
3. **Manual Solving** - Fallback to manual human solving
4. **Bypass Techniques** - Various methods to avoid or bypass captchas

## Features

- ✅ **Automatic Detection** - Detects Altcha captchas on web pages
- ✅ **Multiple Solving Strategies** - Local, third-party, and manual solving
- ✅ **Local Altcha Solving** - Advanced challenge solving using local algorithms
- ✅ **Fallback Mechanisms** - Multiple fallback options if primary methods fail
- ✅ **Configurable Timeouts** - Adjustable timeouts for different solving methods
- ✅ **Comprehensive Logging** - Detailed logging for debugging and monitoring

## Installation

### 1. Install Dependencies

The captcha handling system is already integrated into your existing setup. No additional packages are required beyond what's already in `requirements.txt`.

### 2. Environment Configuration

Add the following environment variables to your `.env` file:

```bash
# Captcha Handling Settings
CAPTCHA_AUTO_HANDLE=True
CAPTCHA_SOLVING_TIMEOUT=120
CAPTCHA_MAX_RETRIES=3
```

## Configuration

### Local Altcha Solving Capabilities

The local solver provides several methods for handling Altcha captchas:

#### Challenge Extraction
- **HTML Elements**: Detects `<altcha-challenge>` elements and data attributes
- **JavaScript Variables**: Extracts challenge data from window variables
- **Script Content**: Parses script tags for Altcha configuration

#### Solving Methods
- **Timestamp-based**: Creates solutions based on challenge timestamps
- **Verifier-based**: Uses challenge verifier data for solution generation
- **Hash-based**: Applies various hash algorithms (MD5, SHA1, SHA256)
- **Bypass Attempts**: Tries to bypass verification when possible

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `CAPTCHA_AUTO_HANDLE` | `True` | Automatically handle captchas when detected |
| `CAPTCHA_SOLVING_TIMEOUT` | `120` | Maximum time to wait for captcha solving (seconds) |
| `CAPTCHA_MAX_RETRIES` | `3` | Maximum number of solving attempts |

## Usage

### 1. Basic Usage with Browser Manager

The browser manager now automatically handles captchas:

```python
from app.browser_manager import browser_manager

# Setup browser with captcha handling enabled
browser, context, page = browser_manager.setup_browser()

# Navigate to a page (captcha handling is automatic)
content = browser_manager.get_page_content_with_retry(
    url="https://www.cdiscount.com/product-url",
    handle_captcha=True  # Default is True
)
```

### 2. CDiscount Extractor with Captcha Handling

Use the enhanced CDiscount extractor:

```python
from app.extractors.cdiscount import CDiscountExtractor

# Create extractor
extractor = CDiscountExtractor(html_content, url)

# Extract with automatic captcha handling
product_info = extractor.extract_with_captcha_handling()

if product_info:
    print(f"Title: {product_info.title}")
    print(f"Price: {product_info.price}")
else:
    print("Extraction failed")
```

### 3. Manual Captcha Handling

For more control over the captcha handling process:

```python
from app.utils.captcha_handler import captcha_handler
from app.services.captcha_solver_service import captcha_solver_service

# Check if captcha is present
if captcha_handler.detect_altcha_captcha(page):
    print("Captcha detected!")
    
    # Try local solving first
    if captcha_handler.solve_altcha_captcha(page, strategy="local"):
        print("Solved locally!")
    
    # Try third-party service
    elif captcha_solver_service.available_services:
        solution = captcha_solver_service.solve_altcha_captcha(
            page.content(), 
            url
        )
        if solution:
            print(f"Solved with service: {solution}")
    
    # Fallback to manual solving
    else:
        captcha_handler.solve_altcha_captcha(page, strategy="manual")
```

## Solving Strategies

### 1. Local Solving (`strategy="local"`)

Attempts to solve captchas automatically using various techniques:

- **Button Interaction**: Looks for and clicks human verification buttons
- **Form Filling**: Attempts to fill form fields that might trigger verification
- **Element Interaction**: Interacts with various page elements

### 2. Local Altcha Solving (`strategy="auto"`)

Uses advanced local solving algorithms:

- **Challenge Analysis**: Extracts and analyzes Altcha challenge data
- **Algorithmic Solving**: Applies mathematical and cryptographic methods
- **Pattern Recognition**: Identifies common Altcha patterns and structures

### 3. Manual Solving (`strategy="manual"`)

Waits for human intervention:

- Opens browser window for manual solving
- Waits up to 60 seconds for completion
- Automatically detects when solved

### 4. Bypass Techniques (`strategy="bypass"`)

Various methods to avoid captchas:

- **Page Refresh**: Reloads the page to get a new session
- **User Agent Changes**: Modifies browser user agent
- **Storage Clearing**: Clears cookies and local storage

## Monitoring and Debugging

### 1. Check Captcha Status

```python
# Get captcha handler status
handler_status = captcha_handler.get_captcha_info()
print(f"Handler Status: {handler_status}")

# Get local solver status
solver_status = altcha_local_solver.get_solver_status()
print(f"Local Solver Status: {solver_status}")

# Get browser manager captcha status
browser_status = browser_manager.get_captcha_status()
print(f"Browser Status: {browser_status}")
```

### 2. Logging

The system provides comprehensive logging:

```python
import logging

# Set logging level for captcha-related messages
logging.getLogger('app.utils.captcha_handler').setLevel(logging.DEBUG)
logging.getLogger('app.services.captcha_solver_service').setLevel(logging.DEBUG)
```

### 3. Error Handling

```python
try:
    # Your scraping code here
    content = browser_manager.get_page_content_with_retry(url)
except Exception as e:
    print(f"Scraping failed: {e}")
    
    # Check captcha status for debugging
    status = browser_manager.get_captcha_status()
    print(f"Captcha Status: {status}")
```

## Testing

### 1. Run Test Suite

```bash
python test_captcha_handling.py
```

### 2. Test Individual Components

```python
# Test captcha detection
from app.utils.captcha_handler import captcha_handler
status = captcha_handler.get_captcha_info()
print(status)

# Test local solver availability
from app.services.captcha_solver_service import altcha_local_solver
solver = altcha_local_solver.get_solver_status()
print(solver)
```

## Troubleshooting

### Common Issues

#### 1. "No captcha solving services available"

**Solution**: Configure API keys in your environment variables:
```bash
export CAPTCHA_2CAPTCHA_API_KEY=your_key_here
```

#### 2. "Captcha detection failed"

**Solution**: Check if the page structure has changed. Altcha elements might have different selectors.

#### 3. "Local Altcha solving failed"

**Solution**: 
- Check if the Altcha challenge structure has changed
- Verify that challenge data is being extracted correctly
- Review logs for specific solving method failures

#### 4. "Manual solving timeout"

**Solution**: Increase the timeout in configuration:
```bash
export CAPTCHA_SOLVING_TIMEOUT=300  # 5 minutes
```

### Debug Mode

Enable debug logging for detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set specific loggers
logging.getLogger('app.utils.captcha_handler').setLevel(logging.DEBUG)
```

## Performance Considerations

### 1. Timeouts

- **Local solving**: Usually 5-15 seconds
- **Third-party services**: 30-120 seconds (depending on service load)
- **Manual solving**: Up to 60 seconds

### 2. Cost Optimization

- Use local solving first (free)
- Local Altcha solving is completely free
- Consider manual solving for development/testing

### 3. Rate Limiting

- Respect website rate limits
- Implement delays between requests
- Use proxy rotation if available

## Security Considerations

### 1. Local Solver Security

- The local solver doesn't require external API keys
- All solving is done locally without external requests
- No sensitive data is transmitted to third parties

### 2. Request Monitoring

- Monitor local solver performance and success rates
- Set up alerts for unusual solving patterns
- Review logs for specific solving method effectiveness

### 3. Compliance

- Ensure compliance with website terms of service
- Respect robots.txt and rate limiting
- Use captcha solving services responsibly

## Advanced Configuration

### 1. Custom Captcha Detection

You can extend the captcha detection for specific websites:

```python
class CustomCaptchaHandler(AltchaCaptchaHandler):
    def detect_altcha_captcha(self, page):
        # Add custom detection logic
        custom_selectors = ['#custom-captcha', '.site-specific-captcha']
        
        for selector in custom_selectors:
            if page.query_selector(selector):
                return True
        
        # Fall back to parent detection
        return super().detect_altcha_captcha(page)
```

### 2. Custom Solving Strategies

Implement custom solving strategies:

```python
def custom_solving_strategy(self, page):
    # Your custom logic here
    pass

# Register custom strategy
captcha_handler.register_strategy("custom", custom_solving_strategy)
```

## Support and Updates

### 1. Keep Updated

- Monitor for updates to Altcha implementation
- Update captcha solving service integrations
- Check for new bypass techniques

### 2. Community Support

- Report issues with detailed logs
- Share successful strategies
- Contribute improvements

### 3. Solver Performance

Monitor solver performance regularly:
- Check success rates for different solving methods
- Review logs for challenge extraction effectiveness
- Monitor bypass attempt success rates

## Conclusion

This captcha handling system provides a robust solution for dealing with Altcha captchas on Cdiscount and other websites. By combining multiple strategies and fallback mechanisms, it ensures high success rates while maintaining flexibility and cost-effectiveness.

For best results:
1. Monitor local solver performance and success rates
2. Adjust timeouts based on solving method effectiveness
3. Use local solving as the primary method
4. Implement proper error handling and logging
5. Stay updated with the latest Altcha developments

Remember that captcha solving should be used responsibly and in compliance with website terms of service.
