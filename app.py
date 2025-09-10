from flask import Flask, render_template, request, redirect, session, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

db = SQLAlchemy(app)

# مدل‌ها
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scroll_text = db.Column(db.String(200), default='به وب‌سایت ما خوش آمدید')
    slider_images = db.Column(db.PickleType, default=[])
    buttons = db.Column(db.PickleType, default=[
        'آموزش و تربیت',
        'هیئت امنا',
        'سینما',
        'مرکز مشاوره',
        'اطلاع‌رسانی',
        'نوجوانانه'
    ])

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    poster = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    release_date = db.Column(db.String(20), nullable=False)
    release_time = db.Column(db.String(10), nullable=False)

class HallConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rows = db.Column(db.Integer, nullable=False)
    seats_per_row = db.Column(db.Integer, nullable=False)

class SeatReservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movie.id'))
    row = db.Column(db.Integer)
    seat = db.Column(db.Integer)
    reserved = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()
    if not Settings.query.first():
        db.session.add(Settings())
        db.session.commit()

@app.route('/')
def home():
    settings = Settings.query.first()
    return render_template('index.html', settings=settings)

@app.route('/cinema')
def cinema():
    movies = Movie.query.all()
    return render_template('cinema.html', movies=movies)

@app.route('/movie/<int:movie_id>', methods=['GET', 'POST'])
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    hall = HallConfig.query.first()

    if not hall:
        return "تنظیمات سالن انجام نشده!"

    reserved_seats = {
        (r.row, r.seat)
        for r in SeatReservation.query.filter_by(movie_id=movie_id, reserved=True)
    }

    if request.method == 'POST':
        selected = request.form.getlist('seats')
        for seat in selected:
            r, s = map(int, seat.split('-'))
            reservation = SeatReservation(movie_id=movie_id, row=r, seat=s, reserved=True)
            db.session.add(reservation)
        db.session.commit()
        return redirect(url_for('ticket', movie_id=movie_id))

    return render_template('movie_detail.html', movie=movie, hall=hall, reserved_seats=reserved_seats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        if username == '795' and password == '795':
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='نام کاربری یا رمز اشتباه است')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))
    settings = Settings.query.first()
    hall = HallConfig.query.first()
    return render_template('dashboard.html', settings=settings, hall=hall)

@app.route('/add-movie', methods=['GET', 'POST'])
def add_movie():
    if not session.get('admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        price = request.form.get('price', '').strip()
        release_date = request.form.get('release_date', '').strip()
        release_time = request.form.get('release_time', '').strip()
        poster = request.files.get('poster')

        if title and poster:
            filename = poster.filename
            poster_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            poster.save(poster_path)

            movie = Movie(
                title=title,
                poster=f'uploads/{filename}',
                price=int(price),
                release_date=release_date,
                release_time=release_time
            )
            db.session.add(movie)
            db.session.commit()
            return redirect(url_for('add_movie'))

    movies = Movie.query.all()
    return render_template('add_movie.html', movies=movies)

@app.route('/delete-movie/<int:movie_id>')
def delete_movie(movie_id):
    if not session.get('admin'):
        return redirect(url_for('login'))
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    return redirect(url_for('add_movie'))

@app.route('/settings', methods=['GET', 'POST'])
def settings_dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))

    hall = HallConfig.query.first()
    if not hall:
        hall = HallConfig(rows=0, seats_per_row=0)
        db.session.add(hall)
        db.session.commit()

    settings = Settings.query.first()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_scroll':
            settings.scroll_text = request.form.get('scroll_text', '').strip()

        elif action == 'update_buttons':
            new_btns = []
            for i in range(6):
                v = request.form.get(f'button{i}', '').strip()
                new_btns.append(v or settings.buttons[i])
            settings.buttons = new_btns

        elif action == 'update_hall':
            try:
                hall.rows = int(request.form.get('rows', 0))
                hall.seats_per_row = int(request.form.get('seats', 0))
            except ValueError:
                hall.rows = 0
                hall.seats_per_row = 0

        db.session.commit()
        return redirect(url_for('settings_dashboard'))

    return render_template('settings.html', settings=settings, hall=hall)

@app.route('/stats')
def stats():
    if not session.get('admin'):
        return redirect(url_for('login'))
    user_count = User.query.count()
    movie_count = Movie.query.count()
    return f"<h2 style='text-align:center;'>👥 کاربران: {user_count} | 🎬 فیلم‌ها: {movie_count}</h2>"

@app.route('/ticket/<int:movie_id>')
def ticket(movie_id):
    reservations = SeatReservation.query.filter_by(movie_id=movie_id, reserved=True).all()
    if not reservations:
        return "بلیط یافت نشد"

    movie = Movie.query.get(movie_id)
    seat_list = [f"{r.row}-{r.seat}" for r in reservations]
    seat_text = ', '.join(seat_list)

    try:
        img = Image.new('RGB', (600, 300), color='white')
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()

        draw.text((20, 20), "🎬 سینما مسجدالزهرا", font=font, fill='black')
        draw.text((20, 60), f"🎞️ فیلم: {movie.title}", font=font, fill='black')
        draw.text((20, 100), f"🪑 صندلی‌ها: {seat_text}", font=font, fill='black')
        draw.text((20, 140), f"📅 تاریخ: {movie.release_date}  ⏰ ساعت: {movie.release_time}", font=font, fill='black')

        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png', as_attachment=True, download_name='ticket.png')
    except Exception as e:
        return f"خطا در تولید بلیط: {e}"

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)