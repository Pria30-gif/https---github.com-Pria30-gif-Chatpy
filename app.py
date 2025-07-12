# app.py - Complete Enhanced Chatbot
from flask import Flask, render_template, request, jsonify, session
import random
import time
from datetime import datetime
import spacy
from difflib import SequenceMatcher
from collections import defaultdict
import uuid
import wikipedia

app = Flask(__name__)
app.secret_key = 'your-secret-key-123'  # Change this for production

# Load spaCy's English language model
try:
    nlp = spacy.load("en_core_web_sm")
except:
    import spacy.cli
    spacy.cli.download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# Initialize conversation context storage
conversation_context = defaultdict(dict)

# Configure Wikipedia
wikipedia.set_lang("en")
wikipedia.set_rate_limiting(True)

# Enhanced response patterns with more categories
response_patterns = [
    # Greetings
    {
        "intent": "greeting",
        "patterns": ["hi", "hello", "hey", "greetings", "good morning", "good afternoon"],
        "responses": ["Hello! How can I assist you today?", "Hi there! What can I do for you?", "Greetings! How may I help?"],
        "context": "greeting"
    },
    # Goodbyes
    {
        "intent": "goodbye",
        "patterns": ["bye", "goodbye", "see you", "farewell"],
        "responses": ["Goodbye! Come back if you have more questions.", "See you later!", "Have a great day!"],
        "context": "goodbye"
    },
    # Name inquiries
    {
        "intent": "identity",
        "patterns": ["what is your name", "who are you", "your name"],
        "responses": ["I'm ChatPy, your AI assistant.", "You can call me ChatPy!", "I'm your friendly chatbot, ChatPy!"],
        "context": "identity"
    },
    # Feelings/status
    {
        "intent": "status",
        "patterns": ["how are you", "how's it going", "how do you feel"],
        "responses": ["I'm just a program, but I'm functioning well!", "I don't have feelings, but I'm here to help!", "All systems are operational!"],
        "context": "status"
    },
    # Help requests
    {
        "intent": "help",
        "patterns": ["help", "assist", "support"],
        "responses": ["I'd be happy to help. What do you need?", "How can I assist you today?", "What can I help you with?"],
        "context": "help"
    },
    # Thanks
    {
        "intent": "thanks",
        "patterns": ["thank", "thanks", "appreciate"],
        "responses": ["You're welcome!", "Happy to help!", "No problem at all!"],
        "context": "thanks"
    },
    # Time inquiries
    {
        "intent": "time",
        "patterns": ["time", "what time is it", "current time"],
        "responses": ["It's currently {time}."],
        "context": "time"
    },
    # Date inquiries
    {
        "intent": "date",
        "patterns": ["date", "today's date", "what date is it"],
        "responses": ["Today is {date}."],
        "context": "date"
    },
    # Weather inquiries
    {
        "intent": "weather",
        "patterns": ["weather", "forecast", "temperature"],
        "responses": ["I can check weather for you. What location?", "For weather info, I can help. Which city?"],
        "context": "weather"
    },
    # Jokes
    {
        "intent": "joke",
        "patterns": ["joke", "tell me a joke", "make me laugh"],
        "responses": [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Did you hear about the mathematician who's afraid of negative numbers? He'll stop at nothing to avoid them!",
            "Why don't skeletons fight each other? They don't have the guts!"
        ],
        "context": "jokes"
    },
    # AI questions
    {
        "intent": "ai",
        "patterns": ["are you ai", "are you human", "are you real"],
        "responses": ["I'm an AI chatbot created to assist you.", "I'm a computer program, but I'll do my best to help!", "I'm artificial intelligence designed to chat with you."],
        "context": "ai"
    },
    # Creator questions
    {
        "intent": "creator",
        "patterns": ["who made you", "who created you", "who built you"],
        "responses": ["I was created by a developer using Python and spaCy.", "My creator is a Python programmer who loves NLP!"],
        "context": "creator"
    },
    # Wikipedia knowledge
    {
        "intent": "knowledge",
        "patterns": ["what is", "who is", "tell me about"],
        "responses": ["I can look that up for you. What specifically would you like to know?"],
        "context": "knowledge"
    }
]

def extract_entities(text):
    """Extract named entities from text"""
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    return entities

def classify_intent(text):
    """Classify user intent based on keywords and entities"""
    doc = nlp(text.lower())
    
    # Check patterns first
    for pattern_group in response_patterns:
        for pattern in pattern_group["patterns"]:
            pattern_doc = nlp(pattern)
            similarity = doc.similarity(pattern_doc)
            if similarity > 0.7:
                return pattern_group["intent"]
    
    # Check for question words
    if any(token.text in ["who", "what", "when", "where", "why", "how"] for token in doc):
        return "question"
    
    # Check entities
    entities = extract_entities(text)
    if entities:
        for entity, label in entities:
            if label in ["GPE", "LOC"]:  # Geographical locations
                return "location_query"
            elif label == "DATE":
                return "date_query"
            elif label == "TIME":
                return "time_query"
            elif label == "PERSON":
                return "person_query"
    
    return "general"

def get_wikipedia_summary(query):
    """Get a brief summary from Wikipedia"""
    try:
        # Try to get page directly first
        try:
            return wikipedia.summary(query, sentences=2)
        except wikipedia.exceptions.DisambiguationError as e:
            # If disambiguation page, get first option
            return wikipedia.summary(e.options[0], sentences=2)
        except wikipedia.exceptions.PageError:
            # If page doesn't exist, do a search
            search_results = wikipedia.search(query)
            if search_results:
                return wikipedia.summary(search_results[0], sentences=2)
            return None
    except:
        return None

def get_contextual_response(user_input, context):
    """Generate response considering conversation context"""
    current_intent = classify_intent(user_input)
    entities = extract_entities(user_input)
    
    # Handle follow-up questions
    if context.get('last_intent') == "weather" and any(e[1] in ["GPE", "LOC"] for e in entities):
        location = next((e[0] for e in entities if e[1] in ["GPE", "LOC"]), None)
        if location:
            return f"I don't have real-time weather data, but you can check {location}'s weather on weather.com."
    
    # Handle Wikipedia knowledge requests
    if current_intent == "knowledge" or (context.get('last_intent') == "knowledge" and "yes" in user_input.lower()):
        if current_intent == "knowledge":
            query = user_input.replace("what is", "").replace("who is", "").replace("tell me about", "").strip()
            context['last_query'] = query
        else:
            query = context.get('last_query', user_input)
        
        summary = get_wikipedia_summary(query)
        if summary:
            return f"Here's what I found: {summary}"
        return f"I couldn't find information about {query}. Could you try different wording?"
    
    # Handle time/date queries
    if current_intent == "time_query":
        return f"The current time is {datetime.now().strftime('%H:%M')}."
    if current_intent == "date_query":
        return f"Today is {datetime.now().strftime('%B %d, %Y')}."
    
    # Find matching pattern group
    for pattern_group in response_patterns:
        if pattern_group["intent"] == current_intent:
            response = random.choice(pattern_group["responses"])
            
            # Format response with dynamic data
            if "{time}" in response:
                response = response.format(time=datetime.now().strftime('%H:%M'))
            if "{date}" in response:
                response = response.format(date=datetime.now().strftime('%B %d, %Y'))
            
            return response
    
    # Fallback responses
    fallbacks = [
        "I'm not sure I understand. Could you rephrase that?",
        "Interesting point. Could you elaborate?",
        "I'm still learning. Could you explain that differently?",
        "That's an interesting question. Let me think about that...",
        "I want to make sure I understand correctly. Could you say that another way?"
    ]
    return random.choice(fallbacks)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    # Initialize session if not exists
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    session_id = session['session_id']
    user_message = request.form['message']
    
    # Get conversation context
    context = conversation_context.get(session_id, {})
    
    # Simulate natural typing delay
    typing_delay = min(2.0, max(0.3, len(user_message) / 25))
    time.sleep(typing_delay)
    
    # Get bot response with context
    bot_response = get_contextual_response(user_message, context)
    
    # Update context
    conversation_context[session_id] = {
        'last_message': user_message,
        'last_response': bot_response,
        'last_intent': classify_intent(user_message),
        'timestamp': datetime.now().isoformat()
    }
    
    # Add timestamp for display
    timestamp = datetime.now().strftime("%H:%M")
    
    return jsonify({
        'user_message': user_message,
        'bot_response': bot_response,
        'timestamp': timestamp,
        'session_id': session_id
    })

if __name__ == '__main__':
    app.run(debug=True)