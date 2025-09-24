import os
import json
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Use SESSION_SECRET if available, otherwise fall back to environment default (with warning)
session_secret = os.environ.get('SESSION_SECRET')
if session_secret:
    app.secret_key = session_secret
else:
    logger.warning("SESSION_SECRET not set - using default (not secure for production)")
    app.secret_key = 'dev-key-change-in-production'

# Configuration file path
CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from file and merge with environment variables"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        # Create default config structure (no secrets stored)
        config = {
            'url': '',
            'keywords': []
        }
        save_config(config)
    
    # Always merge environment variables for secrets and defaults
    # Use environment variables when config values are empty
    config['url'] = config.get('url', '') or os.environ.get('DEFAULT_URL', '')
    keywords_env = os.environ.get('DEFAULT_KEYWORDS', '')
    if not config.get('keywords') and keywords_env:
        config['keywords'] = [kw.strip() for kw in keywords_env.split(',') if kw.strip()]
    
    # Always get email config from environment (never store secrets)
    config['sender_email'] = os.environ.get('SENDER_EMAIL', '')
    config['sender_password'] = os.environ.get('SENDER_EMAIL_PASSWORD', '')
    config['receiver_email'] = os.environ.get('RECEIVER_EMAIL', '')
    
    return config

def save_config(config):
    """Save configuration to file (excluding secrets)"""
    # Only save non-sensitive configuration
    safe_config = {
        'url': config.get('url', ''),
        'keywords': config.get('keywords', [])
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(safe_config, f, indent=2)

def scrape_webpage(url):
    """Scrape webpage content and return text"""
    try:
        logger.info(f"Starting to scrape URL: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        logger.info(f"Successfully scraped {len(text)} characters from {url}")
        return text
    except Exception as e:
        logger.error(f"Error scraping webpage {url}: {str(e)}")
        return None

def check_keywords(text, keywords):
    """Check if any keywords are found in the text (case-insensitive)"""
    found_keywords = []
    text_lower = text.lower()
    
    for keyword in keywords:
        if keyword.strip() and keyword.strip().lower() in text_lower:
            found_keywords.append(keyword.strip())
    
    return found_keywords

def send_email(sender_email, sender_password, receiver_email, subject, body):
    """Send email notification"""
    try:
        logger.info(f"Attempting to send email to {receiver_email}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Gmail SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        
        logger.info("Email sent successfully")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False

@app.route('/')
def index():
    """Main configuration page"""
    config = load_config()
    return render_template('index.html', config=config)

@app.route('/update_config', methods=['POST'])
def update_config():
    """Update configuration from form"""
    # Basic CSRF protection - check referer
    referer = request.headers.get('Referer', '')
    if not referer or not (request.host in referer):
        logger.warning("Invalid referer for config update")
        flash('Invalid request', 'error')
        return redirect(url_for('index'))
    try:
        config = load_config()
        
        # Update config with form data
        config['url'] = request.form.get('url', '').strip()
        config['keywords'] = [kw.strip() for kw in request.form.get('keywords', '').split(',') if kw.strip()]
        
        # Note: Email configuration is not saved - only URL and keywords are persisted
        # Email settings must be configured via environment variables for security
        
        save_config(config)
        flash('Configuration updated successfully!', 'success')
    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        flash('Error updating configuration', 'error')
    
    return redirect(url_for('index'))

@app.route('/check', methods=['POST'])
def check():
    """Check webpage for keywords (API endpoint - requires token)"""
    # Security: require check token to prevent abuse
    check_token = os.environ.get('CHECK_TOKEN')
    if not check_token:
        logger.error("CHECK_TOKEN environment variable is required for API access")
        return jsonify({'status': 'error', 'message': 'CHECK_TOKEN not configured'}), 500
    
    provided_token = request.headers.get('X-Check-Token') or request.args.get('token')
    if not provided_token or provided_token != check_token:
        logger.warning("Unauthorized check attempt")
        return jsonify({'status': 'error', 'message': 'Unauthorized - invalid or missing token'}), 401
    
    logger.info("API check triggered")
    return _perform_check()

@app.route('/check_ui', methods=['POST'])
def check_ui():
    """Check webpage for keywords (UI endpoint - no token required)"""
    # Basic CSRF protection - check referer
    referer = request.headers.get('Referer', '')
    if not referer or not (request.host in referer):
        logger.warning("Invalid referer for UI check")
        return jsonify({'status': 'error', 'message': 'Invalid request'}), 400
    
    logger.info("UI check triggered")
    return _perform_check()

def _perform_check():
    """Perform the actual check logic"""
    
    try:
        config = load_config()
        
        # Use form data if provided, otherwise use saved config
        if request.method == 'POST':
            url = request.form.get('url', config['url']).strip()
            keywords = [kw.strip() for kw in request.form.get('keywords', ','.join(config['keywords'])).split(',') if kw.strip()]
        else:
            url = config['url']
            keywords = config['keywords']
        
        # Validate configuration
        if not url:
            message = "No URL configured"
            logger.warning(message)
            return jsonify({'status': 'error', 'message': message})
        
        if not keywords:
            message = "No keywords configured"
            logger.warning(message)
            return jsonify({'status': 'error', 'message': message})
        
        if not all([config['sender_email'], config['sender_password'], config['receiver_email']]):
            message = "Email configuration incomplete - check your secrets"
            logger.warning(message)
            return jsonify({'status': 'error', 'message': message})
        
        # Scrape webpage
        text = scrape_webpage(url)
        if text is None:
            message = f"Failed to scrape webpage: {url}"
            logger.error(message)
            return jsonify({'status': 'error', 'message': message})
        
        # Check for keywords
        found_keywords = check_keywords(text, keywords)
        
        if found_keywords:
            logger.info(f"Keywords found: {', '.join(found_keywords)}")
            
            # Send email notification
            subject = f"Local Event Notifier: Keywords Found on {url}"
            body = f"""Local Event Notifier Alert

The following keywords were found on {url}:
{', '.join(found_keywords)}

Keywords searched: {', '.join(keywords)}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated message from your Local Event Notifier Agent.
"""
            
            email_sent = send_email(
                config['sender_email'],
                config['sender_password'],
                config['receiver_email'],
                subject,
                body
            )
            
            if email_sent:
                message = f"Keywords found and email sent: {', '.join(found_keywords)}"
                logger.info(message)
                return jsonify({
                    'status': 'success',
                    'message': message,
                    'found_keywords': found_keywords
                })
            else:
                message = f"Keywords found but email failed: {', '.join(found_keywords)}"
                logger.error(message)
                return jsonify({
                    'status': 'warning',
                    'message': message,
                    'found_keywords': found_keywords
                })
        else:
            message = "No keywords found on the webpage"
            logger.info(message)
            return jsonify({
                'status': 'info',
                'message': message,
                'found_keywords': []
            })
    
    except Exception as e:
        message = f"Error during check: {str(e)}"
        logger.error(message)
        return jsonify({'status': 'error', 'message': message})

@app.route('/status')
def status():
    """Get current configuration status"""
    config = load_config()
    return jsonify({
        'url_configured': bool(config['url']),
        'keywords_configured': bool(config['keywords']),
        'email_configured': bool(config['sender_email'] and config['sender_password'] and config['receiver_email']),
        'config': {
            'url': config['url'],
            'keywords': config['keywords'],
            'sender_email': config['sender_email'] if config['sender_email'] else 'Not configured',
            'receiver_email': config['receiver_email'] if config['receiver_email'] else 'Not configured'
        }
    })

if __name__ == '__main__':
    logger.info("Starting Local Event Notifier Agent")
    # Check if we're in a development environment
    is_dev = os.environ.get('FLASK_ENV') == 'development' or os.environ.get('FLASK_DEBUG') == '1'
    app.run(host='0.0.0.0', port=5000, debug=is_dev)