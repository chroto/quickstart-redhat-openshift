FROM python:3
WORKDIR /build
COPY requirements.txt Makefile .rpdk-config awsqs-openshift-manager.json /build/
COPY src /build/src/
RUN make build
CMD mkdir -p /output/ && mv /build/awsqs-openshift-manager.zip /output/