.PHONY: build test clean
PROFILE ?= default
REGION ?=

cloudformation-cli-python-lib-0.0.1.tar.gz:
	wget https://github.com/aws-cloudformation/cloudformation-cli-python-plugin/archive/9a9229c69223271478577f39155df267c9784453.tar.gz -O cloudformation-cli-python-lib-0.0.1.tar.gz
	mkdir -p cloudformation-cli-python-plugin
	tar xzf cloudformation-cli-python-lib-0.0.1.tar.gz -C cloudformation-cli-python-plugin --strip-components 1
	cd cloudformation-cli-python-plugin && bash package_lib.sh
	mv cloudformation-cli-python-plugin/cloudformation-cli-python-lib-0.0.1.tar.gz ./

build: cloudformation-cli-python-lib-0.0.1.tar.gz
	pip install git+https://github.com/aws-cloudformation/aws-cloudformation-rpdk-python-plugin.git@9a9229c69223271478577f39155df267c9784453#egg=cloudformation-cli-python-plugin
	cfn generate
	cfn submit --dry-run

test:
	cfn generate
	cfn submit --dry-run
	sam local start-lambda

clean:
	rm -rf bin
	rm -rf cloudformation-cli-python-plugin
	rm cloudformation-cli-python-lib-0.0.1.tar.gz

