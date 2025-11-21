import os
import hashlib
import json
from flask import Flask, request, render_template, redirect, url_for, make_response

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
    
    # Фильтруем сотрудников: оставляем только тех, у кого showInGeneralList = true
    # Используем get() с значением по умолчанию True, чтобы сотрудники без этого поля тоже показывались
    filtered_employees = [emp for emp in data['employees'] if emp.get('showInGeneralList', True)]
    
    print(f"Загружено сотрудников: {len(filtered_employees)} из {len(data['employees'])}")  # Для отладки
    return filtered_employees

EMPLOYEES = load_employees()

@app.before_request
def check_authentication():
    """Проверка аутентификации для всех запросов"""
    # Разрешаем доступ к статическим файлам без аутентификации
    if request.endpoint == 'static':
        return
    # Исключаем страницу входа из проверки
    if request.endpoint == 'login':
        return
    
    # Проверяем хеш пароля в куках
    password_hash = request.cookies.get('password_hash')
    
    if password_hash != CORRECT_PASSWORD_HASH:
        return redirect(url_for('login'))

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/')
def index():
    """Главная страница (только для аутентифицированных пользователей)"""
    # Получаем ID выбранного сотрудника из куки
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
    # Проверяем существование сотрудника
    employee_exists = any(emp['id'] == employee_id for emp in EMPLOYEES)
    
    if not employee_exists:
        return redirect(url_for('employees'))
    
    # Создаем ответ с редиректом на главную
    response = make_response(redirect(url_for('index')))
    # Устанавливаем куку с ID сотрудника на 3 месяца (90 дней)
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        password = request.form.get('password')
        
        if not password:
            return render_template('login.html', error='❌ Пожалуйста, введите пароль')
        
        # Получаем хеш введенного пароля
        password_hash = get_password_hash(password)
        
        # Проверяем пароль
        if password_hash == CORRECT_PASSWORD_HASH:
            # Создаем ответ с редиректом на страницу сотрудников
            response = make_response(redirect(url_for('employees')))
            # Устанавливаем куку с хешем пароля на 3 месяца (90 дней)
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
    app.run(host='0.0.0.0', port=5000, debug=False)