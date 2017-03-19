#******************************************************************************
#
# This software is licensed under the Python Software Foundation license.
# See the file "license" for a copy of the PSF license.
#
# A simple implementation of constants in python. See:
# http://code.activestate.com/recipes/65207-constants-in-python/?in=user-97991
#
#******************************************************************************


class _const:
    class ConstError(TypeError):
        pass

    def __setattr__(self, name, value):
        if name in self.__dict__:
            raise self.ConstError, "Can't rebind const(%s)" % name
        self.__dict__[name] = value
import sys
sys.modules[__name__] = _const()