import json
import time
import jwt

PRIVATE_KEY_B64 = "MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDZspcSKIP7+pmt8xElQZWyeP/mYEuv6B0lmmZUnheoNpjHuLn1X0QxY34O/MBrTxBoKAZt8ZNAJUjorGOXVyvsY88inRfOZknq8BueRdkESLJ/ANejtrgSc4bOLQHj3fPJiu78I1t0y9LguM2aStTFvfbNtUeFfhmfnUyXRSK+TfqwEjJqY0AAis/MbcuB1HWptnOpz59YOe4AQjNiEL4SYgaKYL546Azg3O0r1T/t+poXRUODFerVHiyvHimKancBpt2LCQ11gSyU5zuBj7fPn5cAp9qQ/vKtY/qfmF1x5Xnd/AJqQX2Aury71p18GRl+AxBTbzl2G8ExbPTOBzCTAgMBAAECggEAXiFQHDxjkWVS5PmobL0WjuSt9b2mjGmnjLZdz/HJ1eTBm/4+fiASuu5DuBRG2T+HHxpLaWee3Yoho+XCbFJ3fg/MJTHa9Naa2Ji4wG+APk92yt6g3zunDOdiHy0r140FmBxYaLKbHX3ycVPHJxN7PAN/P4RGaCzVxIP99ZyhwLnnwDPose8E+XhlbLQVQUlxCy6X0lWI6o/ACidZbekBIN6IFoNUrZ3MVvtjQQND1ZyRv5ySZ/hgB7M7ADGSp7vP1iu/NdK6dD+yElvbzJrYTMnVeZ+OxH0CMy9fFFa10GZSJEhhRtD3edUqLmw/7BAP5zfEeA+pAU8+cyoVlOov6QKBgQD1arXNJlw7ilOQlUq4eu32YjWZI4QK0S4eOXilShQCx4qfvunzvJN/PGX24e0HQyGiNgC/IkC1KjXSl25RjSL4Z/DZL/VrrZSTkORc+DE2KHdYRuJHQsX2+ByXRggG1j9GZ0XiXq5FD9lMw84oaKe6UPhmBhZ8FUxuYkk1BzZwCwKBgQDjFd9YBNLn5FdM5qPJP2trgwpa5LS7uHOOiLmYhozOEOoHq9Y76w3eD23nRCANeiMjblpLFsdljlSxyAnL2E7dmOWuaRbDpR1v3GcEtb9JxtQ+rSaqF+PLtqNIoUgn0fJX61pwXUtMZhaY/cd9r+AJxVSHn05eQDMS/VEC93zumQKBgHAlf0ZsDSG4KE+dqTN8GVnJryx3qlM3G5f8M0F1BIfwn0w4dbhHqC8wbnfO7f2vk6MIgnbVNDSVQVsmj+b8U8qn1Muqur+l5os4XuKNGA/jlgXk/moJ/WTKJGaMPgbByNBnSOwU0BYHFAmcQIz+pgbiEWCtz4CMSwz2JPXygdHZAoGAKSLtMqStEBTtO6EMSoiSjQdP+Oc1Vkwzor5h4J9/IlUuD/Ww+Wm7OV7SKfLNW6OkeeajtLaLqHoAHbR/Ec49eycXdGDVHtvqWTkz8EZ8QIEkMbZsKqPpQB31tlKBH7WIkSSxXWmJGm3j6hMO8FXL3/k/NtJFAA3hMq9w3Xi3yQECgYB5QbEgGzlWpsGw/R5Kh3K8Ns2e/c6AhpVbsZzNrl/uPb1Ezi1NSprv4gxbXExWPBDHbNcHp2SAAVEFQv1rBskj2VrE+fhMM/YCeKkKlQMyNrPZUm/5HCKFkGqxPJ+AFEj/jVK6dBfICohxhoI0nRI5aufDZb6v25icbsyRwlhGjw=="

private_key_pem = (
    "-----BEGIN PRIVATE KEY-----\n"
    + "\n".join(PRIVATE_KEY_B64[i:i+64] for i in range(0, len(PRIVATE_KEY_B64), 64))
    + "\n-----END PRIVATE KEY-----\n"
)

with open("authorities.txt", "r", encoding="utf-8") as f:
    authorities = [line.strip() for line in f if line.strip()]

now = 1787394523  # keep original iat
payload = {
    "iss": "onified-gateway",
    "aud": "onified-backend",
    "sub": "f1ef022f-1fbb-40e5-b13c-b4d3df7a6ce3",
    "iat": now,
    "exp": now + 10 * 365 * 24 * 3600,
    "tkt": "int",
    "tenantId": "352f9f27-83a3-42d3-b3d0-44e72ac807f9",
    "tenantKey": "beta",
    "userPublicId": "usr_nishkarsh001",
    "principal_type": "HUMAN",
    "acr": "urn:onified:aal1",
    "amr": "pwd",
    "auth_time": 1787394500,
    "device_trust": "unmanaged",
    "sid": "c35a605b-c725-4c30-9489-6f7c22d2f6b5",
    "authContext": {
        "sub": "Nishkarsh Singh",
        "roles": ["APP_AUDITOR", "APP_EXT_SUPPORT_ENGINEER", "CARGO_SERVICE"],
        "authorities": authorities,
        "constraints": [],
        "acr": "urn:onified:aal1",
        "amr": "pwd",
    },
}

token = jwt.encode(
    payload,
    private_key_pem,
    algorithm="RS256",
    headers={"kid": "zddmWvcLv5mM5MlrDPUZop9RkX6fgxPvI59d_SAoGtw"},
)

with open("dev-internal-token-all-services.txt", "w", encoding="utf-8") as f:
    f.write(token)

print("minted, authorities:", len(authorities), "token bytes:", len(token))
