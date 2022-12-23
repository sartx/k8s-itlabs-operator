import pytest

from clients.postgres.dto import PgConnectorDbSecretDto
from clients.postgres.tests.factories import PgConnectorDbSecretDtoTestFactory
from clients.postgres.tests.mocks import MockedPostgresClient
from clients.vault.tests.mocks import MockedVaultClient
from connectors.postgres_connector import specifications
from connectors.postgres_connector.dto import PgConnectorInstanceSecretDto, PgConnectorMicroserviceDto, PgConnector
from connectors.postgres_connector.exceptions import PgConnectorCrdDoesNotExist, UnknownVaultPathInPgConnector
from connectors.postgres_connector.factories.dto_factory import PgConnectorDbSecretDtoFactory, PgInstanceDtoFactory
from connectors.postgres_connector.services.postgres import PostgresService
from connectors.postgres_connector.services.postgres_connector import PostgresConnectorService
from connectors.postgres_connector.services.vault import VaultService
from connectors.postgres_connector.tests.factories import PgConnectorInstanceSecretDtoTestFactory, \
    PgConnectorMicroserviceDtoTestFactory
from connectors.postgres_connector.tests.mocks import MockedVaultService, KubernetesServiceMocker, \
    PostgresServiceFactoryMocker, MockedPostgresService


@pytest.mark.unit
class TestPostgresConnectorService:
    def test_get_or_create_db_credentials_when_cred_was_in_vault(self):
        pg_instance_cred: PgConnectorInstanceSecretDto = PgConnectorInstanceSecretDtoTestFactory()
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory(
            db_name=pg_instance_cred.db_name,
            db_username=pg_instance_cred.user
        )
        ms_pg_cred = PgConnectorDbSecretDtoFactory.dto_from_ms_pg_con(pg_instance_creds=pg_instance_cred,
                                                                      ms_pg_con=ms_pg_con)
        pg_con_service = PostgresConnectorService(
            vault_service=MockedVaultService(
                pg_instance_cred=pg_instance_cred,
                ms_pg_cred=ms_pg_cred
            )
        )
        db_creds = pg_con_service.get_or_create_db_credentials(pg_instance_creds=pg_instance_cred, ms_pg_con=ms_pg_con)
        assert isinstance(db_creds, PgConnectorDbSecretDto)
        assert ms_pg_cred.host == db_creds.host
        assert ms_pg_cred.port == db_creds.port
        assert ms_pg_cred.user == db_creds.user
        assert ms_pg_cred.db_name == db_creds.db_name
        assert ms_pg_cred.password == db_creds.password
        assert pg_con_service.vault_service.create_pg_ms_credentials_call_count == 0

    def test_get_or_create_db_credentials_when_cred_was_not_in_vault(self):
        pg_instance_cred: PgConnectorInstanceSecretDto = PgConnectorInstanceSecretDtoTestFactory()
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory(
            db_name=pg_instance_cred.db_name,
            db_username=pg_instance_cred.user
        )
        pg_con_service = PostgresConnectorService(
            vault_service=MockedVaultService(
                pg_instance_cred=pg_instance_cred
            )
        )
        db_creds = pg_con_service.get_or_create_db_credentials(pg_instance_creds=pg_instance_cred, ms_pg_con=ms_pg_con)
        assert isinstance(db_creds, PgConnectorDbSecretDto)
        assert pg_instance_cred.db_kube_domain == db_creds.host
        assert pg_instance_cred.port == db_creds.port
        assert ms_pg_con.db_username == db_creds.user
        assert ms_pg_con.db_name == db_creds.db_name
        assert pg_con_service.vault_service.create_pg_ms_credentials_call_count == 1

    def test_on_create_deployment_no_crds(self, mocker):
        KubernetesServiceMocker.mock_get_pg_connector(mocker)
        pg_con_service = PostgresConnectorService(vault_service=MockedVaultService())
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory()
        with pytest.raises(PgConnectorCrdDoesNotExist):
            pg_con_service.on_create_deployment(ms_pg_con=ms_pg_con)

    def test_on_create_deployment_no_pg_instance_name_in_crds(self, mocker):
        pg_connector = PgConnector()
        KubernetesServiceMocker.mock_get_pg_connector(mocker, pg_connector)
        pg_con_service = PostgresConnectorService(vault_service=MockedVaultService())
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory()
        with pytest.raises(UnknownVaultPathInPgConnector):
            pg_con_service.on_create_deployment(ms_pg_con=ms_pg_con)

    def test_on_create_deployment(self, mocker):
        pg_instance_cred: PgConnectorInstanceSecretDto = PgConnectorInstanceSecretDtoTestFactory()
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory(
            db_name=pg_instance_cred.db_name,
            db_username=pg_instance_cred.user
        )
        pg_instance_dto = PgInstanceDtoFactory.dto_from_pg_con_ms_dto(pg_con_ms_dto=ms_pg_con)
        pg_connector = PgConnector()
        pg_connector.add_pg_instance(pg_instance_dto)
        ms_pg_cred = PgConnectorDbSecretDtoFactory.dto_from_ms_pg_con(pg_instance_creds=pg_instance_cred,
                                                                      ms_pg_con=ms_pg_con)
        kube_mocker = KubernetesServiceMocker.mock_get_pg_connector(mocker, pg_connector)
        mocked_pg_service = MockedPostgresService()
        PostgresServiceFactoryMocker.mock_create_pg_service(mocker, mocked_pg_service)
        mocked_vault_service = MockedVaultService(
            pg_instance_cred=pg_instance_cred,
            ms_pg_cred=ms_pg_cred
        )
        pg_con_service = PostgresConnectorService(
            vault_service=mocked_vault_service
        )
        pg_con_service.on_create_deployment(ms_pg_con=ms_pg_con)
        assert kube_mocker.call_count == 1
        assert mocked_vault_service.get_pg_instance_credentials_call_count == 1
        assert mocked_vault_service.get_pg_ms_credentials_call_count == 1
        assert mocked_vault_service.create_pg_ms_credentials_call_count == 0
        assert mocked_pg_service.create_database_call_count == 1

    def test_mutate_containers_variables_already_in_container(self):
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory()
        mocked_vault_service = MockedVaultService()
        pg_con_service = PostgresConnectorService(
            vault_service=mocked_vault_service
        )
        spec = {
            'containers': [
                {
                    'name': 'first',
                    'env': [
                        {
                            'name': var_name[0],
                            'value': 'some_value'
                        } for var_name in specifications.DATABASE_VAR_NAMES
                    ]
                }
            ]
        }
        assert not pg_con_service.mutate_containers(spec=spec, ms_pg_con=ms_pg_con)

    def test_mutate_containers_variables_not_in_container(self):
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory()
        mocked_vault_service = MockedVaultService()
        pg_con_service = PostgresConnectorService(
            vault_service=mocked_vault_service
        )
        spec = {'containers': [{'name': 'first'}]}
        assert pg_con_service.mutate_containers(spec=spec, ms_pg_con=ms_pg_con)
        assert pg_con_service.vault_service.get_vault_env_value_call_count == len(specifications.DATABASE_VAR_NAMES)

    def test_mutate_containers_variables_already_in_onr_container_not_in_enother(self):
        ms_pg_con: PgConnectorMicroserviceDto = PgConnectorMicroserviceDtoTestFactory()
        mocked_vault_service = MockedVaultService()
        pg_con_service = PostgresConnectorService(
            vault_service=mocked_vault_service
        )
        spec = {
            'containers': [
                {
                    'name': 'first',
                    'env': [
                        {
                            'name': var_name[0],
                            'value': 'some_value'
                        } for var_name in specifications.DATABASE_VAR_NAMES
                    ]
                }, {
                    'name': 'second'
                }
            ]
        }
        assert pg_con_service.mutate_containers(spec=spec, ms_pg_con=ms_pg_con)
        assert pg_con_service.vault_service.get_vault_env_value_call_count == len(specifications.DATABASE_VAR_NAMES)


@pytest.mark.unit
class TestPostgresService:
    def test_create_database_db_exists_user_exists(self):
        pg_client = MockedPostgresClient(db_exist=True, user_exist=True)
        pg_service = PostgresService(pg_client=pg_client)
        db_cred = PgConnectorDbSecretDtoTestFactory()
        pg_service.create_database(db_cred=db_cred)
        assert pg_service.pg_client.db_create_call_count == 0
        assert pg_service.pg_client.user_create_call_count == 0
        assert pg_service.pg_client.user_alter_password_call_count == 1
        assert pg_service.pg_client.grant_user_to_admin_call_count == 1

    def test_create_database_no_db_exists_no_user_exists(self):
        pg_client = MockedPostgresClient(db_exist=False, user_exist=False)
        pg_service = PostgresService(pg_client=pg_client)
        db_cred = PgConnectorDbSecretDtoTestFactory()
        pg_service.create_database(db_cred=db_cred)
        assert pg_service.pg_client.db_create_call_count == 1
        assert pg_service.pg_client.user_create_call_count == 1
        assert pg_service.pg_client.user_alter_password_call_count == 0
        assert pg_service.pg_client.grant_user_to_admin_call_count == 1


@pytest.mark.unit
class TestVaultService:
    def test_get_vault_env_value(self):
        vault_client = MockedVaultClient()
        vault_service = VaultService(vault_client=vault_client)
        vault_path = 'vault:secret/data/vault_path'
        vault_key = 'vault_key'
        vault_env_value = vault_service.get_vault_env_value(vault_path=vault_path, vault_key=vault_key)
        assert vault_env_value == f'{vault_path}#{vault_key}'

    def test_get_pg_ms_credentials_no_secret_in_vault(self):
        vault_client = MockedVaultClient(use_default_secret=False)
        vault_service = VaultService(vault_client=vault_client)
        pg_creds = vault_service.get_pg_ms_credentials(vault_path='any')
        assert pg_creds is None

    def test_get_pg_ms_credentials_with_secret_in_vault(self):
        secret = {
            specifications.DATABASE_NAME_KEY: 'a',
            specifications.DATABASE_USER_KEY: 'a',
            specifications.DATABASE_PASSWORD_KEY: 'a',
            specifications.DATABASE_HOST_KEY: 'a',
            specifications.DATABASE_PORT_KEY: 5432
        }
        vault_client = MockedVaultClient(secret=secret)
        vault_service = VaultService(vault_client=vault_client)
        pg_creds = vault_service.get_pg_ms_credentials(vault_path='any')
        assert pg_creds
