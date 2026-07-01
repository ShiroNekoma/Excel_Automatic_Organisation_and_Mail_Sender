import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# System data queues holding synchronization records, active view states, and image uploads
DATA_QUEUES = {
    "NEW_TASK": [],
    "COMPLETE_TASK": [],
    "NEW_CARD": []
}

ACTIVE_EXCEL_TASKS = []
FINISHED_EXCEL_TASKS = []

@app.route('/')
def index():
    return render_template('Automatica.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        form_data = request.get_json() if request.is_json else request.form.to_dict()
        
        due_date = form_data.get('due_date', '')
        if due_date and '-' in due_date:
            due_date = datetime.strptime(due_date, '%Y-%m-%d').strftime('%d/%m/%Y')
            
        req_date = form_data.get('request_date', datetime.today().strftime('%Y-%m-%d'))
        if req_date and '-' in req_date:
            req_date = datetime.strptime(req_date, '%Y-%m-%d').strftime('%d/%m/%Y')

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
        closure_payload = {"backend_row_index": form_data.get('backend_row_index', '')}
        DATA_QUEUES["COMPLETE_TASK"].append(closure_payload)
        return jsonify({"status": "success", "message": "Task completion queued!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload-card', methods=['POST'])
def upload_card():
    try:
        data = request.get_json()
        DATA_QUEUES["NEW_CARD"].append({
            "filename": data.get('filename', f"card_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"),
            "image_data": data.get('image_data', '')
        })
        return jsonify({"status": "success", "message": "Business card queued for local download!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/tasks', methods=['GET'])
def get_dashboard_tasks():
    # Return both active and recently finished tasks for the dashboard
    return jsonify({
        "active": ACTIVE_EXCEL_TASKS,
        "finished": FINISHED_EXCEL_TASKS
    })

@app.route('/sync-pull', methods=['GET'])
def sync_pull():
    return jsonify(DATA_QUEUES)

@app.route('/sync-clear', methods=['POST'])
def sync_clear():
    global DATA_QUEUES, ACTIVE_EXCEL_TASKS, FINISHED_EXCEL_TASKS
    incoming_payload = request.get_json() or {}
    
    if "active_tasks" in incoming_payload:
        ACTIVE_EXCEL_TASKS = incoming_payload["active_tasks"]
    if "finished_tasks" in incoming_payload:
        FINISHED_EXCEL_TASKS = incoming_payload["finished_tasks"]
        
    DATA_QUEUES = {"NEW_TASK": [], "COMPLETE_TASK": [], "NEW_CARD": []}
    return jsonify({"status": "success", "message": "Cloud arrays updated and flushed cleanly."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)