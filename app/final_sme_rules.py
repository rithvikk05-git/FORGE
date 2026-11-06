"""Reviewable links from the final workbook's labels to CSV specializations.

Only specializations present in the supplied 60-person directory are named.
An omitted label has no supported mapping and must go to human review.
"""

FINAL_MATCHING_RULES = {
    "Applications, Data & AI": {
        "Application Consolidation": ("SAP Transformation", "Application Modernization"),
        "Agentic AI Automation": ("Generative AI & Agentic AI",),
        "Database Migration": ("Oracle Modernization",),
        "Agentic Workflow Integration": ("Generative AI & Agentic AI", "Integration & APIs"),
        "BI Tool Consolidation": ("Data Engineering & Analytics",),
        "Workflow Optimization": ("Integration & APIs", "Application Managed Services"),
    },
    "Cloud": {
        "Cloud Observability": ("Cloud Operations",),
        "Kubernetes Rightsizing": ("Cloud Platform Engineering", "Cloud Optimization"),
        "Virtualization Rightsizing": ("Private Cloud", "Cloud Migration"),
        "Cloud Landing Zone Cleanup": ("Private Cloud", "Cloud Optimization"),
        "Cloud Governance Optimization": ("Cloud Optimization", "DevOps & Platform Automation"),
        "Storage Tiering & Rightsizing": ("Cloud Optimization", "Cloud Operations"),
        "AIOps Autoscaling": ("Cloud Operations", "Cloud Platform Engineering"),
        "Datacenter Exit & AWS Migration": ("Cloud Migration", "Public Cloud Architecture"),
        "Cloud Cost Governance": ("Cloud Optimization", "DevOps & Platform Automation"),
        "Backup Storage Consolidation": ("Managed Hosting", "Cloud Operations"),
    },
    "Digital Workspace Services": {
        "ServiceNow License Optimization": ("ServiceNow Workplace",),
        "SaaS License Reclamation": ("ServiceNow Workplace", "Workplace Automation"),
        "Digital Workplace Engineering": ("Employee Digital Experience", "Endpoint Management"),
        "M365 License Rightsizing": ("Microsoft 365",),
        "MID Server Consolidation": ("ServiceNow Workplace",),
        "Directory & Endpoint Consolidation": ("Workplace Identity", "Endpoint Management"),
        "ITSM Module Rationalization": ("ServiceNow Workplace",),
        "Endpoint Profile Optimization": ("Endpoint Management", "Device Lifecycle Management"),
        "ServiceNow SPM Rightsizing": ("ServiceNow Workplace",),
        "UCaaS Vendor Consolidation": ("Collaboration & Teams", "Microsoft 365"),
    },
    "Core Enterprise and z/OS": {
        "Mainframe Big Data Storage Tiering": ("Mainframe Operations",),
        "Mainframe Software Stack Rationalization": ("z/OS Systems Programming", "Mainframe Modernization"),
        "Mainframe Batch MSU Optimization": ("z/OS Systems Programming", "Mainframe Operations"),
        "Mainframe Payment Stream Optimization": ("CICS & Transaction Systems", "Mainframe Application Services"),
        "Mainframe SCM Consolidation": ("Mainframe Modernization", "Mainframe Application Services"),
        "Mainframe Query Offloading": ("Db2 for z/OS", "zCloud"),
        "Virtual Tape Consolidation": ("Mainframe Operations",),
        "IBM Power Cloud Migration": ("IBM i", "zCloud"),
        "DB2 Bufferpool Optimization": ("Db2 for z/OS",),
    },
    "Network & Edge": {
        "Network Hardware Lease Buyout": ("Data Center Networking", "Enterprise Routing & Switching"),
        "WAN Edge Virtualization": ("WAN & SD-WAN", "Edge Infrastructure"),
        "Core Switch Modernization": ("Enterprise Routing & Switching", "Data Center Networking"),
        "Network Automation": ("Network Automation",),
        "Contract Descoping & Credit": ("WAN & SD-WAN",),
        "Industrial Wireless Mesh Optimization": ("Wireless & LAN", "Edge Infrastructure"),
        "MPLS Bandwidth Optimization": ("WAN & SD-WAN",),
        "Monitoring Tool Rationalization": ("Network Operations",),
    },
    "Security & Resiliency": {
        "OT Security Sensor Consolidation": ("SOC & MXDR",),
        "DR Test Automation": ("Resilience & Disaster Recovery",),
        "Automated Vulnerability Management": ("Vulnerability Management",),
        "Cyber Recovery Vault Automation": ("Cyber Recovery", "Resilience & Disaster Recovery"),
        "EDR Security Agent Consolidation": ("Vulnerability Management", "Incident Response"),
        "IAM Access Recertification Automation": ("Zero Trust", "Identity & PAM"),
        "Mainframe RACF Identity Automation": ("Identity & PAM", "Zero Trust"),
        "Immutable Ransomware Storage Tiering": ("Cyber Recovery",),
        "Secure SD-WAN Consolidation": ("Zero Trust", "Cloud Security"),
    },
}
