# SOAR Sentinel — Enterprise Security Orchestration, Automation & Response

A comprehensive Python Flask + SQLite platform for modern Security Operations Center (SOC) incident investigation, threat intelligence enrichment, and automated multi-vendor containment.

## 🚀 Key Features

### 1. Incident War Room & Case Management (`/incidents/<id>`)
- Detailed incident dossier with MITRE ATT&CK technique tags.
- Extracted IOCs (IPs, Domains, Hashes, Endpoints, Users) with Threat Scores (0-100) and Multi-Engine reputation.
- **Emergency Containment Toolbar**:
  - 🛡️ Push Drop Rule to Palo Alto Networks Perimeter Firewall
  - 💻 Quarantine Endpoint via CrowdStrike EDR Agent
  - 👤 Lock User Account & Revoke OAuth Sessions in Active Directory
  - ⚡ Trigger Response Playbook directly on case
- Collaborative Analyst War Room Timeline & Notes.

### 2. Interactive Playbook Orchestration Hub (`/playbooks`)
- Built-in multi-vendor playbooks:
  - **Automated Brute-Force & Credential Triage** (AbuseIPDB lookup, lockout verification, firewall drop gate)
  - **Ransomware Outbreak & Host Isolation** (Process tree termination, host network severance, C2 blacklisting)
  - **Spearphishing Email & IOC Neutralization** (Attachment hash scan, tenant-wide mailbox search & purge)
  - **Suspicious PowerShell Living-off-the-Land Script Triage** (Deobfuscation, baseline validation, session freeze)
  - **C2 Beaconing & Lateral Movement Defense** (Jitter analysis, DNS sinkholing, PCAP collection)
- **Human-In-The-Loop Approval Gates**: Critical containment steps pause for SOC analyst confirmation before executing.
- Live execution history, step status, and audit trail.

### 3. Threat Intelligence & IOC Lookup Engine (`/threat-intel`)
- Search any IP address, domain name, or file hash.
- Multi-source intelligence scoring: VirusTotal engine ratio, AbuseIPDB confidence percentage, Geolocation, ASN, and category.
- 1-Click addition to Active Perimeter Blocklist.

### 4. Containment Audit & Rollback Management (`/actions`)
- Complete historical record of all containment actions taken.
- **1-Click Rollback**: Safely revert firewall blocks or reconnect quarantined hosts with full timeline auditing.

### 5. Live Attack Telemetry Simulator
- 1-Click synthetic attack injection from any page:
  - ⚡ SSH Credential Stuffing & Tor Relay Surge
  - ☣️ Ransomware Canary Tripped on Finance Workstation
  - 🎣 Executive Spearphishing Macro Delivery
  - 🌐 Periodic DNS C2 Beaconing
- Automatic IOC extraction, incident queue ingestion, and automated playbook triggering.

### 6. Connector Center (`/integrations`)
- Interactive connectors for Wazuh SIEM, CrowdStrike Falcon, Palo Alto Networks, VirusTotal, AbuseIPDB, Active Directory, and Slack.
- Interactive **"Test Connection"** diagnostic ping with live latency and health reporting.

### 7. Webhook API Ingestion (`/api/alerts/webhook`)
- Ingest external alerts via JSON POST from SIEM, EDR, or cloud monitors.

---

## 💻 Run Locally

1. Open a terminal inside the project directory:
   ```bash
   cd e:\final_toch\soar
   ```
2. Ensure Flask is installed:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the SOAR Sentinel application:
   ```bash
   python app.py
   ```
4. Access the web console:
   ```
   http://127.0.0.1:5000
   ```
