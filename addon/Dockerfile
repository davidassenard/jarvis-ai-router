FROM python:3.12-alpine
COPY router.py /opt/jarvis/router.py
COPY server.py /opt/jarvis/server.py
COPY run.sh /run.sh
RUN chmod 755 /run.sh
CMD ["/run.sh"]
