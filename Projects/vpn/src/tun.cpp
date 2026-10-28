#include "vpn/tun.h"

#include <cstring>
#include <cerrno>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <net/if.h>
#include <linux/if.h>
#include <linux/if_tun.h>

namespace vpn {

TunInterface::TunInterface() = default;

TunInterface::~TunInterface() {
    close();
}

void TunInterface::open(const Config& cfg) {
#if defined(__linux__)
    linux_open(cfg);
#elif defined(_WIN32)
    win_open(cfg);
#endif
}

void TunInterface::close() {
    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }
}

ssize_t TunInterface::read(std::vector<uint8_t>& buffer) {
    if (fd_ < 0) return -1;
    ssize_t n = ::read(fd_, buffer.data(), buffer.size());
    return n;
}

ssize_t TunInterface::write(const uint8_t* data, size_t len) {
    if (fd_ < 0) return -1;
    ssize_t n = ::write(fd_, data, len);
    return n;
}

#if defined(__linux__)
void TunInterface::linux_open(const Config& cfg) {
    config_ = cfg;

    fd_ = ::open("/dev/net/tun", O_RDWR);
    if (fd_ < 0) {
        throw std::runtime_error("Failed to open /dev/net/tun: " + std::string(strerror(errno)));
    }

    ifreq ifr{};
    std::memset(&ifr, 0, sizeof(ifr));
    ifr.ifr_flags = IFF_TUN | IFF_NO_PI;  // TUN device, no packet info
    if (!cfg.name.empty()) {
        std::strncpy(ifr.ifr_name, cfg.name.c_str(), IFNAMSIZ - 1);
    }

    if (ioctl(fd_, TUNSETIFF, &ifr) < 0) {
        ::close(fd_);
        fd_ = -1;
        throw std::runtime_error("TUNSETIFF ioctl failed: " + std::string(strerror(errno)));
    }

    config_.name = ifr.ifr_name;

    // Bring the interface up and assign address via netlink/ioctl socket
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock >= 0) {
        ifreq ifr_conf{};
        std::strncpy(ifr_conf.ifr_name, config_.name.c_str(), IFNAMSIZ - 1);

        // Set interface flags (IFF_UP | IFF_RUNNING)
        if (ioctl(sock, SIOCGIFFLAGS, &ifr_conf) == 0) {
            ifr_conf.ifr_flags |= (IFF_UP | IFF_RUNNING);
            ioctl(sock, SIOCSIFFLAGS, &ifr_conf);
        }

        // Set IP address
        if (!cfg.address.empty()) {
            sockaddr_in* addr = reinterpret_cast<sockaddr_in*>(&ifr_conf.ifr_addr);
            addr->sin_family = AF_INET;
            inet_pton(AF_INET, cfg.address.c_str(), &addr->sin_addr);
            std::strncpy(ifr_conf.ifr_name, config_.name.c_str(), IFNAMSIZ - 1);
            ioctl(sock, SIOCSIFADDR, &ifr_conf);
        }

        // Set netmask
        if (!cfg.netmask.empty()) {
            sockaddr_in* netmask = reinterpret_cast<sockaddr_in*>(&ifr_conf.ifr_netmask);
            netmask->sin_family = AF_INET;
            inet_pton(AF_INET, cfg.netmask.c_str(), &netmask->sin_addr);
            std::strncpy(ifr_conf.ifr_name, config_.name.c_str(), IFNAMSIZ - 1);
            ioctl(sock, SIOCSIFNETMASK, &ifr_conf);
        }

        ::close(sock);
    }

    // Set non-blocking for select/poll usage
    int flags = fcntl(fd_, F_GETFL, 0);
    fcntl(fd_, F_SETFL, flags | O_NONBLOCK);
}

void TunInterface::linux_set_nonblocking() {
    int flags = fcntl(fd_, F_GETFL, 0);
    fcntl(fd_, F_SETFL, flags | O_NONBLOCK);
}
#elif defined(_WIN32)
void TunInterface::win_open(const Config& cfg) {
    // Windows implementation would use Wintun or TAP-Windows adapter.
    // This requires the Wintun DLL and a GUID-based adapter registration.
    throw std::runtime_error("Windows TUN/TAP support not yet implemented. Use Linux.");
}
#endif

} // namespace vpn
