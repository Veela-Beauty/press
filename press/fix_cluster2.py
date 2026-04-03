import frappe

def fix():
    frappe.set_user("Administrator")

    # Check cluster
    cluster = frappe.get_doc("Cluster", "Default")
    print(f"Cluster: {cluster.name}")
    print(f"  public: {cluster.public}")
    print(f"  image: {cluster.image}")
    print(f"  beta: {cluster.beta}")

    # Check server's cluster
    server = frappe.get_doc("Server", "press-f1.demo.mvpstorm.com")
    print(f"\nServer cluster: {server.cluster}")

    # Make sure cluster is public
    if not cluster.public:
        cluster.public = 1
        cluster.save(ignore_permissions=True)
        frappe.db.commit()
        print("Fixed: cluster set to public")

    # Test the method
    from press.press.doctype.cluster.cluster import Cluster as ClusterClass
    result = ClusterClass.get_all_for_new_bench()
    print(f"\nget_all_for_new_bench result: {result}")

    # Debug step by step
    cluster_names = list(set(frappe.db.get_all("Server", filters={"status": "Active"}, pluck="cluster")))
    print(f"\nActive server clusters: {cluster_names}")

    clusters = frappe.db.get_all("Cluster",
        filters={"name": ("in", cluster_names), "public": True},
        fields=["name", "title", "image", "beta"]
    )
    print(f"Filtered clusters: {clusters}")
