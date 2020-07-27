# DO NOT modify this file by hand, changes will be overwritten
import sys
from dataclasses import dataclass
from inspect import getmembers, isclass
from typing import (
    AbstractSet,
    Any,
    Generic,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
)

from cloudformation_cli_python_lib.interface import (
    BaseModel,
    BaseResourceHandlerRequest,
)
from cloudformation_cli_python_lib.recast import recast_object
from cloudformation_cli_python_lib.utils import deserialize_list

T = TypeVar("T")


def set_or_none(value: Optional[Sequence[T]]) -> Optional[AbstractSet[T]]:
    if value:
        return set(value)
    return None


@dataclass
class ResourceHandlerRequest(BaseResourceHandlerRequest):
    # pylint: disable=invalid-name
    desiredResourceState: Optional["ResourceModel"]
    previousResourceState: Optional["ResourceModel"]


@dataclass
class ResourceModel(BaseModel):
    LogLevel: Optional[str]
    Action: Optional[str]
    WorkerNodeSize: Optional[int]
    ClusterName: Optional[str]
    OpenShiftMirrorURL: Optional[str]
    OpenShiftVersion: Optional[str]
    OpenShiftClientBinary: Optional[str]
    OpenShiftInstallBinary: Optional[str]
    IgnitionBucket: Optional[str]
    PullSecret: Optional[str]
    SSHKey: Optional[str]
    AwsAccessKeyId: Optional[str]
    AwsSecretAccessKey: Optional[str]
    WorkerInstanceProfileName: Optional[str]
    HostedZoneName: Optional[str]
    AvailabilityZones: Optional[Sequence[str]]
    Subnets: Optional[Sequence[str]]
    CertificateArn: Optional[str]
    ClusterIngressCertificateArn: Optional[str]
    ClusterIngressPrivateKeySecretName: Optional[str]
    InfrastructureName: Optional[str]
    InfrastructureId: Optional[str]
    KubeConfig: Optional[str]
    KubeConfigArn: Optional[str]
    KubeAdminPasswordArn: Optional[str]

    @classmethod
    def _deserialize(
        cls: Type["_ResourceModel"],
        json_data: Optional[Mapping[str, Any]],
    ) -> Optional["_ResourceModel"]:
        if not json_data:
            return None
        dataclasses = {n: o for n, o in getmembers(sys.modules[__name__]) if isclass(o)}
        recast_object(cls, json_data, dataclasses)
        return cls(
            LogLevel=json_data.get("LogLevel"),
            Action=json_data.get("Action"),
            WorkerNodeSize=json_data.get("WorkerNodeSize"),
            ClusterName=json_data.get("ClusterName"),
            OpenShiftMirrorURL=json_data.get("OpenShiftMirrorURL"),
            OpenShiftVersion=json_data.get("OpenShiftVersion"),
            OpenShiftClientBinary=json_data.get("OpenShiftClientBinary"),
            OpenShiftInstallBinary=json_data.get("OpenShiftInstallBinary"),
            IgnitionBucket=json_data.get("IgnitionBucket"),
            PullSecret=json_data.get("PullSecret"),
            SSHKey=json_data.get("SSHKey"),
            AwsAccessKeyId=json_data.get("AwsAccessKeyId"),
            AwsSecretAccessKey=json_data.get("AwsSecretAccessKey"),
            WorkerInstanceProfileName=json_data.get("WorkerInstanceProfileName"),
            HostedZoneName=json_data.get("HostedZoneName"),
            AvailabilityZones=json_data.get("AvailabilityZones"),
            Subnets=json_data.get("Subnets"),
            CertificateArn=json_data.get("CertificateArn"),
            ClusterIngressCertificateArn=json_data.get("ClusterIngressCertificateArn"),
            ClusterIngressPrivateKeySecretName=json_data.get("ClusterIngressPrivateKeySecretName"),
            InfrastructureName=json_data.get("InfrastructureName"),
            InfrastructureId=json_data.get("InfrastructureId"),
            KubeConfig=json_data.get("KubeConfig"),
            KubeConfigArn=json_data.get("KubeConfigArn"),
            KubeAdminPasswordArn=json_data.get("KubeAdminPasswordArn"),
        )


# work around possible type aliasing issues when variable has same name as a model
_ResourceModel = ResourceModel


