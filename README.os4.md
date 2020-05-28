# Development notes for OpenShift4 Quick Start


# Feature Tasks

## Multiple AZ Deployment

**DONE**

## Define machine set for each AZ

**DONE** -- Autoscaling is not configured by default . up to cluster operator to set up autoscaling .

Autoscale testing was completed 05-26 . We can supply documentation on how to
set up autoscaling after cluster is set up

## Take VPC details as parameter

**DONE** --

Tested 05-28

## BYO Certificates

Allow Stack operators to pass in an ACM certificate ARN to use for the default
cluster ingress loadbalancer. OS4 installation does not natively support this and we need to code some steps into a Lambda custom resource

If user BYO certificate, do the following. Otherwise, keep default behavior (OS4 generates a classic load balancer with a self-signed certificate):
1. during installation, turn off DNS zone management
2. Wait for cluster to come up
3. Edit the Openshift router service `oc edit services -n openshift-ingress router-default` using a Lambda func / custom resource
4. Add annotations
```
service.beta.kubernetes.io/aws-load-balancer-backend-protocol: ssl
service.beta.kubernetes.io/aws-load-balancer-proxy-protocol: '*'
service.beta.kubernetes.io/aws-load-balancer-ssl-cert: <ACM_ARN>
service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"
```
6. Wait for loadbalancer resource to be created
7. Create wildcard `*.apps.<clusterdomain>` alias record in private zone
8. Create wildcard `*.apps.<clusterdomain>` alias record in public zone

This process was tested 05-27

# TODOs

- [ ] Allow users to select number of Master nodes at install
- [ ] Allow users to select number of Worker nodes at install
