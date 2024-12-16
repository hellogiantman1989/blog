from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/images'  # 设置上传文件的文件夹
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 设置最大上传文件大小（16MB）
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'} # 允许上传的文件扩展名
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=True) # 添加 image_path 字段

    def __repr__(self):
        return f'Post({self.title}, {self.content})'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    
    def __repr__(self):
        return f'User({self.username})'

with app.app_context():
    db.create_all()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    posts = Post.query.all()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
            
    return render_template('login.html')
    
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

def login_required(func):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image = request.files['image'] if 'image' in request.files else None
        image_path = None

        if image and image.filename != '' and allowed_file(image.filename):
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = secure_filename(image.filename)
            file_extension = filename.rsplit('.',1)[1].lower()
            new_filename = f"{timestamp}-{filename}"
            image_path = os.path.join('images', new_filename).replace('\\','/') # 修改这里，强制使用正斜杠  # 修改这里
            image_save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename) #  添加保存的路径
            image.save(image_save_path)
            print(f"new_post - image_path: {image_path}") # 添加打印语句

        post = Post(title=title, content=content, user_id=session['user_id'], image_path=image_path)
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('new.html')

@app.route('/post/<int:post_id>')
def show_post(post_id):
    post = Post.query.get(post_id)
    if post is None:
        return 'Post not found', 404
    post_content = Markup(post.content)  
    return render_template('post.html', post=post, post_content=post_content)


@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get(post_id)
    if post is None:
        return 'Post not found', 404
    if post.author.id != session['user_id']:
        flash('You are not authorized to edit this post.', 'danger')
        return redirect(url_for('show_post', post_id=post_id))
    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        image = request.files['image'] if 'image' in request.files else None

        if image and image.filename != '' and allowed_file(image.filename):
            if post.image_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path)) #删除旧的图片
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = secure_filename(image.filename)
            file_extension = filename.rsplit('.',1)[1].lower()
            new_filename = f"{timestamp}-{filename}"
            image_path = os.path.join('images', new_filename).replace('\\','/') # 修改这里，强制使用正斜杠 # 修改这里
            image_save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename) #  添加保存的路径
            image.save(image_save_path)
            print(f"edit_post - image_path: {image_path}") # 添加打印语句
       
        elif image is not None and image.filename == '':
             # 如果用户没有上传新图片，并且删除了当前图片的上传
            if post.image_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path)):
               os.remove(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path))
            post.image_path = None
            print(f"edit_post - image_path: {image_path}") # 添加打印语句
     
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('edit_post.html', post=post)


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    if post is None:
        return 'Post not found', 404
    if post.author.id != session['user_id']:
        flash('You are not the author of this post.','danger')
        return redirect(url_for('index'))
    if post.image_path and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path)):
       os.remove(os.path.join(app.config['UPLOAD_FOLDER'],post.image_path)) #删除图片
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)