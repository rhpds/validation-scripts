FROM registry.access.redhat.com/ubi9/python-311
WORKDIR /app/

USER root
RUN chown -R ${USER_UID}:0 /app
USER ${USER_UID}

COPY ./requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

ENV BASE_DIR="/app"
ENV HOST="0.0.0.0"
ENV PORT=80

COPY ./api /app/
CMD ["python", "main.py" ]
