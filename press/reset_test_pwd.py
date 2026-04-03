import frappe

def reset():
    frappe.set_user("Administrator")
    user = frappe.get_doc("User", "test@mvpstorm.com")
    frappe.utils.password.update_password("test@mvpstorm.com", "Test@1234")
    print("Password reset for test@mvpstorm.com")
