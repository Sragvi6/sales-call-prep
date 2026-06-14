import os
import json
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

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

    logger.info(f"Generating sales prep brief for company: {company_name}")

    # Create the structured prompt for Gemini
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

    Provide realistic, actionable, and industry-specific information tailored directly to {company_name}. Do not use generic statements.
    """

    try:
        if has_new_sdk:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )
            response_text = response.text
        else:
            genai_old.configure(api_key=api_key)
            model = genai_old.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            response_text = response.text

        logger.info("Successfully received response from Gemini API.")
        
        # Parse the JSON response to ensure validity
        parsed_data = json.loads(response_text)
        return jsonify(parsed_data)

    except json.JSONDecodeError as je:
        logger.error(f"Failed to parse Gemini response as JSON: {je}. Response content was: {response_text}")
        return jsonify({
            "error": "The AI response could not be parsed as structured JSON. Please try again.",
            "raw_response": response_text
        }), 502
    except Exception as e:
        logger.error(f"Error during Gemini call: {e}")
        return jsonify({"error": f"An error occurred while generating the brief: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    logger.info(f"Starting server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=debug)
