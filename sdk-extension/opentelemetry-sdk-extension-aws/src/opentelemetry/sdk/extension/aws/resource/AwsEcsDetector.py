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

import logging
import socket
from opentelemetry.sdk.resources import (
    Resource,
    ResourceDetector,
)
from opentelemetry.semconv.resource import (
    CloudPlatformValues,
    CloudProviderValues,
    ResourceAttributes,
)

logger = logging.getLogger(__name__)

_CONTAINER_ID_LENGTH = 64


class AwsEcsDetector(ResourceDetector):
    def detect(self) -> "Resource":
        container_id = None
        try:
            with open("proc/self/cgroup", encoding="utf8") as f:
                for line in f.readlines():
                    if len(line) > _CONTAINER_ID_LENGTH:
                        container_id = line[-_CONTAINER_ID_LENGTH:]
        except Exception as e:
            logger.debug(f"AwsEcsDetector failed to get container Id: {e}")

        try:
            # NOTE: (NathanielRN) Should ResourceDetectors use Resource.detect() to pull in the environment variable?
            # `OTELResourceDetector` doesn't do this...
            return Resource(
                {
                    ResourceAttributes.CLOUD_PROVIDER: CloudProviderValues.AWS,
                    ResourceAttributes.CLOUD_PLATFORM: CloudPlatformValues.AWS_ECS,
                    ResourceAttributes.CONTAINER_NAME: socket.gethostname()
                    or "",
                    ResourceAttributes.CONTAINER_ID: container_id,
                }
            )
        except Exception as e:
            logger.debug(f"AwsEcsDetector failed: {e}")
            return Resource.get_empty()
