import logging

from connectors.sentry_connector import specifications
from connectors.sentry_connector.services.vault import AbstractVaultService
from connectors.sentry_connector.dto import SentryConnectorMicroserviceDto
from connectors.sentry_connector.services.kubernetes import KubernetesService
from connectors.sentry_connector.factories.service_factories.sentry import SentryServiceFactory
from connectors.sentry_connector.exceptions import SentryConnectorCrdDoesNotExist, NonExistSecretForSentryConnector


class SentryConnectorService:
    def __init__(self, vault_service: AbstractVaultService):
        self.vault_service = vault_service

    @staticmethod
    def is_sentry_conn_used_by_object(annotations: dict, labels: dict) -> bool:
        has_required_annotations = all(
            annotation_name in annotations
            for annotation_name in specifications.SENTRY_CONNECTOR_REQUIRED_ANNOTATIONS
        )
        has_required_labels = all(
            label_name in labels
            for label_name in specifications.SENTRY_CONNECTOR_REQUIRED_LABELS
        )
        return has_required_annotations and has_required_labels

    def on_create_deployment(self, ms_sentry_conn: SentryConnectorMicroserviceDto):
        sentry_conn_crd = KubernetesService.get_sentry_connector(ms_sentry_conn.sentry_instance_name)
        if not sentry_conn_crd:
            raise SentryConnectorCrdDoesNotExist(
                f"Couldn't find sentryconnector by instance name: {ms_sentry_conn.sentry_instance_name}"
            )
        sentry_api_cred = self.vault_service.get_sentry_api_credentials(sentry_conn_crd.vault_path)
        if not sentry_api_cred:
            raise NonExistSecretForSentryConnector(
                f"Couldn't find sentry credentials in vault by path: {sentry_conn_crd.vault_path}"
            )

        sentry_service = SentryServiceFactory.create_sentry_service(sentry_api_cred)
        sentry_ms_cred = self.vault_service.get_sentry_ms_credentials(ms_sentry_conn.vault_path)

        if sentry_ms_cred and \
                sentry_service.is_sentry_dsn_exist(project_slug=sentry_ms_cred.project_slug, dsn=sentry_ms_cred.dsn):
            logging.info("Sentry dsn-key already exist")
            return

        sentry_ms_cred = sentry_service.configure_sentry(ms_sentry_conn)
        self.vault_service.create_ms_sentry_credentials(ms_sentry_conn.vault_path, sentry_ms_cred)

    def mutate_containers(self, spec, ms_sentry_conn: SentryConnectorMicroserviceDto) -> bool:
        mutated = False
        for container in spec.get("containers", []):
            mutated = self.mutate_container(container, mutated, ms_sentry_conn.vault_path)
        for init_container in spec.get("initContainers", []):
            mutated = self.mutate_container(init_container, mutated, ms_sentry_conn.vault_path)
        return mutated

    def mutate_container(self, container: dict, mutated: bool, vault_path: str) -> bool:
        envs = container.get("env")
        if not envs:
            envs = []
        for env_name, vault_key in specifications.SENTRY_VAR_NAMES:
            if env_name not in [env.get("name") for env in envs]:
                envs.append({
                    "name": env_name,
                    "value": self.vault_service.get_vault_env_value(vault_path, vault_key)
                })
                mutated = True
        if mutated:
            container["env"] = envs
        return mutated
