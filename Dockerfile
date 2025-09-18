# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY backend/requirements.txt ./backend/

# Install system dependencies required for the entrypoint script (netcat and dos2unix)
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && apt-get update && apt-get install -y netcat-openbsd dos2unix && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r backend/requirements.txt

# Copy the entire project into the container at /app
COPY . .

# Expose the port the app runs on
EXPOSE 4568

# Copy the entrypoint script and ensure it has the correct line endings
COPY entrypoint.sh /app/entrypoint.sh
RUN dos2unix /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# The command to run when the container starts (will be passed to the entrypoint)
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "4568"]