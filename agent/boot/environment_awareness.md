# Environment Awareness

Documents the agent's understanding of its operating environment.

---

## Sandbox Type
- **Platform**: Ubuntu LTS (VirtualBox VM)
- **Isolation**: Hardware-virtualized, NAT networking
- **Host**: Windows (no direct access)

## Permissions
- **Root access**: Yes, within sandbox
- **Network**: Outbound allowed (NAT), no inbound except SSH
- **Filesystem**: Full access within VM

## Key Paths
- **Agent home**: `/agent`
- **Scratch space**: `/agent/scratch`
- **System temp**: `/tmp`

## Available Tools
- Standard Linux utilities (coreutils, grep, sed, awk, etc.)
- Git for version control
- Python 3.12 for runtime
- curl/wget for network requests
- jq for JSON processing
- Docker (optional, for additional isolation)

## Constraints
- Cannot access Windows host filesystem directly
- Cannot modify VM configuration from inside
- Network requests subject to VM's NAT rules
- Resource limits defined by VM allocation (RAM, CPU, disk)

## LLM Access
- **Provider**: Ollama (local, running on host or VM)
- **Endpoint**: Configured in runtime settings
- **Fallback**: None currently configured

---

## Self-Checks

Periodic verification:
1. Confirm expected OS (`uname -a`)
2. Confirm `/agent` mount exists and is writable
3. Confirm network connectivity (ping known endpoint)
4. Confirm LLM endpoint reachable
5. Confirm git repository functional

Results logged to `/logs/health/environment-YYYY-MM-DD.json`
