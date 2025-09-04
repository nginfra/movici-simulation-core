from aequilibrae import AequilibraeMatrix as AequilibraeMatrix_


class AequilibraeMatrix(AequilibraeMatrix_):
    def get_matrix(self, core: str, copy=True):
        """Same as upstream get_matrix, but with default copy=True"""
        return super().get_matrix(core, copy=copy)
