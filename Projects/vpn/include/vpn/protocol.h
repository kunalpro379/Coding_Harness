#pragma once

#include <cstdint>
#include <cstddef>
#include <vector>
#include <string>

namespace vpn {

// VPN tunnel protocol header.
// Every packet sent over the control channel is framed with this header:
//   [magic: 4 bytes][version: 2][type: 2][flags: 2][length: 4][payload...]
// Length covers only the payload (not the header).
#pragma pack(push, 1)
struct TunnelHeader {
    static constexpr uint32_t kMagic = 0x56504E21; // 'VPN!'

    uint32_t magic;
    uint16_t version;
    uint16_t type;     // see PacketType
    uint16_t flags;
    uint32_t sequence_num; // Sequence number for replay protection
    uint32_t length;   // payload length in bytes
    // payload follows immediately
};
#pragma pack(pop)

static_assert(sizeof(TunnelHeader) == 14, "TunnelHeader must be 14 bytes");

enum class PacketType : uint16_t {
    kData      = 0x0001, // encapsulated IP packet
    kControl   = 0x0002, // control message (keepalive, route, etc.)
    kHandshake = 0x0003, // initial key exchange
    kAck       = 0x0004, // acknowledgement
};

constexpr uint16_t kProtocolVersion = 1;

// Frame a payload into a wire-ready buffer with the tunnel header.
std::vector<uint8_t> frame_packet(PacketType type, uint16_t flags,
                                  const uint8_t* payload, size_t payload_len);

// Parse a framed packet. Returns true if a complete header+payload is present.
bool parse_frame(const uint8_t* data, size_t data_len,
                 TunnelHeader& header, size_t& payload_offset);

} // namespace vpn
