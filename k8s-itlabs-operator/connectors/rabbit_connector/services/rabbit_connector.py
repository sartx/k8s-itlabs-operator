from connectors.rabbit_connector import specifications
from connectors.rabbit_connector.dto import RabbitConnectorMicroserviceDto, RabbitApiSecretDto, RabbitMsSecretDto
from connectors.rabbit_connector.exceptions import RabbitConnectorCrdDoesNotExist, UnknownVaultPathInRabbitConnector, \
    NotMatchingUsernames, NotMatchingVhostNames
from connectors.rabbit_connector.factories.dto_factory import RabbitMsSecretDtoFactory
from connectors.rabbit_connector.factories.service_factories.rabbit import RabbitServiceFactory
from connectors.rabbit_connector.services.kubernetes import KubernetesService
from connectors.rabbit_connector.services.vault import AbstractVaultService


class RabbitConnectorService:
    def __init__(self, vault_service: AbstractVaultService):
        self.vault_service = vault_service

    def on_create_deployment(self, ms_rabbit_con: RabbitConnectorMicroserviceDto):
        rabbit_con_crds = KubernetesService.get_rabbit_connector()
        if not rabbit_con_crds:
            raise RabbitConnectorCrdDoesNotExist()
        vault_path = rabbit_con_crds.get_vaultpath_by_name(ms_rabbit_con.rabbit_instance_name)
        if not vault_path:
            raise UnknownVaultPathInRabbitConnector()
        rabbit_api_creds = self.vault_service.get_rabbit_api_credentials(vault_path)
        rabbit_service = RabbitServiceFactory.create_rabbit_service(rabbit_api_creds)
        rabbit_ms_creds = self.get_or_create_rabbit_credentials(rabbit_api_creds, ms_rabbit_con)
        rabbit_service.configure_rabbit(rabbit_ms_creds)

    @classmethod
    def is_rabbit_conn_used_by_object(cls, annotations: dict) -> bool:
        return all(
            annotation_name in annotations for annotation_name in specifications.RABBIT_CONNECTOR_REQUIRED_ANNOTATIONS
        )

    def get_or_create_rabbit_credentials(self, rabbit_api_creds: RabbitApiSecretDto,
                                         ms_rabbit_con: RabbitConnectorMicroserviceDto) -> RabbitMsSecretDto:
        rabbit_ms_creds = self.vault_service.get_rabbit_ms_credentials(vault_path=ms_rabbit_con.vault_path)
        if rabbit_ms_creds:
            if rabbit_ms_creds.broker_user != ms_rabbit_con.username:
                raise NotMatchingUsernames()
            if rabbit_ms_creds.broker_vhost != ms_rabbit_con.vhost:
                raise NotMatchingVhostNames()
        else:
            rabbit_ms_creds = RabbitMsSecretDtoFactory.dto_from_ms_rabbit_con(rabbit_api_creds, ms_rabbit_con)
            self.vault_service.create_ms_rabbit_credentials(ms_rabbit_con.vault_path, rabbit_ms_creds)
        return rabbit_ms_creds

    def mutate_containers(self, spec, ms_rabbit_con: RabbitConnectorMicroserviceDto):
        mutated = False
        for container in spec.get('containers', []):
            mutated = self.mutate_container(container, mutated, ms_rabbit_con.vault_path)
        for init_container in spec.get('initContainers', []):
            mutated = self.mutate_container(init_container, mutated, ms_rabbit_con.vault_path)
        return mutated

    def mutate_container(self, container: dict, mutated: bool, vault_path: str) -> bool:
        envs = container.get('env')
        if not envs:
            envs = []
        for envvar_name, vault_key in specifications.RABBIT_VAR_NAMES:
            if envvar_name not in [env.get('name') for env in envs]:
                envs.append({
                    "name": envvar_name,
                    "value": self.vault_service.get_vault_env_value(vault_path, vault_key)
                })
                mutated = True
        if mutated:
            container['env'] = envs
        return mutated
