"""Alibaba Cloud integration methods for Virtual Machine doctype."""

import frappe
from frappe.utils import cint


def get_alibaba_client(vm):
    """Get Alibaba ECS client from VM's cluster config."""
    from alibabacloud_ecs20140526.client import Client as EcsClient
    from alibabacloud_tea_openapi import models as open_api_models

    cluster = frappe.get_doc("Cluster", vm.cluster)
    config = open_api_models.Config(
        access_key_id=cluster.alibaba_access_key_id,
        access_key_secret=cluster.get_password("alibaba_access_key_secret"),
        region_id=cluster.alibaba_region_id,
        endpoint=f"ecs.{cluster.alibaba_region_id}.aliyuncs.com",
    )
    return EcsClient(config)


def get_alibaba_status_map():
    return {
        "Pending": "Pending",
        "Running": "Running",
        "Starting": "Pending",
        "Stopping": "Pending",
        "Stopped": "Stopped",
    }


def provision_alibaba(vm):
    """Provision an Alibaba Cloud ECS instance."""
    from alibabacloud_ecs20140526 import models as ecs_models

    if not vm.machine_image:
        frappe.throw("Machine Image is required to provision Alibaba Cloud Virtual Machine.")

    cluster = frappe.get_doc("Cluster", vm.cluster)
    client = get_alibaba_client(vm)

    # vswitch_id stored in cluster.route_table_id
    vswitch_id = cluster.route_table_id
    if not vswitch_id:
        frappe.throw("VSwitch ID not found. Please provision cluster infrastructure first.")

    try:
        system_disk = ecs_models.RunInstancesRequestSystemDisk(
            size="40",
            category="cloud_essd",
        )

        request = ecs_models.RunInstancesRequest(
            region_id=cluster.alibaba_region_id,
            image_id=vm.machine_image,
            instance_type=vm.machine_type,
            security_group_id=cluster.security_group_id,
            v_switch_id=vswitch_id,
            instance_name=vm.name,
            instance_charge_type="PostPaid",
            internet_max_bandwidth_out=5,
            system_disk=system_disk,
            key_pair_name=vm.ssh_key,
            amount=1,
            user_data=vm.get_cloud_init() if vm.virtual_machine_image else None,
        )

        # Assign private IP if specified
        if vm.private_ip_address:
            request.private_ip_address = vm.private_ip_address

        response = client.run_instances(request)
        instance_id = response.body.instance_id_sets.instance_id_set[0]
        vm.instance_id = instance_id
        vm.status = "Pending"
        vm.save()
        frappe.db.commit()

    except Exception as e:
        frappe.throw(f"Failed to provision Alibaba Cloud ECS instance: {e!s}")


def sync_alibaba(vm, *args, **kwargs):
    """Sync VM state from Alibaba Cloud."""
    from alibabacloud_ecs20140526 import models as ecs_models

    client = get_alibaba_client(vm)
    cluster = frappe.get_doc("Cluster", vm.cluster)

    try:
        request = ecs_models.DescribeInstancesRequest(
            region_id=cluster.alibaba_region_id,
            instance_ids=f'["{vm.instance_id}"]',
        )
        response = client.describe_instances(request)
        instances = response.body.instances.instance

        if not instances:
            vm.status = "Terminated"
            vm.save()
            vm.update_servers()
            return

        instance = instances[0]
        status_map = get_alibaba_status_map()
        vm.status = status_map.get(instance.status, "Pending")
        vm.machine_type = instance.instance_type
        vm.vcpu = instance.cpu
        vm.ram = instance.memory

        # Get IPs
        if instance.vpc_attributes and instance.vpc_attributes.private_ip_address:
            ips = instance.vpc_attributes.private_ip_address.ip_address
            vm.private_ip_address = ips[0] if ips else ""

        if instance.public_ip_address and instance.public_ip_address.ip_address:
            vm.public_ip_address = instance.public_ip_address.ip_address[0]
        elif instance.eip_address and instance.eip_address.ip_address:
            vm.public_ip_address = instance.eip_address.ip_address

        vm.save()
        vm.update_servers()

    except Exception as e:
        frappe.log_error(f"Alibaba Cloud sync error for {vm.name}: {e!s}")


def reboot_alibaba(vm):
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)
    request = ecs_models.RebootInstanceRequest(instance_id=vm.instance_id)
    client.reboot_instance(request)


def start_alibaba(vm):
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)
    request = ecs_models.StartInstanceRequest(instance_id=vm.instance_id)
    client.start_instance(request)


def stop_alibaba(vm, force=False):
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)
    request = ecs_models.StopInstanceRequest(
        instance_id=vm.instance_id,
        force_stop=force,
    )
    client.stop_instance(request)


def terminate_alibaba(vm):
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)

    # First disable deletion protection if enabled
    try:
        mod_request = ecs_models.ModifyInstanceAttributeRequest(
            instance_id=vm.instance_id,
            deletion_protection=False,
        )
        client.modify_instance_attribute(mod_request)
    except Exception:
        pass

    request = ecs_models.DeleteInstanceRequest(
        instance_id=vm.instance_id,
        force=True,
    )
    client.delete_instance(request)


def resize_alibaba(vm, machine_type):
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)
    request = ecs_models.ModifyInstanceSpecRequest(
        instance_id=vm.instance_id,
        instance_type=machine_type,
    )
    client.modify_instance_spec(request)


def get_latest_ubuntu_image_alibaba(vm):
    """Find latest Ubuntu 22.04 image on Alibaba Cloud."""
    from alibabacloud_ecs20140526 import models as ecs_models
    client = get_alibaba_client(vm)
    cluster = frappe.get_doc("Cluster", vm.cluster)

    request = ecs_models.DescribeImagesRequest(
        region_id=cluster.alibaba_region_id,
        os_type="linux",
        image_name="ubuntu_22_04*",
        status="Available",
    )
    response = client.describe_images(request)
    images = response.body.images.image

    if images:
        return images[0].image_id

    return None
