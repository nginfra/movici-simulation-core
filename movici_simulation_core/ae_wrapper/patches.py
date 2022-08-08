# This file contains patches to aequilibrae that have not yet been merged upstream as per
# version 0.7.4

from aequilibrae import AequilibraeMatrix as AequilibraeMatrix_


class AequilibraeMatrix(AequilibraeMatrix_):
    def get_matrix(self, core: str, copy=True):
        return super().get_matrix(core, copy=copy)

    def close(self):
        if self.__omx:
            self.omx_file.close()
        else:
            self.matrices.flush()
            self.index.flush()

        for attr in ("index", "indices", "matrix", "matrices", "matrix_view"):
            delattr(self, attr)
