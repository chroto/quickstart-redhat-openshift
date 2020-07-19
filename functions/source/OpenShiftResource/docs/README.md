# AWSQS::OpenShift::Manager

Manages an OpenShift Cluster. Generates Ignition Configuation to help with installation or manages the bootstrap process

## Syntax

To declare this entity in your AWS CloudFormation template, use the following syntax:

### JSON

<pre>
{
    "Type" : "AWSQS::OpenShift::Manager",
    "Properties" : {
        "<a href="#loglevel" title="LogLevel">LogLevel</a>" : <i>String</i>,
        "<a href="#action" title="Action">Action</a>" : <i>String</i>,
        "<a href="#workernodesize" title="WorkerNodeSize">WorkerNodeSize</a>" : <i>Double</i>,
        "<a href="#clustername" title="ClusterName">ClusterName</a>" : <i>String</i>,
        "<a href="#openshiftmirrorurl" title="OpenShiftMirrorURL">OpenShiftMirrorURL</a>" : <i>String</i>,
        "<a href="#openshiftversion" title="OpenShiftVersion">OpenShiftVersion</a>" : <i>String</i>,
        "<a href="#openshiftclientbinary" title="OpenShiftClientBinary">OpenShiftClientBinary</a>" : <i>String</i>,
        "<a href="#openshiftinstallbinary" title="OpenShiftInstallBinary">OpenShiftInstallBinary</a>" : <i>String</i>,
        "<a href="#ignitionbucket" title="IgnitionBucket">IgnitionBucket</a>" : <i>String</i>,
        "<a href="#pullsecret" title="PullSecret">PullSecret</a>" : <i>String</i>,
        "<a href="#sshkey" title="SSHKey">SSHKey</a>" : <i>String</i>,
        "<a href="#awsaccesskeyid" title="AwsAccessKeyId">AwsAccessKeyId</a>" : <i>String</i>,
        "<a href="#awssecretaccesskey" title="AwsSecretAccessKey">AwsSecretAccessKey</a>" : <i>String</i>,
        "<a href="#workerinstanceprofilename" title="WorkerInstanceProfileName">WorkerInstanceProfileName</a>" : <i>String</i>,
        "<a href="#hostedzonename" title="HostedZoneName">HostedZoneName</a>" : <i>String</i>,
        "<a href="#availabilityzones" title="AvailabilityZones">AvailabilityZones</a>" : <i>[ String, ... ]</i>,
        "<a href="#subnets" title="Subnets">Subnets</a>" : <i>[ String, ... ]</i>,
        "<a href="#clusteringressprivatekeysecretname" title="ClusterIngressPrivateKeySecretName">ClusterIngressPrivateKeySecretName</a>" : <i>String</i>,
        "<a href="#infrastructurename" title="InfrastructureName">InfrastructureName</a>" : <i>String</i>,
    }
}
</pre>

### YAML

<pre>
Type: AWSQS::OpenShift::Manager
Properties:
    <a href="#loglevel" title="LogLevel">LogLevel</a>: <i>String</i>
    <a href="#action" title="Action">Action</a>: <i>String</i>
    <a href="#workernodesize" title="WorkerNodeSize">WorkerNodeSize</a>: <i>Double</i>
    <a href="#clustername" title="ClusterName">ClusterName</a>: <i>String</i>
    <a href="#openshiftmirrorurl" title="OpenShiftMirrorURL">OpenShiftMirrorURL</a>: <i>String</i>
    <a href="#openshiftversion" title="OpenShiftVersion">OpenShiftVersion</a>: <i>String</i>
    <a href="#openshiftclientbinary" title="OpenShiftClientBinary">OpenShiftClientBinary</a>: <i>String</i>
    <a href="#openshiftinstallbinary" title="OpenShiftInstallBinary">OpenShiftInstallBinary</a>: <i>String</i>
    <a href="#ignitionbucket" title="IgnitionBucket">IgnitionBucket</a>: <i>String</i>
    <a href="#pullsecret" title="PullSecret">PullSecret</a>: <i>String</i>
    <a href="#sshkey" title="SSHKey">SSHKey</a>: <i>String</i>
    <a href="#awsaccesskeyid" title="AwsAccessKeyId">AwsAccessKeyId</a>: <i>String</i>
    <a href="#awssecretaccesskey" title="AwsSecretAccessKey">AwsSecretAccessKey</a>: <i>String</i>
    <a href="#workerinstanceprofilename" title="WorkerInstanceProfileName">WorkerInstanceProfileName</a>: <i>String</i>
    <a href="#hostedzonename" title="HostedZoneName">HostedZoneName</a>: <i>String</i>
    <a href="#availabilityzones" title="AvailabilityZones">AvailabilityZones</a>: <i>
      - String</i>
    <a href="#subnets" title="Subnets">Subnets</a>: <i>
      - String</i>
    <a href="#clusteringressprivatekeysecretname" title="ClusterIngressPrivateKeySecretName">ClusterIngressPrivateKeySecretName</a>: <i>String</i>
    <a href="#infrastructurename" title="InfrastructureName">InfrastructureName</a>: <i>String</i>
</pre>

## Properties

#### LogLevel

Set the log level for Lambda events to CloudWatch

_Required_: No

_Type_: String

_Allowed Values_: <code>DEBUG</code> | <code>INFO</code>

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### Action

The Management action to take. Must be one of COMMAND, INSTALL, or WAIT

_Required_: Yes

_Type_: String

_Allowed Values_: <code>BOOTSTRAP</code> | <code>GENERATE_IGNITION</code>

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### WorkerNodeSize

The size of the initial worker cluster. This can be resized later

_Required_: No

_Type_: Double

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### ClusterName

The unique identifier for the OpenShift cluster

_Required_: No

_Type_: String

_Pattern_: <code>^[a-zA-Z0-9_-]+$</code>

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### OpenShiftMirrorURL

The mirror URL for OpenShift binaries

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### OpenShiftVersion

The version of OpenShift to install

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### OpenShiftClientBinary

The OpenShift client name

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### OpenShiftInstallBinary

The OpenShift install program name

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### IgnitionBucket

The S3 Bucket name to use for storing Ignition files

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### PullSecret

The RedHat Pull Secret required to fetch OpenShift container images

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### SSHKey

A public SSH key to add to the OpenShift. Required for administrative SSH access

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### AwsAccessKeyId

An AWS Access Key ID for the cluster to use to manage AWS resources like Ingress ELBs

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### AwsSecretAccessKey

An AWS Secret Access Key for the cluster to use to manage AWS resources like Ingress ELBs

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### WorkerInstanceProfileName

An IAM instance profile to set on Worker nodes

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### HostedZoneName

The DNS zone for this cluster

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### AvailabilityZones

List of all availability zones. Must pick at least 3

_Required_: No

_Type_: List of String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### Subnets

List of all subnets for the cluster. Add both public and private subnets

_Required_: No

_Type_: List of String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### ClusterIngressPrivateKeySecretName

The AWS Secrets Manager name identifier for the private key used to sign ClusterIngressCertificateArn. The Secret String must be PEM encoded

_Required_: No

_Type_: String

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

#### InfrastructureName

The unique identifier for the OpenShift cluster

_Required_: No

_Type_: String

_Pattern_: <code>^[a-zA-Z0-9_-]+$</code>

_Update requires_: [No interruption](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-updating-stacks-update-behaviors.html#update-no-interrupt)

## Return Values

### Fn::GetAtt

The `Fn::GetAtt` intrinsic function returns a value for a specified attribute of this type. The following are the available attributes and sample return values.

For more information about using the `Fn::GetAtt` intrinsic function, see [Fn::GetAtt](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html).

#### KubeAdminPasswordArn

Returns the <code>KubeAdminPasswordArn</code> value.

#### InfrastructureId

The unique identifier for the OpenShift cluster

#### KubeConfigArn

Returns the <code>KubeConfigArn</code> value.

