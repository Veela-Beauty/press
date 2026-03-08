# Alibaba Cloud integration methods for Cluster doctype
# This file is imported into cluster.py via mixin pattern

import frappe
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_vpc20160428.client import Client as VpcClient
from alibabacloud_vpc20160428 import models as vpc_models
from alibabacloud_tea_openapi import models as open_api_models


def get_alibaba_config(cluster):
    """Build OpenAPI config from Cluster fields."""
    return open_api_models.Config(
        access_key_id=cluster.alibaba_access_key_id,
        access_key_secret=cluster.get_password("alibaba_access_key_secret"),
        region_id=cluster.alibaba_region_id,
    )


def get_alibaba_ecs_client(cluster):
    config = get_alibaba_config(cluster)
    config.endpoint = f"ecs.{cluster.alibaba_region_id}.aliyuncs.com"
    return EcsClient(config)


def get_alibaba_vpc_client(cluster):
    config = get_alibaba_config(cluster)
    config.endpoint = f"vpc.{cluster.alibaba_region_id}.aliyuncs.com"
    return VpcClient(config)


def validate_alibaba_credentials(cluster):
    """Validate Alibaba Cloud credentials by listing regions."""
    try:
        client = get_alibaba_ecs_client(cluster)
        request = ecs_models.DescribeRegionsRequest(region_id=cluster.alibaba_region_id)
        response = client.describe_regions(request)
        if not response.body.regions.region:
            frappe.throw("Alibaba Cloud credentials are valid but no regions found.")
    except Exception as e:
        frappe.throw(f"Failed to validate Alibaba Cloud credentials: {e!s}")


def provision_on_alibaba(cluster):
    """Provision VPC, VSwitch, Security Groups on Alibaba Cloud."""
    vpc_client = get_alibaba_vpc_client(cluster)

    # 1. Create VPC
    try:
        vpc_request = vpc_models.CreateVpcRequest(
            region_id=cluster.alibaba_region_id,
            cidr_block=cluster.cidr_block,
            vpc_name=f"Press-{cluster.name}",
        )
        vpc_response = vpc_client.create_vpc(vpc_request)
        cluster.vpc_id = vpc_response.body.vpc_id
        cluster.save()
    except Exception as e:
        frappe.throw(f"Failed to create VPC on Alibaba Cloud: {e!s}")

    # Wait for VPC to be available
    import time
    time.sleep(5)

    # 2. Create VSwitch (subnet)
    try:
        # Get first available zone
        zone_request = vpc_models.DescribeZonesRequest(region_id=cluster.alibaba_region_id)
        # Use ECS to get zones
        ecs_client = get_alibaba_ecs_client(cluster)
        zone_ecs_request = ecs_models.DescribeZonesRequest(region_id=cluster.alibaba_region_id)
        zone_response = ecs_client.describe_zones(zone_ecs_request)
        zone_id = zone_response.body.zones.zone[0].zone_id

        vswitch_request = vpc_models.CreateVSwitchRequest(
            vpc_id=cluster.vpc_id,
            cidr_block=cluster.subnet_cidr_block,
            zone_id=zone_id,
            region_id=cluster.alibaba_region_id,
            v_switch_name=f"Press-{cluster.name}-subnet",
        )
        vswitch_response = vpc_client.create_v_switch(vswitch_request)
        cluster.availability_zone = zone_id
        # Store vswitch_id — we'll need it for VM creation
        # Using route_table_id field to store vswitch_id (reusing existing field)
        cluster.route_table_id = vswitch_response.body.v_switch_id
        cluster.save()
    except Exception as e:
        frappe.throw(f"Failed to create VSwitch on Alibaba Cloud: {e!s}")

    # 3. Create Security Group
    try:
        ecs_client = get_alibaba_ecs_client(cluster)
        sg_request = ecs_models.CreateSecurityGroupRequest(
            region_id=cluster.alibaba_region_id,
            vpc_id=cluster.vpc_id,
            security_group_name=f"Press-{cluster.name}-sg",
        )
        sg_response = ecs_client.create_security_group(sg_request)
        cluster.security_group_id = sg_response.body.security_group_id
        cluster.save()

        # Add firewall rules
        rules = [
            ("tcp", "22/22", "0.0.0.0/0", "SSH"),
            ("tcp", "80/80", "0.0.0.0/0", "HTTP"),
            ("tcp", "443/443", "0.0.0.0/0", "HTTPS"),
            ("tcp", "3306/3306", cluster.subnet_cidr_block, "MariaDB"),
            ("tcp", "2049/2049", cluster.subnet_cidr_block, "NFS"),
            ("tcp", "11000/20000", cluster.subnet_cidr_block, "Redis"),
            ("tcp", "22000/22999", cluster.subnet_cidr_block, "SSH-containers"),
            ("icmp", "-1/-1", "0.0.0.0/0", "ICMP"),
        ]
        for protocol, port_range, source, desc in rules:
            rule_request = ecs_models.AuthorizeSecurityGroupRequest(
                region_id=cluster.alibaba_region_id,
                security_group_id=cluster.security_group_id,
                ip_protocol=protocol,
                port_range=port_range,
                source_cidr_ip=source,
                description=desc,
            )
            ecs_client.authorize_security_group(rule_request)

    except Exception as e:
        frappe.throw(f"Failed to create Security Group on Alibaba Cloud: {e!s}")

    # 4. Create Proxy Security Group (same rules + proxy-specific)
    try:
        proxy_sg_request = ecs_models.CreateSecurityGroupRequest(
            region_id=cluster.alibaba_region_id,
            vpc_id=cluster.vpc_id,
            security_group_name=f"Press-{cluster.name}-proxy-sg",
        )
        proxy_sg_response = ecs_client.create_security_group(proxy_sg_request)
        cluster.proxy_security_group_id = proxy_sg_response.body.security_group_id
        cluster.save()

        proxy_rules = [
            ("tcp", "22/22", "0.0.0.0/0", "SSH"),
            ("tcp", "80/80", "0.0.0.0/0", "HTTP"),
            ("tcp", "443/443", "0.0.0.0/0", "HTTPS"),
            ("tcp", "2222/2222", "0.0.0.0/0", "SSH-proxy"),
            ("icmp", "-1/-1", "0.0.0.0/0", "ICMP"),
        ]
        for protocol, port_range, source, desc in proxy_rules:
            rule_request = ecs_models.AuthorizeSecurityGroupRequest(
                region_id=cluster.alibaba_region_id,
                security_group_id=cluster.proxy_security_group_id,
                ip_protocol=protocol,
                port_range=port_range,
                source_cidr_ip=source,
                description=desc,
            )
            ecs_client.authorize_security_group(rule_request)

    except Exception as e:
        frappe.throw(f"Failed to create Proxy Security Group on Alibaba Cloud: {e!s}")

    frappe.msgprint("Alibaba Cloud infrastructure provisioned successfully.")
