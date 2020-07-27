"""
Set of utility functions to use with this Resource Provider
"""
import logging
import tarfile
from typing import Optional, Mapping

import boto3
import os
import sys
import urllib
import hashlib
import subprocess

from botocore.exceptions import ClientError

from cloudformation_cli_python_lib import SessionProxy

# Use this logger to forward log messages to CloudWatch Logs.
LOG = logging.getLogger(__name__)
log = LOG  # alias


def write_kubeconfig(session, kubeconfig_id, parent_dir='/tmp/'):
    """
    Fetches kubeconfig from secrets manager and writes to file

    :param session:  Boto3 session
    :param parent_dir: where to install kubeconfig file
    :return str: Path to kubeconfig
    """
    LOG.debug('Fetching KubeConfig from Secrets Manager at %s', kubeconfig_id)
    secrets = session.client('secretsmanager')
    kubeconfig_path = os.path.join('/tmp/', 'kubeconfig')
    kubeconfig = secrets.get_secret_value(SecretId=kubeconfig_id)
    with open(kubeconfig_path, 'w') as f:
        f.write(kubeconfig['SecretString'])
    return kubeconfig_path


def fetch_cert_and_key(session: SessionProxy, certificate_arn, private_key_secret_name):
    """
    Fetches Certificate and Private Key material from Amazon Certificate Manager and Secrets Manager

    :param session: Boto3 session
    :param certificate_arn: Valid ACM ARN
    :param private_key_secret_name: Valid Secrets Manager Name ID
    :return: Certificate, Certificate Chain, Private Key
    """
    secrets = session.client('secretsmanager')
    acm = session.client('acm')
    log.info('Fetching custom Ingress Certificate from ACM ')
    log.debug('ACM ARN: %s', certificate_arn)
    cert_response = acm.get_certificate(CertificateArn=certificate_arn)
    log.debug('Certificate Data: %s', cert_response)
    cert = cert_response['Certificate']
    cert_chain = cert_response['CertificateChain']

    log.info('Fetching custom Ingress Private Key from Secrets Manager')
    log.debug('Secret Name: %s', private_key_secret_name)
    private_key = secrets.get_secret_value(SecretId=private_key_secret_name)['SecretString']
    log.info('Secret fetched successfully')

    return cert, cert_chain, private_key


def verify_sha256sum(filename, sha256sum):
    """
    Takes a filename and runs a SHA256 checksum to validate

    :param filename: The filename to verify
    :param sha256sum: The SHA256 checksum to check against
    :return bool: True if checksum is correct. False, otherwise
    """
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as file:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: file.read(4096), b""):
            sha256_hash.update(byte_block)
    if sha256_hash.hexdigest() == sha256sum:
        return True
    else:
        log.info("File {} SHA256 hash is {}".format(filename, sha256_hash.hexdigest()))
        log.info("Expecting {}".format(sha256sum))
        return False


def url_retreive(url, download_path):
    """
    Fetch a URL helper func

    :param url: The URL to fetch
    :param download_path: Path to download the URL body
    :return None:
    """
    log.debug("Downloading from URL: {} to {}".format(url, download_path))
    try:
        urllib.request.urlretrieve(url, download_path)
    except urllib.error.HTTPError as e:
        log.error("Failed to download {} to {}".format(url, download_path))
        log.error("Error code: {}".format(e))
    except urllib.error.URLError as e:
        log.error("Reason: {}".format(e))
        sys.exit(1)


def parse_sha256sum_file(filename):
    """
    Takes a SHA256 checksum file and returns the values as a dict

    :param filename: The file with SHA256 checksums
    :return Mapping: Check sums from file
    """
    with open(filename, 'r') as file:
        string = file.read()
    string = string.rstrip()
    # Parse file into a dictionary, the file format is
    # shasum  filename\nshasum1  filename1\n...
    tmp_dict = dict(item.split("  ") for item in string.split("\n"))
    # Swap keys and values
    sha256sums = dict((v, k) for k, v in tmp_dict.items())
    return sha256sums


def run_process(cmd):
    """
    Run a command as a sub-process
    :param cmd: Command to run
    :return: The completed sub-process object
    """
    log.debug("running cmd: %s", cmd)
    try:
        proc = subprocess.run([cmd], capture_output=True, shell=True)
        proc.check_returncode()
        log.debug(f'Return code: {proc.returncode}')
        log.debug(f'Stdout: {proc.stdout}')
        log.debug(f'Stderr: {proc.stderr}')
        return proc
    except subprocess.CalledProcessError as e:
        log.error("Error Detected on cmd {} with error {}".format(e.cmd, e.stderr))
        log.error(e.cmd)
        log.error(e.stderr)
        log.error(e.stdout)
        raise
    except OSError as e:
        log.error("Error Detected on cmd {} with error {}".format(e.cmd, e.stderr))
        log.error("OSError: {}".format(e.errno))
        log.error(e.strerror)
        log.error(e.filename)
        raise


def upload_file_to_s3(s3_path, local_path, s3_bucket, session: Optional[SessionProxy]):
    """
    Upload file to S3 bucket helper func

    :param session: Boto SessionProxy
    :param s3_path: Path in S3 to upload the file
    :param local_path: Local path to file
    :param s3_bucket: Name of the S3 bucket
    :return:
    """
    client = session.client('s3')
    log.info("Uploading {} to s3 bucket {}...".format(local_path, os.path.join(s3_bucket, s3_path)))
    try:
        log.debug('Checking if object exists at location %s', s3_path)
        client.head_object(Bucket=s3_bucket, Key=s3_path)
    except ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = e.response['Error']['Code']
        if error_code == '404':
            log.debug('No object found. Continuing to upload')
            return client.upload_file(local_path, s3_bucket, s3_path)
        else:
            log.error('S3 Client Error Code: %s', error_code)
            raise e
    else:
        log.error("File found on S3! %s", s3_path)
        raise RuntimeError("An object already exists in S3 at that location. Please clear out the Ignition location")


def upload_ignition_files_to_s3(local_folder, s3_bucket, session: SessionProxy):
    """
    Push Ignition files up to S3

    :param session: Boto SessionProxy
    :param local_folder: The folder to upload
    :param s3_bucket: Name of the S3 Bucket
    :return None:
    """
    files_to_upload = ['auth/kubeconfig', 'auth/kubeadmin-password', 'master.ign', 'worker.ign', 'bootstrap.ign']
    for file in files_to_upload:
        s3_path = os.path.join(os.path.basename(local_folder), file)
        local_path = os.path.join(local_folder, file)
        upload_file_to_s3(s3_path, local_path, s3_bucket, session)


def delete_contents_s3(s3_bucket, session: SessionProxy, filter: Optional[Mapping] = None):
    """
    Clear out an S3 bucket. Handy for cleaning up if the CF Resource is deleted. Default is to delete all objects from
    the bucket.

    Optionally, pass a filter that is passed as **kwargs to the boto3.Bucket.objects.filter(**kwargs) call
    :param session: Boto SessionProxy
    :param filter: A Mapping of valid Filters for the AWS S3 API action `GetObjects`
    :param s3_bucket: Name of the S3 bucket to delete objects from
    :return None:
    """
    s3 = session.resource('s3')
    bucket = s3.Bucket(s3_bucket)
    try:
        if filter is None:
            log.debug("Deleting bucket {}...".format(s3_bucket))
            bucket.objects.all().delete()
        else:
            bucket.objects.filter(**filter).delete()
    except ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = e.response['Error']['Code']
        if error_code == "NoSuchBucket":
            log.debug("{} does not exist, skipping...".format(s3_bucket))
            return
        else:
            log.error("Failed to delete bucket, unhandled exception {}".format(e))
            raise e
    except Exception as e:
        log.error("Failed to delete bucket, unhandled exception {}".format(e))
        raise e


def get_from_s3(s3_bucket, source, destination):
    """
    Fetch an object from S3 helper func
    :param s3_bucket: Name of the S3 Bucket
    :param source: Key in S3 to fetch
    :param destination: Local location to write the object to
    :return None:
    """
    client = boto3.client('s3')
    if check_file_s3(s3_bucket, key=source):
        client.download_file(s3_bucket, source, destination)


def add_file_to_s3(s3_bucket, body, key, content_type, acl):
    """
    Push a blob to S3 helper func

    :param s3_bucket: Name of the S3 Bucket
    :param body: Content of the object to create
    :param key: Key for the new object in S3
    :param content_type: Object content-type
    :param acl: Any S3 ACL to apply
    :return None:
    """
    client = boto3.client('s3')
    client.put_object(Body=body, Bucket=s3_bucket, Key=key,
                      ContentType=content_type, ACL=acl)


def delete_s3_file(s3_bucket, file_name, session: SessionProxy):
    """
    Delete an individual file object from S3

    :param session: Boto SessionProxy
    :param s3_bucket: Name of the S3 bucket
    :param file_name: Name of object to delete in S3
    :return:
    """
    client = session.client('s3')
    client.delete_object(Bucket=s3_bucket, Key=file_name)


def check_file_s3(s3_bucket, key, session: SessionProxy):
    """
    Check if key exists in S3 bucket
    :param session: Boto SessionProxy
    :param s3_bucket: Name of the S3 bucket to check
    :param key: Object key
    :return:
    """
    client = session.client('s3')
    try:
        client.head_object(Bucket=s3_bucket, Key=key)
        log.debug("File at location {} found".format(key))
        return True
    except Exception as e:
        log.debug("File not found at {} and key {}".format(s3_bucket, key))
        return False


def fetch_openshift_binary(openshift_client_mirror_url, openshift_install_package, openshift_install_binary,
                           download_path):
    """
    Fetch OpenShift binaries

    :param openshift_client_mirror_url: The URL to the OpenShift repository mirror for fetching command binaries
    :param openshift_install_package: The name of the `openshift_install` package
    :param openshift_install_binary: The name of the `openshfit_install` binary
    :param download_path: The path to download OpenShift binaries
    :return str: Location of binaries
    """
    sha256sum_file = 'sha256sum.txt'
    sha256sum_path = os.path.join(download_path, sha256sum_file)
    retries = 1
    url = openshift_client_mirror_url + sha256sum_file
    log.info("Downloading sha256sum file for OpenShift install client...")
    url_retreive(url, sha256sum_path)
    log.debug("Getting SHA256 hash for file %s", sha256sum_path)
    sha256sum_dict = parse_sha256sum_file(sha256sum_path)
    sha256sum = sha256sum_dict[openshift_install_package]

    # Download the openshift install binary only if it doesn't exist and retry download if the sha256sum doesn't match
    i = 0
    url = openshift_client_mirror_url + openshift_install_package
    openshift_install_package_path = os.path.join(download_path, openshift_install_package)
    while i <= retries:
        i += 1
        if os.path.exists(openshift_install_package_path):
            # Verify SHA256 hash
            if verify_sha256sum(openshift_install_package_path, sha256sum):
                log.info("OpenShift install client already exists in %s", openshift_install_package_path)
                break
        log.info("Downloading OpenShift install client...")
        url_retreive(url, openshift_install_package_path)
        if verify_sha256sum(openshift_install_package_path, sha256sum):
            log.info("Successfuly downloaded OpenShift install client...")
            break
    if not os.path.exists(os.path.join(download_path, openshift_install_binary)):
        log.info("Extracting the OpenShift install client...")
        tar = tarfile.open(openshift_install_package_path)
        tar.extractall(path=download_path)
        tar.close()
    return openshift_install_package_path


def terminate_bootstrap_instance(model, session):
    """
    Terminates the bootstrap instance. It is no longer needed after the initial Cluster bootstrap

    :param model: CF Resource model
    :param session: Boto3 session
    """

    client = session.client('ec2')
    cluster_tag = f'tag:kubernetes.io/cluster/{model.InfrastructureId}'
    response = client.describe_instances(Filters=[
        {
            'Name': cluster_tag,
            'Values': ['owned']
        },
        {
            'Name': 'tag:cluster-role',
            'Values': ['bootstrap']
        }
    ])
    if len(response['Reservations']) > 0:
        LOG.info('[DELETE] Deleting Bootstrap nodes %s', response['Reservations'])
        client.terminate_instances(
            InstanceIds=[bootstrap_instance['Instances'][0]['InstanceId'] for bootstrap_instance in response['Reservations']]
        )
    else:
        LOG.info('[DELETE] No Worker nodes to delete')
