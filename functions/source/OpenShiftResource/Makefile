.PHONY: build test clean

build:
	cfn generate
	cfn submit --dry-run

test:
	cfn generate
	cfn submit --dry-run
	sam local start-lambda

clean:
	rm -rf bin
