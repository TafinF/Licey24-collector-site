@echo off
chdir /d "C:\Users\Учитель\Documents\0Code\Licey24-collector-site"

echo Создание Docker образа...
docker build -t li_test .

echo Сохранение образа в tar архив...
docker save -o li_test.tar li_test

echo Готово! Образ сохранен в li_test.tar
pause