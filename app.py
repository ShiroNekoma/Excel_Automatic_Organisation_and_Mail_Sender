import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# System data queues holding synchronization records and active view states
DATA_QUEUES = {
    "NEW_TASK": [],
    "COMPLETE_TASK": []
}
ACTIVE_EXCEL_TASKS = []

@app.route('/')
def index():
    return render_template('Automatica.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        form_data = request.get_json() if request.is_json else request.form.to_dict()
        
        # Parse and standardize formatting rules
        due_date = form_data.get('due_date', '')
        if due_date and '-' in due_date:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            
        req_date = form_data.get('request_date', datetime.today().strftime('%Y-%m-%d'))
        if req_date and '-' in req_date:
            req_date = datetime.strptime(req_date, '%Y-%m-%d').strftime('%d/%m/%Y')

        # Map frontend names to backend payload structure
        target_sheet = form_data.get('sheet_select', 'BackEnd')
        if target_sheet == 'Other':
            target_sheet = form_data.get('custom_sheet', 'CustomTab')

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
            "notes": form_data.get('notes', ''),
            "target_sheet": target_sheet
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
            "backend_row_index": form_data.get('backend_row_index', '')
        }
        
        DATA_QUEUES["COMPLETE_TASK"].append(closure_payload)
        return jsonify({"status": "success", "message": "Task completion queued!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Endpoint for HTML layout script to look up live active rows
@app.route('/tasks', methods=['GET'])
def get_dashboard_tasks():
    return jsonify(ACTIVE_EXCEL_TASKS)

# Endpoint for your local machine script to fetch submission operations
@app.route('/sync-pull', methods=['GET'])
def sync_pull():
    return jsonify(DATA_QUEUES)

# Endpoint for your local script to push active spreadsheet records back up to the web dashboard
@app.route('/sync-clear', methods=['POST'])
def sync_clear():
    global DATA_QUEUES, ACTIVE_EXCEL_TASKS
    
    incoming_payload = request.get_json() or {}
    # Retain the latest state of active items from Excel inside cloud memory
    if "active_tasks" in incoming_payload:
        ACTIVE_EXCEL_TASKS = incoming_payload["active_tasks"]
        
    DATA_QUEUES = {"NEW_TASK": [], "COMPLETE_TASK": []}
    return jsonify({"status": "success", "message": "Cloud arrays updated and flushed cleanly."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)