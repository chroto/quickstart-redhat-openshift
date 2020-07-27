"""
Main entry-points for the CloudFormation Resource Provider framework

* `resource` - Main interfacing handler and entry-point
* `test_entrypoint` - For contract and SAM testing
* `ide_entrypoint` - For certain IDE plugins that can not detect `test_entrypoint` as a valid Lambda handler function

"""
import logging
from typing import Any, MutableMapping, Optional

from cloudformation_cli_python_lib import (
    Action,
    HandlerErrorCode,
    OperationStatus,
    ProgressEvent,
    Resource,
    SessionProxy,
    exceptions,
)

from .models import ResourceHandlerRequest, ResourceModel
from .delete import bootstrap_delete, generate_ignition_delete
from .create import generate_ignition_create, bootstrap_create
from .read import fetch_resource, fetch_kube_parameters

DEFAULT_MIRROR_URL = "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/"
DEFAULT_VERSION = "4.3.21"
DEFAULT_INSTALL_BINARY = "openshift-install"
DEFAULT_CLIENT_BINARY = "oc"

# Use this logger to forward log messages to CloudWatch Logs.
# All loggers in this module inherit from `awsqs_openshift_manager`
LOG = logging.getLogger("awsqs_openshift_manager")
TYPE_NAME = "AWSQS::OpenShift::Manager"

resource = Resource(TYPE_NAME, ResourceModel)
test_entrypoint = resource.test_entrypoint


def ide_entrypoint(*args, **kwargs):
    return test_entrypoint(*args, **kwargs)


@resource.handler(Action.CREATE)
def create_handler(
        session: Optional[SessionProxy],
        request: ResourceHandlerRequest,
        callback_context: MutableMapping[str, Any]
) -> ProgressEvent:
    """
    [CREATE] Handler

    :param request:
    :param session: Boto SessionProxy
    :param callback_context: Value Mapping set when the handler returns status=IN_PROGRESS and needs more processing.
    :return ProgressEvent:
    """
    model = request.desiredResourceState
    LOG.setLevel(model.LogLevel or "INFO")
    LOG.info('[CREATE] Entering CREATE Handler')
    model.OpenShiftInstallBinary = model.OpenShiftInstallBinary or DEFAULT_INSTALL_BINARY
    model.OpenShiftVersion = model.OpenShiftVersion or DEFAULT_VERSION
    model.OpenShiftMirrorURL = model.OpenShiftMirrorURL or DEFAULT_MIRROR_URL
    model.OpenShiftClientBinary = model.OpenShiftClientBinary or DEFAULT_CLIENT_BINARY
    LOG.debug('[CREATE] Current model state %s', model)
    try:
        validate_create(model)
        LOG.error("[CREATE] Setting up Action: %s", model.Action)
        if model.Action == "GENERATE_IGNITION":
            event_kwargs = generate_ignition_create(model, session)
        elif model.Action == "BOOTSTRAP":
            event_kwargs = bootstrap_create(model, callback_context.get("stage", None),
                                            callback_context.get("start_time", 0.0), session)
        else:
            raise AttributeError('Action: %s is not a valid action', model.Action)
        return ProgressEvent(**event_kwargs)
    except AttributeError as e:
        return ProgressEvent(
            status=OperationStatus.FAILED,
            errorCode=HandlerErrorCode.InvalidRequest,
            message=f"Operation failed because the parameters were invalid: {e}"
        )
    except BaseException as e:
        return ProgressEvent(
            status=OperationStatus.FAILED,
            errorCode=HandlerErrorCode.InternalFailure,
            message=f"Operation failed due to an internal problem: {e} . Check the logs for more information"
        )


# @resource.handler(Action.UPDATE)
def update_handler(
        session: Optional[SessionProxy],
        request: ResourceHandlerRequest,
        callback_context: MutableMapping[str, Any],
) -> ProgressEvent:
    raise NotImplementedError("UPDATE handler is not implemented. CloudFormation will [delete -> create] this resource")


@resource.handler(Action.DELETE)
def delete_handler(
        session: Optional[SessionProxy],
        request: ResourceHandlerRequest,
        callback_context: MutableMapping[str, Any],
) -> ProgressEvent:
    """
    [DELETE] Handler

    :param session: Boto SessionProxy
    :param model: Resource model
    :param callback_context: Value Mapping set when the handler returns status=IN_PROGRESS and needs more processing.
    :return ProgressEvent:
    """
    model = request.desiredResourceState
    LOG.info('[DELETE] Entering DELETE handler')
    model.OpenShiftInstallBinary = model.OpenShiftInstallBinary or DEFAULT_INSTALL_BINARY
    model.OpenShiftVersion = model.OpenShiftVersion or DEFAULT_VERSION
    model.OpenShiftMirrorURL = model.OpenShiftMirrorURL or DEFAULT_MIRROR_URL
    model.OpenShiftClientBinary = model.OpenShiftClientBinary or DEFAULT_CLIENT_BINARY
    LOG.setLevel(model.LogLevel or "INFO")
    LOG.debug('[DELETE] Current model state %s', model)

    read_kwargs = fetch_resource(model, session) if model.Action == 'BOOTSTRAP' else fetch_kube_parameters(model, session)
    if read_kwargs['status'] == OperationStatus.FAILED:
        return ProgressEvent(**read_kwargs)

    model = read_kwargs['resourceModel']

    try:
        if model.Action == 'BOOTSTRAP':
            event_kwargs = bootstrap_delete(model, session)
        elif model.Action == 'GENERATE_IGNITION':
            event_kwargs = generate_ignition_delete(model, session)
        else:
            raise AttributeError('Action: %s is not a valid action', model.Action)
        return ProgressEvent(**event_kwargs)
    except AttributeError as e:
        return ProgressEvent(
            status=OperationStatus.FAILED,
            errorCode=HandlerErrorCode.InvalidRequest,
            message=f"Operation failed because the parameters were invalid: {e}"
        )
    except BaseException as e:
        return ProgressEvent(
            status=OperationStatus.FAILED,
            errorCode=HandlerErrorCode.InternalFailure,
            message=f"Operation failed due to an internal problem: {e} . Check the logs for more information"
        )


@resource.handler(Action.READ)
def read_handler(
        session: Optional[SessionProxy],
        request: ResourceHandlerRequest,
        callback_context: MutableMapping[str, Any],
) -> ProgressEvent:
    """
    [READ] Handler

    :param request:
    :param session: Boto SessionProxy
    :param model: Resource model
    :param callback_context: Value Mapping set when the handler returns status=IN_PROGRESS and needs more processing.
    :return ProgressEvent:
    """
    model = request.desiredResourceState
    LOG.info('[READ] Entering READ handler')
    model.OpenShiftInstallBinary = model.OpenShiftInstallBinary or DEFAULT_INSTALL_BINARY
    model.OpenShiftVersion = model.OpenShiftVersion or DEFAULT_VERSION
    model.OpenShiftMirrorURL = model.OpenShiftMirrorURL or DEFAULT_MIRROR_URL
    model.OpenShiftClientBinary = model.OpenShiftClientBinary or DEFAULT_CLIENT_BINARY
    LOG.setLevel(model.LogLevel or "DEBUG")
    LOG.debug('[READ] Current model state %s', model)

    # `fetch_resource` looks up all the resource info we need
    return ProgressEvent(**fetch_resource(model, session))


def validate_create(model: ResourceModel):
    """
    Validates the model based on the user's requested parameters and current state of the resource.

    :param model: Resource model
    :return: True if successfully validated
    """
    LOG.info('[CREATE] Validating parameters')
    if model.Action == "GENERATE_IGNITION":
        if model.KubeConfig:
            raise AttributeError("Setting KubeConfig parameter is not allowed for GENERATE_IGNITION. This will be "
                                 "generated as an output")
        if model.InfrastructureName:
            raise AttributeError("Setting InfrastructureName parameter is not allowed for GENERATE_IGNITION. This "
                                 "will be generated as an output")
        if not (model.AwsSecretAccessKey and model.AwsAccessKeyId):
            raise AttributeError(
                "AwsAccessKeyId and AwsSecretAccessKey must be provided when generating Ignition files")
    if model.Action == "BOOTSTRAP":
        if (model.ClusterIngressCertificateArn or model.ClusterIngressPrivateKeySecretName) and \
                (not model.ClusterIngressPrivateKeySecretName or not model.ClusterIngressCertificateArn):
            raise AttributeError(
                "You must set both ClusterIngressCertificateArn and ClusterIngressPrivateKeySecretName or neither. "
                "These two parameters must represent the public-private keypair "
            )
    return True


