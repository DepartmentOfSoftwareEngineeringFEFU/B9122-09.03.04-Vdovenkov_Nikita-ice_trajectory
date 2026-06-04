# Ice Routing Service

Сервис моделирования и оптимизации маршрутов судов с учётом ледовой обстановки.

## Запуск через Docker

```bash
git clone https://github.com/TatarArg/ice_routing_service
cd ice_routing_service
docker compose up --build
```

Открыть в браузере: http://localhost:8000

## Запуск без Docker

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Открыть в браузере: http://localhost:8000
