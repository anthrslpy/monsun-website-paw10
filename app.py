from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'monsun-secret-key-ganti-ini-nanti'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///monsun.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# MODELS

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    novels = db.relationship('Novel', backref='author', lazy=True)

class Novel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    genre = db.Column(db.String(100), nullable=False)
    cover_color = db.Column(db.String(20), default='#95B7FF')  
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    chapters = db.relationship('Chapter', backref='novel', lazy=True, cascade='all, delete-orphan', order_by='Chapter.chapter_number')

class Chapter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey('novel.id'), nullable=False)
    chapter_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Untuk cek apakah sudah login

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Kamu harus login dulu!', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


# AUTH ROUTES

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        identifier = request.form.get('username') 
        password = request.form.get('password')

        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect username/email or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([full_name, email, username, password]):
            flash('All fields are required!', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long!', 'error')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email is already in use!', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username is already in use!', 'error')
            return render_template('register.html')

        new_user = User(
            full_name=full_name,
            email=email,
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# DASHBOARD!

@app.route('/')
@app.route('/dashboard')
def dashboard():
    current_user = get_current_user()
    novels = Novel.query.order_by(Novel.updated_at.desc()).all()
    
    # novel terpopuler = novel dengan chapter terbanyak ajaH..
    popular_novels = Novel.query.join(Chapter).group_by(Novel.id).order_by(
        db.func.count(Chapter.id).desc()
    ).limit(5).all()
    
    if not popular_novels:
        popular_novels = Novel.query.order_by(Novel.created_at.desc()).limit(5).all()

    trending = novels[0] if novels else None

    return render_template('dashboard.html',
        current_user=current_user,
        novels=novels,
        popular_novels=popular_novels,
        trending=trending
    )


# NOVEL ROUTES

@app.route('/novel/<int:novel_id>')
def novel_detail(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    current_user = get_current_user()
    is_author = current_user and current_user.id == novel.author_id
    
    return render_template('novel_detail.html',
        novel=novel,
        current_user=current_user,
        is_author=is_author
    )

# CREATE NOVEL
@app.route('/novel/create', methods=['GET', 'POST'])
@login_required
def create_novel():
    current_user = get_current_user()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        genre = request.form.get('genre', '').strip()
        cover_color = request.form.get('cover_color', '#95B7FF')

        if not all([title, description, genre]):
            flash('Title, description, and genre are required!', 'error')
            return render_template('create_novel.html', current_user=current_user)

        novel = Novel(
            title=title,
            description=description,
            genre=genre,
            cover_color=cover_color,
            author_id=current_user.id
        )
        db.session.add(novel)
        db.session.commit()
        flash(f'Novel "{title}" created successfully!', 'success')
        return redirect(url_for('novel_detail', novel_id=novel.id))

    return render_template('create_novel.html', current_user=current_user)

# EDIT NOVEL
@app.route('/novel/<int:novel_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    current_user = get_current_user()

    if novel.author_id != current_user.id:
        flash('You do not have permission to edit this novel!', 'error')
        return redirect(url_for('novel_detail', novel_id=novel_id))

    if request.method == 'POST':
        novel.title = request.form.get('title', '').strip()
        novel.description = request.form.get('description', '').strip()
        novel.genre = request.form.get('genre', '').strip()
        novel.cover_color = request.form.get('cover_color', novel.cover_color)
        novel.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Novel updated successfully!', 'success')
        return redirect(url_for('novel_detail', novel_id=novel_id))

    return render_template('edit_novel.html', novel=novel, current_user=current_user)

# DELETE NOVEL
@app.route('/novel/<int:novel_id>/delete', methods=['POST'])
@login_required
def delete_novel(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    current_user = get_current_user()

    if novel.author_id != current_user.id:
        flash('You do not have permission to delete this novel!', 'error')
        return redirect(url_for('novel_detail', novel_id=novel_id))

    title = novel.title
    db.session.delete(novel)
    db.session.commit()
    flash(f'Novel "{title}" deleted successfully.', 'success')
    return redirect(url_for('dashboard'))


# CHAPTER ROUTES

@app.route('/novel/<int:novel_id>/chapter/<int:chapter_number>')
def read_chapter(novel_id, chapter_number):
    novel = Novel.query.get_or_404(novel_id)
    chapter = Chapter.query.filter_by(novel_id=novel_id, chapter_number=chapter_number).first_or_404()
    current_user = get_current_user()
    is_author = current_user and current_user.id == novel.author_id

    # navigasi prev n next chapternyah
    prev_chapter = Chapter.query.filter_by(novel_id=novel_id).filter(
        Chapter.chapter_number < chapter_number
    ).order_by(Chapter.chapter_number.desc()).first()

    next_chapter = Chapter.query.filter_by(novel_id=novel_id).filter(
        Chapter.chapter_number > chapter_number
    ).order_by(Chapter.chapter_number.asc()).first()

    return render_template('chapter.html',
        novel=novel,
        chapter=chapter,
        current_user=current_user,
        is_author=is_author,
        prev_chapter=prev_chapter,
        next_chapter=next_chapter
    )

# CREATE CHAPTER
@app.route('/novel/<int:novel_id>/chapter/create', methods=['GET', 'POST'])
@login_required
def create_chapter(novel_id):
    novel = Novel.query.get_or_404(novel_id)
    current_user = get_current_user()

    if novel.author_id != current_user.id:
        flash('You do not have permission to add chapters to this novel!', 'error')
        return redirect(url_for('novel_detail', novel_id=novel_id))

    last_chapter = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.chapter_number.desc()).first()
    next_number = (last_chapter.chapter_number + 1) if last_chapter else 1

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not all([title, content]):
            flash('Title and content are required!', 'error')
            return render_template('create_chapter.html', novel=novel, next_number=next_number, current_user=current_user)

        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=next_number,
            title=title,
            content=content
        )
        novel.updated_at = datetime.utcnow()
        db.session.add(chapter)
        db.session.commit()
        flash(f'Chapter {next_number} created successfully!', 'success')
        return redirect(url_for('read_chapter', novel_id=novel_id, chapter_number=next_number))

    return render_template('create_chapter.html',
        novel=novel,
        next_number=next_number,
        current_user=current_user
    )

# EDIT CHAPTER
@app.route('/novel/<int:novel_id>/chapter/<int:chapter_number>/edit', methods=['GET', 'POST'])
@login_required
def edit_chapter(novel_id, chapter_number):
    novel = Novel.query.get_or_404(novel_id)
    chapter = Chapter.query.filter_by(novel_id=novel_id, chapter_number=chapter_number).first_or_404()
    current_user = get_current_user()

    if novel.author_id != current_user.id:
        flash('You do not have permission to edit this chapter!', 'error')
        return redirect(url_for('read_chapter', novel_id=novel_id, chapter_number=chapter_number))

    if request.method == 'POST':
        chapter.title = request.form.get('title', '').strip()
        chapter.content = request.form.get('content', '').strip()
        chapter.updated_at = datetime.utcnow()
        novel.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Chapter updated successfully!', 'success')
        return redirect(url_for('read_chapter', novel_id=novel_id, chapter_number=chapter_number))

    return render_template('edit_chapter.html',
        novel=novel,
        chapter=chapter,
        current_user=current_user
    )

# DELETE CHAPTER
@app.route('/novel/<int:novel_id>/chapter/<int:chapter_number>/delete', methods=['POST'])
@login_required
def delete_chapter(novel_id, chapter_number):
    novel = Novel.query.get_or_404(novel_id)
    chapter = Chapter.query.filter_by(novel_id=novel_id, chapter_number=chapter_number).first_or_404()
    current_user = get_current_user()

    if novel.author_id != current_user.id:
        flash('You do not have permission to delete this chapter!', 'error')
        return redirect(url_for('read_chapter', novel_id=novel_id, chapter_number=chapter_number))

    db.session.delete(chapter)

    # nyesuaiin nomer chapter lg, biar gada yg lompat2
    remaining = Chapter.query.filter_by(novel_id=novel_id).order_by(Chapter.chapter_number).all()
    for i, ch in enumerate(remaining, start=1):
        ch.chapter_number = i

    novel.updated_at = datetime.utcnow()
    db.session.commit()
    flash(f'Chapter {chapter_number} deleted successfully.', 'success')
    return redirect(url_for('novel_detail', novel_id=novel_id))


# dah INIT DB!

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)