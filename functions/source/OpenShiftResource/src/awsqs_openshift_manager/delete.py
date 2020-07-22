"""
Handles DELETE actions for the Resource
"""
import logging
import time
from typing import Optional, Mapping

from botocore.exceptions import ClientError
from cloudformation_cli_python_lib import SessionProxy, OperationStatus
from .models import ResourceModel
from .util import delete_contents_s3

log = logging.getLogger(__name__)


def generate_ignition_delete(model: Optional[ResourceModel], session: Optional[SessionProxy]) -> Mapping:
    """
    Executes DELETE for the GENERATE_IGNITION Action

    Deletes the Secrets and Parameters associated with the cluster. This also cleans up any installation files left in
    the Ignition Bucket

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: Mapping of arguments for the Delete response
    """
    secrets = session.client('secretsmanager')
    ssm = session.client('ssm')

    log.info(f'[DELETE] Deleting all objects in {model.IgnitionBucket} with prefix {model.ClusterName}')
    if not model.ClusterName or '/' in model.ClusterName:
        raise AttributeError("ClusterName is not valid")
    delete_contents_s3(model.IgnitionBucket, session, filter={'Prefix': f'{model.ClusterName}/', 'Delimiter': '/'})
    delete_contents_s3(model.IgnitionBucket, session, filter={'Prefix': f'{model.ClusterName}/auth/', 'Delimiter': '/'})

    log.info('[DELETE] Deleting KubeAdmin secret')
    secrets.delete_secret(SecretId=model.KubeAdminPasswordArn)
    log.info('[DELETE] Deleting KubeConfig secret')
    secrets.delete_secret(SecretId=model.KubeConfigArn)

    log.info('[DELETE] Deleting InfrastructureId Parameter')
    ssm.delete_parameter(Name=f'/OpenShift/{model.ClusterName}/InfrastructureId')

    log.info('[DELETE] Successfully deleted resources for GENERATE_IGNITION')

    return {
        "status": OperationStatus.SUCCESS,
        "resourceModel": model
    }


def bootstrap_delete(model: Optional[ResourceModel], session: Optional[SessionProxy]) -> Mapping:
    """
    Executes DELETE for the BOOTSTRAP Action

    This handles the deletion of any Cluster-managed AWS resources that it can find. This includes resources like
    LoadBalancers, IAM Users, and Security Groups

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: Mapping of arguments for the Delete response
    """
    log.info('[DELETE] Deleting Route53 records created by the cluster')
    _cleanup_dns(model, session)
    log.info('[DELETE] Deleting Image Registry Bucket')
    _cleanup_image_registry_bucket(model, session)
    log.info('[DELETE] Deleting any ingress load balancers')
    _cleanup_ingress_lbs(model, session)
    log.info('[DELETE] Terminating any stray worker nodes and EC2 resources')
    _cleanup_ec2(model, session)

    return {
        'resourceModel': model,
        'status': OperationStatus.SUCCESS
    }


def _cleanup_dns(model, session):
    """
    Deletes the Internal DNS records that OpenShift creates as part of its bootstrap process

    If DNS is not being managed, this won't delete anything

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: True if successful
    """
    dns = session.client('route53')
    int_dns_zone_response = dns.list_hosted_zones_by_name(
        DNSName=f'{model.ClusterName}.{model.HostedZoneName}.'
    )['HostedZones']

    records_to_delete = [
        f'\\052.apps.{model.ClusterName}.{model.HostedZoneName}.',
        f'oauth.apps.{model.ClusterName}.{model.HostedZoneName}.'
    ]
    if len(int_dns_zone_response) > 0:
        int_zone_id = int_dns_zone_response[0]['Id']
        int_cluster_records = dns.list_resource_record_sets(HostedZoneId=int_zone_id)['ResourceRecordSets']
        log.debug('[DELETE] Found %s DNS records. Only %s will be deleted', len(int_cluster_records), records_to_delete)
        log.debug('[DELETE] %s', int_cluster_records)
        delete_reqs = []
        for rec in \
                [r for r in int_cluster_records
                 if r['Type'] == 'A' and str(r['Name']) in records_to_delete]:
            delete_reqs.append({
                'Action': 'DELETE',
                'ResourceRecordSet': rec
            })
        log.info('[DELETE] Deleting internal apps DNS record for %s', int_zone_id)
        if len(delete_reqs) > 0:
            dns.change_resource_record_sets(
                HostedZoneId=int_zone_id,
                ChangeBatch={'Changes': delete_reqs}
            )
        log.info('[DELETE] Successfully deleted DNS records')
    else:
        log.info('[DELETE] Found no Internal DNS records to delete')
    return True


def _cleanup_image_registry_bucket(model, session):
    """
    Clears out the Image Registry bucket and deletes it

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: True if successful
    """
    s3 = session.resource('s3')
    rg = session.client('resourcegroupstaggingapi')
    response = rg.get_resources(
        TagFilters=[{
            'Key': f'kubernetes.io/cluster/{model.InfrastructureId}', 'Values': ['owned']
        }], ResourceTypeFilters=['s3'])
    if len(response['ResourceTagMappingList']) > 0:
        log.info('[DELETE] Found Image Registry Bucket to delete')
        for b in response['ResourceTagMappingList']:
            for t in b['Tags']:
                if t['Key'] == 'Name' and str(t['Value']).endswith('image-registry'):
                    bucket_name = str(b['ResourceARN']).lstrip('arn:aws:s3:::')
                    log.info('[DELETE] Deleting contents of image registry bucket')
                    delete_contents_s3(bucket_name, session)
                    log.info('[DELETE] Deleting image registry bucket')
                    try:
                        bucket = s3.Bucket(bucket_name)
                        bucket.delete()
                    except ClientError:
                        log.warning("[DELETE] Registry bucket does not exist")
        log.info('[DELETE] Image registry bucket successfully deleted')
    else:
        log.info('[DELETE] No Image Registry bucket found')
    return True


def _remove_security_group_from_ingress(sg_id, sgs):
    """
    Takes a target security group's ID and a list of Security Groups. Revokes any rules from the list of SGs that
    contain the Target Security Group ID.

    :param sg_id: SecurityGroup ID to search for and remove
    :param sgs: List of security groups to search in
    :return bool: True if success. False, otherwise
    """
    for sg in sgs:
        rules_to_delete = []
        for rule in sg.ip_permissions:
            log.debug('[DELETE] Checking security group rule %s', rule)
            for user_id_based_pair in rule.get('UserIdGroupPairs', []):
                if user_id_based_pair['GroupId'] == sg_id:
                    rules_to_delete.append(rule)
        for rule_to_delete in rules_to_delete:
            log.debug('[DELETE] Revoking ingress rule %s on %s', rule_to_delete, sg.id)
            sg.revoke_ingress(IpPermissions=[rule_to_delete])
    return True


def _cleanup_ec2(model, session):
    """
    Terminates any Worker nodes and Security Groups set up for Cluster ingress

    This will attempt to revoke security group rules on the Master and Worker security groups and assumes these rules
    haven't been manually edited. OpenShift adds a rule to the Master/Worker security groups when a new loadbalancer is
    created. The rule contains a single Security Group source for the ingress rule.

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: True if successful
    """
    client = session.client('ec2')
    ec2_resource = session.resource('ec2')
    cluster_tag = f'tag:kubernetes.io/cluster/{model.InfrastructureId}'
    workers = client.describe_instances(Filters=[
        {
            'Name': cluster_tag,
            'Values': ['owned']
        },
        {
            'Name': 'tag:Name',
            'Values': [f'{model.InfrastructureId}-worker*']
        }
    ])
    if len(workers['Reservations']) > 0:
        log.info('[DELETE] Deleting Worker nodes %s', workers['Reservations'])
        client.terminate_instances(
            InstanceIds=[worker['Instances'][0]['InstanceId'] for worker in workers['Reservations']]
        )
    else:
        log.info('[DELETE] No Worker nodes to delete')

    sgs = client.describe_security_groups(Filters=[{
        'Name': cluster_tag,
        'Values': ['owned']
    }])
    log.debug('[DELETE] Finding the worker and master security groups')
    master_sg = client.describe_security_groups(Filters=[{
        'Name': 'tag:Name',
        'Values': [f'{model.InfrastructureId}-master-sg']
    }])['SecurityGroups']
    if len(master_sg) == 0:
        log.debug('[DELETE] Master security group found. Will not be able to manage ingress rules. Deleting '
                  'security groups may fail.')

    worker_sg = client.describe_security_groups(Filters=[{
        'Name': 'tag:Name',
        'Values': [f'{model.InfrastructureId}-worker-sg']
    }])['SecurityGroups']
    if len(worker_sg) == 0:
        log.debug('[DELETE] Worker security group found. Will not be able to manage ingress rules. Deleting '
                  'security groups may fail.')

    log.info('[DELETE] Deleting Security Groups')
    if len(sgs['SecurityGroups']) > 0:
        for sg in sgs['SecurityGroups']:
            log.info('[DELETE] Deleting Security Group %s', sg['GroupId'])
            log.debug('[DELETE] Removing Security group from master security group')
            _remove_security_group_from_ingress(
                sg['GroupId'], [ec2_resource.SecurityGroup(sg['GroupId']) for sg in master_sg]
            )
            log.debug('[DELETE] Removing Security group from worker security group')
            _remove_security_group_from_ingress(
                sg['GroupId'], [ec2_resource.SecurityGroup(sg['GroupId']) for sg in worker_sg]
            )
            sg_deleted = False
            max_attempts = 5
            attempt = 0
            while not sg_deleted:
                try:
                    log.debug('[DELETE] Attempting to delete %s', sg['GroupId'])
                    client.delete_security_group(
                        GroupId=sg['GroupId']
                    )
                    log.info('[DELETE] Security Group %s deleted', sg['GroupId'])
                    sg_deleted = True
                except ClientError as e:  # Assume this is DependencyViolation
                    log.debug("[DELETE] Security Group delete failed with %s", e)
                    if attempt <= max_attempts:
                        time.sleep(15)
                        attempt = attempt + 1
                    else:
                        log.error("[DELETE] Out of retries. Failed with %s", e)
                        raise e
    return True


def _cleanup_ingress_lbs(model, session):
    """
    Cleans up any LoadBalancers created for OpenShift Ingress

    This is accomplished by using the ResourceGroupsTaggingAPI to fetch any ELBs with the Cluster-managed tag

    :param model: Resource model
    :param session: Boto SessionProxy
    :return: True if successful
    """
    elb_client = session.client('elb')
    elb2_client = session.client('elbv2')
    rg = session.client('resourcegroupstaggingapi')
    elb2_waiter = elb2_client.get_waiter('load_balancers_deleted')
    elb_response = rg.get_resources(
        TagFilters=[{
            'Key': f'kubernetes.io/cluster/{model.InfrastructureId}', 'Values': ['owned']
        }], ResourceTypeFilters=['elasticloadbalancing:loadbalancer'])
    for lb in elb_response['ResourceTagMappingList']:
        log.info('[DELETE] Deleting load balancer %s', lb['ResourceARN'])
        if '/net/' in lb['ResourceARN']:
            elb2_client.delete_load_balancer(
                LoadBalancerArn=lb['ResourceARN']
            )
            elb2_waiter.wait(LoadBalancerArns=[lb['ResourceARN']])
        else:
            elb_client.delete_load_balancer(LoadBalancerName=lb['ResourceARN'].split('/')[1])
            time.sleep(15)

    tg_response = rg.get_resources(
        TagFilters=[{
            'Key': f'kubernetes.io/cluster/{model.InfrastructureId}', 'Values': ['owned']
        }], ResourceTypeFilters=['elasticloadbalancing:targetgroup'])
    for tg in tg_response['ResourceTagMappingList']:
        log.info('[DELETE] Deleting Target Group %s', tg['ResourceARN'])
        elb2_client.delete_target_group(TargetGroupArn=tg['ResourceARN'])

    return True
