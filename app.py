from flask import Flask, render_template
import boto3

app = Flask(__name__)

def get_audit_data():
    iam = boto3.client("iam")
    users = iam.list_users()

    def classify_risk(username, policies, mfa_enabled):
        risk_level = "LOW"
        reasons = []
        mitre = []

        for policy in policies:
            if policy == "AdministratorAccess":
                if not mfa_enabled:
                    risk_level = "CRITICAL"
                    reasons.append("Admin access without MFA")
                    mitre.append("T1078 - Valid Accounts")
                else:
                    risk_level = "HIGH"
                    reasons.append("Has AdministratorAccess")
                    mitre.append("T1078 - Valid Accounts")

            if policy == "AmazonS3FullAccess" and "intern" in username.lower():
                if risk_level not in ["CRITICAL", "HIGH"]:
                    risk_level = "MEDIUM"
                reasons.append("Intern has S3 Full Access - violates least privilege")
                mitre.append("T1530 - Data from Cloud Storage")

        if "inactive" in username.lower():
            if risk_level not in ["CRITICAL"]:
                risk_level = "HIGH"
            reasons.append("Inactive user still has active access")
            mitre.append("T1098 - Account Manipulation")

        if not mfa_enabled:
            if risk_level == "LOW":
                risk_level = "MEDIUM"
            reasons.append("MFA not enabled")
            mitre.append("T1556 - Modify Authentication Process")

        return risk_level, reasons, mitre

    audit_results = []

    for user in users["Users"]:
        username = user["UserName"]

        policies_response = iam.list_attached_user_policies(UserName=username)
        policy_names = [p["PolicyName"] for p in policies_response["AttachedPolicies"]]

        mfa_response = iam.list_mfa_devices(UserName=username)
        mfa_enabled = len(mfa_response["MFADevices"]) > 0

        risk, reasons, mitre = classify_risk(username, policy_names, mfa_enabled)

        audit_results.append({
            "username": username,
            "policies": ", ".join(policy_names) if policy_names else "None",
            "mfa": "Enabled" if mfa_enabled else "Disabled",
            "risk": risk,
            "reasons": ", ".join(reasons) if reasons else "No issues found",
            "mitre": ", ".join(mitre) if mitre else "N/A"
        })

    return audit_results


@app.route("/")
def dashboard():
    results = get_audit_data()

    summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in results:
        summary[r["risk"]] += 1

    return render_template("dashboard.html", results=results, summary=summary)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)