# Local Event Notifier Agent

## Overview

This is a web scraping and monitoring application built with Flask that autonomously monitors specified webpages for predefined keywords and sends email notifications when matches are found. The application provides a simple web interface for configuration and manual trigger capabilities, making it suitable for tracking events or content changes on websites.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Web Framework
- **Flask** serves as the lightweight web application framework
- Single-file application structure in `main.py` for simplicity
- Template-based HTML rendering using Jinja2

### Configuration Management
- **JSON-based configuration** stored in `config.json` for non-sensitive data (URL and keywords)
- **Environment variable integration** for sensitive information (email credentials, secrets)
- Hybrid approach where environment variables override empty config file values
- Session secret management with fallback to development key

### Web Scraping Engine
- **Requests library** for HTTP requests to fetch webpage content
- **BeautifulSoup4** for HTML parsing and text extraction
- Case-insensitive keyword detection across scraped content

### Email Notification System
- **SMTP integration** using Python's built-in `smtplib`
- Gmail-compatible authentication using app passwords
- Rich email formatting with HTML and text content
- Dynamic subject lines indicating found keywords and source URLs

### Route Architecture
- `/` - Configuration interface and dashboard
- `/check` - API endpoint for triggering monitoring checks
- RESTful design for external automation integration

### Security Model
- Environment variable separation for sensitive credentials
- No storage of passwords or sensitive data in configuration files
- Session-based flash messaging for user feedback

### Logging and Monitoring
- Structured logging with timestamps and severity levels
- Console output for debugging and operational visibility
- Error handling with graceful degradation

## External Dependencies

### Core Libraries
- **Flask 2.3.3** - Web application framework
- **Requests 2.31.0** - HTTP client for web scraping
- **BeautifulSoup4 4.12.2** - HTML/XML parsing

### Email Services
- **Gmail SMTP** (smtp.gmail.com:587) - Email delivery service
- Requires app-specific passwords for authentication

### Environment Configuration
- **Replit Secrets** for secure credential storage:
  - `SESSION_SECRET` - Flask session encryption key
  - `SENDER_EMAIL` - Notification sender email address
  - `SENDER_EMAIL_PASSWORD` - Email service app password
  - `RECEIVER_EMAIL` - Notification recipient email address
  - `DEFAULT_URL` - Default webpage to monitor
  - `DEFAULT_KEYWORDS` - Comma-separated default keywords

### External Automation
- Designed for integration with external ping services or cron jobs
- `/check` endpoint enables automated monitoring triggers
- Stateless operation suitable for serverless or scheduled execution