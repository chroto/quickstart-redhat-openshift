"""
Handles CREATE actions for the Resource
"""
import logging
import time
import os
from typing import Optional, Mapping

from cloudformation_cli_python_lib import OperationStatus, SessionProxy

from .util import upload_ignition_files_to_s3, fetch_resource
from .openshift import bootstrap_post_process, cluster_api_available, wait_for_operators
from .openshift import fetch_openshift_binary, generate_ignition_files
from .models import ResourceModel

LOG = logging.getLogger(__name__)


def generate_ignition_create(model: Optional[ResourceModel], session: Optional[SessionProxy]) -> Mapping:
    """
    Generates Ignition Configuration, uploads to S3, and returns the cluster Infrastructure Name

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: Mapping of arguments for the Create response
    """
    openshift_install_binary = model.OpenShiftInstallBinary
    openshift_version = model.OpenShiftVersion
    openshift_mirror = model.OpenShiftMirrorURL
    openshift_install_package = f'{openshift_install_binary}-linux-{openshift_version}.tar.gz'
    openshift_client_mirror_url = f'{openshift_mirror}{openshift_version}/'

    LOG.info("[CREATE] Cluster name: %s", model.ClusterName)

    LOG.info("[CREATE] Generating OCP installation files for cluster %s", model.ClusterName)
    download_path = '/tmp/'
    fetch_openshift_binary(openshift_client_mirror_url,
                           openshift_install_package,
                           openshift_install_binary,
                           download_path)
    model.InfrastructureName, model.KubeAdminPassword, kubeconfig, local_folder = generate_ignition_files(
        openshift_install_binary, download_path,
        model.ClusterName, model.SSHKey, model.PullSecret,
        model.HostedZoneName, model.Subnets, model.AvailabilityZones,
        model.AwsAccessKeyId, model.AwsSecretAccessKey,
        worker_instance_profile=model.WorkerInstanceProfileName,
        worker_node_size=model.WorkerNodeSize
    )
    model.InfrastructureId = model.InfrastructureName
    upload_ignition_files_to_s3(local_folder, model.IgnitionBucket, session)
    LOG.info("[CREATE] Completed ignition file generation")

    LOG.info("[CREATE] Storing OpenShift information as SSM Parameters and Secrets Manager Secrets")
    infra_tag = {
        'Key': f'kubernetes.io/cluster/{model.InfrastructureName}',
        'Value': 'owned'
    }
    LOG.info('[CREATE] Saving Infrastructure ID as SSM Parameter')
    ssm = session.client('ssm')
    infra_ssm_path = f'/OpenShift/{model.ClusterName}/InfrastructureId'
    ssm.put_parameter(
        Name=infra_ssm_path,
        Description=f'The Infrastructure ID for {model.ClusterName}',
        Value=model.InfrastructureId,
        Tags=[infra_tag],
        Type='String',
        Tier='Standard'
    )
    LOG.debug('[CREATE] Infrastructure ID saved at %s', infra_ssm_path)
    LOG.info("[CREATE] Saving KubeConfig as Secret")
    secrets = session.client("secretsmanager")
    model.KubeConfigArn = secrets.create_secret(
        Name=f'{model.InfrastructureName}-kubeconfig',
        Description=f'Kubeconfig for cluster/{model.InfrastructureName}',
        SecretString=kubeconfig,
        Tags=[infra_tag]
    )['ARN']
    LOG.debug("[CREATE] KubeConfig ARN: %s", model.KubeConfigArn)
    LOG.info("[CREATE] Saving Kubeadmin password as Secret")
    model.KubeAdminPasswordArn = secrets.create_secret(
        Name=f'{model.InfrastructureName}-kubeadmin',
        Description=f'Kube Admin Password for cluster{model.InfrastructureName}',
        SecretString=model.KubeAdminPassword,
        Tags=[infra_tag]
    )['ARN']
    LOG.debug("[CREATE] KubeConfig ARN: %s", model.KubeAdminPasswordArn)
    LOG.info('[CREATE] Successfully created Ignition files. Exiting with success status.')
    return {
        "status": OperationStatus.SUCCESS,
        "resourceModel": model,
        "message": f"Completed ignition file generation. Check s3://{model.IgnitionBucket}/{model.ClusterName}",
    }


def bootstrap_create(model: ResourceModel, stage: str, start_time: float, session: SessionProxy) -> Mapping:
    """
    Monitors the Cluster's boot-up sequence and takes actions to customize the environment if necessary

    :param stage: Current stage. Retrieved from the callbackContext
    :param start_time: The UNIX epoch for when this Bootstrap CREATE started. Retrieved from the callbackContext
    :param model: Resource model
    :param session: Boto SessionProxy
    :return: Mapping of arguments for the Create response
    """
    openshift_client_binary = model.OpenShiftClientBinary
    openshift_version = model.OpenShiftVersion
    openshift_client_mirror_url = f'{model.OpenShiftMirrorURL}{openshift_version}/'
    openshift_client_package = f'openshift-client-linux-{openshift_version}.tar.gz'
    now = time.time()
    time_elapsed = now - start_time
    if stage:
        LOG.info('[CREATE] Entering Stage %s', stage)
        LOG.info('[CREATE] Time elapsed: %s', _readable_time_delta(time_elapsed))
    else:
        LOG.info('[CREATE] Entering initial stage')

    if not model.InfrastructureName or model.KubeConfig:
        fetch_resource_status_obj = fetch_resource(model, session)
        if fetch_resource_status_obj['status'] != OperationStatus.SUCCESS:
            return fetch_resource_status_obj
        else:
            model = fetch_resource_status_obj['resourceModel']
    else:
        model.InfrastructureID = model.InfrastructureName
        model.KubeConfigArn = model.KubeConfig

    default_response = {
        "status": OperationStatus.IN_PROGRESS,
        "resourceModel": model,
        "message": "Cluster is still being setup. Waiting..."
    }

    oc_bin = f'/tmp/{openshift_client_binary}'
    kubeconfig_path = os.path.join('/tmp/', 'kubeconfig')
    if stage in ["INIT", "WAIT_FOR_INIT", "WAIT_FOR_CLUSTER_OPERATORS", "POST_PROCESS"]:
        fetch_openshift_binary(openshift_client_mirror_url, openshift_client_package, openshift_client_binary, '/tmp/')
        client = session.client('secretsmanager')
        LOG.debug('[CREATE] Fetching KubeConfig from Secrets Manager at %s', model.KubeConfig)
        kubeconfig = client.get_secret_value(SecretId=model.KubeConfig)
        LOG.debug('[CREATE] Writing KubeConfig to file')
        with open(kubeconfig_path, 'w') as f:
            f.write(kubeconfig['SecretString'])

    if stage is None:
        LOG.info('[CREATE] Returning IN_PROGRESS response. Next stage is WAIT_FOR_INIT')
        return {**default_response, **{
            "callbackContext": {
                "stage": "WAIT_FOR_INIT", "start_time": now
            },
            "callbackDelaySeconds": 300
        }}

    elif stage == "WAIT_FOR_INIT":
        if cluster_api_available(oc_bin, kubeconfig_path):
            next_stage = 'CLUSTER_INIT_SUCCESS'
            delay = 0
        else:
            next_stage = 'WAIT_FOR_INIT'
            delay = 300
        return {**default_response, **{
            "message": "Waiting for Cluster API to initialized",
            "callbackContext": {"stage": next_stage, "start_time": start_time},
            "callbackDelaySeconds": delay
        }}
    elif stage == "CLUSTER_INIT_SUCCESS":
        LOG.info('[CREATE] Cluster API is available. Time Elapsed: %s', _readable_time_delta(time_elapsed))
        return {**default_response, **{
            "message": "Cluster API initialized successfully. Waiting for Operators to come online...",
            "callbackContext": {"stage": "WAIT_FOR_CLUSTER_OPERATORS", "start_time": start_time},
            "callbackDelaySeconds": 0
        }}
    elif stage == "WAIT_FOR_CLUSTER_OPERATORS":
        if wait_for_operators(oc_bin, kubeconfig_path):
            delay = 0
            next_stage = 'CLUSTER_OPERATORS_SUCCESS'
        else:
            delay = 300
            next_stage = 'WAIT_FOR_CLUSTER_OPERATORS'

        return {**default_response, **{
            "callbackContext": {"stage": next_stage, "start_time": start_time},
            "callbackDelaySeconds": delay
        }}
    elif stage == "CLUSTER_OPERATORS_SUCCESS":
        LOG.info('[CREATE] Cluster Operators are available. Time Elapsed: %s', _readable_time_delta(time_elapsed))
        return {**default_response, **{
            "message": "Cluster Operators are all Healthy",
            "callbackContext": {"stage": "POST_PROCESS", "start_time": start_time},
            "callbackDelaySeconds": 0
        }}
    elif stage == "POST_PROCESS":
        if bootstrap_post_process(oc_bin, kubeconfig_path, cert_arn=model.CertificateArn):
            return {
                "status": OperationStatus.SUCCESS,
                "message": "Cluster successfully bootstrapped and ready for operations",
            }
        else:
            raise RuntimeError("Post process failed")

    raise AttributeError("Unknown Stage: %s", stage)


def _readable_time_delta(delta: float) -> str:
    """
    Takes a delta of unix timestamps and returns a more human readable style
    :param delta:
    :return:
    """
    LOG.debug('Converting delta timestamp %s to human readable', delta)
    hours, h_rem = divmod(delta, 3600)
    minutes, seconds = divmod(h_rem, 60)
    return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
