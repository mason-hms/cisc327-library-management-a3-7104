# 1. Use Python 3.11 slim base image 
FROM python:3.11-slim

# 2. Set working directory inside the container
WORKDIR /app

# 3. Copy dependency file
COPY requirements.txt .

# 4. Install dependencies
# Note: Installing pytest-playwright is required for running tests inside the container
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install pytest-playwright

# 5. Copy application source code
COPY . .

# 6. Install Playwright browsers 
RUN playwright install chromium
RUN playwright install-deps

# 7. Expose port 5000 for Flask
EXPOSE 5000

# 8. Set environment variables to ensure Flask runs on all interfaces
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# 9. Default command to run the application
CMD ["flask", "run"]