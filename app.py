import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# Internal memory storage queues to hold tasks until your PC grabs them
DATA_QUEUES = {
    "NEW_TASK": [],
    "COMPLETE_TASK": []
}

@app.route('/')
def index():
    return render_template('Automatica.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        # Accept JSON payload from your updated Automatica.html script
        form_data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Clean up and format the due date
        due_date = form_data.get('dueDate', '')
        if due_date and '-' in due_date:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            
        req_date = form_data.get('requestDate', datetime.today().strftime('%d/%m/%Y'))

        task_payload = {
            "project": form_data.get('project', ''),
            "institution": form_data.get('institution', ''),
            "contacts": form_data.get('contacts', ''),
            "action": form_data.get('action', ''),
            "category": form_data.get('category', ''),
            "priority": form_data.get('priority', ''),
            "due_date": due_date,
            "request_date": req_date,
            "owner": form_data.get('owner', ''),
            "notes": form_data.get('comments', ''),
            "target_sheet": form_data.get('targetSheet', '')
        }
        
        DATA_QUEUES["NEW_TASK"].append(task_payload)
        return jsonify({"status": "success", "message": "Task queued successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/complete', methods=['POST'])
def complete():
    try:
        form_data = request.get_json() if request.is_json else request.form.to_dict()
        
        closure_payload = {
            "action": form_data.get('action', ''),
            "backend_row_index": form_data.get('backend_row_index', '')
        }
        
        DATA_QUEUES["COMPLETE_TASK"].append(closure_payload)
        return jsonify({"status": "success", "message": "Task completion queued!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Secure Endpoint for your PC script to grab data via standard web browsing traffic (Port 443)
@app.route('/sync-pull', methods=['GET'])
def sync_pull():
    return jsonify(DATA_QUEUES)

# Secure Endpoint for your PC script to clear the cloud memory once saved to Excel
@app.route('/sync-clear', methods=['POST'])
def sync_clear():
    global DATA_QUEUES
    DATA_QUEUES = {"NEW_TASK": [], "COMPLETE_TASK": []}
    return jsonify({"status": "success", "message": "Cloud queue flushed."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)