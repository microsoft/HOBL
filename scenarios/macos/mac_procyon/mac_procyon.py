# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import scenarios.windows.procyon

class MacProcyon(scenarios.windows.procyon.Procyon):
    module = __module__.split('.')[-1]
    resources = f"{module}_resources"

    def kill(self):
        self._kill("UL_Procyon")
