#include "vpn/tun.h"
#include "vpn/crypto.h"
#include "vpn/protocol.h"

#include <iostream>
#include <atomic>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cerrno>
#include <vector>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <poll.h>
#include <signal.h>

namespace vpn {

class VpnClient {
public:
    struct Config {
        std::string server_addr;
        uint16_t server_port = 1194;
        TunInterface::Config tun_cfg;
        std::vector<uint8_t> shared_key; // must match server
    };

    explicit VpnClient(const Config& cfg) : config_(cfg), running_(false) {}

    void run() {
        // Open TUN interface
        tun_.open(config_.tun_cfg);
        std::cout << "[client] TUN interface " << tun_.name() << " opened\n";

        // Create UDP socket
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock < 0) {
            throw std::runtime_error("socket() failed");
        }

        // Bind to any local port
        sockaddr_in local{};
        local.sin_family = AF_INET;
        local.sin_port = 0;
        local.sin_addr.s_addr = INADDR_ANY;
        bind(sock, reinterpret_cast<sockaddr*>(&local), sizeof(local));

        // Server address
        sockaddr_in server_addr{};
        server_addr.sin_family = AF_INET;
        server_addr.sin_port = htons(config_.server_port);
        inet_pton(AF_INET, config_.server_addr.c_str(), &server_addr.sin_addr);

        std::cout << "[client] Connecting to " << config_.server_addr << ":"
                  << config_.server_port << "\n";

        // Generate ephemeral key pair
        vpn::EcdhKeyPair keypair = vpn::generate_ecdh_keypair();
        std::vector<uint8_t> local_pub_key = keypair.public_key_der;
        std::vector<uint8_t> local_priv_key = keypair.private_key_der;

        // Send handshake (containing public key)
        auto handshake = frame_packet(PacketType::kHandshake, 0, local_pub_key.data(), local_pub_key.size());
        sendto(sock, handshake.data(), handshake.size(), 0,
               reinterpret_cast<const sockaddr*>(&server_addr), sizeof(server_addr));

        running_ = true;
        std::vector<uint8_t> tun_buf(65536);
        std::vector<uint8_t> net_buf(65536);

        while (running_) {
            pollfd fds[2];
            fds[0].fd = sock;
            fds[0].events = POLLIN;
            fds[1].fd = tun_.fd();
            fds[1].events = POLLIN;

            int ret = poll(fds, 2, 1000);
            if (ret < 0) {
                if (errno == EINTR) continue;
                break;
            }

            // Network -> TUN
            if (fds[0].revents & POLLIN) {
                sockaddr_in from{};
                socklen_t from_len = sizeof(from);
                ssize_t n = recvfrom(sock, net_buf.data(), net_buf.size(), 0,
                                     reinterpret_cast<sockaddr*>(&from), &from_len);
                if (n > 0) {
                    handle_network_packet(sock, server_addr, cipher, net_buf.data(), n, tun_buf);
                }
            }

            // TUN -> Network
            if (fds[1].revents & POLLIN) {
                ssize_t n = tun_.read(tun_buf);
                if (n > 0) {
                    handle_tun_packet(sock, server_addr, cipher, tun_buf.data(), n);
                }
            }
        }

        close(sock);
        tun_.close();
        std::cout << "[client] Shutting down\n";
    }

    void stop() { running_ = false; }

private:
    void handle_network_packet(int sock, const sockaddr_in& server_addr,
                               AeadCipher& cipher, const uint8_t* data, size_t len,
                               std::vector<uint8_t>& tun_buf) {
        TunnelHeader hdr;
        size_t payload_offset;
        if (!parse_frame(data, len, hdr, payload_offset)) {
            std::cerr << "[client] Invalid frame from server\n";
            return;
        }

        const uint8_t* payload = data + payload_offset;
        size_t payload_len = hdr.length;

        if (hdr.type == static_cast<uint16_t>(PacketType::kAck)) {
            std::cout << "[client] Handshake acknowledged\n";
            return;
        }

        if (hdr.type != static_cast<uint16_t>(PacketType::kData)) {
            return;
        }

        try {
            std::vector<uint8_t> plaintext = cipher.decrypt(payload, payload_len, nullptr, 0);
            tun_.write(plaintext.data(), plaintext.size());
        } catch (const std::exception& e) {
            std::cerr << "[client] Decrypt failed: " << e.what() << "\n";
        }
    }

    void handle_tun_packet(int sock, const sockaddr_in& server_addr,
                           AeadCipher& cipher, const uint8_t* data, ssize_t len) {
        auto encrypted = cipher.encrypt(data, static_cast<size_t>(len), nullptr, 0);
        auto frame = frame_packet(PacketType::kData, 0,
                                  encrypted.data(), encrypted.size());
        sendto(sock, frame.data(), frame.size(), 0,
               reinterpret_cast<const sockaddr*>(&server_addr), sizeof(server_addr));
    }

    Config config_;
    TunInterface tun_;
    std::atomic<bool> running_;
};

} // namespace vpn

// Example pre-shared key (32 bytes, hex-encoded).
// Both client and server MUST use the same key.
// In production, exchange this securely (e.g., via ECDHE + HKDF).
static const std::vector<uint8_t> kDefaultKey = {
    0x6b, 0xc1, 0xbe, 0xe2, 0x2e, 0x40, 0x9f, 0x96,
    0xe9, 0x3d, 0x7e, 0x11, 0x73, 0x93, 0x17, 0x2a,
    0xae, 0x2d, 0x8a, 0x57, 0x1e, 0x03, 0xac, 0x9c,
    0x9e, 0xb7, 0x6f, 0xac, 0x45, 0xaf, 0x8e, 0x51
};

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <server-ip>\n";
        return 1;
    }

    vpn::VpnClient::Config cfg;
    cfg.server_addr = argv[1];
    cfg.server_port = 1194;

    cfg.tun_cfg.name = "tun0";
    cfg.tun_cfg.address = "10.8.0.2";
    cfg.tun_cfg.netmask = "255.255.255.0";
    cfg.tun_cfg.mtu = 1500;

    // Shared key: allow override via environment variable (hex-encoded, 64 chars)
    cfg.shared_key = kDefaultKey;
    if (const char* env_key = std::getenv("VPN_SHARED_KEY")) {
        if (std::strlen(env_key) == 64) {
            std::vector<uint8_t> key;
            key.reserve(32);
            for (size_t i = 0; i < 64; i += 2) {
                unsigned int byte;
                std::sscanf(env_key + i, "%2x", &byte);
                key.push_back(static_cast<uint8_t>(byte));
            }
            cfg.shared_key = key;
            std::cout << "[client] Using shared key from VPN_SHARED_KEY env var\n";
        } else {
            std::cerr << "[client] Warning: VPN_SHARED_KEY must be 64 hex chars, using default\n";
        }
    }

    std::cout << "[client] Using pre-shared key (32 bytes) - must match server\n";

    vpn::VpnClient client(cfg);

    try {
        client.run();
    } catch (const std::exception& e) {
        std::cerr << "[client] Fatal: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
