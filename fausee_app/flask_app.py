from flask import Flask, render_template, request, redirect, url_for, session
from db_manager import DBManager

app = Flask(__name__)
app.secret_key = "replace_with_a_strong_secret_key"
db_manager = DBManager()

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    user = db_manager.get_user()
    if not user:
        return redirect(url_for('register'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if db_manager.verify_user(username, password):
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('success'))
        else:
            return render_template('login.html', error="Invalid username or password.")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if username and password:
            db_manager.create_or_replace_user(username, password)
            return redirect(url_for('login'))
        return render_template('register.html', error="Please enter both username and password.")
    return render_template('register.html')

@app.route('/success')
def success():
    return render_template('success.html')
