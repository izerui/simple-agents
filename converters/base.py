from typing import override


class BaseConverter:

    @override
    def convert(self, source_file, target_file):
        """convert source_file onto target_file."""
        pass

    @override
    def support(self, suffix):
        """return True if this converter supports source_file."""
        pass