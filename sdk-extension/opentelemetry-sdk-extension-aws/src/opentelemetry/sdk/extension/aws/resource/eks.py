# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import ssl
from urllib.request import Request, urlopen

from opentelemetry.sdk.resources import Resource, ResourceDetector
from opentelemetry.semconv.resource import (
    CloudPlatformValues,
    CloudProviderValues,
    ResourceAttributes,
)

logger = logging.getLogger(__name__)

_CONTAINER_ID_LENGTH = 64
_GET_METHOD = "GET"


def _aws_http_request(method, path, cred_value, cert_data):
    response = urlopen(
        Request(
            "https://kubernetes.default.svc" + path,
            headers={"Authorization": cred_value},
            method=method,
        ),
        timeout=2000,
        context=ssl.create_default_context(cadata=cert_data),
    )
    return response.read().decode("utf-8")


def _get_k8s_cred_value():
    try:
        with open(
            "/var/run/secrets/kubernetes.io/serviceaccount/token",
            encoding="utf8",
        ) as f:
            return "Bearer " + f.read()
    except Exception as e:
        logger.debug(f"Failed to get k8s token: {e}")
        return ""


def _is_Eks(cred_value, cert_data):
    return _aws_http_request(
        _GET_METHOD,
        "/api/v1/namespaces/kube-system/configmaps/aws-auth",
        cred_value,
        cert_data,
    )


def _get_cluster_info(cred_value, cert_data):
    return _aws_http_request(
        _GET_METHOD,
        "/api/v1/namespaces/amazon-cloudwatch/configmaps/cluster-info",
        cred_value,
        cert_data,
    )


def _get_cluster_name():
    cred_value = _get_k8s_cred_value()
    print("ABOUT TO READ CERT FILE")
    with open("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt") as f:
        print("FINISHED CERT FILE")
        k8_cert_data = f.read()
        if not _is_Eks(cred_value, k8_cert_data):
            return Resource.get_empty()

    cluster_info = json.loads(_get_cluster_info(cred_value, k8_cert_data))
    cluster_name = ""
    try:
        cluster_name = cluster_info["data"]["cluster.name"]
    except Exception as e:
        logger.warn(f"Cannot get cluster name on EKS: {e}")

    return cluster_name


def _get_container_id():
    container_id = ""
    print("ABOUT TO READ PROCCCCC FILE")
    with open("proc/self/cgroup", encoding="utf8") as f:
        print("FINISHED PROCCCCC FILE")
        for raw_line in f.readlines():
            line = raw_line.strip()
            if len(line) > _CONTAINER_ID_LENGTH:
                container_id = line[-_CONTAINER_ID_LENGTH:]
    return container_id


class AwsEksResourceDetector(ResourceDetector):
    """Detects attribute values only available when the app is running on AWS
    Elastic Kubernetes Service (EKS) and returns them in a Resource.
    """

    def detect(self) -> "Resource":
        try:
            cluster_name = _get_cluster_name()
            container_id = _get_container_id()

            if not container_id or not cluster_name:
                return Resource.get_empty()

            # NOTE: (NathanielRN) Should ResourceDetectors use Resource.create() to pull in the environment variable?
            # `OTELResourceDetector` doesn't do this...
            return Resource(
                {
                    ResourceAttributes.CLOUD_PROVIDER: CloudProviderValues.AWS.value,
                    ResourceAttributes.CLOUD_PLATFORM: CloudPlatformValues.AWS_EKS.value,
                    ResourceAttributes.K8S_CLUSTER_NAME: cluster_name,
                    ResourceAttributes.CONTAINER_ID: container_id,
                }
            )
        except Exception as e:
            logger.debug(f"{self.__class__.__name__} failed: {e}")
            return Resource.get_empty()
