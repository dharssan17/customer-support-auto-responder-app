# Multi-Company Customer Support Chatbot Platform

A minimal Flask application for a multi-company customer support chatbot platform.

## Project Structure

```
.
├── backend/
│   └── app.py          # Main Flask application
├── templates/          # HTML templates (for future use)
├── static/            # Static files (CSS, JS, images - for future use)
├── requirements.txt   # Python dependencies
└── README.md         # This file
```

## Setup Instructions

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Create a `.env` file in the project root
   - Add your Groq API key:
     ```
     GROQ_API_KEY=your_groq_api_key_here
     ```
   - Get your API key from: https://console.groq.com/

## Running the Application

1. **Navigate to the backend directory**:
   ```bash
   cd backend
   ```

2. **Run the Flask application**:
   ```bash
   python app.py
   ```

3. **Access the application**:
   Open your browser and navigate to: `http://127.0.0.1:5000`

   You should see: "Server Running"

## Development Notes

- The application runs in debug mode by default
- Server listens on all interfaces (0.0.0.0) on port 5000
- No database is configured yet
- Templates and static folders are ready for future use
- AI chatbot powered by Groq LLM (requires GROQ_API_KEY in .env file)
- Chatbot uses company FAQs to answer questions, or connects to support agent if no relevant FAQ exists

