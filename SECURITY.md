# Privacy and security

Use only your own trusted Windows machine and a trusted LAN or encrypted private network such as Tailscale. Do not port-forward RTSP to the public Internet. The random connection code authenticates stream access; it does not encrypt plain RTSP video.

No credentials, private network addresses, local configuration, SSH keys, logs, video frames, or crash dumps belong in this repository or its release assets. User configuration lives outside the application bundle. Logs may contain device names or hostnames; redact those before opening an issue.

The Windows firewall helper requests elevation only when explicitly clicked and allows the selected TCP port from local subnets and Tailscale address ranges. It does not disable the firewall. Dependencies and drivers are installed from their official publishers.

Please report vulnerabilities privately using the repository's security advisory feature rather than including connection codes or private footage in public issues.
