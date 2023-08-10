FROM python:3.10-alpine3.17

RUN apk add --update alpine-sdk

WORKDIR /app

ADD templates ./templates
ADD server.py requirements.txt ./
RUN pip install -r requirements.txt

VOLUME /app/config

CMD ["python", "server.py"]
