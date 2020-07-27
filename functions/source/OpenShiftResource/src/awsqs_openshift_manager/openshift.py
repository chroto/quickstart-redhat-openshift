import glob
import re
import subprocess
import json
import logging
import os

from ruamel import yaml

# Use this logger to forward log messages to CloudWatch Logs.
from .util import run_process

LOG = logging.getLogger(__name__)
log = LOG  # alias

# The minimum amount of healthy operators before the resource provider reports the cluster is healthy overall
MINIMUM_HEALTHY_OPERATORS = 25


def generate_ignition_files(openshift_install_binary, download_path, cluster_name, ssh_key, pull_secret,
                            hosted_zone_name, subnets, availability_zones, aws_access_key_id, aws_secret_access_key,
                            worker_node_size=3, certificate_arn=None, worker_instance_profile=None):
    """
    Produces a set of Ignition files and K8S/OpenShift manifests that are used to orchestrate the majority of the
    OpenShift v4 installation process.

    During bootstrap, cluster nodes (and the bootstrap server) fetch ignition files from S3. This function generates
    these ignition files and uploads up to S3

    When the installation files are generated, we temporarily assume a different AWS identity based on the passed in
    access keys. We do this because OpenShift v4 on the AWS platform *requires* a set of AWS access keys. These keys
    are stored as cluster secrets and are accessed to manage AWS resources (ex: load balancers for ingress, EC2 instances
    for MachineSets, etc.)

    :param worker_node_size: Size of initial worker cluster. Default is 3
    :param certificate_arn: The ARN to the SSL Certificate in Amazon Certificate Manager
    :param openshift_install_binary: The name of the installation binary. `openshift_install`
    :param download_path: Path to download binaries
    :param cluster_name: The name used for the Cluster
    :param ssh_key: A Public SSH key to load into the cluster for administrative access
    :param pull_secret: A valid RedHat Pull Secret JSON for fetching container images from RedHat's repository
    :param hosted_zone_name: DNS Zone name. The `cluster_name` is prepended to this to create a private DNS zone.
    :param subnets: List of all subnets IDs -- both public and private are required.
    :param availability_zones: List of availability zones. Must be at least 3 or greater.
    :param aws_access_key_id: A valid AWS Access Key ID for the Cluster to use for managing the AWS platform
    :param aws_secret_access_key: A valid AWS Secret Access Key for the Cluster to use for managing the AWS platform
    :param worker_instance_profile: [Optional] A IAM Instance Profile to attach to Worker instances

    :return Tuple(InfraName: str, KubeAdminPass: str, KubeConfig: str, AssetsDir: str):
    """
    assets_directory = download_path + cluster_name
    log.info("Creating OpenShift assets directory for {}...".format(cluster_name))
    log.debug('SSHKey: %s', ssh_key)
    log.debug('PullSecret is %s set', "" if pull_secret else "not")
    log.debug('HostedZoneName: %s', hosted_zone_name)
    log.debug('Subnets: %s', subnets)
    log.debug('Availability Zones: %s', availability_zones)
    log.debug('Cluster AWS Access Key: %s', aws_access_key_id)
    log.debug('Cluster AWS Secret Key is %s set', "" if aws_secret_access_key else "not")
    log.debug('Worker Instance Profile: %s', worker_instance_profile)

    if not os.path.exists(assets_directory):
        os.mkdir(assets_directory)
    log.info("Generating install-config file for {}...".format(cluster_name))

    # the CloudFormation logger fails if the line is empty
    for nonempty_line in [line for line in INSTALL_CONFIG_YAML.splitlines() if line]:
        log.debug(nonempty_line)

    log.info('Building Install Config YAML object')
    openshift_install_config = yaml.safe_load(INSTALL_CONFIG_YAML)
    openshift_install_config['metadata']['name'] = cluster_name
    openshift_install_config['sshKey'] = ssh_key
    openshift_install_config['pullSecret'] = pull_secret
    openshift_install_config['baseDomain'] = hosted_zone_name
    openshift_install_config['platform']['aws']['subnets'] = subnets
    openshift_install_config['platform']['aws']['region'] = os.getenv('AWS_REGION')
    openshift_install_config['controlPlane']['platform']['aws']['zones'] = availability_zones
    openshift_install_config['compute'][0]['platform']['aws']['zones'] = availability_zones
    openshift_install_config['compute'][0]['replicas'] = worker_node_size

    cluster_install_config_file = os.path.join(assets_directory, 'install-config.yaml')
    yaml.dump(openshift_install_config,
              open(cluster_install_config_file, 'w'),
              explicit_start=True, default_style='\"',
              width=4096)
    original_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
    original_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    session_token = os.getenv('AWS_SESSION_TOKEN', '')
    try:
        log.debug("Using the provided AWS credentials to generate the cluster install configs. Using IAM roles is not "
                  "supported by the installer ")
        os.putenv('AWS_ACCESS_KEY_ID', aws_access_key_id)
        os.putenv('AWS_SECRET_ACCESS_KEY', aws_secret_access_key)
        os.putenv('AWS_SESSION_TOKEN', '')
        log.info("Generating manifests for {}...".format(cluster_name))
        cmd = f'{download_path}{openshift_install_binary} create manifests --dir {assets_directory}'
        run_process(cmd)
        log.info('Deleting Master Machinesets from Manifests')
        control_plane_manifests = glob.glob(
            os.path.join(assets_directory, 'openshift', '99_openshift-cluster-api_master-machines-*.yaml')
        )
        for manifest in control_plane_manifests:
            log.debug('Found Control Plane manifest to remove from installer: %s', manifest)
            os.remove(manifest)

        if certificate_arn:
            log.info('Customizing installation settings because a Certificate ARN was supplied')
            dns_manifest = os.path.join(assets_directory, 'manifests', 'cluster-dns-02-config.yml')
            with open(dns_manifest, 'r') as f:
                dns_manifest_yaml = yaml.safe_load(f)
            del dns_manifest_yaml['spec']['privateZone']
            del dns_manifest_yaml['spec']['publicZone']
            with open(dns_manifest, 'w') as f:
                yaml.dump(dns_manifest_yaml, f, explicit_start=True, default_style='\"', width=4096)
            log.info('Disabled OpenShift management of DNS records')
        else:
            log.info('No custom SSL Certificate provided. Using default behavior and OpenShift will manage DNS')

        if worker_instance_profile:
            log.info('Customizing Worker IAM Instance Profile')
            worker_manifests = glob.glob(
                os.path.join(assets_directory, 'openshift', '99_openshift-cluster-api_worker-machineset-*.yaml')
            )
            for manifest in worker_manifests:
                log.debug('Found worker manifest to modify: %s', manifest)
                with open(manifest, 'r') as f:
                    worker_machine_manifest = yaml.safe_load(f)
                log.debug('Original Worker Manifest', worker_machine_manifest)
                worker_machine_manifest['spec']['template']['spec']['providerSpec']['value']['iamInstanceProfile'][
                    'id'] = worker_instance_profile
                log.debug('New Worker Manifest', worker_machine_manifest)
                with open(manifest, 'w') as f:
                    yaml.dump(worker_machine_manifest, f, explicit_start=True, default_style='\"', width=4096)
            log.info('Finished customizing Worker Machinesets')
        else:
            log.info('No Worker Machineset customizations found. Skipping customization phase...')

        log.info("Generating ignition files for {}...".format(cluster_name))
        cmd = download_path + openshift_install_binary + " create ignition-configs --dir {}".format(assets_directory)
        run_process(cmd)
    finally:
        log.debug('Resetting AWS API access credentials')
        os.putenv('AWS_ACCESS_KEY_ID', original_access_key_id)
        os.putenv('AWS_SECRET_ACCESS_KEY', original_secret_access_key)
        os.putenv('AWS_SESSION_TOKEN', session_token)
    log.info('Collecting InfraId, KubeConfig, and KubeAdmin Password from generated installation files')
    infra_name, kubeadmin_password, kubeconfig = collect_kube_info(os.path.join(assets_directory, 'metadata.json'),
                                                                   os.path.join(assets_directory, 'auth'))
    return infra_name, kubeadmin_password, kubeconfig, assets_directory


def collect_kube_info(metadata_path, auth_path):
    """
    Accesses generated metadata and authdata files to retrieve KubeConfig, KubeAdmin Password, and Infrastructure ID

    :param metadata_path: Path to the cluster metadata json
    :param auth_path: Path to the auth directory that contains the `kubeconfig` and `kubeadmin-password` files
    :return tuple(infra_name: str, kubeadmin_password: str, kubeconfig: str):
    """
    with open(metadata_path) as f:
        metadata = json.load(f)
        infra_name = metadata['infraID']
        log.debug('Found generated cluster InfrastructureId: %s', infra_name)
    with open(os.path.join(auth_path, 'kubeadmin-password')) as f:
        kubeadmin_password = f.read().strip()
        if not kubeadmin_password:
            raise RuntimeError("No kubeadmin password found in file")
        log.debug('Found KubeAdmin password')
    with open(os.path.join(auth_path, 'kubeconfig')) as f:
        kubeconfig = f.read().strip()
        if not kubeconfig:
            raise RuntimeError("No kubeconfig found in file")

    return infra_name, kubeadmin_password, kubeconfig


def cluster_api_available(oc: str, kubeconfig_path: str) -> bool:
    """
    Checks to see if the Cluster's API endpoint is alive

    :param oc: The OpenShift Client binary
    :param kubeconfig_path: Path to a KubeConfig file for the cluster
    :return bool: True if API available. False, otherwise
    """
    try:
        run_process(f'{oc} --config {kubeconfig_path} cluster-info')
        log.info('Cluster is available for connections')
        return True
    except (subprocess.CalledProcessError, OSError):
        log.info('Cluster is not available for connections yet')
        return False


def wait_for_operators(oc: str, kubeconfig_path: str) -> bool:
    """
    Waits for enough Cluster Operators to report back healthy. The number of reporting Operators must be greater
    than the constant `MINIMUM_HEALTHY_OPERATORS`

    :param oc: The OpenShift Client binary
    :param kubeconfig_path: Path to a KubeConfig file for the cluster
    :return bool: True if the cluster is healthy. False, otherwise
    """
    operator_re = re.compile(
        r'^(?P<operator>\S+)\s+(?P<version>\S+)\s+(?P<available>\S+)\s+(?P<progressing>\S+)\s+(?P<degraded>\S+)')
    try:
        p = run_process(f'{oc} --config {kubeconfig_path} get clusteroperators')
        operators = []
        cluster_ready = False
        for line in p.stdout.splitlines()[1:]:
            str_line = line.decode('utf-8')
            operator_match = operator_re.match(str_line)
            if operator_match is None:
                continue
            operator = operator_match.groupdict()
            operators.append(operator)
            if operator['available'] == 'False':
                log.info('[Operator Check] Waiting for operator %s to boot up', operator['operator'])
            else:
                log.info('[Operator Check] %s is ready', operator['operator'])
                if operator['operator'] == 'ingress':
                    log.info('[Operator Check] Ingress Operator is Ready. Post-processing tasks can begin')
                    cluster_ready = True

        if len(operators) == 0:
            log.info('[Operator Check] No operators are ready yet')
        return cluster_ready or all([True if operator['available'] == 'True' else False for operator in operators]) and \
               len(operators) >= MINIMUM_HEALTHY_OPERATORS
    except (subprocess.CalledProcessError, OSError):
        return False


def bootstrap_post_process(oc, kubeconfig_path, remove_builtin_ingress=False, domain=None):
    """
    Performs any post-install steps on the cluster

    :param oc: Openshift client
    :param kubeconfig_path: KubeConfig path
    :param remove_builtin_ingress: Set to True to remove the builtin Ingress / LoadBalancer manageent. Default is False
    :param domain: The base domain of the cluster. Usually it's {ClusterName}.{BaseDomain}. Ex: my-cluster.example.com
    :return:
    """
    LOG.info('Starting Post-Process steps')
    if not remove_builtin_ingress:
        LOG.debug('No Certificate ARN found. No post-boot processes necessary')
        return
    LOG.info('Replacing default Ingress Controller')
    ingress_yaml_path = os.path.join('/tmp', 'ingress.yaml')
    ingress_yaml = DEFAULT_INGRESS_REPLACEMENT.format(domain=f'apps.{domain}')
    with open(ingress_yaml_path, 'w') as f:
        f.write(ingress_yaml)
    LOG.debug('Ingress YAML: %s', ingress_yaml)
    run_process(f'{oc} --config {kubeconfig_path} replace --force --wait -f {ingress_yaml_path}')
    LOG.info('Finished Post-Process steps')


def load_certificate_and_patch_ingress(oc, kubeconfig_path, cert, private_key, cert_chain=''):
    """
    Takes a Private Key and Certificate and loads into the OpenShift cluster as the default ingress' TLS certificate

    :param oc: OpenShift client cmd
    :param kubeconfig_path: Path to kubeconfig file
    :param cert: The Certificate to load into the cluster
    :param private_key: The Private Key to load into the cluster
    :param cert_chain:  A certificate chain. Default is empty string
    :return: True if success. False, otherwise
    """
    log.info('Attempting to load a custom TLS certificate from the cert/key provided')
    cert_path = os.path.join('/tmp', 'tls.crt')
    key_path = os.path.join('/tmp', 'tls.key')
    with open(cert_path, 'w') as f:
        f.write('\n'.join([cert, cert_chain]))
    with open(key_path, 'w') as f:
        f.write(private_key)

    try:
        run_process(f'{oc} --config {kubeconfig_path} --namespace openshift-ingress create secret tls '
                    f'custom-certs-default --cert={cert_path} --key={key_path}')
        log.info('Successfully loaded cert/key into cluster as a Kube secret')
        log.info('Patching default ingress to use our cert/key pair')
        run_process(f'{oc} --config {kubeconfig_path} patch --type=merge --namespace openshift-ingress-operator '
                    f'ingresscontrollers/default --patch '
                    '\'{"spec": {"defaultCertificate": {"name": "custom-certs-default"}}}\'')

        log.info('Validating that certificate was changed successfully')
        validate = run_process(f'{oc} --config {kubeconfig_path} get --namespace openshift-ingress-operator '
                               'ingresscontrollers/default --output jsonpath=\'{.spec.defaultCertificate}\'')

        if 'map[name:custom-certs-default]' in validate.stdout.decode('utf-8'):
            log.info('Successfully patched the default ingress. Routes will now use our imported cert/key pair')
            return True
        else:
            log.warning('WARNING - Something went wrong. Our custom certificate is not being used. Check the logs and '
                        'cluster for more info ')
            return False
    except (subprocess.CalledProcessError, OSError, TypeError):
        log.warning('WARNING - Something went wrong while importing the custom cert/key pair. Check the logs for more '
                    'info')
        return False


# Used when SSL certificate integration is requested
DEFAULT_INGRESS_REPLACEMENT = '''apiVersion: operator.openshift.io/v1
kind: IngressController
items:
- apiVersion: operator.openshift.io/v1
  kind: IngressController
  metadata:
    name: default
    namespace: openshift-ingress-operator
  spec:
    replicas: 3
    domain: {domain}
    endpointPublishingStrategy:
      loadBalancer:
        scope: External
      type: HostNetwork
    selector: ingresscontroller.operator.openshift.io/deployment-ingresscontroller=default
'''
#
# Template for install-config.yaml
#
INSTALL_CONFIG_YAML = '''apiVersion: v1
baseDomain: example.com 
compute:
- hyperthreading: Enabled
  name: worker
  platform:
    aws:
      zones: []
  replicas: 3
controlPlane:
  hyperthreading: Enabled
  name: master
  platform:
    aws:
      zones: []
  replicas: 3
metadata:
  creationTimestamp: null
  name: your_clustername
networking:
  clusterNetwork:
  - cidr: 10.32.0.0/16
    hostPrefix: 23
  networkType: OpenShiftSDN
  serviceNetwork:
  - 172.30.0.0/16
platform:
  aws:
    region: updateme
    subnets: []

pullSecret: "{ 'UpdateMe': true }"
sshKey: |
  ssh-rsa {{ yourkey }}
'''
