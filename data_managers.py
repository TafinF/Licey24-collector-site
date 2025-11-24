import os
import hashlib
import json
from datetime import datetime

class EmployeeManager:
    """Менеджер для работы с данными сотрудников"""
    
    def __init__(self, base_dir='storage'):
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, 'employees.json')
        self._employees = None
    
    def load_employees(self):
        """Загрузка и фильтрация сотрудников"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            filtered_employees = [emp for emp in data['employees'] if emp.get('showInGeneralList', True)]
            print(f"Загружено сотрудников: {len(filtered_employees)} из {len(data['employees'])}")
            self._employees = filtered_employees
            return filtered_employees
        except Exception as e:
            print(f"Ошибка при загрузке сотрудников: {e}")
            return []
    
    def get_employee_by_id(self, employee_id):
        """Получение сотрудника по ID"""
        if self._employees is None:
            self.load_employees()
        
        # Преобразуем employee_id в int для сравнения
        try:
            employee_id_int = int(employee_id)
        except (ValueError, TypeError):
            return None
        
        for employee in self._employees:
            if employee['id'] == employee_id_int:
                return employee
        return None
    
    def get_all_employees(self):
        """Получение всех сотрудников"""
        if self._employees is None:
            return self.load_employees()
        return self._employees

class StudentManager:
    """Менеджер для работы с данными студентов и классов"""
    
    def __init__(self, base_dir='storage'):
        self.base_dir = base_dir
        self.file_path = os.path.join(base_dir, 'student.json')
        self._classes = None
    
    def load_classes(self):
        """Загрузка и сортировка классов"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
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
            self._classes = classes
            return classes
        except Exception as e:
            print(f"Ошибка при загрузке классов: {e}")
            return []
    
    def get_class_students(self, class_name):
        """Получение списка студентов для указанного класса"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for class_info in data['classes']:
                if class_info['name'] == class_name:
                    return class_info['students']
            return []
        except Exception as e:
            print(f"Ошибка при загрузке студентов класса {class_name}: {e}")
            return []
    
    def get_all_classes(self):
        """Получение всех классов"""
        if self._classes is None:
            return self.load_classes()
        return self._classes

class ViolationManager:
    """Менеджер для работы с нарушениями"""
    
    def __init__(self, base_dir='storage'):
        self.base_dir = os.path.join(base_dir, 'violations')
        os.makedirs(self.base_dir, exist_ok=True)
    
    def save_violations(self, class_name, violations_data, employee_info=None):
        """Сохранение данных о нарушениях в файл"""
        try:
            # Создаем папку с сегодняшней датой
            today = datetime.now().strftime('%Y-%m-%d')
            date_dir = os.path.join(self.base_dir, today)
            os.makedirs(date_dir, exist_ok=True)
            
            # Создаем имя файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'{timestamp}_{class_name}.json'
            filepath = os.path.join(date_dir, filename)
            
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
    
    def get_violations_by_date(self, date_str):
        """Получение всех нарушений за определенную дату"""
        try:
            violations = []
            date_dir = os.path.join(self.base_dir, date_str)
            
            if os.path.exists(date_dir):
                for filename in os.listdir(date_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(date_dir, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            violation_data = json.load(f)
                            violations.append(violation_data)
            
            return violations
        except Exception as e:
            print(f"Ошибка при загрузке нарушений за {date_str}: {e}")
            return []

class AuthManager:
    """Менеджер для работы с аутентификацией"""
    
    def __init__(self, secret_key, admin_password):
        self.secret_key = secret_key
        self.correct_password_hash = self._get_password_hash(admin_password)
    
    def _get_password_hash(self, password):
        """Генерация хеша пароля"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password):
        """Проверка пароля"""
        return self._get_password_hash(password) == self.correct_password_hash
    
    def set_password_cookie(self, response, password):
        """Установка cookie с хешем пароля"""
        password_hash = self._get_password_hash(password)
        response.set_cookie(
            'password_hash', 
            password_hash, 
            max_age=90*24*60*60,
            httponly=True,
            secure=True,
            samesite='Lax'
        )
        return response
    
    def verify_cookie(self, cookie_value):
        """Проверка cookie"""
        return cookie_value == self.correct_password_hash