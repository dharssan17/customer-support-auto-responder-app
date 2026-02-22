"""
Multi-Company Customer Support Chatbot Platform
Main Flask application entry point
"""

import json
import os
import re
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session
from groq import Groq

# Load environment variables from .env file
load_dotenv()

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

# Initialize Flask application
# Set template and static folders to parent directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, 
            template_folder=os.path.join(base_dir, "templates"),
            static_folder=os.path.join(base_dir, "static"))

# Set secret key for session management
app.secret_key = os.urandom(24)

# Path to companies configuration file
COMPANIES_FILE = os.path.join(os.path.dirname(__file__), "companies.json")

# Path to tickets storage file
TICKETS_FILE = os.path.join(os.path.dirname(__file__), "tickets.json")


def load_company(company_id):
    """
    Load company data from companies.json file
    
    Args:
        company_id (str): The unique identifier of the company
        
    Returns:
        dict: Company data dictionary, or None if company not found
    """
    try:
        # Read companies.json file
        with open(COMPANIES_FILE, "r", encoding="utf-8") as file:
            companies = json.load(file)
        
        # Find company by ID
        for company in companies:
            if company.get("id") == company_id:
                return company
        
        # Company not found
        return None
        
    except FileNotFoundError:
        # File doesn't exist
        return None
    except json.JSONDecodeError:
        # Invalid JSON format
        return None


def load_tickets():
    """
    Load tickets from tickets.json file
    
    Returns:
        list: List of ticket dictionaries, or empty list if file doesn't exist
    """
    try:
        if os.path.exists(TICKETS_FILE):
            with open(TICKETS_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        return []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_ticket(ticket):
    """
    Save a new ticket to tickets.json file
    
    Args:
        ticket (dict): Ticket data to save
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        tickets = load_tickets()
        tickets.append(ticket)
        
        with open(TICKETS_FILE, "w", encoding="utf-8") as file:
            json.dump(tickets, file, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving ticket: {e}")
        return False


def format_ai_response(response):
    """
    Format AI response with numbered list if it contains multiple steps.
    Converts multi-sentence responses into numbered list format for better readability.
    
    Args:
        response (str): The AI response text
        
    Returns:
        str: Formatted response with numbered list if applicable
    """
    # Split response by periods to get sentences
    sentences = [s.strip() for s in response.split('.') if s.strip()]
    
    # Apply formatting only if response has more than 2 sentences
    if len(sentences) > 2:
        # Format as numbered list
        formatted_response = ""
        for i, sentence in enumerate(sentences, 1):
            # Add period back to each sentence
            sentence_text = sentence.strip()
            if sentence_text:  # Only process non-empty sentences
                formatted_response += f"{i}. {sentence_text}.\n"
        
        # Remove trailing newline
        return formatted_response.strip()
    
    # Return original response if 2 or fewer sentences
    return response


def is_invalid_input(user_message):
    """
    Check if user message contains only symbols or numbers (invalid input).
    Uses regex to detect if message has no meaningful text content.
    
    Args:
        user_message (str): The user's message
        
    Returns:
        bool: True if input is invalid (only symbols/numbers), False otherwise
    """
    # Remove whitespace for checking
    message_clean = user_message.strip()
    
    if not message_clean:
        return True
    
    # Check if message contains only symbols, numbers, or whitespace
    # Valid input should contain at least one letter
    # Pattern: if message has no letters (a-z, A-Z), it's invalid
    if not re.search(r'[a-zA-Z]', message_clean):
        return True
    
    return False


def normalize_user_message(user_message):
    """
    Normalize user message by mapping synonyms to standardized keywords.
    This improves NLP intent recognition by standardizing similar phrases.
    
    Args:
        user_message (str): The original user message
        
    Returns:
        str: User message with synonyms replaced by standardized keywords
    """
    # Dictionary mapping synonyms/phrases to standardized keywords
    synonym_mapping = {
        "login credentials": "password",
        "sign in problem": "login issue",
        "account access": "login issue"
    }
    
    # Convert message to lowercase for case-insensitive matching
    normalized_message = user_message
    
    # Replace each synonym with its standardized keyword
    for synonym, standard_keyword in synonym_mapping.items():
        # Case-insensitive replacement using regex
        pattern = re.compile(re.escape(synonym), re.IGNORECASE)
        normalized_message = pattern.sub(standard_keyword, normalized_message)
    
    return normalized_message


def is_greeting_message(user_message):
    """
    Check if the user message is a greeting or small-talk
    
    Args:
        user_message (str): The user's message
        
    Returns:
        bool: True if it's a greeting, False otherwise
    """
    # List of greeting keywords to detect
    greeting_keywords = [
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "good morning",
        "good evening"
    ]
    
    # Convert to lowercase for case-insensitive comparison
    message_lower = user_message.lower().strip()
    
    # Check if message matches any greeting keyword
    # Match exact word or phrase at the start of message
    for keyword in greeting_keywords:
        if message_lower == keyword or message_lower.startswith(keyword + " "):
            return True
    
    return False


def is_escalation_message(response):
    """
    Check if the response is an escalation message
    
    Args:
        response (str): The AI response message
        
    Returns:
        bool: True if it's an escalation message, False otherwise
    """
    response_lower = response.lower()
    escalation_phrases = [
        "i will connect you to a support agent",
        "connect you to a support agent"
    ]
    
    for phrase in escalation_phrases:
        if phrase in response_lower:
            return True
    return False


def should_show_satisfaction(response, user_message):
    """
    Determine if satisfaction buttons should be shown for a response.
    
    Do NOT show satisfaction buttons for:
    - Greetings (hi, hello, thanks)
    - Escalation messages
    - Agent connection messages
    
    Args:
        response (str): The AI response message
        user_message (str): The original user message
        
    Returns:
        bool: True if satisfaction buttons should be shown, False otherwise
    """
    response_lower = response.lower()
    user_message_lower = user_message.lower()
    
    # Check for escalation/agent connection messages
    escalation_phrases = [
        "i will connect you to a support agent",
        "connect you to a support agent",
        "support agent"
    ]
    
    for phrase in escalation_phrases:
        if phrase in response_lower:
            return False
    
    # Check if user message is a greeting
    greeting_words = ["hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye"]
    for greeting in greeting_words:
        if user_message_lower.strip() == greeting or user_message_lower.strip().startswith(greeting + " "):
            return False
    
    # Check if response is a greeting acknowledgment
    greeting_responses = [
        "hello",
        "hi there",
        "how can i help",
        "you're welcome",
        "glad i could help"
    ]
    
    for greeting_response in greeting_responses:
        if greeting_response in response_lower:
            return False
    
    # If none of the above conditions match, show satisfaction buttons
    return True


def generate_ai_response(user_message, company_data, is_retry=False, previous_response=""):
    """
    Generate AI response using Groq LLM based on user message and company data
    
    Args:
        user_message (str): The user's question/message
        company_data (dict): Company configuration data including name and FAQs
        is_retry (bool): Whether this is a retry attempt
        previous_response (str): The previous AI response (for retry context)
        
    Returns:
        str: AI-generated response or fallback message
    """
    # Check if Groq client is available
    if not groq_client:
        return "I will connect you to a support agent."
    
    try:
        # Extract company information
        company_name = company_data.get("name", "the company")
        faqs = company_data.get("faqs", [])
        
        # Format FAQs for prompt
        faq_text = ""
        if faqs:
            for faq in faqs:
                faq_text += f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}\n\n"
        
        # Build prompt based on whether it's a retry
        if is_retry:
            # Retry prompt - ask for alternate solution
            prompt = f"""You are a customer support assistant for {company_name}.

Available FAQs:
{faq_text if faq_text else "No FAQs available."}

Previous response that didn't help the customer:
{previous_response}

Customer Question: {user_message}

Instructions:
- Provide an alternate solution or different approach to help the customer.
- Use the FAQs above to find a different answer.
- Keep your response concise and helpful."""
        else:
            # Initial prompt
            prompt = f"""You are a customer support assistant for {company_name}.

Available FAQs:
{faq_text if faq_text else "No FAQs available."}

Customer Question: {user_message}

Instructions:
- If the question can be answered using the FAQs above, provide a step-by-step solution.
- If no relevant FAQ exists, respond with: "I will connect you to a support agent."
- Keep your response concise and helpful."""
        
        # Call Groq API
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant",  # Fast and efficient model
            temperature=0.7,
            max_tokens=200
        )
        
        # Extract response
        content = chat_completion.choices[0].message.content
        if content:
            response = content.strip()
            
            # Safety escalation detection
            # Check if AI response contains phrases that indicate escalation to human support
            # These phrases suggest the AI is trying to schedule calls or direct to phone/office support
            escalation_phrases = [
                "schedule a call",
                "call our support",
                "phone support",
                "business hours",
                "visit our office"
            ]
            
            # Convert response to lowercase for case-insensitive matching
            response_lower = response.lower()
            
            # Check if any escalation phrase exists in the response
            for phrase in escalation_phrases:
                if phrase in response_lower:
                    # AI response contains escalation phrase - return fallback message instead
                    # This prevents the AI from suggesting direct human contact methods
                    return "I will connect you to a support agent."
            
            # AI response formatting enhancement
            # If response contains password reset keywords, append reset password link
            password_keywords = ["reset password", "forgot password"]
            response_lower_for_password = response.lower()
            
            for keyword in password_keywords:
                if keyword in response_lower_for_password:
                    # Append password reset link to the response
                    response = response + "\n\nYou can reset your password here: /reset-password"
                    break
            
            # Format AI response - convert multi-step solutions to numbered list
            # Only applies when response has more than 2 sentences
            response = format_ai_response(response)
            
            # No escalation phrases found - return AI response (with potential enhancement)
            return response
        else:
            return "I will connect you to a support agent."
        
    except Exception as e:
        # Fallback on error
        print(f"Error generating AI response: {e}")
        return "I will connect you to a support agent."


@app.route("/")
def index():
    """
    Root route - loads company "1" and renders the chat UI
    """
    company = load_company("1")
    
    if company:
        return render_template("index.html", company_name=company.get("name", "Support"))
    else:
        return "Company not found", 404


@app.route("/chat", methods=["POST"])
def chat():
    """
    Chat endpoint - handles user messages and satisfaction feedback
    
    Returns:
        JSON response: AI-generated reply or satisfaction response
    """
    try:
        data = request.get_json()
        
        # Initialize session variables if not present
        if "attempt_count" not in session:
            session["attempt_count"] = 0
        if "last_message" not in session:
            session["last_message"] = ""
        if "last_response" not in session:
            session["last_response"] = ""
        
        # Check if this is a satisfaction feedback
        satisfaction = data.get("satisfaction")
        
        if satisfaction is not None:
            # Handle satisfaction feedback
            if satisfaction == "yes":
                # User satisfied - reset attempt count
                session["attempt_count"] = 0
                session["last_message"] = ""
                session["last_response"] = ""
                return jsonify({"message": "Glad I could help!", "show_satisfaction": False}), 200
            
            elif satisfaction == "no":
                # User not satisfied - check attempt count
                attempt_count = session.get("attempt_count", 0)
                
                if attempt_count < 2:
                    # Increment attempt count
                    session["attempt_count"] = attempt_count + 1
                    
                    # Generate alternate solution
                    company = load_company("1")
                    if not company:
                        return jsonify({"error": "Company not found"}), 404
                    
                    ai_response = generate_ai_response(
                        session["last_message"], 
                        company, 
                        is_retry=True,
                        previous_response=session["last_response"]
                    )
                    
                    # Update last response
                    session["last_response"] = ai_response
                    
                    # Determine if satisfaction buttons should be shown for retry response
                    show_satisfaction = should_show_satisfaction(ai_response, session["last_message"])
                    
                    return jsonify({"message": ai_response, "show_satisfaction": show_satisfaction}), 200
                else:
                    # Max attempts reached - trigger escalation
                    # Keep last message for ticket creation
                    escalation_message = "I will connect you to a support agent."
                    return jsonify({
                        "message": escalation_message, 
                        "show_satisfaction": False,
                        "show_ticket_form": True
                    }), 200
        
        # Regular message handling
        user_message = data.get("message", "")
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Greeting detection - check before AI and escalation logic
        # If user message is a greeting, return friendly response without calling AI
        if is_greeting_message(user_message):
            # Return friendly greeting response
            # Do not call AI, do not escalate, do not create ticket
            greeting_response = "Hello! How can I assist you today?"
            return jsonify({
                "message": greeting_response,
                "show_satisfaction": False,
                "show_ticket_form": False
            }), 200
        
        # Invalid input detection - check for symbols/numbers only
        # If message contains only symbols or numbers, return error without calling AI
        if is_invalid_input(user_message):
            return jsonify({
                "message": "Please enter a valid support query.",
                "show_satisfaction": False,
                "show_ticket_form": False
            }), 200
        
        # Reset attempt count for new message (non-greeting, valid input)
        session["attempt_count"] = 0
        
        # Normalize user message - map synonyms to standardized keywords for better intent recognition
        normalized_message = normalize_user_message(user_message)
        
        # Load company data (using company "1" for now)
        company = load_company("1")
        
        if not company:
            return jsonify({"error": "Company not found"}), 404
        
        # Generate AI response using Groq with normalized message
        ai_response = generate_ai_response(normalized_message, company)
        
        # Determine if satisfaction buttons should be shown
        show_satisfaction = should_show_satisfaction(ai_response, user_message)
        
        # Check if this is an escalation message
        show_ticket_form = is_escalation_message(ai_response)
        
        # Store original message and response in session
        # Store normalized message for retry attempts
        session["last_message"] = normalized_message
        session["last_response"] = ai_response
        
        return jsonify({
            "message": ai_response, 
            "show_satisfaction": show_satisfaction,
            "show_ticket_form": show_ticket_form
        }), 200
        
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return jsonify({"error": "Invalid request"}), 400


@app.route("/create_ticket", methods=["POST"])
def create_ticket():
    """
    Create a new support ticket
    
    Returns:
        JSON response: Success or error message
    """
    try:
        data = request.get_json()
        user_name = data.get("name", "").strip()
        user_email = data.get("email", "").strip()
        
        # Validate input
        if not user_name or not user_email:
            return jsonify({"error": "Name and email are required"}), 400
        
        # Get last user message from session for issue summary
        issue_summary = session.get("last_message", "Customer support request")
        
        # Generate ticket ID
        ticket_id = str(uuid.uuid4())[:8].upper()
        
        # Get current timestamp
        timestamp = datetime.now().isoformat()
        
        # Create ticket object
        ticket = {
            "ticket_id": ticket_id,
            "company_id": "1",  # Using company "1" for now
            "user_name": user_name,
            "user_email": user_email,
            "issue_summary": issue_summary,
            "timestamp": timestamp
        }
        
        # Save ticket to file
        if save_ticket(ticket):
            # Clear session data after ticket creation
            session["last_message"] = ""
            session["last_response"] = ""
            session["attempt_count"] = 0
            
            return jsonify({
                "message": "Your issue has been forwarded to our support team.",
                "ticket_id": ticket_id
            }), 200
        else:
            return jsonify({"error": "Failed to create ticket"}), 500
            
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return jsonify({"error": "Invalid request"}), 400


@app.route("/company/<company_id>")
def get_company(company_id):
    """
    Get company configuration by company ID
    
    Args:
        company_id (str): The unique identifier of the company
        
    Returns:
        JSON response: Company data or error message
    """
    company = load_company(company_id)
    
    if company:
        return jsonify(company), 200
    else:
        return jsonify({"error": "Company not found"}), 404


if __name__ == "__main__":
    # Run the Flask development server
    # Default: http://127.0.0.1:5000
    app.run(debug=True, host="0.0.0.0", port=5000)

