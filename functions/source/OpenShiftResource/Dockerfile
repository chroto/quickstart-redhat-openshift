FROM python:3
WORKDIR /build
COPY requirements.txt Makefile .rpdk-config awsqs-openshift-manager.json /build/
RUN pip install -r requirements.txt
RUN pip install --upgrade cloudformation-cli-go-plugin
COPY src /build/src/
RUN make build
CMD mkdir -p /output/ && mv /build/awsqs-openshift-manager.zip /output/