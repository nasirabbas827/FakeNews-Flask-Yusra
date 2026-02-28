from datetime import datetime
import os
import json

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session,
    send_file, send_from_directory
)
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO

# ────────────────────────────────────────────────
# Project Imports (your custom modules)
# ────────────────────────────────────────────────
from model_training import run_ai_model, train_model

# ────────────────────────────────────────────────
# Flask Application Setup & Configuration
# ────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL Configuration
app.config['MYSQL_HOST']     = 'localhost'
app.config['MYSQL_USER']     = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB']       = 'fakenews_db'
mysql = MySQL(app)

# File Upload Folders & Allowed Extensions
UPLOAD_FOLDER = 'static/uploads'
DATASET_FOLDER = 'static/datasets'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATASET_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER']   = UPLOAD_FOLDER
app.config['DATASET_FOLDER']  = DATASET_FOLDER

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_DATASET_EXTENSIONS = {'csv', 'xlsx', 'json', 'txt'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_dataset(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DATASET_EXTENSIONS


# ────────────────────────────────────────────────
# Helper Routes & General Pages
# ────────────────────────────────────────────────

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


# ────────────────────────────────────────────────
# Admin Authentication
# ────────────────────────────────────────────────

@app.route('/adminlogin', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM admin WHERE username = %s AND password = %s', (username, password))
        admin = cur.fetchone()
        cur.close()
        
        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = 'Invalid credentials. Please try again.'
    
    return render_template('admin_login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


# ────────────────────────────────────────────────
# User Authentication
# ────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                    (username, email, password))
        mysql.connection.commit()
        cur.close()
        
        flash('Registration successful. You can now login.', 'success')
        return redirect(url_for('user_login'))
    
    return render_template('register.html')


@app.route('/user/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cur.fetchone()
        cur.close()
        
        if user:
            session['user_id']   = user[0]
            session['username']  = user[1]
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    
    return render_template('login.html')


@app.route('/user/logout')
def user_logout():
    session.clear()
    return redirect(url_for('index'))


# ────────────────────────────────────────────────
# User Area – Dashboard & Analysis
# ────────────────────────────────────────────────

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    username = session.get('username')

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, dataset_name FROM datasets ORDER BY uploaded_at DESC")
    datasets = cur.fetchall()
    cur.close()

    return render_template('dashboard.html', username=username, datasets=datasets)


@app.route('/analyze-news', methods=['POST'])
def analyze_news():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    title   = request.form.get('title')
    content = request.form.get('content')

    if not content:
        flash("Content is required", "danger")
        return redirect(url_for('dashboard'))

    cur = mysql.connection.cursor()

    # Save article
    cur.execute("""
        INSERT INTO news_articles (user_id, title, content)
        VALUES (%s, %s, %s)
    """, (user_id, title, content))
    mysql.connection.commit()

    article_id = cur.lastrowid

    # AI Prediction
    prediction, confidence = run_ai_model(content)

    # Save result
    cur.execute("""
        INSERT INTO analysis_results 
        (article_id, prediction, confidence_score, model_version)
        VALUES (%s, %s, %s, %s)
    """, (article_id, prediction, confidence, "V3.2"))

    mysql.connection.commit()
    cur.close()

    flash("Article analyzed successfully", "success")
    return redirect(url_for('analysis_history'))


@app.route('/analysis-history')
def analysis_history():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT n.id, n.title, a.prediction, a.confidence_score, a.analyzed_at
        FROM news_articles n
        JOIN analysis_results a ON n.id = a.article_id
        WHERE n.user_id = %s
        ORDER BY a.analyzed_at DESC
    """, (user_id,))
    history = cur.fetchall()
    cur.close()

    return render_template('analysis_history.html', history=history)


# ────────────────────────────────────────────────
# User Profile Management
# ────────────────────────────────────────────────

@app.route('/view_profile')
def view_profile():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT username, password, first_name, last_name, email, profile_picture 
        FROM users WHERE id = %s
    """, (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    
    if user:
        user_data = {
            'username':       user[0],
            'password':       user[1],
            'first_name':     user[2],
            'last_name':      user[3],
            'email':          user[4],
            'profile_picture': user[5].replace('\\', '/') if user[5] else None
        }
        return render_template('view_profile.html', user=user_data)
    
    flash('User not found', 'error')
    return redirect(url_for('dashboard'))


@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name  = request.form['last_name']
        email      = request.form['email']
        password   = request.form['password']

        profile_picture = None
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                profile_picture = file_path.replace('\\', '/')

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE users 
            SET first_name=%s, last_name=%s, email=%s, password=%s, profile_picture=%s 
            WHERE id=%s
        """, (first_name, last_name, email, password, profile_picture, session['user_id']))
        mysql.connection.commit()
        cur.close()

        flash('Profile updated successfully!', 'success')
        return redirect(url_for('view_profile'))

    return render_template('update_profile.html')


# ────────────────────────────────────────────────
# User Exports
# ────────────────────────────────────────────────

@app.route('/export/history/excel')
def export_history_excel():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT n.title, a.prediction, a.confidence_score, a.analyzed_at
        FROM news_articles n
        JOIN analysis_results a ON n.id = a.article_id
        WHERE n.user_id = %s
        ORDER BY a.analyzed_at DESC
    """, (user_id,))
    history = cur.fetchall()
    cur.close()

    df = pd.DataFrame(history, columns=['Title', 'Prediction', 'Confidence', 'Date'])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Analysis History')
    output.seek(0)
    return send_file(output, download_name='analysis_history.xlsx', as_attachment=True)


@app.route('/user/download-dataset/<int:dataset_id>')
def download_dataset(dataset_id):
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT dataset_file FROM datasets WHERE id=%s", (dataset_id,))
    data = cur.fetchone()
    cur.close()

    if not data or not data[0]:
        flash("Dataset not found.", "danger")
        return redirect(url_for('dashboard'))

    filename = data[0]
    return send_from_directory(
        directory=app.config['DATASET_FOLDER'],
        path=filename,
        as_attachment=True
    )


# ────────────────────────────────────────────────
# Admin Dashboard & Statistics
# ────────────────────────────────────────────────

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # Quick stats
    cur.execute("SELECT COUNT(*) FROM news_articles")
    total_articles = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM analysis_results WHERE prediction = 'FAKE'")
    fake_count = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0] or 0

    # Articles per user (top 10) – Bar chart
    cur.execute("""
        SELECT u.username, COUNT(n.id) as article_count
        FROM users u
        LEFT JOIN news_articles n ON u.id = n.user_id
        GROUP BY u.id, u.username
        ORDER BY article_count DESC
        LIMIT 10
    """)
    articles_per_user_rows = cur.fetchall() or []

    articles_chart = {
        "data": [{
            "x": [row[0] if row[0] else "Unknown" for row in articles_per_user_rows],
            "y": [int(row[1]) for row in articles_per_user_rows],
            "type": "bar",
            "marker": {"color": "#3b82f6"},
            "text": [str(int(y)) for y in [row[1] for row in articles_per_user_rows]],
            "textposition": "auto"
        }],
        "layout": {
            "title": "",
            "xaxis": {"title": "Users", "tickangle": -30},
            "yaxis": {"title": "Articles"},
            "margin": {"t": 30, "b": 100, "l": 60, "r": 30},
            "height": 400,
            "plot_bgcolor": "#f8fafc",
            "paper_bgcolor": "#ffffff"
        }
    }

    # Model performance history – Line chart
    cur.execute("""
        SELECT trained_at, accuracy, f1_score
        FROM model_training_logs
        ORDER BY trained_at ASC
        LIMIT 20
    """)
    training_rows = cur.fetchall() or []

    performance_chart = {
        "data": [
            {
                "x": [row[0].strftime("%Y-%m-%d %H:%M") if row[0] else "" for row in training_rows],
                "y": [float(row[1]) if row[1] is not None else 0 for row in training_rows],
                "type": "scatter",
                "mode": "lines+markers",
                "name": "Accuracy",
                "line": {"color": "#10b981", "width": 2.5},
                "marker": {"size": 8}
            },
            {
                "x": [row[0].strftime("%Y-%m-%d %H:%M") if row[0] else "" for row in training_rows],
                "y": [float(row[2]) if row[2] is not None else 0 for row in training_rows],
                "type": "scatter",
                "mode": "lines+markers",
                "name": "F1 Score",
                "line": {"color": "#8b5cf6", "width": 2.5},
                "marker": {"size": 8}
            }
        ],
        "layout": {
            "title": "",
            "xaxis": {"title": "Training Date"},
            "yaxis": {"title": "Score (%)", "range": [0, 110]},
            "legend": {"orientation": "h", "y": 1.15, "x": 0.5, "xanchor": "center"},
            "margin": {"t": 60, "b": 80, "l": 60, "r": 30},
            "height": 400,
            "plot_bgcolor": "#f8fafc",
            "paper_bgcolor": "#ffffff",
            "hovermode": "x unified"
        }
    }

    if not training_rows:
        performance_chart["layout"]["annotations"] = [{
            "text": "No model training history yet",
            "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.5,
            "showarrow": False,
            "font": {"size": 18, "color": "#6b7280"}
        }]

    # Recent fake articles
    cur.execute("""
        SELECT 
            a.id AS analysis_id,
            a.article_id,
            n.title,
            n.submitted_at,
            a.confidence_score,
            u.username,
            a.analyzed_at
        FROM analysis_results a
        JOIN news_articles n ON a.article_id = n.id
        LEFT JOIN users u ON n.user_id = u.id
        WHERE a.prediction = 'FAKE'
        ORDER BY a.analyzed_at DESC
        LIMIT 12
    """)
    recent_fakes_raw = cur.fetchall() or []

    recent_fakes = []
    for row in recent_fakes_raw:
        recent_fakes.append({
            'analysis_id': row[0],
            'article_id': row[1],
            'title': row[2],
            'submitted_at': row[3],
            'confidence_score': row[4],
            'username': row[5],
            'analyzed_at': row[6]
        })

    cur.close()

    return render_template(
        'admin/admin_dashboard.html',
        total_articles=total_articles,
        fake_count=fake_count,
        total_users=total_users,
        articles_per_user_json=json.dumps(articles_chart),
        model_performance_json=json.dumps(performance_chart),
        recent_fakes=recent_fakes
    )


# ────────────────────────────────────────────────
# Admin – Users Management
# ────────────────────────────────────────────────

@app.route('/admin/users')
def admin_users():
    if 'admin_logged_in' not in session or not session['admin_logged_in']:
        flash('Please login as admin first', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT id, username, email, first_name, last_name, profile_picture
        FROM users
    """)
    users = cur.fetchall()
    cur.close()

    return render_template('admin/admin_users.html', users=users)


# ────────────────────────────────────────────────
# Admin – Datasets Management
# ────────────────────────────────────────────────

@app.route('/admin/datasets', methods=['GET', 'POST'])
def admin_datasets():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        dataset_id   = request.form.get('dataset_id')
        dataset_name = request.form['dataset_name']
        file         = request.files.get('dataset_file')

        if dataset_id:  # Update
            if file and allowed_dataset(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['DATASET_FOLDER'], filename))
                cur.execute("""
                    UPDATE datasets 
                    SET dataset_name=%s, dataset_file=%s
                    WHERE id=%s
                """, (dataset_name, filename, dataset_id))
            else:
                cur.execute("""
                    UPDATE datasets 
                    SET dataset_name=%s
                    WHERE id=%s
                """, (dataset_name, dataset_id))
            mysql.connection.commit()
            flash("Dataset updated successfully", "success")

        else:  # Add new
            if file and allowed_dataset(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['DATASET_FOLDER'], filename))
                cur.execute("""
                    INSERT INTO datasets (dataset_name, dataset_file)
                    VALUES (%s, %s)
                """, (dataset_name, filename))
                mysql.connection.commit()
                flash("Dataset added successfully", "success")
            else:
                flash("Invalid file format", "danger")

    # Delete
    delete_id = request.args.get('delete')
    if delete_id:
        cur.execute("DELETE FROM datasets WHERE id=%s", (delete_id,))
        mysql.connection.commit()
        flash("Dataset deleted successfully", "danger")
        return redirect(url_for('admin_datasets'))

    # List all
    cur.execute("SELECT * FROM datasets ORDER BY uploaded_at DESC")
    datasets = cur.fetchall()
    cur.close()

    return render_template("admin/admin_datasets.html", datasets=datasets)


# ────────────────────────────────────────────────
# Admin – Model Training & Logs
# ────────────────────────────────────────────────

@app.route('/admin/train/<int:dataset_id>')
def train_dataset(dataset_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT dataset_file FROM datasets WHERE id=%s", (dataset_id,))
    data = cur.fetchone()

    if not data:
        flash("Dataset not found", "danger")
        return redirect(url_for('admin_datasets'))

    dataset_path = os.path.join(app.config['DATASET_FOLDER'], data[0])

    accuracy, precision, recall, f1 = train_model(dataset_path)

    cur.execute("""
        INSERT INTO model_training_logs
        (dataset_id, accuracy, precision_score, recall_score, f1_score)
        VALUES (%s, %s, %s, %s, %s)
    """, (dataset_id, accuracy, precision, recall, f1))
    mysql.connection.commit()
    cur.close()

    flash("Model retrained successfully", "success")
    return redirect(url_for('training_logs'))


@app.route('/admin/training-logs')
def training_logs():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT m.id, d.dataset_name,
               m.accuracy, m.precision_score, m.recall_score, m.f1_score,
               m.trained_at
        FROM model_training_logs m
        LEFT JOIN datasets d ON m.dataset_id = d.id
        ORDER BY m.trained_at DESC
    """)
    logs = cur.fetchall()
    cur.close()

    return render_template('admin/training_logs.html', logs=logs)


@app.route('/admin/delete-training-log/<int:log_id>')
def delete_training_log(log_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM model_training_logs WHERE id=%s", (log_id,))
    mysql.connection.commit()
    cur.close()

    flash("Training log deleted successfully", "danger")
    return redirect(url_for('training_logs'))


# ────────────────────────────────────────────────
# Admin – Analysis History & Reports
# ────────────────────────────────────────────────

@app.route('/admin/analysis-history')
def admin_analysis_history():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT a.id, u.username, n.title, a.prediction, a.confidence_score, a.analyzed_at
        FROM analysis_results a
        JOIN news_articles n ON a.article_id = n.id
        JOIN users u ON n.user_id = u.id
        ORDER BY a.analyzed_at DESC
    """)
    history = cur.fetchall()
    cur.close()

    total_articles = len(history)
    total_real = sum(1 for h in history if h[3] == 'Real')
    total_fake = sum(1 for h in history if h[3] == 'Fake')

    return render_template(
        'admin/admin_analysis_history.html',
        history=history,
        total_articles=total_articles,
        total_real=total_real,
        total_fake=total_fake
    )


@app.route('/admin/delete-analysis/<int:analysis_id>')
def delete_analysis(analysis_id):
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM analysis_results WHERE id=%s", (analysis_id,))
    mysql.connection.commit()
    cur.close()

    flash('Analysis record deleted successfully!', 'success')
    return redirect(url_for('admin_analysis_history'))


@app.route('/admin/export/analysis/excel')
def export_analysis_excel():
    if 'admin_logged_in' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT u.username, n.title, a.prediction, a.confidence_score, a.analyzed_at
        FROM analysis_results a
        JOIN news_articles n ON a.article_id = n.id
        JOIN users u ON n.user_id = u.id
        ORDER BY a.analyzed_at DESC
    """)
    history = cur.fetchall()
    cur.close()

    df = pd.DataFrame(history, columns=['Username', 'Title', 'Prediction', 'Confidence', 'Date'])
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Analysis History')
    output.seek(0)
    return send_file(output, download_name='system_usage_report.xlsx', as_attachment=True)


# ────────────────────────────────────────────────
# Run Application
# ────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=True)