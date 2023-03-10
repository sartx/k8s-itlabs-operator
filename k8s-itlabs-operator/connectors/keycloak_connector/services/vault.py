from typing import Optional

from clients.vault.vaultclient import AbstractVaultClient
from connectors.keycloak_connector.dto import KeycloakMsSecretDto
from connectors.keycloak_connector.factories.dto_factory import KeycloakMsSecretDtoFactory


class VaultService:

    def __init__(self, client: AbstractVaultClient):
        self.client = client

    def get_kk_api_secret(self, path: str) -> Optional[str]:
        return self.client.read_secret_key(path)

    def get_kk_ms_secret(self, path: str) -> Optional[KeycloakMsSecretDto]:
        data = self.client.read_secret(path)
        if data:
            return KeycloakMsSecretDtoFactory.dto_from_dict(data)

    def create_kk_ms_secret(self, path: str, kk_ms_cred: KeycloakMsSecretDto):
        secret = KeycloakMsSecretDtoFactory.dict_from_dto(kk_ms_cred)
        self.client.create_secret(path, secret)

    @staticmethod
    def get_vault_env_value(path: str, key: str) -> str:
        return f"{path}#{key}"
