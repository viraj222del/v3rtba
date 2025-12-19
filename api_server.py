from flask import Flask, request, jsonify
from flask_cors import CORS 
import os
import sys

# Import the core analysis function from your modified file
from git_debt_analyzer import run_analysis_and_return_data 

app = Flask(__name__)
# IMPORTANT: This allows your HTML file to fetch data from the Flask server
CORS(app) 

@app.route('/analyze', methods=['POST'])
def analyze_repo():
    """Endpoint to trigger analysis and return JSON results."""
    data = request.get_json()
    repo_url = data.get('repo_url')
    
    if not repo_url:
        return jsonify({"error": "Missing repo_url"}), 400
        
    try:
        # Run the core analysis and get the JSON data back
        print(f"API Request: Starting analysis for: {repo_url}", file=sys.stderr)
        results = run_analysis_and_return_data(repo_url)
        
        # Flask automatically serializes the dictionary to JSON
        return jsonify(results) 
    except Exception as e:
        # This catches exceptions from run_analysis_and_return_data
        print(f"API Error: Analysis failed for {repo_url}. {e}", file=sys.stderr)
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

@app.route('/', methods=['GET'])
def home():
    """Simple status check."""
    return "Git Debt Analyzer API is running on Port 5000. Send POST request with repo_url to /analyze"

if __name__ == '__main__':
    # Ensure you have 'pip install flask flask-cors'
    app.run(host='0.0.0.0', port=5000, debug=True)