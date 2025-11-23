import os
from flask import Flask, request, render_template, redirect, url_for, make_response, jsonify
from urllib.parse import unquote
import json
from data_managers import EmployeeManager, StudentManager, ViolationManager, AuthManager

# Инициализация менеджеров
BASE_DIR = 'storage'
employee_manager = EmployeeManager(BASE_DIR)
student_manager = StudentManager(BASE_DIR)
violation_manager = ViolationManager(BASE_DIR)
auth_manager = AuthManager(
    secret_key=os.environ.get('SECRET_KEY', 'dev-secret-key'),
    admin_password=os.environ.get('ADMIN_PASSWORD', 'default_password')
)

# Загрузка данных сотрудников при старте
EMPLOYEES = employee_manager.load_employees()

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = auth_manager.secret_key

@app.before_request
def check_authentication():
    """Проверка аутентификации для всех запросов"""
    if request.endpoint == 'static':
        return
    if request.endpoint == 'login':
        return
    
    password_hash = request.cookies.get('password_hash')
    if not auth_manager.verify_cookie(password_hash):
        return redirect(url_for('login'))

@app.route('/robots.txt')
def robots():
    return app.send_static_file('robots.txt')

@app.route('/')
def index():
    """Главная страница"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    return render_template('index.html', selected_employee=selected_employee)

@app.route('/employees')
def employees():
    """Страница выбора сотрудника"""
    return render_template('employees.html', employees=EMPLOYEES)

@app.route('/select-employee/<int:employee_id>')
def select_employee(employee_id):
    """Выбор сотрудника и редирект на главную"""
    employee_exists = employee_manager.get_employee_by_id(employee_id) is not None
    
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
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    classes = student_manager.get_all_classes()
    
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
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    # Получаем студентов класса с ID
    students_data = student_manager.get_class_students(decoded_class_name)
    
    return render_template(
        'appearance_class.html',
        class_name=decoded_class_name,
        students=students_data,
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
            employee = employee_manager.get_employee_by_id(employee_id)
            if employee:
                employee_info = {
                    'id': employee['id'],
                    'lastName': employee['lastName'],
                    'firstName': employee['firstName'],
                    'middleName': employee.get('middleName', '')
                }
        
        # Сохраняем данные в файл
        saved_data = violation_manager.save_violations(class_name, violations, employee_info)
        
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
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
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
        
        if auth_manager.verify_password(password):
            response = make_response(redirect(url_for('employees')))
            return auth_manager.set_password_cookie(response, password)
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
    # Создаем папку storage если её нет
    os.makedirs(BASE_DIR, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=False)