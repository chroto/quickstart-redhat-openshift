# Development notes for OpenShift4 Quick Start

Features and Changes:
- Adds Resource Provider: `AWSQS::OpenShift::Manager`
- Adds support for OpenShift 4.x installation
- Backwards compatible with previous 3.x installations
- Multi-AZ (3) Deployment with OpenShift managed MachineSets
- BYO VPC Configuration or auto-generate VPC
- BYO Application SSL Certificates (via Amazon Certificate Manager) or auto-generate an ACM certificate
- BYO IAM Roles for Worker and Control Plane nodes
- Installation Logs and Metrics delivered to AWS CloudWatch
- KubeConfig is stored in Secrets Manager to help integrate w/ AWSQS::Kubernetes::Helm
- Removed CI directory in favor of .taskcat.yml file in order to match patterns from other Quickstart projects
- Split existing /non-existing VPC paths into two separate master templates

# Live Demo

<https://console-openshift-console.apps.openshift4-useast1.t3-osqs43.openshift.awsworkshop.io/>

Built with following settings:
* BYO VPC
* BYO ACM Certificate (*.apps.openshift4-useast1.t3-osqs43.openshift.awsworkshop.io)
* BYO Cluster Ingress cert (for OAuth any other "passthrough" services; uses LetsEncrypt test certificate)
* `kubeadmin` and `kubeconfig` located in AWS Secrets Manager

# Before Starting

- You must provision a RedHat Pull Secret
- Install `taskcat` (if using)
- Create an S3 Bucket for uploading the QuickStart templates

# Installation Examples

## Required Parameters

Setting the following parameters will perform a basic OpenShift4 installation.
A VPC and ACM Certificate will be created for you. OpenShift's operators will
take care of setting up much of the AWS infrastructure on your behalf.

**Note** The Cluster Login (OAuth) page can not use the ACM certificate in this
configuration. To use a trusted CA signed certificate for the Cluster Login you
must set  `ClusterIngressPrivateKeySecretName` and
`ClusterIngressCertificateArn`

- **ClusterName**: Name of the cluster
- **AvailabilityZones**: List of valid AZs
- **DomainName**: Base domain name of the cluster. Full cluster domain will be ${ClusterName}.${DomainName}
- **HostedZoneId** (optional, but recommended): Route53 Public Zone for DNS
- **PullSecret**: Redhat Pull Secret JSON
- **QSS3BucketName** (optional after quickstart is public release): S3 Bucket where these quickstart templates exist
- **QSSKeyPrefix** (optional after quickstart is public release): S3 Prefix where these quickstart templates exist


## BYO VPC

Instead of letting the QuickStart templates create a VPC, you can optionally provide a VPC ID and Subnet IDs. You must
provide valid Public/Private subnets for the availability zones parameter.

- **ClusterName**: Name of the cluster
- **AvailabilityZones**: List of valid AZs
- **DomainName**: Base domain name of the cluster. Full cluster domain will be ${ClusterName}.${DomainName}
- **HostedZoneId** (optional, but recommended): Route53 Public Zone for DNS
- **PullSecret**: Redhat Pull Secret JSON
- **QSS3BucketName** (optional after quickstart is public release): S3 Bucket where these quickstart templates exist
- **QSSKeyPrefix** (optional after quickstart is public release): S3 Prefix where these quickstart templates exist
- **VPCID**: VPC ID
- **PublicSubnet1ID**: Public Subnet in AZ-1
- **PublicSubnet2ID**: Public Subnet in AZ-2
- **PublicSubnet3ID**: Public Subnet in AZ-3
- **PrivateSubnet1ID**: Private Subnet in AZ-1
- **PrivateSubnet2ID**: Private Subnet in AZ-2
- **PrivateSubnet3ID**: Private Subnet in AZ-3

## BYO SSL Certificates

Instead of auto-generating ACM certificates, you can pass in an ACM ARN for both the Applications endpoint (where all
user-defined applications are accessible) and the OAuth login endpoint (which must use the internal Cluster certificate)

- **ClusterName**: Name of the cluster
- **AvailabilityZones**: List of valid AZs
- **DomainName**: Base domain name of the cluster. Full cluster domain will be ${ClusterName}.${DomainName}
- **HostedZoneId** (optional, but recommended): Route53 Public Zone for DNS
- **PullSecret**: Redhat Pull Secret JSON
- **QSS3BucketName** (optional after quickstart is public release): S3 Bucket where these quickstart templates exist
- **QSSKeyPrefix** (optional after quickstart is public release): S3 Prefix where these quickstart templates exist
- **CertificateArn**: An ACM Certificate ARN for the Applications (default) endpoint
- **ClusterIngressCertificateArn**: An **imported** ACM certificate ARN that is signed by a trusted public CA. 
  Use if you need a valid, trusted certificate imported into the Cluster so the OAuth endpoint has a valid cert. 
  See <https://access.redhat.com/solutions/4922421> for more info.
- **ClusterIngressPrivateKeySecretName**: An Amazon Secrets Manager Secret Name for the Private Key portion (PEM) of
  `ClusterIngressCertificateArn`

## BYO IAM Roles


- **ClusterName**: Name of the cluster
- **AvailabilityZones**: List of valid AZs
- **DomainName**: Base domain name of the cluster. Full cluster domain will be ${ClusterName}.${DomainName}
- **HostedZoneId** (optional, but recommended): Route53 Public Zone for DNS
- **PullSecret**: Redhat Pull Secret JSON
- **QSS3BucketName** (optional after quickstart is public release): S3 Bucket where these quickstart templates exist
- **QSSKeyPrefix** (optional after quickstart is public release): S3 Prefix where these quickstart templates exist
- **WorkerInstanceProfileName**: Valid IAM Instance profile for all Worker nodes
- **MasterInstanceProfileName**: Valid IAM Instance profile for all control plane nodes


## Sample `.taskcat_overrides.yml`

```yaml

OpenshiftContainerPlatformVersion: '4.3'
QSS3BucketName: awsqs-cproto-aws-ocp-cft-test
QSS3KeyPrefix: aws-ocp/

MasterInstanceProfileName: ocp4-testing-byo-iam-testcase-master
WorkerInstanceProfileName: ocp4-testing-byo-iam-testcase-worker
RemoteAccessCIDR: 73.180.173.93/32
ContainerAccessCIDR: 73.180.173.93/32
MasterInstanceType: m4.xlarge
NodesInstanceType: m4.large
HostedZoneID: Z00493972ENBG5355MNQ
DomainName: t3-osqs43.openshift.awsworkshop.io
SubDomainPrefix: ''
ClusterName: openshift4-useast1
SSHKey: "ssh-rsa AAAAB3N ...."
CertificateArn: arn:aws:acm:us-east-1:755152575036:certificate/3576aff3-b8df-4bdc-9e69-0c3267d55624
ClusterIngressCertificateArn: arn:aws:acm:us-east-1:755152575036:certificate/19f29c88-ad72-419a-858a-f514fddd48c9
ClusterIngressPrivateKeySecretName: letsencrypt-openshfit4-quickstart-test
VPCID: vpc-0f6104af212e83bd4
PublicSubnet1ID: subnet-0adeaaebcbca6259b
PublicSubnet2ID: subnet-0c49657d6e9350777
PublicSubnet3ID: subnet-0ca4120a3b64e1859
PrivateSubnet1ID: subnet-0d26862efc2d8f831
PrivateSubnet2ID: subnet-0686a56576313e36e
PrivateSubnet3ID: subnet-044cba7bbe98a87e7
PullSecret: '{"auths":{"cloud.openshift.com":{"auth": ......

```

# Code re-organization FYIs

- Created sub-directories to organize common, os3, and os4 templates
- More os3 resources broken up into nested child stacks
- OS4 built with more child stacks
- Custom Resource Provider manages the Cluster installation. Uses two instances of the provider. one to manage the
  Ignition File generation and a second instance to monitor and manage the Cluster bootstrap.

# Custom Resource Provider

Installation instructions located in [README](resource_providers/openshift-resource-provider/README.md)

# Differences between OS3 and OS4 Quickstarts

- Installation process is vastly different. OS3 uses a set of Ansible playbooks
  to configure the cluster. OS4 uses Ignition and a Bootstrap server to
  initiate the cluster
- OS4 is more tightly coupled with the AWS environment and is aware of AWS
  resources. During installation, OS4 will automatically set up the AWS
  resources it needs (loadbalancer, security groups)
- OS4 installation is managed by a custom resource Lambda. This Lambda uses the
  Openshift4 tools (`oc` and `openshift-install` ) to run the commands that
  normally would be manual steps in the install process
- OS4 requires a set of AWS Access keys at installation and uses these keys
  throughout the lifecycle of the cluster. This identity is used to manage
  networking resources that OpenShift needs to control in order to intgerate
  with AWS
- OS4 must use its own managed LoadBalancer for application routes (the
  services routed at `*.apps`). Because of this, there are more considerations
  for setting up the ACM SSL certificate than in OS3 (see `BYO Certificates`
      below)
- OS4 kubeadmin password is auto-generated and stored in AWS Secrets Manager
- Architecture: mostly similar except that ETCD is now located on the Control
  Plane
- Using a KeyPairName is deprecated in OS4. A public ssh key must be passed
  instead
- GlusterFS is no longer used in OS4
- Hawkular metrics is no longer used in OS4

# Feature Tasks

## BYO IAM Profiles / Roles

**DONE** 


- [x] Add parameters for iam roles and profiles
- [x] Set up conditionals
- [x] Use ARNs if exist, otherwise generate

Tested 06-01

## Multiple AZ Deployment

**DONE**

## Define machine set for each AZ

**DONE** -- Autoscaling is not configured by default . up to cluster operator to set up autoscaling .

Autoscale testing was completed 05-26 . We can supply documentation on how to
set up autoscaling after cluster is set up

## Take VPC details as parameter

**DONE** --

Tested 05-28

## BYO Certificates

This process was tested 06-14

See <https://access.redhat.com/solutions/4922421> for solution

# TODOs

- [x] Allow users to select number of Worker nodes at install
- [x] Custom resource provider for OPenshift4 installer
- [x] Create AWS Secret in Openshift4 installer. Fetches Kubeconfig
- [x] Known Bug: the first time we request a certificate for a new subdomain /
  clustername, the `*.apps` wildcard validation CNAME DNS record doesn't get created. no errors?
- [x] Be more efficient with Custom Lambdas Stack -- not all the functions need to be created for OS4
- [x] Test some Helm Custom resources
- [x] Delete Openshift resources on delete events: IntDNS records, Security Groups, Loadbalancers -- all findable by Tags
