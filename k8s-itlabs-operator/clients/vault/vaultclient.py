import logging
from abc import ABCMeta, abstractmethod
from typing import Optional

import hvac

from clients.vault.parse import parse_secret_path
from exceptions import InfrastructureServiceProblem

logger = logging.getLogger('vault_logger')


class AbstractVaultClient:
    __metaclass__ = ABCMeta

    @abstractmethod
    def read_secret_version_data(self, path: str) -> Optional[dict]:
        raise NotImplementedError

    @abstractmethod
    def create_secret(self, path: str, data: dict):
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_prefix_path(cls):
        raise NotImplementedError

    @abstractmethod
    def delete_secret_all_versions(self, path: str):
        raise NotImplementedError


class VaultClient(AbstractVaultClient):
    _SECURED_VALUE = "******"
    _SECURED_KEYS = ["pass", "token", "BROKER_PASSWORD", 'DATABASE_PASSWORD', 'SENTRY_DSN']

    def __init__(self, hvac_vault_client: hvac.Client, mount_point: str):
        self.client = hvac_vault_client
        self.mount_point = mount_point

    def _get_secured_value(self, key: str, value: str) -> str:
        """
        Returns mask of key value if key is secured.
        """
        if value and key and any(secured_key in key for secured_key in self._SECURED_KEYS):
            return self._SECURED_VALUE
        return value

    def _read_secret_version(self, path) -> dict:
        """
        Get last secret version from Vault (kv2) by path /{mount_point}/data/{path}.
        """
        logger.info(f"Started reading Vault secret version: {path}")
        result = None
        try:
            secret_path = parse_secret_path(path)
            result = self.client.secrets.kv.v2.read_secret_version(
                path=secret_path.path, mount_point=secret_path.mount_point
            )
        except hvac.v1.exceptions.InvalidPath:
            logger.info(f"Error while Read Vault secret version: {path} - invalid path")
        except Exception as e:
            raise InfrastructureServiceProblem('Vault', e)
        logger.info(f"Ended reading Vault secret version: {path}")
        return result

    def read_secret_version_data(self, path: str) -> Optional[dict]:
        result = None
        raw_response = self._read_secret_version(path=path)
        if raw_response:
            result = raw_response['data']['data']
        return result

    def _create_or_update_secret(self, path: str, data: dict, update_allowed: bool = False) -> dict:
        secured_data = {k: self._get_secured_value(k, v) for k, v in data.items()}
        logger.info(f"Write secret '{path}' to Vault: {secured_data}")
        secret_path = parse_secret_path(path)
        try:
            cas = None if update_allowed else 0
            result = self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path.path, secret=data, cas=cas, mount_point=secret_path.mount_point
            )
            return result
        except Exception as e:
            InfrastructureServiceProblem('Vault', e)

    def create_secret(self, path: str, data: dict):
        self._create_or_update_secret(path=path, data=data)

    def get_prefix_path(self) -> str:
        return f'vault:{self.mount_point}/data'

    def delete_secret_all_versions(self, path: str):
        try:
            logger.info(f"Delete secret'{path}' from Vault")
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(path=path)
        except Exception as e:
            raise InfrastructureServiceProblem('Vault', e)
