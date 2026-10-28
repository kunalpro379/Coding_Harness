#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <memory>
#include <stdexcept>

namespace vpn {

// Represents a virtual network interface (TUN/TAP device).
// On Linux this wraps /dev/net/tun. On Windows it wraps a Wintap/Wintun adapter.
class TunInterface {
public:
    struct Config {
        std::string name;        // e.g. "tun0" (empty = auto-assign)
        std::string address;     // VPN tunnel IP, e.g. "10.8.0.1"
        std::string netmask;     // e.g. "255.255.255.0"
        std::string destination; // peer endpoint (point-to-point)
        int mtu = 1500;
    };

    TunInterface();
    ~TunInterface();

    TunInterface(const TunInterface&) = delete;
    TunInterface& operator=(const TunInterface&) = delete;

    // Open and configure the virtual interface. Requires root/admin.
    void open(const Config& cfg);

    // Close the interface.
    void close();

    bool is_open() const { return fd_ >= 0; }

    // Read a raw Ethernet/IP frame from the interface.
    // Returns number of bytes read, or -1 on error.
    ssize_t read(std::vector<uint8_t>& buffer);

    // Write a raw Ethernet/IP frame to the interface.
    // Returns number of bytes written, or -1 on error.
    ssize_t write(const uint8_t* data, size_t len);

    // Get the underlying file descriptor (for select/poll).
    int fd() const { return fd_; }

    const std::string& name() const { return config_.name; }

private:
    int fd_ = -1;
    Config config_;

    // Platform-specific helpers
#if defined(__linux__)
    void linux_open(const Config& cfg);
    void linux_set_nonblocking();
#elif defined(_WIN32)
    void win_open(const Config& cfg);
#else
#error "Unsupported platform: only Linux and Windows are supported"
#endif
};

} // namespace vpn
