# AWSQS::OpenShift::Manager

## Installation

```bash
aws cloudformation create-stack \
  --stack-name awsqs-openshift-manager \
  --capabilities CAPABILITY_NAMED_IAM \
  --template-url https://s3.amazonaws.com/aws-quickstart/quickstart-openshift-resource-provider/deploy.template.yaml \
  --region us-west-2

aws cloudformation describe-stacks \
--stack-name awsqs-openshift4-manager | jq -r ".Stacks[0].Outputs[0].OutputValue" 
```

A template is provided to make deploying the resource into an account easy.

To deploy template from this directory

```bash
aws cloudformation create-stack \
  --stack-name awsqs-openshift-manager \
  --capabilities CAPABILITY_NAMED_IAM \
  --template-url https://s3.amazonaws.com/aws-quickstart/quickstart-openshift-resource-provider/deploy.template.yaml \
  --region us-west-2

```

Example usage:

```yaml
AWSTemplateFormatVersion: 2010-09-09
Parameters:
  Cluster:
    Type: String
Resources:
  MyClusterIgnition:
    Type: "AWSQS::OpenShift::Manager"
    Properties:
      Action: "GENERATE_IGNITION"
      ClusterName: my-cluster
      PullSecret: "{\"auth\": ....} ...."
      SSHKey: ssh-rsa .....
      HostedZoneName: my.example.com
      AwsAccessKeyId: AXXXXXXX
      AwsSecretAccessKey: ^4arxxxxxxxxxxxxx
      AvailabilityZones: ["us-east-1a", "us-east-1b", "us-east-1c"]
      Subnets: 
        - subnet-private1-id
        - subnet-private2-id
        - subnet-private3-id
        - subnet-public1-id
        - subnet-public2-id
        - subnet-public3-id
  
  MyClusterInstall:
    Type: "AWSQS::OpenShift::Manager"
    Properties:
      Action: "BOOTSTRAP"
      CertificateArn: "arn:....."

Outputs:
  MyInfraName:
      Value: !GetAtt MyClusterInstall.InfrastructureId
  MyKubeConfigLocation:
      Value: !GetAtt MyClusterInstall.KubeConfigArn
   
```

## Development

> Don't modify `models.py` by hand, any modifications will be overwritten when the `generate` or `package` commands are run.

Implement CloudFormation resource here. Each function must always return a ProgressEvent.

```python
ProgressEvent(
    # Required
    # Must be one of OperationStatus.IN_PROGRESS, OperationStatus.FAILED, OperationStatus.SUCCESS
    status=OperationStatus.IN_PROGRESS,
    # Required on SUCCESS (except for LIST where resourceModels is required)
    # The current resource model after the operation; instance of ResourceModel class
    resourceModel=model,
    resourceModels=None,
    # Required on FAILED
    # Customer-facing message, displayed in e.g. CloudFormation stack events
    message="",
    # Required on FAILED: a HandlerErrorCode
    errorCode=HandlerErrorCode.InternalFailure,
    # Optional
    # Use to store any state between re-invocation via IN_PROGRESS
    callbackContext={},
    # Required on IN_PROGRESS
    # The number of seconds to delay before re-invocation
    callbackDelaySeconds=0,
)
```

Failures can be passed back to CloudFormation by either raising an exception from `cloudformation_cli_python_lib.exceptions`, or setting the ProgressEvent's `status` to `OperationStatus.FAILED` and `errorCode` to one of `cloudformation_cli_python_lib.HandlerErrorCode`. There is a static helper function, `ProgressEvent.failed`, for this common case.

## What's with the type hints?

We hope they'll be useful for getting started quicker with an IDE that support type hints. Type hints are optional - if your code doesn't use them, it will still work.
