#include "vpn/crypto.h"
#include <cstring>
#include <stdexcept>
#include <openssl/evp.h>
#include <openssl/rand.h>
#include <openssl/ec.h>
#include <openssl/obj_mac.h>
#include <openssl/err.h>

namespace vpn {

// ECDH key pair structure
struct EcdhKeyPair {
    std::vector<uint8_t> private_key_der; // Private key in DER format
    std::vector<uint8_t> public_key_der;  // Public key in DER format
};

// Generate an ephemeral ECDH key pair (e.g., using NIST P-256)
EcdhKeyPair generate_ecdh_keypair() {
    EVP_PKEY* pkey = EVP_PKEY_CTX_new_id(EVP_PKEY_EC, nullptr);
    if (!pkey) throw std::runtime_error("EVP_PKEY_CTX_new_id failed");

    if (EVP_PKEY_keygen_init(pkey) <= 0) {
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_keygen_init failed");
    }

    // Use NIST P-256 curve
    if (EVP_PKEY_CTX_set_ec_paramgen_curve_nid(pkey, NID_X9_62_prime256v1) <= 0) {
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_CTX_set_ec_paramgen_curve_nid failed");
    }

    if (EVP_PKEY_keygen(pkey, nullptr) <= 0) {
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_keygen failed");
    }

    size_t pub_len = 0;
    if (EVP_PKEY_get1_encoded_public_key(pkey, nullptr, &pub_len) <= 0) {
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_get1_encoded_public_key (size) failed");
    }

    std::vector<uint8_t> pub_key_der(pub_len);
    if (EVP_PKEY_get1_encoded_public_key(pkey, pub_key_der.data(), &pub_len) <= 0) {
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_get1_encoded_public_key (data) failed");
    }

    // Extract private key (PKCS#8 DER format)
    EVP_PKEY* priv_pkey = EVP_PKEY_dup(pkey);
    EVP_PKEY_CTX* priv_ctx = EVP_PKEY_CTX_new(priv_pkey, nullptr);
    if (!priv_ctx) {
        EVP_PKEY_free(priv_pkey);
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_CTX_new failed for private key");
    }
    
    size_t priv_len = 0;
    if (EVP_PKEY_get1_encoded_private_key(priv_pkey, nullptr, &priv_len) <= 0) {
        EVP_PKEY_CTX_free(priv_ctx);
        EVP_PKEY_free(priv_pkey);
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_get1_encoded_private_key (size) failed");
    }

    std::vector<uint8_t> priv_key_der(priv_len);
    if (EVP_PKEY_get1_encoded_private_key(priv_pkey, priv_key_der.data(), &priv_len) <= 0) {
        EVP_PKEY_CTX_free(priv_ctx);
        EVP_PKEY_free(priv_pkey);
        EVP_PKEY_CTX_free(pkey);
        throw std::runtime_error("EVP_PKEY_get1_encoded_private_key (data) failed");
    }

    EVP_PKEY_CTX_free(priv_ctx);
    EVP_PKEY_free(priv_pkey);
    EVP_PKEY_CTX_free(pkey);

    return {priv_key_der, pub_key_der};
}

std::vector<uint8_t> compute_shared_secret(const std::vector<uint8_t>& private_key_der,
                                            const std::vector<uint8_t>& peer_public_key_der) {
    EVP_PKEY* pkey_local = d2i_PrivateKey(private_key_der.data(), private_key_der.size());
    EVP_PKEY* pkey_peer = d2i_PUBKEY(peer_public_key_der.data(), peer_public_key_der.size());

    if (!pkey_local || !pkey_peer) {
        ERR_print_errors_fp(stderr);
        EVP_PKEY_free(pkey_local);
        EVP_PKEY_free(pkey_peer);
        throw std::runtime_error("Failed to load private or public key from DER format.");
    }

    EVP_PKEY_CTX* pctx = EVP_PKEY_CTX_new(pkey_local, nullptr);
    if (!pctx) {
        EVP_PKEY_free(pkey_local);
        EVP_PKEY_free(pkey_peer);
        throw std::runtime_error("EVP_PKEY_CTX_new failed.");
    }

    if (EVP_PKEY_derive_init(pctx) <= 0) {
        EVP_PKEY_CTX_free(pctx);
        EVP_PKEY_free(pkey_local);
        EVP_PKEY_free(pkey_peer);
        throw std::runtime_error("EVP_PKEY_derive_init failed.");
    }

    size_t secret_len = 0;
    if (EVP_PKEY_derive(pctx, nullptr, &secret_len) <= 0) {
        EVP_PKEY_CTX_free(pctx);
        EVP_PKEY_free(pkey_local);
        EVP_PKEY_free(pkey_peer);
        throw std::runtime_error("EVP_PKEY_derive (size) failed.");
    }

    std::vector<uint8_t> shared_secret(secret_len);
    if (EVP_PKEY_derive(pctx, shared_secret.data(), &secret_len) <= 0) {
        EVP_PKEY_CTX_free(pctx);
        EVP_PKEY_free(pkey_local);
        EVP_PKEY_free(pkey_peer);
        throw std::runtime_error("EVP_PKEY_derive (data) failed.");
    }

    EVP_PKEY_CTX_free(pctx);
    EVP_PKEY_free(pkey_local);
    EVP_PKEY_free(pkey_peer);

    return shared_secret;
}

AeadCipher::AeadCipher(std::vector<uint8_t> key) : key_(std::move(key)) {
    if (key_.size() != 32) {
        throw std::invalid_argument("AES-256-GCM requires a 32-byte key");
    }
}

AeadCipher::~AeadCipher() {
    // Zero out the key material
    std::memset(key_.data(), 0, key_.size());
}

std::vector<uint8_t> AeadCipher::encrypt(const uint8_t* plaintext, size_t plaintext_len,
                                           const uint8_t* aad, size_t aad_len) const {
    // Generate random nonce
    std::vector<uint8_t> nonce(kNonceSize);
    if (RAND_bytes(nonce.data(), static_cast<int>(nonce.size())) != 1) {
        throw std::runtime_error("RAND_bytes failed");
    }

    // Output: nonce + ciphertext + tag
    std::vector<uint8_t> output;
    output.reserve(kNonceSize + plaintext_len + kTagSize);
    output.insert(output.end(), nonce.begin(), nonce.end());

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        throw std::runtime_error("EVP_CIPHER_CTX_new failed");
    }

    // Initialize encryption
    if (EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_EncryptInit_ex failed");
    }

    // Set key and nonce
    if (EVP_EncryptInit_ex(ctx, nullptr, nullptr, key_.data(), nonce.data()) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_EncryptInit_ex (key/nonce) failed");
    }

    // Provide AAD
    if (aad_len > 0) {
        int len = 0;
        if (EVP_EncryptUpdate(ctx, nullptr, &len, aad, static_cast<int>(aad_len)) != 1) {
            EVP_CIPHER_CTX_free(ctx);
            throw std::runtime_error("EVP_EncryptUpdate (AAD) failed");
        }
    }

    // Encrypt plaintext
    std::vector<uint8_t> ciphertext(plaintext_len);
    int len = 0;
    if (EVP_EncryptUpdate(ctx, ciphertext.data(), &len, plaintext,
                          static_cast<int>(plaintext_len)) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_EncryptUpdate failed");
    }
    int ciphertext_len = len;

    // Finalize
    if (EVP_EncryptFinal_ex(ctx, ciphertext.data() + len, &len) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_EncryptFinal_ex failed");
    }
    ciphertext_len += len;

    // Get authentication tag
    std::vector<uint8_t> tag(kTagSize);
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_GET_TAG, static_cast<int>(kTagSize), tag.data()) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_CIPHER_CTX_ctrl (GET_TAG) failed");
    }

    EVP_CIPHER_CTX_free(ctx);

    output.insert(output.end(), ciphertext.begin(), ciphertext.begin() + ciphertext_len);
    output.insert(output.end(), tag.begin(), tag.end());

    return output;
}

std::vector<uint8_t> AeadCipher::decrypt(const uint8_t* ciphertext, size_t ciphertext_len,
                                           const uint8_t* aad, size_t aad_len) const {
    if (ciphertext_len < kNonceSize + kTagSize) {
        throw std::invalid_argument("Ciphertext too short for nonce + tag");
    }

    // Extract nonce (first 12 bytes)
    std::vector<uint8_t> nonce(ciphertext, ciphertext + kNonceSize);

    // Ciphertext body (after nonce, before tag)
    size_t body_len = ciphertext_len - kNonceSize - kTagSize;
    const uint8_t* body = ciphertext + kNonceSize;

    // Tag (last 16 bytes)
    const uint8_t* tag = ciphertext + kNonceSize + body_len;

    EVP_CIPHER_CTX* ctx = EVP_CIPHER_CTX_new();
    if (!ctx) {
        throw std::runtime_error("EVP_CIPHER_CTX_new failed");
    }

    if (EVP_DecryptInit_ex(ctx, EVP_aes_256_gcm(), nullptr, nullptr, nullptr) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_DecryptInit_ex failed");
    }

    if (EVP_DecryptInit_ex(ctx, nullptr, nullptr, key_.data(), nonce.data()) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_DecryptInit_ex (key/nonce) failed");
    }

    // Provide AAD
    if (aad_len > 0) {
        int len = 0;
        if (EVP_DecryptUpdate(ctx, nullptr, &len, aad, static_cast<int>(aad_len)) != 1) {
            EVP_CIPHER_CTX_free(ctx);
            throw std::runtime_error("EVP_DecryptUpdate (AAD) failed");
        }
    }

    // Decrypt
    std::vector<uint8_t> plaintext(body_len);
    int len = 0;
    if (EVP_DecryptUpdate(ctx, plaintext.data(), &len, body, static_cast<int>(body_len)) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_DecryptUpdate failed");
    }
    int plaintext_len = len;

    // Set expected tag before finalizing
    if (EVP_CIPHER_CTX_ctrl(ctx, EVP_CTRL_GCM_SET_TAG, static_cast<int>(kTagSize),
                            const_cast<uint8_t*>(tag)) != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("EVP_CIPHER_CTX_ctrl (SET_TAG) failed");
    }

    // Finalize - this verifies the tag
    int ret = EVP_DecryptFinal_ex(ctx, plaintext.data() + len, &len);
    if (ret != 1) {
        EVP_CIPHER_CTX_free(ctx);
        throw std::runtime_error("Authentication tag verification failed (decrypt)");
    }
    plaintext_len += len;

    EVP_CIPHER_CTX_free(ctx);

    plaintext.resize(plaintext_len);
    return plaintext;
}

std::vector<uint8_t> AeadCipher::generate_key() {
    std::vector<uint8_t> key(32);
    if (RAND_bytes(key.data(), static_cast<int>(key.size())) != 1) {
        throw std::runtime_error("RAND_bytes failed");
    }
    return key;
}

std::vector<uint8_t> derive_key(const std::vector<uint8_t>& secret,
                                 const std::vector<uint8_t>& salt,
                                 const std::vector<uint8_t>& info,
                                 size_t out_len) {
    std::vector<uint8_t> out(out_len);
    if (HKDF(out.data(), out_len, EVP_sha256(),
             secret.data(), secret.size(),
             salt.empty() ? nullptr : salt.data(), salt.size(),
             info.empty() ? nullptr : info.data(), info.size()) == nullptr) {
        throw std::runtime_error("HKDF failed");
    }
    return out;
}

} // namespace vpn