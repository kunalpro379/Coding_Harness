#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <memory>
#include <stdexcept>

#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/err.h>

namespace vpn {

// ECDH key pair structure
struct EcdhKeyPair {
    std::vector<uint8_t> private_key_der; // Private key in DER format
    std::vector<uint8_t> public_key_der;  // Public key in DER format
};

// Generate an ephemeral ECDH key pair (e.g., using NIST P-256)
EcdhKeyPair generate_ecdh_keypair();

// Compute the shared secret from local private key and remote public key
std::vector<uint8_t> compute_shared_secret(const std::vector<uint8_t>& private_key_der,
                                            const std::vector<uint8_t>& peer_public_key_der);
class AeadCipher {
public:
    // Key must be exactly 32 bytes (256 bits).
    explicit AeadCipher(std::vector<uint8_t> key);
    ~AeadCipher();

    AeadCipher(const AeadCipher&) = delete;
    AeadCipher& operator=(const AeadCipher&) = delete;

    // Encrypt plaintext into ciphertext.
    // Output layout: [nonce (12 bytes)][ciphertext][tag (16 bytes)]
    std::vector<uint8_t> encrypt(const uint8_t* plaintext, size_t plaintext_len,
                                 const uint8_t* aad, size_t aad_len) const;

    // Decrypt ciphertext back into plaintext.
    // Input layout: [nonce (12 bytes)][ciphertext][tag (16 bytes)]
    std::vector<uint8_t> decrypt(const uint8_t* ciphertext, size_t ciphertext_len,
                                 const uint8_t* aad, size_t aad_len) const;

    size_t key_size() const { return key_.size(); }

    // Generate a random 256-bit key.
    static std::vector<uint8_t> generate_key();

private:
    std::vector<uint8_t> key_;

    static const size_t kNonceSize = 12;   // 96-bit nonce for GCM
    static const size_t kTagSize = 16;     // GCM authentication tag
};

// Derive a 256-bit key from a shared secret using HKDF-SHA256.
std::vector<uint8_t> derive_key(const std::vector<uint8_t>& secret,
                                const std::vector<uint8_t>& salt,
                                const std::vector<uint8_t>& info,
                                size_t out_len = 32);

} // namespace vpn
