FROM python:3.14.3-alpine
COPY examples/server.py server.py
RUN python -m pip install prompt-toolkit
CMD ["python", "server.py"]