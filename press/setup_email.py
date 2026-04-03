import frappe

def run():
    # Check if Email Account already exists
    if frappe.db.exists("Email Account", "Demo Notifications"):
        print("Email Account 'Demo Notifications' already exists, updating...")
        doc = frappe.get_doc("Email Account", "Demo Notifications")
    else:
        print("Creating Email Account 'Demo Notifications'...")
        doc = frappe.new_doc("Email Account")
        doc.email_account_name = "Demo Notifications"

    doc.email_id = "info@optiflowsys.com"
    doc.password = "info@345621!"
    doc.smtp_server = "mail.acsprosys.com"
    doc.smtp_port = 587
    doc.use_tls = 1
    doc.use_ssl = 0
    doc.default_outgoing = 1
    doc.enable_outgoing = 1
    doc.enable_incoming = 0
    doc.send_notifications_to = ""
    doc.always_use_account_email_id_as_sender = 1

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Email Account saved: {doc.name}")

    # Remove disable_mail_notifications from site_config
    conf = frappe.get_site_config()
    if conf.get("disable_mail_notifications"):
        print("Removing disable_mail_notifications from site_config...")
        frappe.conf.disable_mail_notifications = 0

    # Test send
    try:
        frappe.sendmail(
            recipients=["info@optiflowsys.com"],
            subject="Press Demo - Email Test",
            message="<p>Email notifications are working on the Press panel.</p>",
            now=True,
        )
        print("Test email sent to info@optiflowsys.com")
    except Exception as e:
        print(f"Test email failed: {e}")
        print("Try port 465 with SSL instead...")
