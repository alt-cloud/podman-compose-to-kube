import os
from setuptools import setup

try:
    readme = open(os.path.join(os.path.dirname(__file__), "README.md")).read()
except:
    readme = ""

setup(
    name="podman-compose-to-kube",
    description="The script podman-compose-to-kube generates kubernetes manifests to deploy the specified service stack in kubernetes.",
    long_description=readme,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords="podman-compose, podman-compose-to-kube, kubernetes",
    author="Alexey Kostarev",
    author_email="kaf@basealt.ru",
    url="https://github.com/alt-cloud/podman-compose-to-kube",
    py_modules=["podman_compose_to_kube"],
    entry_points={"console_scripts": ["podman-compose-to-kube = podman_compose_to_kube:main"]},
    include_package_data=True,
    license="GPL-2.0-only",
    install_requires=[
        "pyyaml",
        "yaml"
    ],
    extras_require={
      "devel": [
        "yaml",
      ]
    }
)
