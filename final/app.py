from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
import sqlite3, os, json, random, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = "soar-sentinel-enterprise-soc-token-2026-hypercyber"
DB_PATH = os.path.join(os.path.dirname(__file__), "soar.db")

# Demo users with roles
USERS = {
    "sarah@soar.corp": {"name": "Sarah Connor", "role": "Senior SOC Analyst", "avatar": "SC", "clearance": "Top Secret // Alpha", "color": "#06b6d4"},
    "alex@soar.corp": {"name": "Alex Vance", "role": "Incident Commander", "avatar": "AV", "clearance": "Command Staff", "color": "#8b5cf6"},
    "admin@soar.corp": {"name": "David Lightman", "role": "SecOps Architect", "avatar": "DL", "clearance": "System Root", "color": "#10b981"}
}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_current_user():
    user_email = session.get("user_email", "sarah@soar.corp")
    return USERS.get(user_email, USERS["sarah@soar.corp"])

@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}

def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'Medium',
            source TEXT NOT NULL DEFAULT 'Manual',
            status TEXT NOT NULL DEFAULT 'New',
            details TEXT DEFAULT '',
            assigned_to TEXT DEFAULT 'Analyst Sarah',
            mitre_technique TEXT DEFAULT 'T1110 - Brute Force',
            artifacts_json TEXT DEFAULT '[]',
            containment_status TEXT DEFAULT 'None',
            created_at TEXT NOT NULL,
            updated_at TEXT DEFAULT ''
        )""")

        cursor = conn.execute("PRAGMA table_info(incidents)")
        cols = [c[1] for c in cursor.fetchall()]
        if "assigned_to" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN assigned_to TEXT DEFAULT 'Analyst Sarah'")
        if "mitre_technique" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN mitre_technique TEXT DEFAULT 'T1110 - Brute Force'")
        if "artifacts_json" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN artifacts_json TEXT DEFAULT '[]'")
        if "containment_status" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN containment_status TEXT DEFAULT 'None'")
        if "updated_at" not in cols:
            conn.execute("ALTER TABLE incidents ADD COLUMN updated_at TEXT DEFAULT ''")

        conn.execute("""CREATE TABLE IF NOT EXISTS iocs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER,
            ioc_type TEXT NOT NULL,
            value TEXT NOT NULL,
            reputation TEXT NOT NULL DEFAULT 'Unknown',
            threat_score INTEGER DEFAULT 50,
            enrichment_details TEXT DEFAULT '{}',
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS playbooks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            severity_trigger TEXT DEFAULT 'High',
            description TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            auto_trigger INTEGER DEFAULT 0,
            runs_count INTEGER DEFAULT 0,
            last_run TEXT DEFAULT 'Never'
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS playbook_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playbook_id TEXT NOT NULL,
            incident_id INTEGER,
            playbook_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Completed',
            triggered_by TEXT DEFAULT 'Analyst',
            current_step INTEGER DEFAULT 1,
            total_steps INTEGER DEFAULT 4,
            logs_json TEXT DEFAULT '[]',
            started_at TEXT NOT NULL,
            completed_at TEXT DEFAULT ''
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS containment_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER,
            action_type TEXT NOT NULL,
            target TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            executed_by TEXT DEFAULT 'SOAR Orchestrator',
            system TEXT NOT NULL,
            details TEXT DEFAULT '',
            timestamp TEXT NOT NULL
        )""")

        conn.execute("""CREATE TABLE IF NOT EXISTS incident_timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            action_type TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )""")

        pb_count = conn.execute("SELECT COUNT(*) FROM playbooks").fetchone()[0]
        if pb_count == 0:
            default_playbooks = [
                ("pb-bruteforce", "Automated Brute-Force & Credential Triage", "Identity & Auth", "High",
                 "Enriches source IP via AbuseIPDB, checks user lockout status in AD, prompts firewall containment gate, and revokes active token sessions.",
                 json.dumps([
                     {"id": 1, "title": "Extract Source IP & Target User", "system": "Internal Parser", "action": "parse_ioc", "requires_approval": False},
                     {"id": 2, "title": "Enrich IP Reputation via AbuseIPDB & GeoIP", "system": "AbuseIPDB API", "action": "threat_intel_lookup", "requires_approval": False},
                     {"id": 3, "title": "Check Active Directory Lockout Threshold", "system": "Active Directory LDAP", "action": "check_ad_status", "requires_approval": False},
                     {"id": 4, "title": "Human-In-The-Loop: Confirm Perimeter Block", "system": "SOC Approval Gate", "action": "analyst_approval", "requires_approval": True},
                     {"id": 5, "title": "Push Drop Rule to Palo Alto Firewall", "system": "Palo Alto Networks", "action": "firewall_block_ip", "requires_approval": False},
                     {"id": 6, "title": "Post Alert Summary to #soc-triage", "system": "Slack Webhook", "action": "send_notification", "requires_approval": False}
                 ]), 1, 14, "2026-10-12 18:32:10"),
                ("pb-ransomware", "Ransomware Outbreak & Host Isolation", "Endpoint & Malware", "Critical",
                 "Rapid host isolation via CrowdStrike EDR, halts high-frequency disk write process trees, dumps memory snapshot, and blacklists external C2 IP.",
                 json.dumps([
                     {"id": 1, "title": "Identify Compromised Host & Process Tree", "system": "CrowdStrike Falcon", "action": "query_endpoint", "requires_approval": False},
                     {"id": 2, "title": "Quarantine Endpoint from Network", "system": "EDR Agent", "action": "isolate_endpoint", "requires_approval": True},
                     {"id": 3, "title": "Terminate Rogue Cryptor Process & Subprocesses", "system": "EDR Agent", "action": "kill_process", "requires_approval": False},
                     {"id": 4, "title": "Block C2 Beacon IP across Border Gateways", "system": "Perimeter Firewall", "action": "firewall_block_ip", "requires_approval": False},
                     {"id": 5, "title": "Dispatch High-Priority PagerDuty to CISO", "system": "PagerDuty API", "action": "dispatch_escalation", "requires_approval": False}
                 ]), 1, 6, "2026-10-13 04:15:22"),
                ("pb-phishing", "Spearphishing Email & IOC Neutralization", "Email Security", "High",
                 "Extracts malicious headers, attachments, and URLs; queries VirusTotal; purges matching messages from all Exchange/M365 mailboxes; sinkholes domain.",
                 json.dumps([
                     {"id": 1, "title": "Extract Sender, URL, & Attachment Hash", "system": "Email Parser", "action": "parse_ioc", "requires_approval": False},
                     {"id": 2, "title": "VirusTotal & URLScan Multi-Engine Scan", "system": "VirusTotal API", "action": "threat_intel_lookup", "requires_approval": False},
                     {"id": 3, "title": "Global Tenant Mailbox Search for Message-ID", "system": "Microsoft 365 Graph", "action": "search_mailboxes", "requires_approval": False},
                     {"id": 4, "title": "Purge Malicious Message Across All Inboxes", "system": "Microsoft 365 Graph", "action": "purge_email", "requires_approval": True},
                     {"id": 5, "title": "Add Phishing Domain to Perimeter DNS Sinkhole", "system": "DNS Gateway", "action": "sinkhole_domain", "requires_approval": False}
                 ]), 0, 9, "2026-10-11 11:40:00"),
                ("pb-powershell", "Suspicious Living-off-the-Land Script Triage", "Endpoint & OS", "Medium",
                 "Deobfuscates Base64 encoded PowerShell commands, extracts command line arguments, checks against IT admin approved whitelist, and halts execution.",
                 json.dumps([
                     {"id": 1, "title": "Decode EncodedCommand & Parse Arguments", "system": "Script Deobfuscator", "action": "decode_powershell", "requires_approval": False},
                     {"id": 2, "title": "Compare Against Approved SysAdmin Baseline", "system": "Baseline Engine", "action": "baseline_check", "requires_approval": False},
                     {"id": 3, "title": "Human-In-The-Loop: Confirm Execution Context", "system": "Analyst Gate", "action": "analyst_approval", "requires_approval": True},
                     {"id": 4, "title": "Suspend Compromised User Active Session", "system": "Active Directory", "action": "suspend_user", "requires_approval": False}
                 ]), 0, 12, "2026-10-12 14:05:12"),
                ("pb-c2beacon", "C2 Beaconing & Lateral Movement Defense", "Network & Perimeter", "High",
                 "Detects regular interval jitter beacons, flags suspect DNS tunneling, injects firewall drop rules, and triggers automated PCAP packet capture.",
                 json.dumps([
                     {"id": 1, "title": "Correlate Jitter and Beacon Frequency", "system": "Suricata / Zeek", "action": "analyze_traffic", "requires_approval": False},
                     {"id": 2, "title": "Check Domain Age & Reputation on Whois / VT", "system": "Threat Intel Engine", "action": "threat_intel_lookup", "requires_approval": False},
                     {"id": 3, "title": "Block Destination IP & Sinkhole Domain", "system": "Palo Alto Firewall", "action": "firewall_block_ip", "requires_approval": True},
                     {"id": 4, "title": "Collect Full Network PCAP for Host", "system": "Network Sensor", "action": "capture_pcap", "requires_approval": False}
                 ]), 1, 8, "2026-10-13 08:50:33")
            ]
            for pb in default_playbooks:
                conn.execute("INSERT INTO playbooks (id, name, category, severity_trigger, description, steps_json, auto_trigger, runs_count, last_run) VALUES (?,?,?,?,?,?,?,?,?)", pb)

        inc_count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        if inc_count == 0:
            sample_incidents = [
                ("Critical Credential Stuffing & SSH Brute Force", "Critical", "Wazuh SIEM", "In Progress",
                 "Over 3,400 failed SSH logins detected against srv-dc01.corp within 4 minutes originating from suspected bulletproof Tor exit node.",
                 "Sarah Connor", "T1110.001 - Password Guessing",
                 json.dumps([
                     {"type": "IP", "value": "185.220.101.5", "role": "Attacker Source"},
                     {"type": "Host", "value": "srv-dc01.corp", "role": "Target Domain Controller"},
                     {"type": "User", "value": "root", "role": "Target Account"}
                 ]), "Pending Approval", "2026-10-13 09:12:00", "2026-10-13 09:15:00"),

                ("High-Entropy File Renaming & Ransomware Canary Tripped", "Critical", "CrowdStrike Falcon", "Containment",
                 "Canary file honeypot on finance workstation WS-FIN-04 modified by unverified binary updater.exe with shadow copy deletion command.",
                 "Alex Vance", "T1486 - Data Encrypted for Impact",
                 json.dumps([
                     {"type": "Host", "value": "WS-FIN-04", "role": "Infected Host"},
                     {"type": "Hash", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "role": "Malware SHA256"},
                     {"type": "IP", "value": "91.240.118.172", "role": "C2 Server"}
                 ]), "Isolated", "2026-10-13 08:30:00", "2026-10-13 08:45:00"),

                ("Obfuscated Base64 PowerShell Invocation via Word Macro", "High", "Windows Defender ATP", "In Progress",
                 "User opened invoice_oct_2026.docm which spawned powershell.exe -enc SQBFAFgA... connecting to external webdav share.",
                 "Sarah Connor", "T1059.001 - PowerShell",
                 json.dumps([
                     {"type": "Host", "value": "WS-HR-02", "role": "Executing Endpoint"},
                     {"type": "User", "value": "j.smith", "role": "Compromised User"},
                     {"type": "Domain", "value": "payload-cdn-download.ru", "role": "Drop Site"}
                 ]), "None", "2026-10-13 07:44:00", "2026-10-13 07:50:00"),

                ("DNS Tunneling & C2 Beaconing Activity", "High", "Suricata IDS", "New",
                 "Workstation sending anomalous TXT record DNS queries of 210 bytes length every 60 seconds with low jitter to external nameserver.",
                 "David Lightman", "T1071.004 - DNS C2",
                 json.dumps([
                     {"type": "IP", "value": "192.168.1.144", "role": "Internal Source"},
                     {"type": "Domain", "value": "ns1.c2-exfil-node.top", "role": "Suspect Nameserver"}
                 ]), "None", "2026-10-13 06:18:00", "2026-10-13 06:20:00"),

                ("Unauthorized Admin Privileges Granted to Service Account", "Medium", "AWS CloudTrail", "Resolved",
                 "IAM Role svc-deploy granted AdministratorAccess policy outside maintenance window by user alex_soc.",
                 "Alex Vance", "T1098 - Account Manipulation",
                 json.dumps([
                     {"type": "User", "value": "svc-deploy", "role": "Target Role"},
                     {"type": "User", "value": "alex_soc", "role": "Granting Identity"}
                 ]), "Contained", "2026-10-12 21:05:00", "2026-10-12 21:30:00")
            ]
            for inc in sample_incidents:
                conn.execute("""INSERT INTO incidents 
                (title, severity, source, status, details, assigned_to, mitre_technique, artifacts_json, containment_status, created_at, updated_at) 
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""", inc)

        ioc_count = conn.execute("SELECT COUNT(*) FROM iocs").fetchone()[0]
        if ioc_count == 0:
            sample_iocs = [
                (1, "IP", "185.220.101.5", "Malicious", 96, json.dumps({"asn": "AS208323", "country": "Germany", "abuse_confidence": 98, "isp": "Tor Exit Router", "reports": 312}), "Blocked", "2026-10-13 09:12:00"),
                (2, "Host", "WS-FIN-04", "Suspicious", 85, json.dumps({"os": "Windows 11 Enterprise", "ip": "10.0.4.15", "domain": "corp.local", "quarantine": "Active"}), "Active", "2026-10-13 08:30:00"),
                (2, "IP", "91.240.118.172", "Malicious", 99, json.dumps({"asn": "AS49505", "country": "Russia", "abuse_confidence": 100, "isp": "Known Bulletproof Host", "reports": 850}), "Blocked", "2026-10-13 08:32:00"),
                (3, "Domain", "payload-cdn-download.ru", "Malicious", 92, json.dumps({"registrar": "Reg.ru", "created": "2026-10-09", "virustotal_positives": "47/72"}), "Blocked", "2026-10-13 07:45:00"),
                (4, "Domain", "ns1.c2-exfil-node.top", "Suspicious", 78, json.dumps({"category": "Dynamic DNS", "entropy": 4.8, "virustotal_positives": "22/71"}), "Active", "2026-10-13 06:19:00"),
                (None, "Hash", "44d88612fea8a8f36de82e1278abb02f", "Malicious", 100, json.dumps({"family": "Mimikatz / LSASS Dumper", "virustotal_positives": "66/70"}), "Blocked", "2026-10-12 18:00:00")
            ]
            for ioc in sample_iocs:
                conn.execute("INSERT INTO iocs (incident_id, ioc_type, value, reputation, threat_score, enrichment_details, status, created_at) VALUES (?,?,?,?,?,?,?,?)", ioc)

        act_count = conn.execute("SELECT COUNT(*) FROM containment_actions").fetchone()[0]
        if act_count == 0:
            sample_actions = [
                (1, "Block IP", "185.220.101.5", "Active", "Playbook Engine", "Palo Alto Firewall", "Pushed dynamic block rule to Edge-FW-01 via REST API.", "2026-10-13 09:16:10"),
                (2, "Isolate Host", "WS-FIN-04", "Active", "Alex Vance", "CrowdStrike Falcon", "Network containment applied via agent RTR. Host isolated.", "2026-10-13 08:35:22"),
                (2, "Block IP", "91.240.118.172", "Active", "SOAR Orchestrator", "Palo Alto Firewall", "C2 IP blocked across all security policy zones.", "2026-10-13 08:36:00"),
                (3, "Sinkhole Domain", "payload-cdn-download.ru", "Active", "SOAR Orchestrator", "Internal DNS Resolver", "Sinkholed to loopback 127.0.0.1", "2026-10-13 07:51:14")
            ]
            for act in sample_actions:
                conn.execute("INSERT INTO containment_actions (incident_id, action_type, target, status, executed_by, system, details, timestamp) VALUES (?,?,?,?,?,?,?,?)", act)

        time_count = conn.execute("SELECT COUNT(*) FROM incident_timeline").fetchone()[0]
        if time_count == 0:
            sample_timeline = [
                (1, "Wazuh SIEM", "Alert Ingested", "Alert received: SSH brute force detection rule 5710 triggered 340 times.", "2026-10-13 09:12:00"),
                (1, "Playbook Engine", "Playbook Executed", "Playbook 'Automated Brute-Force & Credential Triage' auto-initiated.", "2026-10-13 09:12:05"),
                (1, "Threat Intel", "Enrichment", "IOC 185.220.101.5 scored 96/100 (AbuseIPDB Tor exit node).", "2026-10-13 09:12:12"),
                (1, "Sarah Connor", "Approval Given", "Sarah Connor approved emergency firewall perimeter drop rule.", "2026-10-13 09:16:00"),
                (2, "CrowdStrike Falcon", "Alert Ingested", "Behavioral detection: Host WS-FIN-04 tripped ransomware canary files.", "2026-10-13 08:30:00"),
                (2, "Alex Vance", "Host Isolated", "Host quarantined from local subnet to prevent SMB lateral spreading.", "2026-10-13 08:35:22")
            ]
            for tl in sample_timeline:
                conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)", tl)

init_db()

# Threat Intel Calculation
def calculate_ioc_intelligence(ioc_type, value):
    val = value.strip()
    score = (sum(ord(c) for c in val) % 65) + 35
    if any(k in val.lower() for k in ["tor", "185.220", "evil", "c2", "mimikatz", "malware", "payload", "pastebin"]):
        score = min(100, score + 25)
        reputation = "Malicious"
    elif score >= 75:
        reputation = "Malicious"
    elif score >= 50:
        reputation = "Suspicious"
    else:
        reputation = "Benign"

    details = {
        "query_time": now_str(),
        "query_target": val,
        "ioc_type": ioc_type,
        "threat_score": score,
        "reputation": reputation,
        "virustotal": f"{min(68, int(score * 0.72))}/72 security engines flagged as malicious",
        "abuseipdb_confidence": f"{min(100, int(score * 1.05))}% confidence of abuse",
        "category": "Command & Control / Botnet" if score > 80 else "Suspicious Scanning & Probing",
        "geo": {"country": "Germany" if "185" in val else "Netherlands", "asn": "AS39812", "city": "Frankfurt"} if ioc_type == "IP" else {},
        "mitre_technique": "T1071 - Application Layer Protocol" if ioc_type in ["IP", "Domain"] else "T1059 - Command and Scripting Interpreter"
    }
    return score, reputation, details

# ==========================================
# AUTHENTICATION & LOGIN ROUTES
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if email in USERS:
            session["user_email"] = email
            return redirect(url_for("dashboard"))
        else:
            # Default to Sarah
            session["user_email"] = "sarah@soar.corp"
            return redirect(url_for("dashboard"))
    return render_template("login.html", users=USERS)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==========================================
# AI SOC COPILOT / CHATBOT
# ==========================================

@app.route("/copilot")
def copilot():
    with db() as conn:
        incidents = conn.execute("SELECT id, title, severity, status FROM incidents ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("copilot.html", incidents=incidents, page="copilot")

@app.route("/api/copilot/chat", methods=["POST"])
def copilot_chat():
    data = request.get_json(silent=True) or {}
    msg = data.get("message", "").strip().lower()

    with db() as conn:
        inc_count = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('New', 'Open', 'In Progress')").fetchone()[0]
        critical_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Critical'").fetchone()[0]
        latest_inc = conn.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 1").fetchone()
        blocked_iocs = conn.execute("SELECT COUNT(*) FROM iocs WHERE status='Blocked'").fetchone()[0]

    # Smart contextual responses
    reply = ""
    suggested_action = None

    if "incident" in msg or "triage" in msg or "analyze" in msg or "#1" in msg or "latest" in msg:
        if latest_inc:
            reply = f"🛡️ **Analysis for #{latest_inc['id']} ({latest_inc['title']})**:\n\n" \
                    f"- **Severity:** {latest_inc['severity']} | **Status:** {latest_inc['status']}\n" \
                    f"- **MITRE ATT&CK:** `{latest_inc['mitre_technique']}`\n" \
                    f"- **Recommended SOAR Response:** Immediate containment via Palo Alto perimeter block & Host isolation.\n\n" \
                    f"Would you like me to trigger the matching response playbook automatically?"
            suggested_action = {"label": "Run Playbook on Latest Alert", "url": f"/incidents/{latest_inc['id']}"}
        else:
            reply = "No active incidents found in the local telemetry queue."

    elif "ransomware" in msg or "encrypt" in msg or "canary" in msg:
        reply = "☣️ **Ransomware Threat Protocol Activated (MITRE T1486)**:\n\n" \
                "1. **Host Isolation:** Sever network connection to prevent SMB lateral spreading.\n" \
                "2. **Process Termination:** Kill rogue cryptor binaries & child subprocesses.\n" \
                "3. **C2 Blacklisting:** Block external IP addresses across all Palo Alto border firewalls.\n" \
                "4. **VSS Recovery:** Assess volume shadow copy integrity for system restoration.\n\n" \
                "Use the **'Simulate Attack'** button to test the automated Ransomware containment gate!"
        suggested_action = {"label": "Launch Ransomware Simulation", "url": "#simModal"}

    elif "brute" in msg or "password" in msg or "login" in msg or "ssh" in msg:
        reply = "⚡ **Brute Force Defense Procedure (MITRE T1110)**:\n\n" \
                "1. Extracted source IP will be evaluated against AbuseIPDB & Tor exit lists.\n" \
                "2. Active Directory lockout threshold verified.\n" \
                "3. If abuse confidence > 75%, SOAR pauses for analyst approval to push permanent DROP rule to edge routers."
        suggested_action = {"label": "Query Threat Intel", "url": "/threat-intel"}

    elif "isolate" in msg or "block" in msg or "contain" in msg:
        reply = f"🛡️ **Current Containment Status**:\n\n" \
                f"- Active Perimeter Blocks: **{blocked_iocs} indicators**\n" \
                f"- All containment actions are logged to the immutable audit trail with **1-click Rollback**.\n\n" \
                f"You can trigger manual containment actions directly from any incident War Room or the Containment Audit page."
        suggested_action = {"label": "View Containment Audit", "url": "/actions"}

    elif "summary" in msg or "status" in msg or "overview" in msg or "hello" in msg or "hi" in msg:
        user = get_current_user()
        reply = f"Greetings, **{user['name']}** ({user['role']}). Here is your real-time SOC snapshot:\n\n" \
                f"- Total Incidents Recorded: **{inc_count}**\n" \
                f"- Active Triage Queue: **{open_count} open cases** ({critical_count} Critical)\n" \
                f"- Perimeter Blocked IOCs: **{blocked_iocs}**\n" \
                f"- Playbook Orchestrator: **Online & Automated (74% MTTR reduction)**\n\n" \
                f"How may I assist your threat hunting operation today?"
    else:
        reply = f"🤖 **Sentinel AI Copilot**: I have inspected our telemetry database.\n\n" \
                f"You currently have **{open_count} active incidents** in the queue. " \
                f"I can analyze specific incidents, recommend MITRE ATT&CK mitigation tactics, run Threat Intel enrichment on suspicious IPs, or guide playbook execution."
        suggested_action = {"label": "View Incident Queue", "url": "/incidents"}

    return jsonify({
        "reply": reply,
        "suggested_action": suggested_action,
        "timestamp": now_str()
    })

# ==========================================
# CORE ROUTES
# ==========================================

@app.route("/")
def dashboard():
    with db() as conn:
        incidents = conn.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 6").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        open_count = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('New', 'Open')").fetchone()[0]
        investigating = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('In Progress', 'Investigating')").fetchone()[0]
        containment = conn.execute("SELECT COUNT(*) FROM incidents WHERE status='Containment'").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('Resolved', 'Closed')").fetchone()[0]

        critical = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Critical'").fetchone()[0]
        high = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='High'").fetchone()[0]
        medium = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Medium'").fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Low'").fetchone()[0]

        blocked_iocs = conn.execute("SELECT COUNT(*) FROM iocs WHERE status='Blocked'").fetchone()[0]
        playbook_runs = conn.execute("SELECT COUNT(*) FROM playbook_executions").fetchone()[0]
        containment_count = conn.execute("SELECT COUNT(*) FROM containment_actions").fetchone()[0]

        recent_executions = conn.execute("SELECT * FROM playbook_executions ORDER BY id DESC LIMIT 4").fetchall()
        recent_actions = conn.execute("SELECT * FROM containment_actions ORDER BY id DESC LIMIT 5").fetchall()

    chart_data = {
        "severity": [critical, high, medium, low],
        "timeline_labels": ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "Now"],
        "timeline_series": [12, 19, 34, 45, 62, 58, max(total, 64)],
        "response_series": [8, 14, 28, 38, 52, 49, max(playbook_runs, 55)]
    }

    return render_template("dashboard.html",
                           incidents=incidents,
                           total=total,
                           open_count=open_count,
                           investigating=investigating,
                           containment=containment,
                           resolved=resolved,
                           critical=critical,
                           high=high,
                           medium=medium,
                           low=low,
                           blocked_iocs=blocked_iocs,
                           playbook_runs=playbook_runs,
                           containment_count=containment_count,
                           recent_executions=recent_executions,
                           recent_actions=recent_actions,
                           chart_data=chart_data,
                           page="dashboard")

@app.route("/incidents")
def incidents():
    sev_filter = request.args.get("severity", "all")
    stat_filter = request.args.get("status", "all")
    q = request.args.get("q", "").strip().lower()

    query = "SELECT * FROM incidents WHERE 1=1"
    params = []
    if sev_filter != "all":
        query += " AND LOWER(severity) = ?"
        params.append(sev_filter.lower())
    if stat_filter != "all":
        query += " AND LOWER(status) = ?"
        params.append(stat_filter.lower())

    query += " ORDER BY id DESC"

    with db() as conn:
        rows = conn.execute(query, params).fetchall()
        parsed_rows = []
        for r in rows:
            item = dict(r)
            try:
                item["artifacts"] = json.loads(r["artifacts_json"] or "[]")
            except:
                item["artifacts"] = []
            if not q or q in item["title"].lower() or q in item["details"].lower() or q in item["source"].lower():
                parsed_rows.append(item)

    return render_template("incidents.html",
                           incidents=parsed_rows,
                           sev_filter=sev_filter,
                           stat_filter=stat_filter,
                           q=q,
                           page="incidents")

@app.route("/incidents/<int:incident_id>")
def incident_detail(incident_id):
    with db() as conn:
        incident = conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if not incident:
            return redirect(url_for("incidents"))

        inc_dict = dict(incident)
        try:
            inc_dict["artifacts"] = json.loads(incident["artifacts_json"] or "[]")
        except:
            inc_dict["artifacts"] = []

        iocs = conn.execute("SELECT * FROM iocs WHERE incident_id=? ORDER BY id DESC", (incident_id,)).fetchall()
        timeline = conn.execute("SELECT * FROM incident_timeline WHERE incident_id=? ORDER BY id DESC", (incident_id,)).fetchall()
        actions = conn.execute("SELECT * FROM containment_actions WHERE incident_id=? ORDER BY id DESC", (incident_id,)).fetchall()
        executions = conn.execute("SELECT * FROM playbook_executions WHERE incident_id=? ORDER BY id DESC", (incident_id,)).fetchall()
        playbooks = conn.execute("SELECT * FROM playbooks ORDER BY name ASC").fetchall()

    return render_template("incident_detail.html",
                           incident=inc_dict,
                           iocs=iocs,
                           timeline=timeline,
                           actions=actions,
                           executions=executions,
                           playbooks=playbooks,
                           page="incidents")

@app.route("/incidents/new", methods=["POST"])
def new_incident():
    title = request.form.get("title", "").strip()
    if title:
        severity = request.form.get("severity", "Medium")
        source = request.form.get("source", "Manual Analyst").strip() or "Manual Analyst"
        details = request.form.get("details", "").strip()
        assigned_to = request.form.get("assigned_to", get_current_user()["name"])
        mitre_technique = request.form.get("mitre_technique", "T1110 - Brute Force")
        iocs_raw = request.form.get("iocs_raw", "").strip()

        artifacts = []
        if iocs_raw:
            for line in iocs_raw.split("\n"):
                line = line.strip()
                if not line: continue
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", line):
                    artifacts.append({"type": "IP", "value": line, "role": "Investigated Entity"})
                elif "." in line and not line.startswith("http"):
                    artifacts.append({"type": "Domain", "value": line, "role": "Suspect Domain"})
                elif len(line) in [32, 40, 64]:
                    artifacts.append({"type": "Hash", "value": line, "role": "File Hash"})
                else:
                    artifacts.append({"type": "User/Host", "value": line, "role": "Entity"})

        with db() as conn:
            cursor = conn.execute("""INSERT INTO incidents 
            (title, severity, source, status, details, assigned_to, mitre_technique, artifacts_json, containment_status, created_at, updated_at) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (title, severity, source, "New", details, assigned_to, mitre_technique, json.dumps(artifacts), "None", now_str(), now_str()))
            new_id = cursor.lastrowid

            for art in artifacts:
                score, rep, det = calculate_ioc_intelligence(art["type"], art["value"])
                conn.execute("INSERT INTO iocs (incident_id, ioc_type, value, reputation, threat_score, enrichment_details, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                             (new_id, art["type"], art["value"], rep, score, json.dumps(det), "Active", now_str()))

            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (new_id, "System / Ingest", "Incident Created", f"Incident #{new_id} initialized with {len(artifacts)} extracted artifacts.", now_str()))

        return redirect(url_for("incident_detail", incident_id=new_id))
    return redirect(url_for("incidents"))

@app.route("/incidents/<int:incident_id>/status", methods=["POST"])
def update_status(incident_id):
    status = request.form.get("status", "New")
    assigned_to = request.form.get("assigned_to")
    user = get_current_user()
    with db() as conn:
        if assigned_to:
            conn.execute("UPDATE incidents SET status=?, assigned_to=?, updated_at=? WHERE id=?",
                         (status, assigned_to, now_str(), incident_id))
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (incident_id, user["name"], "Assignment / Status", f"Status changed to '{status}', assigned to {assigned_to}", now_str()))
        else:
            conn.execute("UPDATE incidents SET status=?, updated_at=? WHERE id=?", (status, now_str(), incident_id))
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (incident_id, user["name"], "Status Changed", f"Incident status transitioned to '{status}'", now_str()))
    return redirect(request.referrer or url_for("incident_detail", incident_id=incident_id))

@app.route("/incidents/<int:incident_id>/note", methods=["POST"])
def add_incident_note(incident_id):
    note = request.form.get("note", "").strip()
    author = request.form.get("author", get_current_user()["name"])
    if note:
        with db() as conn:
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (incident_id, author, "Analyst Note", note, now_str()))
            conn.execute("UPDATE incidents SET updated_at=? WHERE id=?", (now_str(), incident_id))
    return redirect(url_for("incident_detail", incident_id=incident_id))

@app.route("/incidents/<int:incident_id>/action", methods=["POST"])
def execute_containment_action(incident_id):
    action_type = request.form.get("action_type")
    target = request.form.get("target")
    system = request.form.get("system", "Security Gateway")
    actor = get_current_user()["name"]

    with db() as conn:
        details = f"Containment action '{action_type}' applied to {target} via {system} API by {actor}."
        conn.execute("INSERT INTO containment_actions (incident_id, action_type, target, status, executed_by, system, details, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                     (incident_id, action_type, target, "Active", actor, system, details, now_str()))

        conn.execute("UPDATE iocs SET status='Blocked' WHERE incident_id=? AND value=?", (incident_id, target))

        conn.execute("UPDATE incidents SET containment_status='Contained', status='Containment', updated_at=? WHERE id=?",
                     (now_str(), incident_id))

        conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                     (incident_id, actor, "Containment Action", f"Executed {action_type} on target [{target}] via {system}.", now_str()))

    return redirect(url_for("incident_detail", incident_id=incident_id))

# ==========================================
# PLAYBOOKS ENGINE
# ==========================================

@app.route("/playbooks")
def playbooks():
    with db() as conn:
        playbooks_list = conn.execute("SELECT * FROM playbooks ORDER BY runs_count DESC").fetchall()
        parsed_playbooks = []
        for p in playbooks_list:
            item = dict(p)
            item["steps"] = json.loads(p["steps_json"] or "[]")
            parsed_playbooks.append(item)

        executions = conn.execute("SELECT * FROM playbook_executions ORDER BY id DESC LIMIT 15").fetchall()
        parsed_executions = []
        for e in executions:
            item = dict(e)
            item["logs"] = json.loads(e["logs_json"] or "[]")
            parsed_executions.append(item)

        incidents = conn.execute("SELECT id, title, severity FROM incidents ORDER BY id DESC LIMIT 10").fetchall()

    return render_template("playbooks.html",
                           playbooks=parsed_playbooks,
                           executions=parsed_executions,
                           incidents=incidents,
                           page="playbooks")

@app.route("/playbooks/<pb_id>/execute", methods=["POST"])
def run_playbook(pb_id):
    incident_id = request.form.get("incident_id")
    triggered_by = get_current_user()["name"]

    with db() as conn:
        pb = conn.execute("SELECT * FROM playbooks WHERE id=?", (pb_id,)).fetchone()
        if not pb:
            return redirect(url_for("playbooks"))

        steps = json.loads(pb["steps_json"] or "[]")
        target_ip = "185.220.101.5"

        if incident_id:
            inc = conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
            if inc:
                try:
                    arts = json.loads(inc["artifacts_json"] or "[]")
                    for a in arts:
                        if a.get("type") == "IP":
                            target_ip = a.get("value")
                            break
                except:
                    pass

        logs = []
        requires_approval = False
        approval_step_idx = None

        for idx, step in enumerate(steps, 1):
            if step.get("requires_approval") and not requires_approval:
                requires_approval = True
                approval_step_idx = idx
                logs.append({
                    "step": idx,
                    "title": step["title"],
                    "system": step["system"],
                    "status": "Awaiting Approval",
                    "output": f"Gate paused: waiting for sign-off to proceed with {step['title']} on target {target_ip}."
                })
                break
            else:
                logs.append({
                    "step": idx,
                    "title": step["title"],
                    "system": step["system"],
                    "status": "Success",
                    "output": f"Executed successfully in 120ms on {step['system']}."
                })

        status = "Awaiting Approval" if requires_approval else "Completed"
        completed_at = "" if requires_approval else now_str()
        current_step = approval_step_idx if requires_approval else len(steps)

        cursor = conn.execute("""INSERT INTO playbook_executions
        (playbook_id, incident_id, playbook_name, status, triggered_by, current_step, total_steps, logs_json, started_at, completed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (pb_id, incident_id if incident_id else None, pb["name"], status, triggered_by, current_step, len(steps), json.dumps(logs), now_str(), completed_at))
        exec_id = cursor.lastrowid

        conn.execute("UPDATE playbooks SET runs_count = runs_count + 1, last_run = ? WHERE id = ?", (now_str(), pb_id))

        if incident_id:
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (incident_id, "Playbook Engine", "Playbook Triggered",
                          f"Triggered workflow '{pb['name']}' (Execution #{exec_id}). Status: {status}.", now_str()))

    if request.referrer and "incidents" in request.referrer:
        return redirect(request.referrer)
    return redirect(url_for("playbooks"))

@app.route("/playbooks/execution/<int:exec_id>/approve", methods=["POST"])
def approve_playbook_step(exec_id):
    user = get_current_user()
    with db() as conn:
        pe = conn.execute("SELECT * FROM playbook_executions WHERE id=?", (exec_id,)).fetchone()
        if not pe:
            return redirect(url_for("playbooks"))

        pb = conn.execute("SELECT * FROM playbooks WHERE id=?", (pe["playbook_id"],)).fetchone()
        steps = json.loads(pb["steps_json"] or "[]")
        logs = json.loads(pe["logs_json"] or "[]")

        curr_step = pe["current_step"]
        for l in logs:
            if l.get("status") == "Awaiting Approval":
                l["status"] = "Approved"
                l["output"] = f"Approved by {user['name']}. Executing automated containment step."

        for idx in range(curr_step + 1, len(steps) + 1):
            step = steps[idx - 1]
            logs.append({
                "step": idx,
                "title": step["title"],
                "system": step["system"],
                "status": "Success",
                "output": f"Step completed on {step['system']}."
            })

        conn.execute("""UPDATE playbook_executions 
        SET status='Completed', current_step=?, logs_json=?, completed_at=? WHERE id=?""",
        (len(steps), json.dumps(logs), now_str(), exec_id))

        if pe["incident_id"]:
            conn.execute("INSERT INTO containment_actions (incident_id, action_type, target, status, executed_by, system, details, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                         (pe["incident_id"], "Playbook Containment", "Automated Policy", "Active", user["name"], "SOAR Orchestrator", f"Playbook #{exec_id} completed successfully.", now_str()))
            conn.execute("UPDATE incidents SET containment_status='Contained', status='Containment', updated_at=? WHERE id=?",
                         (now_str(), pe["incident_id"]))
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (pe["incident_id"], user["name"], "Approval Granted", f"Approval granted for execution #{exec_id}. Workflow successfully finished.", now_str()))

    return redirect(request.referrer or url_for("playbooks"))

# ==========================================
# THREAT INTELLIGENCE & IOC LOOKUP
# ==========================================

@app.route("/threat-intel")
def threat_intel():
    search_q = request.args.get("q", "").strip()
    result = None
    if search_q:
        ioc_type = "IP" if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", search_q) else ("Domain" if "." in search_q else "Hash")
        score, rep, det = calculate_ioc_intelligence(ioc_type, search_q)
        result = {
            "value": search_q,
            "type": ioc_type,
            "threat_score": score,
            "reputation": rep,
            "details": det
        }

    with db() as conn:
        all_iocs = conn.execute("SELECT * FROM iocs ORDER BY threat_score DESC LIMIT 25").fetchall()
        parsed_iocs = []
        for i in all_iocs:
            item = dict(i)
            try:
                item["details"] = json.loads(i["enrichment_details"] or "{}")
            except:
                item["details"] = {}
            parsed_iocs.append(item)

        blocked_count = conn.execute("SELECT COUNT(*) FROM iocs WHERE status='Blocked'").fetchone()[0]
        malicious_count = conn.execute("SELECT COUNT(*) FROM iocs WHERE reputation='Malicious'").fetchone()[0]

    return render_template("threat_intel.html",
                           search_q=search_q,
                           result=result,
                           iocs=parsed_iocs,
                           blocked_count=blocked_count,
                           malicious_count=malicious_count,
                           page="threat_intel")

@app.route("/threat-intel/block", methods=["POST"])
def block_ioc_directly():
    value = request.form.get("value")
    ioc_type = request.form.get("type", "IP")
    system = request.form.get("system", "Palo Alto Firewall")
    user = get_current_user()

    if value:
        with db() as conn:
            score, rep, det = calculate_ioc_intelligence(ioc_type, value)
            conn.execute("INSERT INTO iocs (incident_id, ioc_type, value, reputation, threat_score, enrichment_details, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (None, ioc_type, value, "Malicious", 100, json.dumps(det), "Blocked", now_str()))

            conn.execute("INSERT INTO containment_actions (incident_id, action_type, target, status, executed_by, system, details, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                         (None, f"Perimeter Block ({ioc_type})", value, "Active", user["name"], system, f"Manually blacklisted indicator {value}.", now_str()))

    return redirect(url_for("threat_intel"))

# ==========================================
# CONTAINMENT AUDIT & ACTIONS
# ==========================================

@app.route("/actions")
def actions():
    with db() as conn:
        actions_list = conn.execute("SELECT * FROM containment_actions ORDER BY id DESC").fetchall()
    return render_template("actions.html", actions=actions_list, page="actions")

@app.route("/actions/<int:action_id>/rollback", methods=["POST"])
def rollback_action(action_id):
    user = get_current_user()
    with db() as conn:
        act = conn.execute("SELECT * FROM containment_actions WHERE id=?", (action_id,)).fetchone()
        if act:
            conn.execute("UPDATE containment_actions SET status='Rolled Back', details=details || ' [ROLLED BACK by ' || ? || ']' WHERE id=?", (user["name"], action_id))
            if act["incident_id"]:
                conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                             (act["incident_id"], user["name"], "Action Rollback", f"Rolled back containment action '{act['action_type']}' on {act['target']}.", now_str()))
            conn.execute("UPDATE iocs SET status='Active' WHERE value=?", (act["target"],))
    return redirect(url_for("actions"))

# ==========================================
# INTEGRATIONS & CONNECTORS
# ==========================================

@app.route("/integrations")
def integrations():
    integrations_list = [
        {"id": "wazuh", "name": "Wazuh SIEM / XDR", "type": "Alert Ingestion & Telemetry", "status": "Connected", "latency": "12ms",
         "desc": "Real-time sync with Wazuh Manager v4.8. Pulls security alerts, agent telemetry, and FIM file changes.",
         "api_version": "v4.8.1-release", "stats": "2,410 events/min ingested"},
        {"id": "crowdstrike", "name": "CrowdStrike Falcon", "type": "EDR & Host Containment", "status": "Connected", "latency": "48ms",
         "desc": "Real-Time Response (RTR) API for isolating endpoints, killing hostile process trees, and pulling memory dumps.",
         "api_version": "Falcon OAuth2 API v2", "stats": "418 managed endpoints online"},
        {"id": "paloalto", "name": "Palo Alto NGFW", "type": "Perimeter Firewall Orchestration", "status": "Connected", "latency": "22ms",
         "desc": "PAN-OS XML/REST API connector for dynamic address groups, external blocklists, and immediate border drop rules.",
         "api_version": "PAN-OS 11.1.2", "stats": "124 active perimeter blocks"},
        {"id": "virustotal", "name": "VirusTotal Intelligence", "type": "Threat Intel & Multi-Engine AV", "status": "Connected", "latency": "110ms",
         "desc": "Automated SHA256, URL, domain, and IP reputation lookup querying 70+ antivirus engines and sandbox behaviors.",
         "api_version": "v3 REST API", "stats": "API Quota: 4,820 / 5,000 requests"},
        {"id": "abuseipdb", "name": "AbuseIPDB", "type": "IP Reputation & Geolocation", "status": "Connected", "latency": "95ms",
         "desc": "Checks global reporting database for SSH brute-forcers, web scrapers, and malicious botnet exit nodes.",
         "api_version": "v2 API", "stats": "Confidence threshold: >=75%"},
        {"id": "activedirectory", "name": "Active Directory / Entra ID", "type": "Identity & Access Control", "status": "Connected", "latency": "18ms",
         "desc": "LDAP/Graph API integration to revoke OAuth tokens, lock compromised credentials, and trigger emergency password resets.",
         "api_version": "Microsoft Graph v1.0", "stats": "Directory Sync Active"},
        {"id": "slack", "name": "Slack SOC War Room", "type": "Notifications & ChatOps", "status": "Connected", "latency": "140ms",
         "desc": "Dispatches high-priority alert cards to #soc-incidents with interactive 1-click containment action buttons.",
         "api_version": "Incoming Webhooks v2", "stats": "Target: #soc-incidents"}
    ]
    return render_template("integrations.html", integrations=integrations_list, page="integrations")

@app.route("/integrations/<conn_id>/test", methods=["POST"])
def test_integration(conn_id):
    return jsonify({
        "status": "success",
        "connector": conn_id,
        "message": f"Connection test to {conn_id} verified: HTTP 200 OK, latency {random.randint(15, 60)}ms.",
        "timestamp": now_str()
    })

# ==========================================
# REPORTS & SOC ANALYTICS
# ==========================================

@app.route("/reports")
def reports():
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
        resolved = conn.execute("SELECT COUNT(*) FROM incidents WHERE status IN ('Resolved', 'Closed')").fetchone()[0]
        critical = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Critical'").fetchone()[0]
        high = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='High'").fetchone()[0]
        medium = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Medium'").fetchone()[0]
        low = conn.execute("SELECT COUNT(*) FROM incidents WHERE severity='Low'").fetchone()[0]

        total_actions = conn.execute("SELECT COUNT(*) FROM containment_actions").fetchone()[0]
        total_playbook_runs = conn.execute("SELECT COUNT(*) FROM playbook_executions").fetchone()[0]
        blocked_iocs = conn.execute("SELECT COUNT(*) FROM iocs WHERE status='Blocked'").fetchone()[0]

    return render_template("reports.html",
                           total=total,
                           resolved=resolved,
                           critical=critical,
                           high=high,
                           medium=medium,
                           low=low,
                           total_actions=total_actions,
                           total_playbook_runs=total_playbook_runs,
                           blocked_iocs=blocked_iocs,
                           page="reports")

# ==========================================
# ATTACK SIMULATOR & WEBHOOK INGESTION
# ==========================================

@app.route("/api/simulator/trigger", methods=["POST"])
def simulate_attack():
    attack_type = request.form.get("type", "bruteforce")

    scenarios = {
        "bruteforce": {
            "title": f"SSH Credential Stuffing Surge ({random.randint(2000, 6000)} attempts)",
            "severity": "High",
            "source": "Wazuh SIEM",
            "details": f"Targeted credential attack against internal server sshd from known botnet node.",
            "mitre": "T1110.001 - Password Guessing",
            "assigned_to": "Sarah Connor",
            "artifacts": [
                {"type": "IP", "value": f"185.220.{random.randint(100, 250)}.{random.randint(1, 254)}", "role": "Attacker IP"},
                {"type": "Host", "value": "srv-bastion01.corp", "role": "Target SSH Bastion"},
                {"type": "User", "value": "admin", "role": "Target User"}
            ],
            "playbook_id": "pb-bruteforce"
        },
        "ransomware": {
            "title": f"Ransomware Canary Tripped on Host-WKSTN-{random.randint(10, 99)}",
            "severity": "Critical",
            "source": "CrowdStrike Falcon",
            "details": "Mass encrypted .locked file extension modification and VSS shadow copy purge detected in under 15 seconds.",
            "mitre": "T1486 - Data Encrypted for Impact",
            "assigned_to": "Alex Vance",
            "artifacts": [
                {"type": "Host", "value": f"Host-WKSTN-{random.randint(10, 99)}", "role": "Target Host"},
                {"type": "Hash", "value": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0", "role": "Ransomware Binary"},
                {"type": "IP", "value": f"91.240.118.{random.randint(10, 200)}", "role": "C2 Server"}
            ],
            "playbook_id": "pb-ransomware"
        },
        "phishing": {
            "title": "Executive Spearphishing with Malicious Macro Delivery",
            "severity": "High",
            "source": "M365 Defender",
            "details": "Email received with subject 'Q4 Financial Adjustment_Confidential.xlsm' containing payload dropped from untrusted CDN.",
            "mitre": "T1566.001 - Spearphishing Attachment",
            "assigned_to": "Sarah Connor",
            "artifacts": [
                {"type": "Domain", "value": f"auth-verify-cdn-{random.randint(100, 999)}.ru", "role": "Malicious Domain"},
                {"type": "User", "value": "cfo@company.com", "role": "Target Mailbox"},
                {"type": "Hash", "value": "8f4e2b109ac74836d123456789abcdef0123456789abcdef0123456789abcdef", "role": "Macro Hash"}
            ],
            "playbook_id": "pb-phishing"
        },
        "c2": {
            "title": "Periodic DNS Tunneling & Cobalt Strike Beaconing",
            "severity": "High",
            "source": "Suricata IDS",
            "details": "Client performing periodic 60-second jitter requests containing base32 encoded data in DNS TXT queries.",
            "mitre": "T1071.004 - DNS C2",
            "assigned_to": "David Lightman",
            "artifacts": [
                {"type": "Domain", "value": f"beacon-{random.randint(10, 99)}.cobalt-c2-network.xyz", "role": "C2 Domain"},
                {"type": "IP", "value": "10.0.12.88", "role": "Internal Infected Workstation"}
            ],
            "playbook_id": "pb-c2beacon"
        }
    }

    sc = scenarios.get(attack_type, scenarios["bruteforce"])

    with db() as conn:
        cursor = conn.execute("""INSERT INTO incidents
        (title, severity, source, status, details, assigned_to, mitre_technique, artifacts_json, containment_status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (sc["title"], sc["severity"], sc["source"], "New", sc["details"], sc["assigned_to"], sc["mitre"], json.dumps(sc["artifacts"]), "None", now_str(), now_str()))
        new_inc_id = cursor.lastrowid

        for a in sc["artifacts"]:
            score, rep, det = calculate_ioc_intelligence(a["type"], a["value"])
            conn.execute("INSERT INTO iocs (incident_id, ioc_type, value, reputation, threat_score, enrichment_details, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (new_inc_id, a["type"], a["value"], rep, score, json.dumps(det), "Active", now_str()))

        conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                     (new_inc_id, sc["source"], "Attack Ingested", f"Attack simulation '{attack_type.upper()}' generated incident #{new_inc_id}.", now_str()))

        pb = conn.execute("SELECT * FROM playbooks WHERE id=?", (sc["playbook_id"],)).fetchone()
        if pb and pb["auto_trigger"]:
            steps = json.loads(pb["steps_json"] or "[]")
            logs = []
            for idx, s in enumerate(steps[:3], 1):
                logs.append({"step": idx, "title": s["title"], "system": s["system"], "status": "Success", "output": f"Auto-triaged artifact."})
            if len(steps) > 3 and steps[3].get("requires_approval"):
                logs.append({"step": 4, "title": steps[3]["title"], "system": steps[3]["system"], "status": "Awaiting Approval", "output": "Waiting for SOC analyst sign-off to execute containment."})
                status = "Awaiting Approval"
                curr_step = 4
            else:
                status = "Completed"
                curr_step = len(steps)

            conn.execute("""INSERT INTO playbook_executions
            (playbook_id, incident_id, playbook_name, status, triggered_by, current_step, total_steps, logs_json, started_at, completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (pb["id"], new_inc_id, pb["name"], status, "Simulation Rule Engine", curr_step, len(steps), json.dumps(logs), now_str(), "" if status=="Awaiting Approval" else now_str()))

            conn.execute("UPDATE playbooks SET runs_count = runs_count + 1, last_run=? WHERE id=?", (now_str(), pb["id"]))
            conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                         (new_inc_id, "SOAR Orchestrator", "Auto-Playbook Triggered", f"Playbook '{pb['name']}' automatically started.", now_str()))

    return redirect(url_for("incident_detail", incident_id=new_inc_id))

@app.route("/api/alerts/webhook", methods=["POST"])
def alert_webhook():
    payload = request.get_json(silent=True) or {}
    title = payload.get("title", "Incoming SIEM Alert")
    severity = payload.get("severity", "Medium")
    source = payload.get("source", "Webhook Ingest")
    details = payload.get("details", "External webhook payload ingested.")
    iocs = payload.get("iocs", [])

    with db() as conn:
        cursor = conn.execute("""INSERT INTO incidents
        (title, severity, source, status, details, assigned_to, mitre_technique, artifacts_json, containment_status, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (title, severity, source, "New", details, "Auto-Triage Bot", "T1059 - Command Execution", json.dumps(iocs), "None", now_str(), now_str()))
        inc_id = cursor.lastrowid

        for i in iocs:
            score, rep, det = calculate_ioc_intelligence(i.get("type", "IP"), i.get("value", "127.0.0.1"))
            conn.execute("INSERT INTO iocs (incident_id, ioc_type, value, reputation, threat_score, enrichment_details, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
                         (inc_id, i.get("type", "IP"), i.get("value"), rep, score, json.dumps(det), "Active", now_str()))

        conn.execute("INSERT INTO incident_timeline (incident_id, author, action_type, message, timestamp) VALUES (?,?,?,?,?)",
                     (inc_id, "API Gateway", "Webhook Ingest", f"Ingested alert from {source} with ID #{inc_id}.", now_str()))

    return jsonify({"status": "success", "incident_id": inc_id, "message": "Alert parsed and ingested into SOAR queue."})

@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "app": "SOAR Sentinel Enterprise Platform",
        "version": "3.0.0",
        "database": "sqlite_connected",
        "orchestrator_status": "ONLINE",
        "copilot_status": "ONLINE",
        "active_connectors": 7,
        "mode": "enterprise_simulation"
    })

if __name__ == "__main__":
    app.run(debug=True)
