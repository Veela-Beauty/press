def check_hetzner_keys():
    import frappe
    from hcloud import Client

    cluster = frappe.get_doc("Cluster", "Default")
    api_token = cluster.get_password("hetzner_api_token")

    client = Client(token=api_token)
    ssh_keys = client.ssh_keys.get_all()
    for key in ssh_keys:
        print(f"Name: {key.name}, ID: {key.id}")
        print(f"  Public key: {key.public_key[:100]}...")

    return "done"
