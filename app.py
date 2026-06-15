import os
import re
import json
import logging
import time
import threading
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Thread-safe in-memory rate limiting store: IP -> list of timestamps
rate_limit_lock = threading.Lock()
rate_limit_records = {}

# Thread-safe in-memory cache store: Key (lowercase company name) -> {"data": dict, "timestamp": float}
cache_lock = threading.Lock()
company_cache = {}

# Prompt injection patterns to block
INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above|all)\s+instructions",
    r"disregard\s+(previous|prior|above|all)\s+instructions",
    r"forget\s+(previous|prior|above|all)\s+instructions",
    r"you\s+are\s+now",
    r"act\s+as\s+(a|an)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"new\s+instructions",
    r"system\s*:",
    r"<\s*system\s*>",
    r"\[system\]",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"do\s+anything\s+now",
]

def contains_prompt_injection(text):
    """Check if input contains prompt injection attempts."""
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def sanitize_company_name(name):
    """Sanitize company name - allow only safe characters."""
    # Allow letters, numbers, spaces, hyphens, dots, ampersands, commas
    sanitized = re.sub(r"[^\w\s\-\.\,\&\(\)']", "", name)
    return sanitized.strip()

def get_client_ip():
    x_forwarded_for = request.headers.getlist("X-Forwarded-For")
    if x_forwarded_for:
        return x_forwarded_for[0].split(',')[0].strip()
    return request.remote_addr

def is_rate_limited(ip_address):
    now = time.time()
    one_hour_ago = now - 3600
    
    with rate_limit_lock:
        if ip_address not in rate_limit_records:
            rate_limit_records[ip_address] = []
            
        rate_limit_records[ip_address] = [t for t in rate_limit_records[ip_address] if t > one_hour_ago]
        
        if len(rate_limit_records[ip_address]) >= 10:
            return True
            
        rate_limit_records[ip_address].append(now)
        return False

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
        "font-src 'self' fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

# Setup SDK wrappers
api_key = os.getenv("GEMINI_API_KEY")

try:
    from google import genai
    from google.genai import types
    has_new_sdk = True
    logger.info("Successfully imported modern 'google-genai' SDK.")
except ImportError:
    try:
        import google.generativeai as genai_old
        has_new_sdk = False
        logger.info("Fallback: Successfully imported 'google-generativeai' SDK.")
    except ImportError:
        has_new_sdk = None
        logger.warning("No Gemini SDK found. Please ensure requirements are installed.")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_prep():
    # 1. Rate Limiting Check
    client_ip = get_client_ip()
    if is_rate_limited(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return jsonify({
            "error": "Rate limit exceeded. Maximum of 10 requests per hour are allowed."
        }), 429

    # Verify API key is present
    if not api_key or api_key.strip() == "" or api_key == "YOUR_API_KEY_HERE":
        return jsonify({
            "error": "Gemini API key is not configured. Please add your GEMINI_API_KEY to the .env file."
        }), 400

    if has_new_sdk is None:
        return jsonify({
            "error": "No Gemini SDK library installed. Please run 'pip install -r requirements.txt' first."
        }), 500

    data = request.get_json()
    if not data or 'company_name' not in data:
        return jsonify({"error": "Company name is required."}), 400

    company_name = data['company_name'].strip()
    if not company_name:
        return jsonify({"error": "Company name cannot be blank."}), 400

    # 2. Input Validation
    if len(company_name) > 100:
        return jsonify({"error": "Company name is too long. Maximum length is 100 characters."}), 400

    if "<" in company_name or ">" in company_name:
        return jsonify({"error": "Company name contains invalid characters."}), 400

    # 3. Prompt Injection Check
    if contains_prompt_injection(company_name):
        logger.warning(f"Prompt injection attempt detected from IP: {client_ip}, input: {company_name}")
        return jsonify({"error": "Invalid company name. Please enter a real company name."}), 400

    # 4. Sanitize input
    company_name = sanitize_company_name(company_name)
    if not company_name:
        return jsonify({"error": "Company name contains invalid characters."}), 400

    # 5. Cache Check (1 hour TTL)
    cache_key = company_name.lower()
    cached_result = None
    with cache_lock:
        if cache_key in company_cache:
            entry = company_cache[cache_key]
            if time.time() - entry["timestamp"] < 21600:
                cached_result = entry["data"]

    if cached_result:
        logger.info(f"Serving cached report for company: {company_name}")
        response_data = dict(cached_result)
        response_data["cached"] = True
        return jsonify(response_data)

    logger.info(f"Generating sales prep brief for company: {company_name}")

    prompt = f"""
    You are an expert sales preparation assistant. Analyze the company "{company_name}" and generate a detailed sales preparation brief.
    Your response must be in JSON format matching the following structure:
    {{
        "company_name": "Name of the company",
        "company_summary": "A detailed 2-3 paragraph summary of the company, including their industry, core products/services, target market, scale, and value proposition.",
        "recent_news": [
            {{
                "title": "Headline or description of recent news/event",
                "summary": "Short explanation of the event and why it is relevant for a sales introduction."
            }},
            {{
                "title": "Headline or description of recent news/event",
                "summary": "Short explanation of the event and why it is relevant for a sales introduction."
            }},
            {{
                "title": "Headline or description of recent news/event",
                "summary": "Short explanation of the event and why it is relevant for a sales introduction."
            }}
        ],
        "pain_points": [
            {{
                "issue": "Specific business or operational challenge",
                "impact": "The impact of this issue on their business growth or efficiency",
                "solution_angle": "How a modern software/consulting solution could address this"
            }},
            {{
                "issue": "Specific business or operational challenge",
                "impact": "The impact of this issue on their business growth or efficiency",
                "solution_angle": "How a modern software/consulting solution could address this"
            }},
            {{
                "issue": "Specific business or operational challenge",
                "impact": "The impact of this issue on their business growth or efficiency",
                "solution_angle": "How a modern software/consulting solution could address this"
            }}
        ],
        "discovery_questions": [
            {{
                "question": "Strategic open-ended question to ask key decision makers",
                "intent": "What specific business intelligence or gap we want to uncover with this question"
            }},
            {{
                "question": "Strategic open-ended question to ask key decision makers",
                "intent": "What specific business intelligence or gap we want to uncover with this question"
            }},
            {{
                "question": "Strategic open-ended question to ask key decision makers",
                "intent": "What specific business intelligence or gap we want to uncover with this question"
            }},
            {{
                "question": "Strategic open-ended question to ask key decision makers",
                "intent": "What specific business intelligence or gap we want to uncover with this question"
            }}
        ],
        "key_people": [
            {{
                "name": "Full name or Representative role (e.g. Chief Information Officer / VP of Sales)",
                "role": "Exact role/title at the company",
                "focus": "Their primary performance goals, what they care about, and how to build rapport with them."
            }},
            {{
                "name": "Full name or Representative role (e.g. Chief Information Officer / VP of Sales)",
                "role": "Exact role/title at the company",
                "focus": "Their primary performance goals, what they care about, and how to build rapport with them."
            }},
            {{
                "name": "Full name or Representative role (e.g. Chief Information Officer / VP of Sales)",
                "role": "Exact role/title at the company",
                "focus": "Their primary performance goals, what they care about, and how to build rapport with them."
            }}
        ]
    }}

    Important: Only analyze real companies. Provide realistic, actionable, and industry-specific information tailored directly to {company_name}. Do not use generic statements.
    """

    try:
        if has_new_sdk:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-pro',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            response_text = response.text
        else:
            genai_old.configure(api_key=api_key)
            model = genai_old.GenerativeModel('gemini-pro')
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            response_text = response.text

        logger.info("Successfully received response from Gemini API.")
        
        parsed_data = json.loads(response_text)
        
        with cache_lock:
            company_cache[cache_key] = {
                "data": parsed_data,
                "timestamp": time.time()
            }
            
        response_data = dict(parsed_data)
        response_data["cached"] = False
        return jsonify(response_data)

    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse Gemini response as JSON: {je}")
        return jsonify({
            "error": "The AI response could not be parsed. Please try again.",
        }), 502
    except Exception as e:
        logger.error(f"Error generating brief: {str(e)}")
        return jsonify({"error": "Something went wrong. Please try again later."}), 500

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "t")
    logger.info(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=debug)
