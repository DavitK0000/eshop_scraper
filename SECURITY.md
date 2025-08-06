# E-commerce Scraper API - Security Guide

## Overview

This API implements a comprehensive security system to protect against abuse while remaining publicly accessible. The security features are designed to prevent brute-force attacks, rate limiting abuse, and unauthorized access.

## Security Features

### 1. API Key Authentication (Optional)
- **Bearer Token Authentication**: Use API keys for enhanced rate limits and features
- **Multiple API Keys**: Support for up to 10 different API keys with individual configurations
- **Flexible Rate Limits**: Each API key can have custom rate limits and daily limits
- **Demo Mode**: Includes a demo key for testing

### 2. Rate Limiting
- **IP-based Rate Limiting**: Anonymous users limited to 10 requests per minute
- **API Key Rate Limiting**: Customizable per-key limits (default: 100 requests/minute)
- **Daily Limits**: Configurable daily request limits per API key
- **Concurrent Request Limits**: Maximum 5 concurrent requests per IP

### 3. IP Blocking & Monitoring
- **Automatic IP Blocking**: Suspicious IPs are automatically blocked for 1 hour
- **Suspicious Activity Detection**: IPs with suspicious patterns are marked for 30 minutes
- **Real-time Monitoring**: All security events are logged and monitored

### 4. Request Validation
- **URL Validation**: Only allowed domains can be scraped
- **User Agent Validation**: Blocks requests with suspicious user agents
- **URL Length Limits**: Maximum URL length of 2048 characters
- **Domain Whitelist**: Only supported e-commerce domains are allowed

### 5. Security Monitoring
- **Security Statistics**: Real-time monitoring of blocked IPs and security events
- **Request Logging**: All requests are logged with IP addresses and timestamps
- **Security Events**: Detailed logging of security violations and suspicious activity

## Configuration

### Environment Variables

Copy `env_example.txt` to `.env` and configure your security settings:

```bash
# API Keys (up to 10 keys supported)
API_KEY_1=your_secure_api_key_here
API_KEY_1_NAME=Premium User
API_KEY_1_RATE_LIMIT=200
API_KEY_1_DAILY_LIMIT=5000

API_KEY_2=another_secure_api_key_here
API_KEY_2_NAME=Standard User
API_KEY_2_RATE_LIMIT=100
API_KEY_2_DAILY_LIMIT=1000
```

### Security Configuration

The security system uses the following default settings:

```python
SECURITY_CONFIG = {
    "MAX_REQUESTS_PER_MINUTE": 60,
    "MAX_REQUESTS_PER_HOUR": 1000,
    "MAX_REQUESTS_PER_DAY": 10000,
    "BLOCKED_IPS_TTL": 3600,  # 1 hour
    "SUSPICIOUS_ACTIVITY_TTL": 1800,  # 30 minutes
    "MAX_URL_LENGTH": 2048,
    "MAX_CONCURRENT_REQUESTS_PER_IP": 5,
}
```

## Usage Examples

### Without API Key (Anonymous Access)
```bash
# Basic scraping (limited to 10 requests/minute)
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://amazon.com/product/123"}'
```

### With API Key (Enhanced Access)
```bash
# Using Bearer token authentication
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_secure_api_key_here" \
  -d '{"url": "https://amazon.com/product/123"}'
```

### Demo API Key
For testing purposes, you can use the demo key:
```bash
curl -X POST "http://localhost:8000/api/v1/scrape" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_key_12345" \
  -d '{"url": "https://amazon.com/product/123"}'
```

## Supported Domains

The API currently supports scraping from these domains:
- Amazon (amazon.com, amazon.co.uk, amazon.de, amazon.fr, amazon.it, amazon.es)
- eBay (ebay.com, ebay.co.uk, ebay.de, ebay.fr, ebay.it, ebay.es)
- Bol.com
- Cdiscount
- Otto.de
- JD.com

## Security Endpoints

### Get Security Statistics
```bash
curl -X GET "http://localhost:8000/api/v1/security/stats"
```

Response:
```json
{
  "blocked_ips": 5,
  "suspicious_ips": 12,
  "total_requests_today": 15420,
  "security_events": [
    {
      "type": "security_violation",
      "timestamp": "2024-01-15T10:30:00",
      "details": {
        "ip": "192.168.1.100",
        "status_code": 429,
        "path": "/api/v1/scrape",
        "method": "POST"
      }
    }
  ]
}
```

### Get Security Status
```bash
curl -X GET "http://localhost:8000/api/v1/security/status"
```

Response:
```json
{
  "security_enabled": true,
  "rate_limiting": true,
  "ip_blocking": true,
  "domain_validation": true,
  "user_agent_validation": true,
  "supported_domains": ["amazon.com", "ebay.com", ...],
  "api_keys_configured": 2,
  "demo_mode": true
}
```

## Rate Limits

| Access Type | Rate Limit | Daily Limit | Notes |
|-------------|------------|-------------|-------|
| Anonymous | 10 req/min | None | Basic access |
| Demo Key | 100 req/min | 1000 req/day | For testing |
| API Key 1 | 200 req/min | 5000 req/day | Premium user |
| API Key 2 | 100 req/min | 1000 req/day | Standard user |

## Security Best Practices

### 1. API Key Management
- Use strong, randomly generated API keys
- Rotate API keys regularly
- Never share API keys in public repositories
- Use different keys for different environments (dev, staging, prod)

### 2. Rate Limiting
- Monitor your usage to stay within limits
- Implement exponential backoff for retries
- Use caching to reduce API calls

### 3. Request Validation
- Always validate URLs before sending
- Use appropriate user agents
- Avoid sending requests with suspicious patterns

### 4. Monitoring
- Regularly check security statistics
- Monitor for unusual activity patterns
- Set up alerts for security violations

## Troubleshooting

### Common Error Responses

#### 429 - Too Many Requests
```json
{
  "detail": "Rate limit exceeded"
}
```
**Solution**: Wait before making more requests or upgrade to a higher rate limit tier.

#### 403 - Access Denied
```json
{
  "detail": "Access denied"
}
```
**Solution**: Your IP may be blocked due to suspicious activity. Wait for the block to expire (1 hour).

#### 400 - Bad Request
```json
{
  "detail": "Domain not supported"
}
```
**Solution**: Check that the URL is from a supported domain.

#### 400 - Invalid User Agent
```json
{
  "detail": "Invalid user agent"
}
```
**Solution**: Use a standard browser user agent instead of bot-like user agents.

### Security Event Logs

Security events are logged with detailed information:
- IP addresses
- Request timestamps
- Violation types
- Response status codes

Check your application logs for security-related messages.

## Production Deployment

### 1. Environment Setup
- Set `DEBUG=False` in production
- Configure proper Redis connection
- Set up proper logging
- Use HTTPS in production

### 2. API Key Management
- Remove the demo key in production
- Configure proper API keys with appropriate limits
- Use environment variables for all sensitive data

### 3. Monitoring
- Set up monitoring for security events
- Configure alerts for unusual activity
- Regular review of security statistics

### 4. Infrastructure
- Use a reverse proxy (nginx) for additional security
- Configure proper firewall rules
- Use rate limiting at the infrastructure level
- Consider using a CDN for additional protection

## Support

For security-related issues or questions:
1. Check the security statistics endpoint
2. Review application logs
3. Monitor rate limit usage
4. Contact support with specific error details 