import subprocess
import unittest
import time

from conans import __version__ as client_version
from conans import tools
from conans.model.ref import ConanFileReference
from conans.model.version import Version
from cpt.packager import ConanMultiPackager
from cpt.test.integration.base import BaseTest, CONAN_UPLOAD_PASSWORD, CONAN_LOGIN_UPLOAD
from cpt.test.unit.utils import MockCIManager


def is_linux_and_have_docker():
    return tools.os_info.is_linux and tools.which("docker")


class DockerTest(BaseTest):

    CONAN_SERVER_ADDRESS = "http://0.0.0.0:9300"

    def setUp(self):
        super(DockerTest, self).setUp()
        self.server_process = subprocess.Popen("conan_server")
        time.sleep(3)

    def tearDown(self):
        self.server_process.kill()
        super(DockerTest, self).tearDown()

    @unittest.skipUnless(is_linux_and_have_docker(), "Requires Linux and Docker")
    def test_docker(self):
        ci_manager = MockCIManager()
        unique_ref = "zlib/%s" % str(time.time())
        conanfile = """from conans import ConanFile
import os

class Pkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

"""

        self.save_conanfile(conanfile)
        with tools.environment_append({"CONAN_DOCKER_RUN_OPTIONS": "--network=host -v{}:/tmp/cpt".format(self.root_project_folder),
                                       "CONAN_DOCKER_ENTRY_SCRIPT": "pip install -U /tmp/cpt",
                                       "CONAN_USE_DOCKER": "1",
                                       "CONAN_DOCKER_IMAGE_SKIP_UPDATE": "TRUE",
                                       "CONAN_LOGIN_USERNAME": "demo",
                                       "CONAN_USERNAME": "demo",
                                       "CONAN_UPLOAD": DockerTest.CONAN_SERVER_ADDRESS,
                                       "CONAN_PASSWORD": "demo"}):

            self.packager = ConanMultiPackager(channel="mychannel",
                                               gcc_versions=["6"],
                                               archs=["x86", "x86_64"],
                                               build_types=["Release"],
                                               reference=unique_ref,
                                               ci_manager=ci_manager)
            self.packager.add_common_builds()
            self.packager.run()

        search_pattern = "%s*" % unique_ref
        ref = ConanFileReference.loads("%s@demo/mychannel" % unique_ref)

        # Remove from remote
        if Version(client_version) < Version("1.7"):
            results = self.api.search_recipes(search_pattern, remote="upload_repo")["results"][0]["items"]
            self.assertEquals(len(results), 1)
            packages = self.api.search_packages(ref, remote="upload_repo")["results"][0]["items"][0]["packages"]
            self.assertEquals(len(packages), 2)
            self.api.authenticate(name=CONAN_LOGIN_UPLOAD, password=CONAN_UPLOAD_PASSWORD,
                                  remote="upload_repo")
            self.api.remove(search_pattern, remote="upload_repo", force=True)
            self.assertEquals(self.api.search_recipes(search_pattern)["results"], [])
        else:
            results = self.api.search_recipes(search_pattern, remote_name="upload_repo")["results"][0]["items"]
            self.assertEquals(len(results), 1)
            if Version(client_version) >= Version("1.12.0"):
                ref = repr(ref)
            packages = self.api.search_packages(ref, remote_name="upload_repo")["results"][0]["items"][0]["packages"]
            self.assertEquals(len(packages), 2)
            self.api.authenticate(name="demo", password="demo",
                                  remote_name="upload_repo")
            self.api.remove(search_pattern, remote_name="upload_repo", force=True)
            self.assertEquals(self.api.search_recipes(search_pattern)["results"], [])

        # Try upload only when stable, shouldn't upload anything
        with tools.environment_append({"CONAN_DOCKER_RUN_OPTIONS": "--network=host -v{}:/tmp/cpt".format(self.root_project_folder),
                                       "CONAN_DOCKER_ENTRY_SCRIPT": "pip install -U /tmp/cpt",
                                       "CONAN_USE_DOCKER": "1",
                                       "CONAN_LOGIN_USERNAME": "demo",
                                       "CONAN_USERNAME": "demo",
                                       "CONAN_PASSWORD": "demo",
                                       "CONAN_DOCKER_IMAGE_SKIP_UPDATE": "TRUE",
                                       "CONAN_UPLOAD_ONLY_WHEN_STABLE": "1"}):
            self.packager = ConanMultiPackager(channel="mychannel",
                                               gcc_versions=["6"],
                                               archs=["x86", "x86_64"],
                                               build_types=["Release"],
                                               reference=unique_ref,
                                               upload=DockerTest.CONAN_SERVER_ADDRESS,
                                               ci_manager=ci_manager)
            self.packager.add_common_builds()
            self.packager.run()

        if Version(client_version) < Version("1.7"):
            results = self.api.search_recipes(search_pattern, remote="upload_repo")["results"]
            self.assertEquals(len(results), 0)
            self.api.remove(search_pattern, remote="upload_repo", force=True)
        else:
            results = self.api.search_recipes(search_pattern, remote_name="upload_repo")["results"]
            self.assertEquals(len(results), 0)
            self.api.remove(search_pattern, remote_name="upload_repo", force=True)

    @unittest.skipUnless(is_linux_and_have_docker(), "Requires Linux and Docker")
    def test_docker_run_options(self):
        conanfile = """from conans import ConanFile
import os

class Pkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = "zlib/1.2.11@conan/stable"

    def build(self):
        pass
"""
        self.save_conanfile(conanfile)
        # Validate by Environemnt Variable
        with tools.environment_append({"CONAN_DOCKER_ENTRY_SCRIPT": "pip install -U /tmp/cpt",
                                       "CONAN_USERNAME": "bar",
                                       "CONAN_DOCKER_IMAGE": "conanio/gcc8",
                                       "CONAN_REFERENCE": "foo/0.0.1@bar/testing",
                                       "CONAN_DOCKER_RUN_OPTIONS": "--network=host, --add-host=google.com:8.8.8.8 -v{}:/tmp/cpt".format(self.root_project_folder),
                                       "CONAN_DOCKER_IMAGE_SKIP_UPDATE": "TRUE"
                                       }):
            self.packager = ConanMultiPackager(gcc_versions=["8"],
                                               archs=["x86_64"],
                                               build_types=["Release"],
                                               out=self.output.write)
            self.packager.add({})
            self.packager.run()
            self.assertIn("--network=host --add-host=google.com:8.8.8.8 -v", self.output)

        # Validate by parameter
        with tools.environment_append({"CONAN_USERNAME": "bar",
                                       "CONAN_DOCKER_IMAGE": "conanio/gcc8",
                                       "CONAN_REFERENCE": "foo/0.0.1@bar/testing"
                                       }):

            self.packager = ConanMultiPackager(gcc_versions=["8"],
                                               archs=["x86_64"],
                                               build_types=["Release"],
                                               docker_run_options="--network=host -v{}:/tmp/cpt --cpus=1".format(self.root_project_folder) ,
                                               docker_entry_script="pip install -U /tmp/cpt",
                                               docker_image_skip_update=True,
                                               out=self.output.write)
            self.packager.add({})
            self.packager.run()
            self.assertIn("--cpus=1  conanio/gcc8", self.output)
