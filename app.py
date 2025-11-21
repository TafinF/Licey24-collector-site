import os
import hashlib
import json
from flask import Flask, request, render_template, redirect, url_for, make_response, jsonify
from urllib.parse import quote, unquote
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Получаем пароль из переменных окружения
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'default_password')

def get_password_hash(password):
    """Генерация хеша пароля"""
    return hashlib.sha256(password.encode()).hexdigest()

# Предварительно вычисляем хеш правильного пароля
CORRECT_PASSWORD_HASH = get_password_hash(ADMIN_PASSWORD)

# Загружаем данные сотрудников
def load_employees():
    with open('employees.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    filtered_employees = [emp for emp in data['employees'] if emp.get('showInGeneralList', True)]
    print(f"Загружено сотрудников: {len(filtered_employees)} из {len(data['employees'])}")
    return filtered_employees

EMPLOYEES = load_employees()

def load_classes():
    """Загрузка и сортировка классов из student.json"""
    with open('student.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    classes = []
    for class_info in data['classes']:
        classes.append({
            'name': class_info['name'],
            'building': class_info['building']
        })
    
    def class_sort_key(cls):
        class_num = cls['name'].split('-')[0]
        try:
            num = int(class_num)
        except ValueError:
            num = float('inf')
        return (cls['building'], num)
    
    classes.sort(key=class_sort_key)
    return classes

def get_class_students(class_name):
    """Получение списка студентов для указанного класса"""
    with open('student.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    for class_info in data['classes']:
        if class_info['name'] == class_name:
            return class_info['students']
    return []

def save_violations_data(class_name, violations_data, employee_info=None):
    """Сохранение данных о нарушениях в файл"""
    try:
        # Создаем папку с сегодняшней датой
        today = datetime.now().strftime('%Y-%m-%d')
        os.makedirs(f'violations_data/{today}', exist_ok=True)
        
        # Создаем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{timestamp}_{class_name}.json'
        filepath = f'violations_data/{today}/{filename}'
        
        # Формируем данные для сохранения
        data_to_save = {
            'class_name': class_name,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'violations': violations_data,
            'employee': employee_info
        }
        
        # Сохраняем в файл
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        print(f"Данные сохранены в файл: {filepath}")
        return data_to_save
        
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")
        return None

@app.before_request
def check_authentication():
    """Проверка аутентификации для всех запросов"""
    if request.endpoint == 'static':
        return
    if request.endpoint == 'login':
        return
    
    password_hash = request.cookies.get('password_hash')
    if password_hash != CORRECT_PASSWORD_HASH:
        return redirect(url_for('login'))

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/')
def index():
    """Главная страница"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = None
    
    if employee_id:
        for employee in EMPLOYEES:
            if employee['id'] == int(employee_id):
                selected_employee = employee
                break
    
    return render_template('index.html', selected_employee=selected_employee)

@app.route('/employees')
def employees():
    """Страница выбора сотрудника"""
    return render_template('employees.html', employees=EMPLOYEES)

@app.route('/select-employee/<int:employee_id>')
def select_employee(employee_id):
    """Выбор сотрудника и редирект на главную"""
    employee_exists = any(emp['id'] == employee_id for emp in EMPLOYEES)
    
    if not employee_exists:
        return redirect(url_for('employees'))
    
    response = make_response(redirect(url_for('index')))
    response.set_cookie(
        'employee_id', 
        str(employee_id), 
        max_age=90*24*60*60,
        httponly=True,
        secure=True,
        samesite='Lax'
    )
    return response

@app.route('/clear-employee')
def clear_employee():
    """Очистка выбранного сотрудника"""
    response = make_response(redirect(url_for('employees')))
    response.set_cookie('employee_id', '', expires=0)
    return response

@app.route('/appearance')
def appearance():
    """Страница для отметки внешнего вида - выбор класса"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = None
    
    if employee_id:
        for employee in EMPLOYEES:
            if employee['id'] == int(employee_id):
                selected_employee = employee
                break
    
    classes = load_classes()
    
    return render_template(
        'appearance.html', 
        classes=classes,
        selected_employee=selected_employee
    )

@app.route('/appearance/<class_name>')
def appearance_class(class_name):
    """Страница для отметки нарушений внешнего вида конкретного класса"""
    decoded_class_name = unquote(class_name)
    
    employee_id = request.cookies.get('employee_id')
    selected_employee = None
    
    if employee_id:
        for employee in EMPLOYEES:
            if employee['id'] == int(employee_id):
                selected_employee = employee
                break
    
    # Получаем студентов класса с ID
    students_data = get_class_students(decoded_class_name)
    
    return render_template(
        'appearance_class.html',
        class_name=decoded_class_name,
        students=students_data,  # Теперь передаем полные данные студентов
        selected_employee=selected_employee
    )

@app.route('/submit-appearance', methods=['POST'])
def submit_appearance():
    """Обработка отправки данных о нарушениях внешнего вида"""
    try:
        data = request.get_json()
        class_name = data.get('class_name')
        violations = data.get('violations', {})
        
        print(f"Получены данные о нарушениях для класса {class_name}:")
        for student_id, student_violations in violations.items():
            if student_violations:
                print(f"  ID {student_id}: {student_violations}")
        
        # Получаем информацию о сотруднике
        employee_id = request.cookies.get('employee_id')
        employee_info = None
        if employee_id:
            for employee in EMPLOYEES:
                if employee['id'] == int(employee_id):
                    employee_info = {
                        'id': employee['id'],
                        'lastName': employee['lastName'],
                        'firstName': employee['firstName'],
                        'middleName': employee.get('middleName', '')
                    }
                    break
        
        # Сохраняем данные в файл
        saved_data = save_violations_data(class_name, violations, employee_info)
        
        if saved_data:
            return jsonify({
                'success': True,
                'message': 'Данные успешно сохранены',
                'class_name': class_name,
                'timestamp': saved_data['timestamp'],
                'violations': violations
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Ошибка при сохранении данных'
            }), 500
        
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")
        return jsonify({
            'success': False,
            'message': 'Ошибка при сохранении данных'
        }), 500

@app.route('/appearance-submission-success')
def appearance_submission_success():
    """Страница успешной отправки данных"""
    class_name = request.args.get('class_name', '')
    timestamp = request.args.get('timestamp', '')
    violations_json = request.args.get('violations', '{}')
    
    # Парсим нарушения из JSON строки
    try:
        violations = json.loads(violations_json)
    except:
        violations = {}
    
    # Получаем информацию о выбранном сотруднике
    employee_id = request.cookies.get('employee_id')
    selected_employee = None
    
    if employee_id:
        for employee in EMPLOYEES:
            if employee['id'] == int(employee_id):
                selected_employee = employee
                break
    
    return render_template(
        'appearance_submission_success.html',
        class_name=class_name,
        timestamp=timestamp,
        violations=violations,
        selected_employee=selected_employee
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password:
            return render_template('login.html', error='❌ Пожалуйста, введите пароль')
        
        password_hash = get_password_hash(password)
        
        if password_hash == CORRECT_PASSWORD_HASH:
            response = make_response(redirect(url_for('employees')))
            response.set_cookie(
                'password_hash', 
                password_hash, 
                max_age=90*24*60*60,
                httponly=True,
                secure=True,
                samesite='Lax'
            )
            return response
        else:
            return render_template('login.html', error='❌ Неверный пароль')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Выход из системы"""
    response = make_response(redirect(url_for('login')))
    response.set_cookie('password_hash', '', expires=0)
    response.set_cookie('employee_id', '', expires=0)
    return response

if __name__ == '__main__':
    # Создаем папку для данных если её нет
    os.makedirs('violations_data', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)