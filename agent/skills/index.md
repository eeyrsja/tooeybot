# Skills Index

Catalog of available capabilities and how to use them.

---

## Core Capabilities

These are conceptual skills - use actual bash commands to accomplish them:

### File Operations
- **Create/write file**: `echo "content" > /path/to/file.txt`
- **Append to file**: `echo "content" >> /path/to/file.txt`  
- **Read file**: `cat /path/to/file.txt`
- **Create directory**: `mkdir -p /path/to/dir`
- **Copy file**: `cp source.txt dest.txt`
- **Move/rename**: `mv old.txt new.txt`
- **Delete file**: `rm /path/to/file.txt`

### Information Gathering
- **List files**: `ls -la /path`
- **Check file exists**: `test -f /path/to/file.txt && echo "exists"`
- **File info**: `stat /path/to/file.txt`
- **Search content**: `grep "pattern" file.txt`

### System Operations
- **Current directory**: `pwd`
- **Disk usage**: `df -h`
- **Process list**: `ps aux`

---

## Reference Documentation

For design patterns and detailed procedures, see:
- [execute_command](core/execute_command.md) - Command execution patterns
- [read_file](core/read_file.md) - File reading patterns
- [write_file](core/write_file.md) - File writing patterns
- [log_event](core/log_event.md) - Event logging patterns

## Reference Documentation

For design patterns and detailed procedures, see:
- [execute_command](core/execute_command.md) - Command execution patterns
- [read_file](core/read_file.md) - File reading patterns
- [write_file](core/write_file.md) - File writing patterns
- [log_event](core/log_event.md) - Event logging patterns

---

*Last updated: 2026-02-01*
