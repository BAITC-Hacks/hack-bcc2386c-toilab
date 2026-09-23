FROM python:3.12-slim
WORKDIR /app
COPY chat-widget/ /app/
RUN useradd --create-home app
USER app
EXPOSE 3000
CMD ["python", "server.py"]
