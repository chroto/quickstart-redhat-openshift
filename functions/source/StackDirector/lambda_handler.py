import urllib.request
import urllib.error
from ruamel import yaml
import cfnresponse
import os
import logging
import sys
import hashlib
import tarfile
import boto3
from botocore.exceptions import ClientError
import subprocess
import time
import json

log = logging.getLogger(__name__)


def handler(event, context):
    """
    The main Lambda handler
    """
    status = cfnresponse.SUCCESS
    data = {}
    cluster_info = {
        'status': 'complete'
    }
    level = logging.getLevelName(os.getenv('LogLevel'))
    log.setLevel(level)
    log.debug(event)

    subnets = event["ResourceProperties"]["Subnets"]
    availability_zones = event["ResourceProperties"]["AvailabilityZones"]
    s3_bucket = os.getenv('AuthBucket')
    cluster_name = os.getenv('ClusterName')
    hosted_zone_name = os.getenv('HostedZoneName')
    openshift_user_access_key = os.getenv('AwsAccessKeyId')
    openshift_user_secret_access_key = os.getenv('AwsSecretAccessKey')
    openshift_client_base_mirror_url = os.getenv('OpenShiftMirrorURL')
    openshift_version = os.getenv('OpenShiftVersion')
    openshift_client_binary = os.getenv('OpenShiftClientBinary')
    openshift_install_binary = os.getenv('OpenShiftInstallBinary')

    file_extension = '.tar.gz'
    cluster_data = {"cluster_name": cluster_name,
                    "openshift_version": openshift_version,
                    "clusters_information": {}}
    stack_dict = {}

    if not event.get('RequestType') == 'Delete':
        stack_dict = build_stack_dict(cluster_name,
                                      hosted_zone_name,
                                      s3_bucket,
                                      openshift_version)
    if sys.platform == 'darwin':
        openshift_install_os = '-mac-'
    else:
        openshift_install_os = '-linux-'
    openshift_client_package = openshift_client_binary + openshift_install_os + openshift_version + file_extension
    openshift_client_mirror_url = openshift_client_base_mirror_url + openshift_version + "/"
    download_path = '/tmp/'
    log.info("Cluster name: " + os.getenv('ClusterName'))

    # We are in the Deploy CloudFormation event
    if 'RequestType' in event.keys():
        try:
            if event['RequestType'] == 'Delete':
                pass
                #                waiter_array = []
                #                wait_for_state = "stack_delete_complete"
                #                log.info("Deleting all stacks in {} deployment'.format(cluster_name)")
                delete_contents_s3(s3_bucket=s3_bucket)
            ##                delete_stack(cluster_name)
            #                waiter_array.append({
            #                    "stack_name": cluster_name,
            #                    "stack_state": wait_for_state })
            #                # TODO: If the stack is in state other than
            #                # 'DELETE_IN_PROGRESS' then the lambda will timeout waiting on
            #                # 'stack_delete_complete' state
            #                wait_for_stack_state(waiter_array)
            elif event['RequestType'] == 'Update':
                log.info("Update sent, however, this is unsupported at this time.")
                pass
            else:
                #                cf_client = boto3.client('cloudformation')
                cf_params = parse_properties(event['ResourceProperties'])
                log.info("Delete and Update not detected, proceeding with Create")

                pull_secret = os.environ.get('PullSecret')
                ssh_key = os.environ.get('SSHKey')
                openshift_install_package = openshift_install_binary \
                                            + openshift_install_os \
                                            + openshift_version \
                                            + file_extension
                log.info("Generating OCP installation files for cluster " + cluster_name)
                install_dependencies(openshift_client_mirror_url,
                                     openshift_install_package,
                                     openshift_install_binary,
                                     download_path)
                # The only status is either building or complete, skip if either is found
                if not stack_dict["status"]:
                    build_array = []
                    log.debug("STACK: {}".format(stack_dict))
                    cluster_name = stack_dict["name"]
                    building_key = os.path.join(cluster_name, "building")
                    local_folder = download_path + cluster_name
                    data['InfrastructureName'], data['KubeAdminPassword'] = generate_ignition_files(
                        openshift_install_binary, download_path,
                        cluster_name, ssh_key, pull_secret,
                        hosted_zone_name, subnets, availability_zones,
                        openshift_user_access_key, openshift_user_secret_access_key
                    )
                    upload_ignition_files_to_s3(local_folder, s3_bucket)
                    save_cfparams_json(cf_params=cf_params,
                                       s3_bucket=s3_bucket,
                                       cluster_name=cluster_name)
                    cf_params["StackName"] = stack_dict["name"]
                    build_array.append(cf_params)
                    log.debug(build_array)
                    stack_dict["status"] = "building"
                    add_file_to_s3(s3_bucket=s3_bucket, body="building", key=building_key,
                                   content_type="text/plain", acl="private")

            log.info("Complete")
        except Exception:
            logging.error('Unhandled exception', exc_info=True)
            status = cfnresponse.FAILED
        finally:
            cfnresponse.send(event, context, status, data, None)
    else:
        try:
            install_dependencies(openshift_client_mirror_url,
                                 openshift_client_package,
                                 openshift_client_binary,
                                 download_path)
            failed_clusters = []
            if stack_dict["status"] == "complete":
                log.debug("Stack complete {}".format(stack_dict["name"]))
            elif not cluster_available(url=stack_dict["api_url"]):
                failed_clusters.append(stack_dict["name"])
            elif scale_ocp_replicas(s3_bucket, stack_dict["name"], stack_dict["status"]):
                stack_dict["status"] = "complete"
            else:
                log.debug("Stack failed {}".format(stack_dict["name"]))
                failed_clusters.append(stack_dict["name"])
            if len(failed_clusters) == 0:
                deactivate_event(cluster_name)
            else:
                log.debug("failed_clusters = {}".format(failed_clusters))
        except Exception:
            logging.error('Unhandled exception', exc_info=True)


def parse_properties(properties):
    cf_params = {'Capabilities': ['CAPABILITY_IAM',
                                  'CAPABILITY_AUTO_EXPAND',
                                  'CAPABILITY_NAMED_IAM'],
                 'DisableRollback': True
                 }
    cf_params["Parameters"] = []
    for key, value in properties.items():
        if key == "TemplateURL":
            cf_params["TemplateURL"] = value
        elif key == "StackName":
            cf_params["StackName"] = value
        elif key == "KeyToUpdate":
            cf_params["KeyToUpdate"] = value
        elif key == "ServiceToken" or key == "Function" or key == "NumStacks":
            log.debug("Skipping over unneeded keys")
        else:
            temp = {'ParameterKey': key, 'ParameterValue': value}
            log.debug(temp)
            cf_params["Parameters"].append(temp)
    return cf_params


def get_kubeadmin_pass(s3_bucket, cluster_name):
    kubeadmin_file = os.path.join(cluster_name, "auth/kubeadmin-password")
    local_kubeadmin_file = os.path.join("/tmp", cluster_name + "-admin")
    get_from_s3(s3_bucket, source=kubeadmin_file, destination=local_kubeadmin_file)
    try:
        cur_file = open(local_kubeadmin_file, "r")
        return cur_file.read()
    except Exception as e:
        log.info("Unable to open and read file")
        return "not found"


def save_cfparams_json(cf_params, s3_bucket, cluster_name):
    cf_params["StackName"] = cluster_name
    cf_params_json = os.path.join(cluster_name, "cf_params.json")
    add_file_to_s3(s3_bucket=s3_bucket,
                   body=json.dumps(cf_params),
                   key=cf_params_json,
                   content_type="text/json",
                   acl="private")


def build_stack_dict(cluster_name, hosted_zone_name, s3_bucket, openshift_version):
    building_key = os.path.join(cluster_name, "building")
    complete_key = os.path.join(cluster_name, "completed")
    fqdn_cluster_name = cluster_name + "." + hosted_zone_name
    stack_dict = {"name": cluster_name,
                  "ssh_url": "ssh.{}.{}".format(cluster_name, hosted_zone_name),
                  "status": ""
                  }
    if openshift_version != "3":
        stack_dict["console_url"] = "https://console-openshift-console.apps.{}.{}".format(cluster_name,
                                                                                          hosted_zone_name)
        stack_dict["api_url"] = "https://api.{}:6443".format(fqdn_cluster_name)
    else:
        stack_dict["console_url"] = "https://{}.{}:8443/console".format(cluster_name, hosted_zone_name)
    if check_file_s3(s3_bucket=s3_bucket, key=building_key):
        stack_dict["status"] = "building"
        stack_dict["kubeadmin_password"] = get_kubeadmin_pass(s3_bucket, cluster_name)
    elif check_file_s3(s3_bucket=s3_bucket, key=complete_key):
        stack_dict["status"] = "complete"
        stack_dict["kubeadmin_password"] = get_kubeadmin_pass(s3_bucket, cluster_name)
    log.debug("STACK DICTIONARY: {}".format(stack_dict))
    return stack_dict


def install_dependencies(openshift_client_mirror_url, openshift_install_package, openshift_install_binary,
                         download_path):
    sha256sum_file = 'sha256sum.txt'
    retries = 1
    url = openshift_client_mirror_url + sha256sum_file
    log.info("Downloading sha256sum file for OpenShift install client...")
    url_retreive(url, download_path + sha256sum_file)
    log.debug("Getting SHA256 hash for file {}".format(download_path + sha256sum_file))
    sha256sum_dict = parse_sha256sum_file(download_path + sha256sum_file)
    sha256sum = sha256sum_dict[openshift_install_package]

    # Download the openshift install binary only if it doesn't exist and retry download if the sha256sum doesn't match

    i = 0
    url = openshift_client_mirror_url + openshift_install_package
    while i <= retries:
        i += 1
        if os.path.exists(download_path + openshift_install_package):
            # Verify SHA256 hash
            if verify_sha256sum(download_path + openshift_install_package, sha256sum):
                log.info(
                    "OpenShift install client already exists in {}".format(download_path + openshift_install_package))
                break
        log.info("Downloading OpenShift install client...")
        url_retreive(url, download_path + openshift_install_package)
        if verify_sha256sum(download_path + openshift_install_package, sha256sum):
            log.info("Successfuly downloaded OpenShift install client...")
            break
    if not os.path.exists(download_path + openshift_install_binary):
        log.info("Extracting the OpenShift install client...")
        tar = tarfile.open(download_path + openshift_install_package)
        tar.extractall(path=download_path)
        tar.close()


def url_retreive(url, download_path):
    log.debug("Downloading from URL: {} to {}".format(url, download_path))
    try:
        response = urllib.request.urlretrieve(url, download_path)
    except urllib.error.HTTPError as e:
        log.error("Failed to download {} to {}".format(url, download_path))
        log.error("Error code: {}".format(e))
    except urllib.error.URLError as e:
        log.error("Reason: {}".format(e))
        sys.exit(1)


def parse_sha256sum_file(filename):
    with open(filename, 'r') as file:
        string = file.read()
    string = string.rstrip()
    # Parse file into a dictionary, the file format is
    # shasum  filename\nshasum1  filename1\n...
    tmp_dict = dict(item.split("  ") for item in string.split("\n"))
    # Swap keys and values
    sha256sums = dict((v, k) for k, v in tmp_dict.items())
    return sha256sums


def verify_sha256sum(filename, sha256sum):
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


def generate_ignition_files(openshift_install_binary, download_path, cluster_name, ssh_key, pull_secret,
                            hosted_zone_name, subnets, availability_zones, aws_access_key_id, aws_secret_access_key):
    assets_directory = download_path + cluster_name
    install_config_file = 'install-config.yaml'
    log.debug("Creating OpenShift assets directory for {}...".format(cluster_name))
    if not os.path.exists(assets_directory):
        os.mkdir(assets_directory)
    log.info("Generating install-config file for {}...".format(cluster_name))
    with open(install_config_file) as f:
        for line in f.readlines():
            log.debug(line)
    openshift_install_config = yaml.safe_load(open(install_config_file, 'r'))
    openshift_install_config['metadata']['name'] = cluster_name
    openshift_install_config['sshKey'] = ssh_key
    openshift_install_config['pullSecret'] = pull_secret
    openshift_install_config['baseDomain'] = hosted_zone_name
    openshift_install_config['platform']['aws']['subnets'] = subnets
    openshift_install_config['platform']['aws']['region'] = os.getenv('AWS_REGION')
    openshift_install_config['controlPlane']['platform']['aws']['zones'] = availability_zones
    openshift_install_config['compute'][0]['platform']['aws']['zones'] = availability_zones

    cluster_install_config_file = os.path.join(assets_directory, install_config_file)
    # Using this to get around the ssh-key multiline issue in yaml
    yaml.dump(openshift_install_config,
              open(cluster_install_config_file, 'w'),
              explicit_start=True, default_style='\"',
              width=4096)
    original_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    original_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    session_token = os.getenv('AWS_SESSION_TOKEN')
    try:
        os.putenv('AWS_ACCESS_KEY_ID', aws_access_key_id)
        os.putenv('AWS_SECRET_ACCESS_KEY', aws_secret_access_key)
        os.putenv('AWS_SESSION_TOKEN', '')
        log.info("Generating manifests for {}...".format(cluster_name))
        cmd = download_path + openshift_install_binary + " create manifests --dir {}".format(assets_directory)
        run_process(cmd)
        log.info('Deleting Master Machinesets from Manifests')
        import glob
        control_plane_manifests = glob.glob(
            os.path.join(assets_directory, 'openshift', '99_openshift-cluster-api_master-machines-*.yaml')
        )
        for manifest in control_plane_manifests:
            os.remove(manifest)
        log.info("Generating ignition files for {}...".format(cluster_name))
        cmd = download_path + openshift_install_binary + " create ignition-configs --dir {}".format(assets_directory)
        run_process(cmd)
    finally:
        os.putenv('AWS_ACCESS_KEY_ID', original_access_key_id)
        os.putenv('AWS_SECRET_ACCESS_KEY', original_secret_access_key)
        os.putenv('AWS_SESSION_TOKEN', session_token)
    with open(os.path.join(assets_directory, 'metadata.json')) as f:
        metadata = json.load(f)
        infra_name = metadata['infraID']
    with open(os.path.join(assets_directory, 'auth', 'kubeadmin-password')) as f:
        kubeadmin_password = f.read().strip()
    return infra_name, kubeadmin_password


def run_process(cmd):
    try:
        proc = subprocess.run([cmd], capture_output=True, shell=True)
        proc.check_returncode()
        log.debug(proc.returncode)
        log.debug(proc.stdout)
        log.debug(proc.stderr)
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


def upload_file_to_s3(s3_path, local_path, s3_bucket):
    client = boto3.client('s3')
    log.info("Uploading {} to s3 bucket {}...".format(local_path, os.path.join(s3_bucket, s3_path)))
    try:
        client.head_object(Bucket=s3_bucket, Key=s3_path)
        log.debug("File found on S3! Skipping {}...".format(s3_path))
    except:
        client.upload_file(local_path, s3_bucket, s3_path)


def upload_ignition_files_to_s3(local_folder, s3_bucket):
    files_to_upload = ['auth/kubeconfig', 'auth/kubeadmin-password', 'master.ign', 'worker.ign', 'bootstrap.ign']
    for file in files_to_upload:
        s3_path = os.path.join(os.path.basename(local_folder), file)
        local_path = os.path.join(local_folder, file)
        upload_file_to_s3(s3_path, local_path, s3_bucket)


def delete_contents_s3(s3_bucket):
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket)
    try:
        log.debug("Deleting bucket {}...".format(s3_bucket))
        bucket.objects.all().delete()
    except ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = e.response['Error']['Code']
        if error_code == "NoSuchBucket":
            log.debug("{} does not exist, skipping...".format(s3_bucket))
            return
        else:
            log.error("Failed to delete bucket, unhandled exception {}".format(e))
    except Exception as e:
        log.error("Failed to delete bucket, unhandled exception {}".format(e))


def get_from_s3(s3_bucket, source, destination):
    client = boto3.client('s3')
    if check_file_s3(s3_bucket, key=source):
        client.download_file(s3_bucket, source, destination)


def add_file_to_s3(s3_bucket, body, key, content_type, acl):
    client = boto3.client('s3')
    client.put_object(Body=body, Bucket=s3_bucket, Key=key,
                      ContentType=content_type, ACL=acl)


def delete_s3_file(s3_bucket, file_name):
    client = boto3.client('s3')
    client.delete_object(Bucket=s3_bucket, Key=file_name)


def check_file_s3(s3_bucket, key):
    client = boto3.client('s3')
    try:
        client.head_object(Bucket=s3_bucket, Key=key)
        log.debug("File at location {} found".format(key))
        return True
    except Exception as e:
        log.debug("File not found at {} and key {}".format(s3_bucket, key))
        return False


def cluster_available(url):
    response = False
    try:
        log.debug("Checking cluster API at {}".format(url))
        urllib.request.urlopen(url)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in e.reason.strerror:
            response = True
            log.debug("Cluster is reachable at {}".format(url))
    except:
        log.error("Unhandled exception, cluster must not be ready")
    return response


def scale_ocp_replicas(s3_bucket, cluster_name, status):
    complete_key = os.path.join(cluster_name, "completed")
    building_key = os.path.join(cluster_name, "building")
    kubeconfig_file = os.path.join(cluster_name, "auth/kubeconfig")
    local_kubeconfig_file = os.path.join("/tmp", cluster_name + "kubeconfig")
    get_from_s3(s3_bucket, kubeconfig_file, local_kubeconfig_file)
    cmd = "./bin/openshift-4-scale-replicas {}".format(local_kubeconfig_file)
    try:
        run_process(cmd)
        # If the scale replicas script ran correctly, the status is now complete
        if status == "building":
            delete_s3_file(s3_bucket, building_key)
        add_file_to_s3(s3_bucket=s3_bucket, body="completed", key=complete_key,
                       content_type="text/plain", acl="private")
        return True
    except Exception as e:
        log.error(e)
        log.error("Unhandled Exception")
        return False


def deactivate_event(cluster_name):
    log.info("Deactivating event")
    client = boto3.client('events')
    event_name = cluster_name + "-ValidateEvent"
    response = client.disable_rule(Name=event_name)
    log.debug(response)
