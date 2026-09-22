FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        pip install --no-cache-dir requests uuid; \
    fi

CMD ["python", "traffic_simulator.py"]
