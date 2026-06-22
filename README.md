# Ice Routing Service
Сервис моделирования и оптимизации маршрутов судов с учётом ледовой обстановки.

> **Внимание:** `git clone` может занять продолжительное время(5-10 минут), т.к вместе с репозиторием подгружается база данных SQLite с AIS-данными.

## Запуск через Docker
```bash
git clone https://github.com/TatarArg/ice_routing_service
cd ice_routing_service
docker compose up --build
```
Открыть в браузере: http://localhost:8000

## Запуск без Docker
```bash
git clone https://github.com/TatarArg/ice_routing_service
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
python manage.py runserver
```
Открыть в браузере: http://localhost:8000

## Быстрый старт

1. Выберите акваторию **Тест** из списка. (см. скриншот ниже).
2. Установите начальную и конечную точки маршрута на карте (см. скриншот ниже).
3. Выберите тип судна и нажмите **Построить маршрут**.

![Выбор акватории](<img width="1916" height="903" alt="Image" src="https://github.com/user-attachments/assets/a241ae6d-da35-4671-892e-2e2836ba7796" />)
![Выбор точек маршрута](<img width="661" height="312" alt="image" src="https://github.com/user-attachments/assets/4e10a808-8048-4dab-98bf-da03a5dcc69a" />)

Примечание: маршрут не всегда строится с изгибами - это зависит от расположения точек. Для наглядного результата рекомендуется выбирать точки как на скриншоте или добавить ледовую обстановку поперек маршруту: алгоритм проложит маршрут в обход ледовых зон.
