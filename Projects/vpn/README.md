# C++ VPN from Scratch

A lightweight, educational VPN implemented in modern C++17. It uses a virtual
TUN/TAP network interface, AES-256-GCM authenticated encryption, and a simple
UDP-based tunneling protocol.

> ⚠️ **Educational purposes only.** This is a minimal VPN for learning. It does
> not include a full key exchange (uses a pre-shared key), advanced routing,
> NAT traversal, or production-grade hardening. Do not use for sensitive traffic
> without a security audit.

## Architecture

```
+-------------------+      UDP (encrypted)      +-------------------+
|   Client App      | <========================> |   Server App      |
|  (vpn_client)     |                           |  (vpn_server)     |
+-------------------+                           +-------------------+
        |                                               |
        | TUN interface (tun0)                          | TUN interface (tun0)
        v                                               v
+-------------------+                           +-------------------+
|  Client OS        |                           |  Server OS        |
|  (routing table)  |                           |  (routing table)  |
+-------------------+                           +-------------------+
```

### Components

| Component | Responsibility |
|-----------|---------------|
| `tun.h/cpp` | Virtual network interface (Linux `/dev/net/tun`) |
| `crypto.h/cpp` | AES-256-GCM authenticated encryption via OpenSSL |
| `protocol.h/cpp` | Binary framing protocol over UDP |
| `vpn_server.cpp` | Server: decrypts client packets, injects into TUN |
| `vpn_client.cpp` | Client: encrypts local packets, sends to server |

### Packet Format

Every tunneled packet is framed as:

```
Offset  Size  Field
0       4     Magic (0x56504E21 = "VPN!")
4       2     Version (1)
6       2     Type (1=Data, 2=Control, 3=Handshake, 4=Ack)
8       2     Flags
10      4     Payload length
14      N     Payload (encrypted for Data packets)
```

Encrypted payload layout: `[nonce: 12 bytes][ciphertext][tag: 16 bytes]`

## Prerequisites

- **Linux** (tested on Ubuntu/Debian) — TUN/TAP via `/dev/net/tun`
- **C++17 compiler** (g++ 7+ or clang++)
- **CMake 3.10+**
- **OpenSSL 1.1.1+** (development headers)
- **Root privileges** (required to create/configure TUN interfaces)

Install dependencies on Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake libssl-dev
```

## Build

```bash
cd vpn
mkdir build && cd build
cmake ..
make
```

This produces two binaries: `vpn_server` and `vpn_client`.

## Usage

### 1. Start the server (requires root)

```bash
sudo ./vpn_server
```

The server creates `tun0` with address `10.8.0.1/24` and listens on UDP port 1194.

### 2. Start the client (requires root)

```bash
sudo ./vpn_client <server-ip>
```

The client creates `tun0` with address `10.8.0.2/24` and connects to the server.

### 3. Route traffic through the VPN

On the client, add a route so traffic goes through the tunnel:

```bash
# Example: route 10.8.0.0/24 through the tunnel
sudo ip route add 10.8.0.0/24 dev tun0

# Or route all traffic through VPN (careful - may disconnect you!)
sudo ip route add default via 10.8.0.1 dev tun0
```

On the server, enable IP forwarding so the server can forward client traffic
to the internet:

```bash
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
```

Replace `eth0` with your server's public interface.

### 4. Test

From the client, ping the server's tunnel IP:

```bash
ping 10.8.0.1
```

Or ping an external host through the VPN (after setting up routing/NAT on the server):

```bash
ping 8.8.8.8
```

## Key Management

Currently both sides use a pre-shared 256-bit key generated at startup. In the
example code the key is generated randomly each run, so client and server keys
won't match unless you hardcode the same key.

For production, replace this with a proper key exchange:
- **Diffie-Hellman** (ECDHE) for session key establishment
- **HKDF** to derive AES-256-GCM keys from the shared secret
- **Certificate-based authentication** (TLS) for server identity

## Platform Support

| Platform | TUN/TAP Backend | Status |
|----------|----------------|--------|
| Linux | `/dev/net/tun` | ✅ Implemented |
| Windows | Wintun / TAP-Windows | ⚠️ Stub (throws) |
| macOS | `/dev/tun*` | ❌ Not implemented |

## Security Notes

- No perfect forward secrecy (static pre-shared key)
- No replay protection (add sequence numbers)
- No certificate authentication
- No MTU path discovery / fragmentation handling
- No keepalive / connection monitoring

These are intentional omissions for a minimal educational implementation.

## License

MIT
