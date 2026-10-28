#include "vpn/tun.h"
#include "vpn/crypto.h"
#include "vpn/protocol.h"

#include <iostream>
#include <thread>
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

class VpnServer {
public:
    struct Config {
        std::string listen_addr = "0.0.0.0";
        uint16_t listen_port = 1194;
        TunInterface::Config tun_cfg;
        std::vector<uint8_t> shared_key; // pre-shared 256-bit key
    };

    explicit VpnServer(const Config& cfg) : config_(cfg), running_(false) {}

    void run() {
        // Open TUN interface
        tun_.open(config_.tun_cfg);
        std::cout << "[server] TUN interface " << tun_.name() << " opened\n";

        // Create UDP socket
        int sock = socket(AF_INET, SOCK_DGRAM, 0);
        if (sock < 0) {
            throw std::runtime_error("socket() failed");
        }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(config_.listen_port);
        inet_pton(AF_INET, config_.listen_addr.c_str(), &addr.sin_addr);

        if (bind(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0) {
            close(sock);
            throw std::runtime_error("bind() failed");
        }

        std::cout << "[server] Listening on " << config_.listen_addr << ":"
                  << config_.listen_port << "\n";

        running_ = true;
        std::atomic<bool> client_connected = false;
        sockaddr_in client_addr{};
        socklen_t client_len = sizeof(client_addr);

        AeadCipher cipher(config_.shared_key);

        // Buffers
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

            // Network -> TUN (encrypted packets from client)
            if (fds[0].revents & POLLIN) {
                ssize_t n = recvfrom(sock, net_buf.data(), net_buf.size(), 0,
                                     reinterpret_cast<sockaddr*>(&client_addr), &client_len);
                if (n > 0) {
                    client_connected = true;
                    handle_network_packet(sock, client_addr, cipher, net_buf.data(), n, tun_buf);
                }
            }

            // TUN -> Network (encrypt and send to client)
            if (fds[1].revents & POLLIN) {
                if (!client_connected) continue;
                ssize_t n = tun_.read(tun_buf);
                if (n > 0) {
                    handle_tun_packet(sock, client_addr, cipher, tun_buf.data(), n);
                }
            }
        }

        close(sock);
        tun_.close();
        std::cout << "[server] Shutting down\n";
    }

    void stop() { running_ = false; }

private:
    void handle_network_packet(int sock, const sockaddr_in& client_addr,
                               AeadCipher& cipher, const uint8_t* data, size_t len,
                               std::vector<uint8_t>& tun_buf) {
        // Parse frame
        TunnelHeader hdr;
        size_t payload_offset;
        if (!parse_frame(data, len, hdr, payload_offset)) {
            std::cerr << "[server] Invalid frame from client\n";
            return;
        }

        const uint8_t* payload = data + payload_offset;
        size_t payload_len = hdr.length;

        if (hdr.type == static_cast<uint16_t>(PacketType::kHandshake)) {
            std::cout << "[server] Handshake from client\n";
            // Send ACK
            auto ack = frame_packet(PacketType::kAck, 0, nullptr, 0);
            sendto(sock, ack.data(), ack.size(), 0,
                   reinterpret_cast<const sockaddr*>(&client_addr), sizeof(client_addr));
            return;
        }

        if (hdr.type != static_cast<uint16_t>(PacketType::kData)) {
            return;
        }

        // Decrypt the payload
        try {
            std::vector<uint8_t> plaintext = cipher.decrypt(payload, payload_len, nullptr, 0);
            // Write decrypted IP packet to TUN
            tun_.write(plaintext.data(), plaintext.size());
        } catch (const std::exception& e) {
            std::cerr << "[server] Decrypt failed: " << e.what() << "\n";
        }
    }

    void handle_tun_packet(int sock, const sockaddr_in& client_addr,
                           AeadCipher& cipher, const uint8_t* data, ssize_t len) {
        // Encrypt the IP packet
        auto encrypted = cipher.encrypt(data, static_cast<size_t>(len), nullptr, 0);

        // Frame it
        auto frame = frame_packet(PacketType::kData, 0,
                                  encrypted.data(), encrypted.size());

        // Send to client
        sendto(sock, frame.data(), frame.size(), 0,
               reinterpret_cast<const sockaddr*>(&client_addr), sizeof(client_addr));
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
    // Simple config - in production parse from command line / config file
    vpn::VpnServer::Config cfg;
    cfg.listen_addr = "0.0.0.0";
    cfg.listen_port = 1194;

    // TUN config
    cfg.tun_cfg.name = "tun0";
    cfg.tun_cfg.address = "10.8.0.1";
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
            std::cout << "[server] Using shared key from VPN_SHARED_KEY env var\n";
        } else {
            std::cerr << "[server] Warning: VPN_SHARED_KEY must be 64 hex chars, using default\n";
        }
    }

    std::cout << "[server] Using pre-shared key (32 bytes)\n";

    vpn::VpnServer server(cfg);

    std::signal(SIGINT, [](int) { /* handled via running_ */ });

    try {
        server.run();
    } catch (const std::exception& e) {
        std::cerr << "[server] Fatal: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
