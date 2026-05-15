FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Initialize the database during build or startup
RUN python main.py --auto

# Give execution permissions to the script
RUN chmod +x run.sh

ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["./run.sh"]
