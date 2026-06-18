import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='.')

# --- GMAIL CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "nouamaneapp@gmail.com"
SENDER_PASSWORD = "wshn fvcm khun xbwq"  # Your secure App Password
RECEIVER_EMAIL = "nouamaneapp@gmail.com"  # Sends the data back to yourself

def send_data_email(subject, payload):
    """Sends a machine-readable email to the local broker script."""
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL
    msg['Subject'] = f"DATA_SYNC: {subject}"
    
    # Secure raw text format that the local PC script can easily extract
    body = (
        f"START_DATA\n"
        f"TYPE:{subject}\n"
        f"ACTION:{payload.get('action', '')}\n"
        f"CATEGORY:{payload.get('category', '')}\n"
        f"PRIORITY:{payload.get('priority', '')}\n"
        f"DUE_DATE:{payload.get('due_date', '')}\n"
        f"OWNER:{payload.get('owner', '')}\n"
        f"COMMENTS:{payload.get('comments', '')}\n"
        f"END_DATA"
    )
    
    msg.attach(MIMEText(body, 'plain'))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"SMTP Error: {e}")
        return False

@app.route('/')
def index():
    return render_template('Automatica.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = {
            'action': request.form.get('action'),
            'category': request.form.get('category'),
            'priority': request.form.get('priority'),
            'due_date': request.form.get('dueDate'),
            'owner': request.form.get('owner'),
            'comments': request.form.get('comments')
        }
        
        # Format due date nicely if provided
        if data['due_date']:
            dt = datetime.strptime(data['due_date'], '%Y-%m-%d')
            data['due_date'] = dt.strftime('%d/%m/%Y')

        if send_data_email("NEW_TASK", data):
            return jsonify({"status": "success", "message": "Task queued for sync successfully!"})
        else:
            return jsonify({"status": "error", "message": "Failed to forward task data."}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/complete', methods=['POST'])
def complete():
    try:
        data = {
            'action': request.form.get('action'),
            'category': request.form.get('category'),
            'priority': request.form.get('priority'),
            'due_date': request.form.get('dueDate'),
            'owner': request.form.get('owner'),
            'comments': request.form.get('comments')
        }
        
        if data['due_date']:
            dt = datetime.strptime(data['due_date'], '%Y-%m-%d')
            data['due_date'] = dt.strftime('%d/%m/%Y')

        if send_data_email("COMPLETE_TASK", data):
            return jsonify({"status": "success", "message": "Completion queued for sync successfully!"})
        else:
            return jsonify({"status": "error", "message": "Failed to forward closure data."}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)