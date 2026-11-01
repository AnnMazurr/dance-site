import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = 'super_secret_key'
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Создание таблиц (если их нет)
def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS classifier (classifier_id INTEGER PRIMARY KEY AUTOINCREMENT, classifier_type TEXT, classifier_code INTEGER, classifier_name TEXT);
            CREATE TABLE IF NOT EXISTS dance_club (club_id INTEGER PRIMARY KEY AUTOINCREMENT, direction_id INTEGER, club_name TEXT, city TEXT, address TEXT, phone TEXT, description TEXT, venue TEXT);
            CREATE TABLE IF NOT EXISTS role (role_id INTEGER PRIMARY KEY, role_name TEXT);
            CREATE TABLE IF NOT EXISTS person (person_id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, post TEXT, education TEXT, years INTEGER, number TEXT, email TEXT, last_name TEXT, first_name TEXT, middle_name TEXT, role_id INTEGER, position_id INTEGER);
            CREATE TABLE IF NOT EXISTS dance_group (group_id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER, group_name TEXT, age_min INTEGER, age_max INTEGER, level TEXT, schedule TEXT, price NUMERIC);
            CREATE TABLE IF NOT EXISTS event (event_id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER, event_name TEXT, event_type TEXT, event_date TEXT, event_time TEXT, duration INTEGER, location TEXT, description TEXT);
        ''')
        
        # Добавляем роли и направления, если их нет
        conn.execute("INSERT OR IGNORE INTO role VALUES (1, 'Руководитель'), (2, 'Педагог')")
        conn.execute("INSERT OR IGNORE INTO classifier (classifier_id, classifier_type, classifier_code, classifier_name) VALUES (1, 'Направление', 1, 'Хип-хоп'), (2, 'Направление', 2, 'Современный'), (3, 'Направление', 3, 'Классический')")
        
        # Проверяем, есть ли объединения. Если нет — генерируем 50 штук!
        count = conn.execute("SELECT COUNT(*) FROM dance_club").fetchone()[0]
        if count == 0:
            import random
            cities = ['Москва', 'Санкт-Петербург', 'Казань', 'Екатеринбург', 'Новосибирск']
            names = ['Студия', 'Клуб', 'Ансамбль', 'Школа', 'Центр']
            directions = [1, 2, 3]
            
            for i in range(1, 51):
                c_name = f"{random.choice(names)} танца №{i}"
                c_city = random.choice(cities)
                d_id = random.choice(directions)
                phone = f"+7-9{random.randint(10,99)}-{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}"
                
                conn.execute("""INSERT INTO dance_club (direction_id, club_name, city, address, phone, description, venue) 
                                VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                             (d_id, c_name, c_city, f"ул. Ленина, д. {i}", phone, "Описание студии", "Дом культуры"))
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# --- ВВОД ДАННЫХ (Формы) ---
@app.route('/add', methods=['GET', 'POST'])
def add_data():
    db = get_db()
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        try:
            if form_type == 'add_direction': # Быстрое добавление направления
                name = request.form.get('new_direction')
                if name:
                    db.execute("INSERT INTO classifier (classifier_type, classifier_code, classifier_name) VALUES ('Направление', 1, ?)", (name,))
                    db.commit()
                    flash(f'Направление "{name}" добавлено!', 'success')
            
            elif form_type == 'add_club':
                db.execute("""INSERT INTO dance_club (direction_id, club_name, city, address, phone, description, venue) 
                              VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           (request.form['direction_id'], request.form['club_name'], request.form['city'], 
                            request.form['address'], request.form['phone'], request.form['description'], request.form['venue']))
                db.commit()
                flash('Объединение добавлено!', 'success')

            elif form_type == 'add_group':
                db.execute("""INSERT INTO dance_group (club_id, group_name, age_min, age_max, level, schedule, price) 
                              VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           (request.form['club_id'], request.form['group_name'], request.form['age_min'], 
                            request.form['age_max'], request.form['level'], request.form['schedule'], request.form['price']))
                db.commit()
                flash('Группа добавлена!', 'success')

            elif form_type == 'add_event':
                db.execute("""INSERT INTO event (group_id, event_name, event_type, event_date, location) 
                              VALUES (?, ?, ?, ?, ?)""",
                           (request.form['group_id'], request.form['event_name'], request.form['event_type'], 
                            request.form['event_date'], request.form['location']))
                db.commit()
                flash('Мероприятие добавлено!', 'success')

        except Exception as e:
            flash(f'Ошибка: {e}', 'danger')
        finally:
            db.close()
        return redirect(url_for('add_data'))

    # Данные для списков (обновляются при каждом заходе)
    directions = db.execute("SELECT classifier_id, classifier_name FROM classifier WHERE classifier_type = 'Направление'").fetchall()
    clubs = db.execute("SELECT club_id, club_name FROM dance_club").fetchall()
    groups = db.execute("SELECT group_id, group_name FROM dance_group").fetchall()
    db.close()
    return render_template('add_data.html', directions=directions, clubs=clubs, groups=groups)

# --- ПОИСК ДАННЫХ (Два вида поиска по заданию) ---
@app.route('/search', methods=['GET'])
def search():
    db = get_db()
    directions = db.execute("SELECT classifier_id, classifier_name FROM classifier WHERE classifier_type = 'Направление'").fetchall()
    
    # 1. Поиск по двум синхронизированным спискам (Направление -> Объединение)
    dir_id = request.args.get('direction_id')
    club_id = request.args.get('club_id')
    
    clubs = []
    if dir_id:
        clubs = db.execute("SELECT club_id, club_name FROM dance_club WHERE direction_id = ?", (dir_id,)).fetchall()

    # 2. Поиск по ОДНОМУ атрибуту (выбор конкретного объединения из всех)
    single_club_id = request.args.get('single_club_id')
    single_result = []
    if single_club_id:
        single_result = db.execute("""SELECT c.*, cl.classifier_name as direction_name 
                                      FROM dance_club c JOIN classifier cl ON c.direction_id = cl.classifier_id
                                      WHERE c.club_id = ?""", (single_club_id,)).fetchall()

    # Результаты для двойного поиска
    results = []
    if dir_id and club_id:
        results = db.execute("""SELECT c.*, cl.classifier_name as direction_name 
                                FROM dance_club c JOIN classifier cl ON c.direction_id = cl.classifier_id
                                WHERE c.direction_id = ? AND c.club_id = ?""", (dir_id, club_id)).fetchall()
    elif dir_id:
        results = db.execute("""SELECT c.*, cl.classifier_name as direction_name 
                                FROM dance_club c JOIN classifier cl ON c.direction_id = cl.classifier_id
                                WHERE c.direction_id = ?""", (dir_id,)).fetchall()

    all_clubs = db.execute("SELECT club_id, club_name FROM dance_club").fetchall()
    db.close()
    
    return render_template('search.html', directions=directions, clubs=clubs, results=results,
                           selected_dir=dir_id, selected_club=club_id,
                           all_clubs=all_clubs, single_result=single_result, single_club_id=single_club_id)

# --- СТАТИСТИКА ---
@app.route('/statistics')
def statistics():
    db = get_db()
    stats_cities = db.execute("SELECT city, COUNT(club_id) as count FROM dance_club GROUP BY city ORDER BY count DESC").fetchall()
    stats_directions = db.execute("""SELECT cl.classifier_name as direction, COUNT(c.club_id) as count 
                                     FROM dance_club c JOIN classifier cl ON c.direction_id = cl.classifier_id 
                                     GROUP BY cl.classifier_name ORDER BY count DESC""").fetchall()
    total_clubs = db.execute("SELECT COUNT(*) as count FROM dance_club").fetchone()['count']
    db.close()
    return render_template('statistics.html', stats_cities=stats_cities, stats_directions=stats_directions, total_clubs=total_clubs)

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(debug=True)