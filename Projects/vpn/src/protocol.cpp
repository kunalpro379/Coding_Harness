#include "vpn/protocol.h"

#include <cstring>
#include <stdexcept>

namespace vpn {

std::vector<uint8_t> frame_packet(PacketType type, uint16_t flags,
                                  const uint8_t* payload, size_t payload_len) {
    TunnelHeader hdr{};
    hdr.magic = TunnelHeader::kMagic;
    hdr.version = kProtocolVersion;
    hdr.type = static_cast<uint16_t>(type);
    hdr.flags = flags;
    hdr.sequence_num = 0; // Initial sequence number
    hdr.length = static_cast<uint32_t>(payload_len);

    std::vector<uint8_t> frame;
    frame.reserve(sizeof(TunnelHeader) + payload_len);
    frame.insert(frame.end(), reinterpret_cast<const uint8_t*>(&hdr),
                 reinterpret_cast<const uint8_t*>(&hdr) + sizeof(TunnelHeader));
    if (payload_len > 0 && payload) {
        frame.insert(frame.end(), payload, payload + payload_len);
    }
    return frame;
}

bool parse_frame(const uint8_t* data, size_t data_len,
                 TunnelHeader& header, size_t& payload_offset) {
    if (data_len < sizeof(TunnelHeader)) {
        return false;
    }

    std::memcpy(&header, data, sizeof(TunnelHeader));

    if (header.magic != TunnelHeader::kMagic) {
        return false;
    }
    if (header.version != kProtocolVersion) {
        return false;
    }

    payload_offset = sizeof(TunnelHeader);
    if (data_len < payload_offset + header.length) {
        return false; // incomplete payload
    }

    return true;
}

} // namespace vpn
