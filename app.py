import os
import hashlib
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
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Главная страница</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .success { color: green; font-size: 18px; margin: 20px 0; }
            .info { background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <h1>🎉 Добро пожаловать!</h1>
        <div class="success">✅ Вы успешно авторизованы!</div>
        <div class="info">
            <h3>📊 Доступные функции:</h3>
            <ul>
                <li>Просмотр защищенных данных</li>
                <li>Работа с системой</li>
                <li>Доступ к инструментам</li>
            </ul>
        </div>
        <a href="/logout" style="color: blue; text-decoration: none;">🚪 Выйти</a>
    </body>
    </html>
    '''

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
            # Создаем ответ с редиректом
            response = make_response(redirect(url_for('index')))
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
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)