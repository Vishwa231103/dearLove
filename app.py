from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///matchmaker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'a-very-secure-secret-key-2025-matchmaker'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    hobbies = db.Column(db.String(200), nullable=False)
    tastes = db.Column(db.String(200), nullable=False)
    nature = db.Column(db.String(200), nullable=False)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.name}>'

# Define Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f'<Message {self.sender_id} to {self.recipient_id}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Initialize database with error handling
def init_db():
    try:
        with app.app_context():
            db.create_all()
            print("Database tables created successfully!")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        raise

def calculate_compatibility(user1, user2):
    hobbies1 = [h.strip().lower() for h in user1.hobbies.split(',')]
    hobbies2 = [h.strip().lower() for h in user2.hobbies.split(',')]
    tastes1 = [t.strip().lower() for t in user1.tastes.split(',')]
    tastes2 = [t.strip().lower() for t in user2.tastes.split(',')]
    nature1 = [n.strip().lower() for n in user1.nature.split(',')]
    nature2 = [n.strip().lower() for n in user2.nature.split(',')]

    # Weighted scoring: hobbies (40%), tastes (30%), nature (30%)
    hobby_matches = len(set(hobbies1).intersection(hobbies2)) * 0.4
    taste_matches = len(set(tastes1).intersection(tastes2)) * 0.3
    nature_matches = len(set(nature1).intersection(nature2)) * 0.3

    # Normalize to percentage (assuming max 5 matches per category)
    max_score = (5 * 0.4) + (5 * 0.3) + (5 * 0.3)  # 2 + 1.5 + 1.5 = 5
    total_score = hobby_matches + taste_matches + nature_matches
    compatibility = (total_score / max_score) * 100
    return round(min(compatibility, 100), 2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('matches'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        gender = request.form.get('gender', '').strip()
        hobbies = request.form.get('hobbies', '').strip()
        tastes = request.form.get('tastes', '').strip()
        nature = request.form.get('nature', '').strip()

        # Input validation
        if not all([name, email, password, gender, hobbies, tastes, nature]):
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect(url_for('register'))
        if '@' not in email or '.' not in email:
            flash('Invalid email address.', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))

        try:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(name=name, email=email, password=hashed_password, gender=gender,
                            hobbies=hobbies, tastes=tastes, nature=nature)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Registration successful! Welcome to MatchMaker.', 'success')
            return redirect(url_for('matches'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering user: {str(e)}', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('matches'))  # Reverted redirect to /matches
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Email and password are required.', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('matches'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/matches')
@login_required
def matches():
    all_users = User.query.filter(User.id != current_user.id).all()
    matches = []

    for other_user in all_users:
        compatibility = calculate_compatibility(current_user, other_user)
        matches.append({
            'id': other_user.id,
            'name': other_user.name,
            'gender': other_user.gender,
            'hobbies': other_user.hobbies,
            'tastes': other_user.tastes,
            'nature': other_user.nature,
            'compatibility': compatibility
        })

    matches.sort(key=lambda x: x['compatibility'], reverse=True)
    return render_template('matches.html', current_user=current_user, matches=matches)

@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    user = User.query.get_or_404(user_id)
    compatibility = calculate_compatibility(current_user, user) if user.id != current_user.id else None
    return render_template('profile.html', user=user, compatibility=compatibility)

@app.route('/chat/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def chat(recipient_id):
    recipient = User.query.get_or_404(recipient_id)
    if recipient.id == current_user.id:
        flash('You cannot chat with yourself.', 'error')
        return redirect(url_for('matches'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Message cannot be empty.', 'error')
            return redirect(url_for('chat', recipient_id=recipient_id))
        if len(content) > 500:
            flash('Message is too long (max 500 characters).', 'error')
            return redirect(url_for('chat', recipient_id=recipient_id))

        try:
            message = Message(sender_id=current_user.id, recipient_id=recipient_id, content=content)
            db.session.add(message)
            db.session.commit()
            flash('Message sent!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error sending message: {str(e)}', 'error')
        return redirect(url_for('chat', recipient_id=recipient_id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == recipient_id)) |
        ((Message.sender_id == recipient_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', recipient=recipient, messages=messages, recipient_id=recipient_id)

@app.route('/debug/users')
def debug_users():
    users = User.query.all()
    return render_template('debug_users.html', users=users)

if __name__ == '__main__':
    init_db()  # Initialize database
    app.run(debug=True, host='0.0.0.0', port=5000)