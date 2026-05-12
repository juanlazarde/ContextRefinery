import pytest

from doc_preprocessor.deps import GLOBAL_DEP_REGISTRY


@pytest.fixture(autouse=True)
def reset_dep_registry():
    GLOBAL_DEP_REGISTRY.attempted_packages.clear()
    GLOBAL_DEP_REGISTRY.successful_packages.clear()
    GLOBAL_DEP_REGISTRY.failed_packages.clear()
    yield
    GLOBAL_DEP_REGISTRY.attempted_packages.clear()
    GLOBAL_DEP_REGISTRY.successful_packages.clear()
    GLOBAL_DEP_REGISTRY.failed_packages.clear()
