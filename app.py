from datetime import datetime, timezone, timedelta
import os
from flask import Flask, request, render_template, redirect, url_for, make_response, jsonify
from urllib.parse import unquote
import json
from data_managers import EmployeeManager, StudentManager, AuthManager

# Инициализация менеджеров
BASE_DIR = 'storage'
employee_manager = EmployeeManager(BASE_DIR)
student_manager = StudentManager(BASE_DIR)

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
    
    # Получаем сегодняшние отчеты для этого сотрудника
    todays_reports = []
    if selected_employee:
        todays_reports = get_todays_reports_for_employee(selected_employee['id'])
    
    return render_template('index.html', 
                         selected_employee=selected_employee,
                         todays_reports=todays_reports)

def get_todays_reports_for_employee(employee_id):
    """Получение сегодняшних отчетов доступных сотруднику"""
    moscow_tz = timezone(timedelta(hours=3))
    today = datetime.now(moscow_tz).strftime('%Y-%m-%d')
    reports_dir = os.path.join('storage', 'reports', today)
    
    todays_reports = []
    
    if not os.path.exists(reports_dir):
        return todays_reports
    
    for filename in os.listdir(reports_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(reports_dir, filename), 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                # Проверяем доступ
                access_control = report_data.get('access_control', {})
                if (employee_id == access_control.get('author_id') or 
                    employee_id in access_control.get('class_teachers', [])):
                    
                    # Форматируем время для отображения
                    report_time = datetime.fromisoformat(report_data['timestamp'])
                    formatted_time = report_time.strftime('%H:%M')
                    
                    todays_reports.append({
                        'date': today,
                        'filename': filename,
                        'class_name': report_data['class_name'],
                        'data_type': report_data['data_type'],
                        'time': formatted_time,
                        'author_id': access_control.get('author_id')
                    })
                    
            except Exception as e:
                print(f"Ошибка при загрузке отчета {filename}: {e}")
    
    # Сортируем по времени (новые сверху)
    todays_reports.sort(key=lambda x: x['time'], reverse=True)
    return todays_reports

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
    """Страница проверки внешнего вида для конкретного класса"""
    return render_data_collection_page(class_name, 'appearance')

@app.route('/missing/<class_name>')
def missing_class(class_name):
    """Страница отметки отсутствующих для конкретного класса"""
    return render_data_collection_page(class_name, 'missing')

def render_data_collection_page(class_name, data_type):
    """Рендер страницы сбора данных"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    if not selected_employee:
        return redirect(url_for('employees'))
    
    # Загружаем конфигурацию
    config_path = os.path.join('storage', f'config-{data_type}.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        return f"Конфигурация для {data_type} не найдена", 404
    
    # Фильтруем опции по condition
    filtered_options = []
    for option in config.get('options', []):
        condition = option.get('condition')
        if condition is None or condition in selected_employee.get('specialParams', []):
            filtered_options.append(option)
    
    config['options'] = filtered_options
    
    # Получаем студентов класса
    students = student_manager.get_class_students(class_name)
    
    return render_template(
        'data_collection.html',
        class_name=class_name,
        config=config,
        students=students,
        selected_employee=selected_employee,
        data_type=data_type
    )

@app.route('/save-data/<data_type>/<class_name>', methods=['POST'])
def save_data(data_type, class_name):
    """Сохранение собранных данных"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    if not selected_employee:
        return jsonify({'error': 'Сотрудник не выбран'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Нет данных'}), 400
    
    # Устанавливаем московский часовой пояс
    moscow_tz = timezone(timedelta(hours=3))
    current_time = datetime.now(moscow_tz)
    
    # Формируем полные данные для сохранения
    save_data = {
        'timestamp': current_time.isoformat(),
        'class_name': class_name,
        'data_type': data_type,
        'employee': {
            'id': selected_employee['id'],
            'lastName': selected_employee['lastName'],
            'firstName': selected_employee['firstName'],
            'middleName': selected_employee.get('middleName', '')
        },
        'access_control': {
            'author_id': selected_employee['id'],
            'class_teachers': [],
            'class_name': class_name
        },
        'students_data': {}
    }
    
    # Определяем классных руководителей для этого класса
    class_teachers = []
    for employee in employee_manager.get_all_employees():
        if (employee.get('classSupervision') and 
            class_name in employee['classSupervision']):
            class_teachers.append(employee['id'])
    
    save_data['access_control']['class_teachers'] = class_teachers
    
    # Обрабатываем данные студентов
    for student_id, student_data in data.get('data', {}).items():
        student_info = next((s for s in student_manager.get_class_students(class_name) 
                           if str(s['id']) == student_id), None)
        
        if student_info:
            save_data['students_data'][student_id] = {
                'student': {
                    'id': student_info['id'],
                    'lastName': student_info['lastName'],
                    'firstName': student_info['firstName']
                },
                'selections': student_data.get('selections', []),
                'otherText': student_data.get('otherText', '')
            }
    
    # Сохраняем в файл
    try:
        # Создаем папку с датой (в московском времени)
        date_folder = current_time.strftime('%Y-%m-%d')
        save_dir = os.path.join('storage', 'reports', date_folder)
        os.makedirs(save_dir, exist_ok=True)
        
        # Имя файла: время_класс_тип_данных.json
        filename = f"{current_time.strftime('%H-%M-%S')}_{class_name}_{data_type}.json"
        file_path = os.path.join(save_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        
        # Вместо редиректа возвращаем JSON с URL для перехода
        report_url = url_for('view_report', date=date_folder, filename=filename, _external=False)
        return jsonify({
            'success': True, 
            'redirect_url': report_url,
            'message': 'Данные успешно сохранены'
        })
    
    except Exception as e:
        print(f"Ошибка при сохранении данных: {e}")
        return jsonify({'error': 'Ошибка сохранения'}), 500

@app.route('/report/<date>/<filename>')
def view_report(date, filename):
    """Просмотр отчета"""
    employee_id = request.cookies.get('employee_id')
    selected_employee = employee_manager.get_employee_by_id(employee_id) if employee_id else None
    
    if not selected_employee:
        return redirect(url_for('login'))
    
    # Загружаем отчет
    report_path = os.path.join('storage', 'reports', date, filename)
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
    except FileNotFoundError:
        return "Отчёт не найден", 404
    
    # Проверяем доступ
    access_control = report_data.get('access_control', {})
    if (selected_employee['id'] != access_control.get('author_id') and 
        selected_employee['id'] not in access_control.get('class_teachers', [])):
        return "Доступ запрещен", 403
    
    # Проверяем, нужно ли показывать шапку успеха
    show_success = request.args.get('success') == 'true'
    
    # Получаем конфигурацию для правильного отображения опций
    config_path = os.path.join('storage', f"config-{report_data['data_type']}.json")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {'options': []}
    
    return render_template('report.html', 
                         report=report_data,
                         config=config,
                         selected_employee=selected_employee,
                         show_success=show_success)

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
    
    # Обработка GET запроса с параметрами авторизации
    password_param = request.args.get('p')
    key_param = request.args.get('k')
    
    if password_param and key_param:
        # Автоматическая авторизация если переданы оба параметра
        if auth_manager.verify_password(password_param):
            response = make_response(redirect(url_for('employees')))
            return auth_manager.set_password_cookie(response, password_param)
        else:
            return render_template('login.html', error='❌ Неверный пароль в ссылке')
    
    # Обычная авторизация если параметров нет
    return render_template('login.html', password_param=password_param, key_param=key_param)

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