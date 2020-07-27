"""
AWSQS::OpenShift::Manager Resource Provider

Provides handlers for an OpenShift CloudFormation resource

Supports the following Actions:

* GENERATE_IGNITION: Creates ignition configuration files for use with a User-Provided Infrastructure Deployment of
OpenShift 4.x. Generated files are uploaded to a user-provided S3 Bucket and Cluster auth data is stored as SSM
Parameters and Secrets Manager secrets. The DELETE handler deletes these generated resources.

* BOOTSTRAP: Monitors the Cluster bootstrap process and manages any necessary Infrastructure or Cluster-config changes.
On DELETE, the resource provider attempts to clean up any cluster-managed infrastructure that OpenShift created during
its initial boot-up.


"""
