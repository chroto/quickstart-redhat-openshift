"""
Functions for reading information about our OpenShift resource
"""
import logging
from typing import Optional, Mapping

from cloudformation_cli_python_lib import SessionProxy, OperationStatus

from .models import ResourceModel

LOG = logging.getLogger(__name__)
log = LOG  # alias


def fetch_resource(model: Optional[ResourceModel], session: Optional[SessionProxy]) -> Mapping:
    """
    Fetches resource information from AWS and adds them to our model.

    We specifically grab the Infrastructure ID from Parameter store and any Kubernetes information from Secrets Manager

    :param model: Resource model
    :param session: Boto SessionProxy
    :return Mapping: A Mapping of values that can be used as **kwargs to a ProgressEvent or used for something else
    """

    response_dict = fetch_kube_parameters(model, session)
    if response_dict['status'] == OperationStatus.FAILED:
        return response_dict

    return {'status': OperationStatus.SUCCESS, 'resourceModel': model}


def fetch_kube_parameters(model, session):
    """
    Helps the READ handler and other functions read Kube and OpenShift information from AWS parameter sources

    :param session: Boto3 session
    :param model: Resource Model
    :return:
    """
    secrets = session.client('secretsmanager')
    ssm = session.client('ssm')
    LOG.info('Retrieving Cluster information from AWS Parameter Store and Secrets Manager')
    try:
        if model.InfrastructureName:
            log.info("InfrastructureName %s was provided to the resource. Will not fetch from Parameter Store",
                     model.InfrastructureName)
            model.InfrastructureId = model.InfrastructureName
        else:
            LOG.debug('Fetching Infrastructure ID')
            model.InfrastructureId = model.InfrastructureName = ssm.get_parameter(
                Name=f'/OpenShift/{model.ClusterName}/InfrastructureId'
            )['Parameter']['Value']
        if model.KubeConfig:
            log.info("KubeConfig %s was provided to the resource. Will not fetch from Secrets Manager",
                     model.KubeConfig)
            model.KubeConfigArn = model.KubeConfig
        else:
            LOG.debug('Fetching KubeConfig')
            model.KubeConfigArn = model.KubeConfig = \
                secrets.describe_secret(SecretId=f'{model.InfrastructureId}-kubeconfig')['ARN']

    except ssm.exceptions.ParameterNotFound:
        err_msg = f"ERROR - Parameter at /OpenShift/{model.ClusterName}/InfrastructureId not found"
        LOG.error(err_msg)
        return {
            'status': OperationStatus.FAILED,
            'message': err_msg,
            'resourceModel': model
        }
    except secrets.exceptions.ResourceNotFoundException as e:
        err_msg = f'ERROR - Required Secret values for Kubernetes connections could not be found: {e}'
        LOG.error(err_msg)
        return {
            'status': OperationStatus.FAILED,
            'message': err_msg,
            'resourceModel': model
        }
    try:
        LOG.debug('Fetching KubeAdminPassword')
        model.KubeAdminPasswordArn = secrets.describe_secret(SecretId=f'{model.InfrastructureId}-kubeadmin')['ARN']
    except secrets.exceptions.ResourceNotFoundException as e:
        if model.Action == 'GENERATE_IGNITION':
            err_msg = f'ERROR - Required Secret values for Kubernetes admin password could not be found: {e}',
            LOG.error(err_msg)
            return {
                'status': OperationStatus.FAILED,
                'message': err_msg,
                'resourceModel': model
            }
        LOG.warning('WARNING - KubeAdminPassword not required for BOOTSTRAP action. Continuing...')

    return {'status': OperationStatus.SUCCESS, 'resourceModel': model}