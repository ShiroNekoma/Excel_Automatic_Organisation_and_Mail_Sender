import os
import io
import uuid
import json
import time
import base64
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__, template_folder='.')

# System data queues holding synchronization records, active view states, and image uploads
DATA_QUEUES = {
    "NEW_TASK": [],
    "COMPLETE_TASK": [],
    "NEW_CARD": [],
    "NEW_REPORT_REQ": []
}

ACTIVE_EXCEL_TASKS = []
FINISHED_EXCEL_TASKS = []

GENERATED_REPORTS = {}
REPORT_FILES = {}

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
            target_sheet = form_data.get('custom_sheet_name', 'BackEnd')

        task_record = {
            "project": form_data.get('project', ''),
            "institution": form_data.get('institution', ''),
            "contact": form_data.get('contacts', ''),
            "action": form_data.get('action', ''),
            "category": form_data.get('category', ''),
            "priority": form_data.get('priority', 'Medium'),
            "request_date": req_date,
            "due_date": due_date,
            "owner": form_data.get('owner', ''),
            "notes": form_data.get('notes', ''),
            "sheet": target_sheet
        }

        DATA_QUEUES["NEW_TASK"].append(task_record)
        return jsonify({"status": "success", "message": "Task successfully queued to sync!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/complete', methods=['POST'])
def complete_task():
    try:
        data = request.get_json() or {}
        row_index = data.get('backend_row_index')
        if row_index is not None:
            DATA_QUEUES["COMPLETE_TASK"].append({
                "backend_row_index": int(row_index)
            })
            return jsonify({"status": "success", "message": "Task queued for completion sync."})
        return jsonify({"status": "error", "message": "Missing backend row index reference."}), 400
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

    # Safely clear items that have been handled by local client
    processed_tasks = incoming_payload.get("processed_new_tasks", [])
    DATA_QUEUES["NEW_TASK"] = [t for t in DATA_QUEUES["NEW_TASK"] if t not in processed_tasks]
    
    processed_complete = incoming_payload.get("processed_complete_tasks", [])
    DATA_QUEUES["COMPLETE_TASK"] = [t for t in DATA_QUEUES["COMPLETE_TASK"] if t not in processed_complete]
    
    processed_cards = incoming_payload.get("processed_cards", [])
    DATA_QUEUES["NEW_CARD"] = [c for c in DATA_QUEUES["NEW_CARD"] if c.get('filename') not in processed_cards]
    
    processed_reports = incoming_payload.get("processed_reports", [])
    DATA_QUEUES["NEW_REPORT_REQ"] = [r for r in DATA_QUEUES["NEW_REPORT_REQ"] if r.get('report_id') not in processed_reports]

    return jsonify({"status": "success", "message": "Global registers synchronized."})

@app.route('/generate-report', methods=['POST'])
def generate_report():
    data = request.get_json() or {}
    period = data.get('period', 'weekly')

    report_id = uuid.uuid4().hex
    GENERATED_REPORTS[report_id] = {"status": "pending", "created_at": time.time()}

    # Send report request variables down to the local worker queue. This
    # endpoint no longer blocks the Flask worker thread waiting for the local
    # PC to respond — it just enqueues the request and returns immediately.
    # The frontend polls /report-status/<report_id> until it's ready. This
    # also avoids the single-threaded dev server deadlocking itself (the
    # local worker's own /sync-pull and /respond-report calls could never be
    # served while this handler was busy sleeping for up to 2 minutes).
    DATA_QUEUES["NEW_REPORT_REQ"].append({
        "report_id": report_id,
        "period": period,
        "active_tasks": ACTIVE_EXCEL_TASKS,
        "finished_tasks": FINISHED_EXCEL_TASKS
    })

    return jsonify({"status": "queued", "report_id": report_id})

@app.route('/report-status/<report_id>', methods=['GET'])
def report_status(report_id):
    entry = GENERATED_REPORTS.get(report_id)
    if entry is None:
        return jsonify({"status": "error", "message": "Unknown report_id (it may have already expired)."}), 404

    if entry.get("status") == "pending":
        # Give up waiting on the local worker after 3 minutes so the
        # frontend doesn't poll forever if mail_reader.py isn't running.
        if time.time() - entry.get("created_at", 0) > 180:
            GENERATED_REPORTS.pop(report_id, None)
            return jsonify({
                "status": "error",
                "message": "Failed to connect to local Llama 3 via pipeline. Ensure mail_reader.py and Ollama are active on your local machine."
            }), 500
        return jsonify({"status": "pending"})

    report_data = GENERATED_REPORTS.pop(report_id)
    return jsonify({
        "status": "success",
        "html": report_data["html"],
        "file_id": report_id
    })

@app.route('/respond-report', methods=['POST'])
def respond_report():
    data = request.get_json() or {}
    report_id = data.get('report_id')
    html_content = data.get('html', '')
    excel_base64 = data.get('excel_base64', '')

    if not report_id:
        return jsonify({"status": "error", "message": "Missing report_id"}), 400

    GENERATED_REPORTS[report_id] = {"status": "ready", "html": html_content.strip()}
    if excel_base64:
        REPORT_FILES[report_id] = base64.b64decode(excel_base64)

    return jsonify({"status": "success", "message": "Report instance loaded successfully."})

@app.route('/download-report/<file_id>')
def download_report(file_id):
    if file_id in REPORT_FILES:
        return send_file(
            io.BytesIO(REPORT_FILES[file_id]), 
            download_name=f"Tasks_Report_{datetime.today().strftime('%Y%m%d')}.xlsx",
            as_attachment=True
        )
    return "Report file data instance expired or not found.", 404

if __name__ == '__main__':
    # threaded=True is important: without it, this dev server handles one
    # request at a time, which previously caused the report feature to
    # deadlock itself (see /generate-report above).
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)