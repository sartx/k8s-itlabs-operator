from connectors.keycloak_connector.crd import KeycloakConnectorCrd
from connectors.keycloak_connector.specifications import (
    KEYCLOAK_INSTANCE_NAME_ANNOTATION,
    KEYCLOAK_VAULT_PATH_ANNOTATION,
    KEYCLOAK_CLIENT_ID_ANNOTATION,

    KEYCLOAK_CLIENT_ID_KEY,
    KEYCLOAK_SECRET_KEY,
)

from connectors.keycloak_connector.dto import KeycloakConnectorMicroserviceDto, \
    KeycloakConnector, KeycloakMsSecretDto


class KeycloakConnectorMicroserviceDtoFactory:
    @classmethod
    def dto_from_metadata(
            cls,
            annotations: dict
    ) -> KeycloakConnectorMicroserviceDto:
        return KeycloakConnectorMicroserviceDto(
            keycloak_instance_name=annotations.get(KEYCLOAK_INSTANCE_NAME_ANNOTATION),
            vault_path=annotations.get(KEYCLOAK_VAULT_PATH_ANNOTATION),
            client_id=annotations.get(KEYCLOAK_CLIENT_ID_ANNOTATION),
        )


class KeycloakConnectorFactory:
    @staticmethod
    def dto_from_kk_connector_crd(kk_connector_crd: KeycloakConnectorCrd) -> KeycloakConnector:
        return KeycloakConnector(
            url=kk_connector_crd.spec.url,
            realm=kk_connector_crd.spec.realm,
            username_secret=kk_connector_crd.spec.username,
            password_secret=kk_connector_crd.spec.password,
        )


class KeycloakMsSecretDtoFactory:
    @staticmethod
    def dto_from_dict(data: dict) -> KeycloakMsSecretDto:
        return KeycloakMsSecretDto(
            client_id=data.get(KEYCLOAK_CLIENT_ID_KEY),
            secret=data.get(KEYCLOAK_SECRET_KEY),
        )

    @staticmethod
    def dict_from_dto(dto: KeycloakMsSecretDto) -> dict:
        return {
            KEYCLOAK_CLIENT_ID_KEY: dto.client_id,
            KEYCLOAK_SECRET_KEY: dto.secret,
        }
